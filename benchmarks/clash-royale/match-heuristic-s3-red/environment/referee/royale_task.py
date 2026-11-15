"""Referee for the Harbor/Valkyrie match tasks: one agent plays a full match through the `cr` CLI.

The agent never touches the engine. A game server, running as a separate OS user, owns the match
and talks to the agent's `cr` client over a Unix socket. Every decision the agent makes is appended
to an action log that only the server can write. Grading happens in a fresh container: the
verifier rebuilds the match from the task's seed and replays the logged decisions against the same
deterministic opponent, so the score depends only on the moves the agent chose.

    python -m cr_arena.royale_task serve  --config task.json --state-dir DIR --socket PATH
    python -m cr_arena.royale_task verify --config task.json --log actions.jsonl --out DIR
    python -m cr_arena.royale_task selfplay --config task.json   # local check: bot vs bot through the referee

Decision protocol (shared by server and verifier, so replays are exact): the engine runs in
``decision_ticks`` intervals. At each interval the opponent decides on the frozen state; the agent is
asked only when it has a move besides waiting (exactly as in :mod:`cr_arena.match`), otherwise it
waits automatically. A decision the agent never makes (timeout, abandoned game) counts as waiting.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import socketserver
import sys
import time
from pathlib import Path

from .game import Game, Move
from .bots.baselines import HeuristicBot, RandomBot
from .player_types import Player
from .telemetry import Capture, GameTelemetry, atomic_json, digest

RESULT_WORDS = {0: "BLUE", 1: "RED", 2: "DRAW"}
FAST_DECISION_S = 1.0  # a reply quicker than this after the state was shown is flagged as likely scripted


def make_opponent(spec: str) -> Player:
    if spec == "heuristic":
        return HeuristicBot()
    if spec.startswith("random"):
        return RandomBot(seed=int(spec.split(":")[1]) if ":" in spec else 0)
    raise ValueError(f"unknown opponent {spec!r}")


class Referee:
    """One match from the agent's seat. ``cfg`` keys: seed, agent_team (0 blue / 1 red),
    agent_deck, opponent_deck, opponent, decision_ticks."""

    capture: Capture | None = None
    action_source = "agent"

    def __init__(self, cfg: dict, record: bool = False, capture: Capture | None = None):
        self.cfg = cfg
        self.capture = capture
        self.action_source = "agent"
        self.team = int(cfg["agent_team"])
        self.opp_team = 1 - self.team
        decks: list[list[str]] = [[], []]
        decks[self.team] = list(cfg["agent_deck"])
        decks[self.opp_team] = list(cfg["opponent_deck"])
        self.game = Game(decks[0], decks[1], seed=int(cfg["seed"]),
                         decision_ticks=int(cfg["decision_ticks"]), record=record)
        if capture is not None:
            self.game.telemetry = GameTelemetry(capture, self.game)
        self.opponent = make_opponent(cfg["opponent"])
        self.opponent.start(self.game, self.opp_team)
        self.decision = 0  # number of decisions the agent has made
        self.moves: list[Move] | None = None
        self.history: list[str] = []
        self._advance()

    @property
    def over(self) -> bool:
        return self.game.over

    @property
    def tick(self) -> int:
        return int(self.game.state.tick)

    def _step(self, agent_move: Move) -> str:
        g = self.game
        opp_moves = g.legal_moves(self.opp_team)
        if len(opp_moves) == 1:
            opp_move = opp_moves[0]
        else:
            opp_move = opp_moves[self.opponent.decide(g, self.opp_team, "", opp_moves).index]
        chosen: list[Move] = [agent_move, agent_move]
        chosen[self.team], chosen[self.opp_team] = agent_move, opp_move
        tick = self.tick
        sources = ["opponent", "opponent"]
        sources[self.opp_team] = "forced_wait" if len(opp_moves) == 1 else "opponent"
        sources[self.team] = "forced_wait" if self.moves is None else self.action_source
        if self.capture:
            self.capture.snapshot(g, phase="pre_step", decision_id=f"{self.team}:{tick}")
        results = g.step(chosen)
        if self.capture:
            for team, mv in enumerate(chosen):
                self.capture.command(g, team, f"{team}:{tick}", mv, kind="application", tick=tick,
                    end_tick=self.tick, action_source=sources[team], result=results[team],
                    accepted=results[team] == "wait" or results[team].startswith("played"))
            self.capture.snapshot(g, phase="post_step")
        return results[self.team]

    def _advance(self) -> None:
        """Run forced waits until the agent has a real choice or the match ends."""
        while not self.game.over:
            moves = self.game.legal_moves(self.team)
            if len(moves) > 1:
                self.moves = moves
                return
            self.moves = None
            self._step(moves[0])
        self.moves = None

    def check_move(self, index: int) -> Move:
        if self.moves is None:
            raise ValueError("the match is over")
        if not 0 <= index < len(self.moves):
            raise ValueError(f"move {index} is not in the list (0-{len(self.moves) - 1})")
        return self.moves[index]

    def act(self, index: int) -> str:
        mv = self.check_move(index)
        self.game.consume_events(self.team)  # the agent has seen this state's events
        result = self._step(mv)
        self.decision += 1
        self._advance()
        return result

    def observation(self) -> str:
        if self.over:
            return self.final_text()
        header = f"DECISION {self.decision + 1} (you are {RESULT_WORDS[self.team]})"
        body = self.game.describe(self.team, self.moves)
        return f"{header}\n{body}\n\nPlay with: cr act <move number>"

    def outcome(self) -> dict:
        s = self.game.state
        me, en = s.players[self.team], s.players[self.opp_team]
        winner = int(s.winner) if s.game_over else -1
        result = "win" if winner == self.team else "draw" if winner == 2 else "loss" if winner >= 0 else "unfinished"

        def damage_frac(p) -> float:
            total = sum(p.tower_max_hp)
            return round(1 - sum(p.tower_hp) / total, 4) if total else 0.0

        return {"result": result, "crowns_for": int(me.crowns), "crowns_against": int(en.crowns),
                "enemy_tower_damage_frac": damage_frac(en), "own_tower_damage_frac": damage_frac(me),
                "ticks": int(s.tick)}

    def final_text(self) -> str:
        o = self.outcome()
        return (f"GAME OVER: {o['result'].upper()}. Crowns: you {o['crowns_for']} - enemy {o['crowns_against']}. "
                "The match is finished; there is nothing more to do.")

    def success(self) -> bool:
        return self.outcome()["result"] == "win"


def make_referee(cfg: dict, record: bool = False, capture: Capture | None = None) -> Referee:
    if "scenario" in cfg:
        from .scenario_task import ScenarioReferee

        ref = ScenarioReferee(cfg, record=record)
        ref.capture = capture
        if capture:
            ref.game.telemetry = GameTelemetry(capture, ref.game)
        return ref
    return Referee(cfg, record=record, capture=capture)


# ---------------------------------------------------------------------------------------- log

def read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


class LogMismatch(RuntimeError):
    pass


def replay_entries(ref: Referee, entries: list[dict]) -> int:
    """Apply logged decisions, checking each one was made at the state it claims. Returns the
    number of entries applied (entries after the end of the match are ignored)."""
    applied = 0
    for e in entries:
        if ref.over:
            if ref.cfg.get("scenario"):
                raise LogMismatch("extra decisions after the scenario ended")
            break
        if not isinstance(e, dict) or any(type(e.get(k)) is not int for k in ("decision", "tick", "move")):
            raise LogMismatch(f"entry {applied}: decision, tick and move must be integers")
        think_s = e.get("think_s", 0)
        if (think_s is not None or ref.cfg.get("scenario")) and (
                type(think_s) not in (int, float) or not math.isfinite(think_s) or think_s < 0):
            raise LogMismatch(f"entry {applied}: invalid think_s")
        expected = (ref.decision, ref.tick)
        if (e.get("decision"), e.get("tick")) != expected:
            raise LogMismatch(f"entry {applied}: logged decision/tick {(e.get('decision'), e.get('tick'))}, "
                              f"replay is at {expected}")
        mv = ref.check_move(e["move"])
        if e.get("label") != mv.label():
            raise LogMismatch(f"entry {applied}: logged move {e.get('label')!r}, replay offers {mv.label()!r}")
        if e.get("state_hash") and e["state_hash"] != digest(ref.game.state):
            raise LogMismatch(f"entry {applied}: state hash differs from the original observation")
        ref.act(int(e["move"]))
        applied += 1
    return applied


# ------------------------------------------------------------------------------------- server

class GameServer(socketserver.TCPServer):
    """Single-threaded on purpose: requests are applied one at a time, in order."""

    address_family = getattr(socket, "AF_UNIX", socket.AF_INET)

    def __init__(self, sock_path: str, ref: Referee, log_path: Path):
        if not hasattr(socket, "AF_UNIX"):
            raise RuntimeError("the cr socket server requires Linux; use the task Docker image")
        self.ref = ref
        self.log_path = log_path
        self.shown_at = time.time()
        self.first_shown_ns = None
        if ref.capture is None:
            ref.capture = Capture(log_path.parent / "capture", source="referee", config=ref.cfg)
        self.capture = ref.capture
        ref.game.telemetry = GameTelemetry(self.capture, ref.game)
        self.persist_trace()
        if os.path.exists(sock_path):
            os.unlink(sock_path)
        super().__init__(sock_path, Handler)
        os.chmod(sock_path, 0o666)

    def handle_command(self, req: dict) -> dict:
        ref = self.ref
        cmd = req.get("cmd", "observe")
        self.capture.emit("commands", {"kind": "request", "request": req,
            "decision_id": f"{ref.team}:{ref.tick}", "tick": ref.tick, "team": ref.team})
        if cmd == "observe":
            return self.response(ref.observation())
        if cmd == "act":
            try:
                index = int(req["move"])
                mv = ref.check_move(index)
            except (KeyError, TypeError, ValueError) as exc:
                self.capture.emit("events", {"event": "invalid_command", "tick": ref.tick,
                    "decision_id": f"{ref.team}:{ref.tick}", "error": str(exc), "request": req})
                return {"ok": False, "over": ref.over, "text": f"Not played: {exc}. Run `cr` to see the legal moves."}
            now = time.time()
            entry = {"decision": ref.decision, "tick": ref.tick, "move": index, "label": mv.label(),
                     "think_s": round((time.monotonic_ns() - self.first_shown_ns) / 1e9, 6)
                                if self.first_shown_ns is not None else None,
                     "wall": round(now, 3), "segment_id": self.capture.segment,
                     "observation_id": getattr(self, "observation_id", None)}
            entry["state_hash"] = digest(ref.game.state)
            with self.log_path.open("a") as f:  # logged before it takes effect: the log is the source of truth
                f.write(json.dumps(entry) + "\n")
                f.flush()
                os.fsync(f.fileno())
            result = ref.act(index)
            self.first_shown_ns = None
            text = f"Your move: {result}\n\n{ref.observation()}"
            return self.response(text)
        self.capture.emit("events", {"event": "invalid_command", "error": "unknown command", "request": req})
        return {"ok": False, "over": ref.over, "text": f"unknown command {cmd!r}"}

    def response(self, text):
        if self.first_shown_ns is None:
            self.first_shown_ns = time.monotonic_ns()
            self.shown_at = time.time()
        self.observation_id = self.capture.observe(self.ref.game, self.ref.team,
            f"{self.ref.team}:{self.ref.tick}", text, self.ref.moves or [])
        self.persist_trace()
        if self.ref.over and self.capture.manifest.get("status") != "completed":
            self.capture.finish(self.ref.game, status="completed", result=self.ref.outcome())
        return {"ok": True, "over": self.ref.over, "text": text}

    def persist_trace(self):
        """The hosted service carries referee artifacts, but not verifier files.

        Checkpoint after every response so a stopped agent still has its actual
        frames. Independent verifier rewards remain the scoring authority.
        """
        recorder = self.ref.game.recorder
        if recorder is not None and recorder.trace is not None:
            from royalegym.replay import save_trace
            try:
                path = self.log_path.parent / "replay.msgpack"
                tmp = path.with_suffix(".tmp")
                if self.ref.over and recorder.trace.result is None:
                    self.ref.game.finish()
                save_trace(recorder.trace, tmp)
                os.replace(tmp, path)
                self.capture.manifest["counts"] = self.capture.counts
                atomic_json(self.capture.root / "manifest.json", self.capture.manifest)
            except (OSError, ValueError) as exc:
                self.capture.manifest["capture_errors"].append(f"replay checkpoint: {exc}")

    def server_close(self):
        super().server_close()
        self.capture.close()


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline(65536)
        try:
            req = json.loads(line or b"{}")
            resp = self.server.handle_command(req if isinstance(req, dict) else {})
        except Exception as exc:  # never let one bad request kill the match
            self.server.capture.emit("events", {"event": "malformed_request", "error": str(exc),
                                              "raw": line.decode(errors="replace")})
            resp = {"ok": False, "over": False, "text": f"referee error: {type(exc).__name__}: {exc}"}
        try:
            self.wfile.write((json.dumps(resp) + "\n").encode())
        except (BrokenPipeError, ConnectionResetError) as exc:
            self.server.capture.emit("events", {"event": "disconnect", "error": str(exc)})


def serve(config: Path, state_dir: Path, sock: str) -> None:
    import fcntl  # server locking is Linux-only; replay/calibration also run on Windows
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = open(state_dir / "server.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("server already running", file=sys.stderr)
        return
    cfg = json.loads(config.read_text())
    ref = make_referee(cfg, record=True)
    log_path = state_dir / "actions.jsonl"
    resumed = replay_entries(ref, read_log(log_path))  # a restarted server continues the same match
    print(f"serving seed={cfg['seed']} team={ref.team} resumed={resumed}", file=sys.stderr, flush=True)
    with GameServer(sock, ref, log_path) as server:
        server.serve_forever()


# ----------------------------------------------------------------------------------- verifier

def verify(cfg: dict, log_path: Path, out_dir: Path | None) -> dict:
    capture = None
    if out_dir is not None:
        identity_path = log_path.parent / "capture" / "manifest.json"
        identity = json.loads(identity_path.read_text()) if identity_path.exists() else {}
        # Verification is a reproducible new export, rather than appending another copy.
        import shutil
        shutil.rmtree(out_dir / "telemetry", ignore_errors=True)
        capture = Capture(out_dir / "telemetry", source="verifier", config=cfg,
                          match_id=identity.get("match_id"), attempt_id=identity.get("attempt_id"))
    ref = make_referee(cfg, record=out_dir is not None, capture=capture)
    parse_error = None
    try:
        entries = read_log(log_path)
        if any(not isinstance(e, dict) for e in entries):
            raise ValueError("log entries must be objects")
    except (ValueError, OSError, UnicodeError) as exc:
        entries, parse_error = [], str(exc)
    report: dict = {"seed": cfg["seed"], "agent_team": ref.team, "opponent": cfg["opponent"],
                    "log_entries": len(entries)}
    try:
        if parse_error:
            raise LogMismatch(parse_error)
        applied = replay_entries(ref, entries)
        integrity = 1
    except (LogMismatch, ValueError, KeyError, TypeError, OverflowError) as exc:
        report["integrity_error"] = str(exc)
        applied, integrity = 0, 0
    completed = int(ref.over)
    termination_tick = ref.tick
    if capture:
        capture.emit("events", {"event": "agent_termination", "tick": termination_tick,
            "completed": bool(completed), "reason": "game_over" if completed else "unmade_decisions",
            "detailed_reason": None, "reason_source": "external task metadata distinguishes stop/timeout/error"})
    ref.action_source = "verifier_wait"
    while not ref.over:  # decisions never made count as waits
        ref.act(0)
    outcome = ref.outcome()
    players = ref.game.state.players
    reason = ("king_destroyed" if any(p.tower_hp[0] <= 0 for p in players) else
              "crowns" if players[0].crowns != players[1].crowns else
              "tower_hp" if sum(players[0].tower_hp) != sum(players[1].tower_hp) else "seed_parity")
    think = []
    for e in entries[:applied]:
        try:
            t = float(e["think_s"])
            if math.isfinite(t) and t >= 0:
                think.append(t)
        except (KeyError, TypeError, ValueError):
            pass
    rewards = {
        "reward": float(ref.success() and integrity and (not cfg.get("scenario") or (completed and applied > 0))),
        "win": float(outcome["result"] == "win" and integrity),
        "crowns_for": float(outcome["crowns_for"]),
        "crowns_against": float(outcome["crowns_against"]),
        "enemy_tower_damage_frac": outcome["enemy_tower_damage_frac"],
        "own_tower_damage_frac": outcome["own_tower_damage_frac"],
        "completed": float(completed),
        "integrity": float(integrity),
        "decisions": float(applied),
        "fast_decision_frac": round(sum(t < FAST_DECISION_S for t in think) / len(think), 4) if think else 0.0,
    }
    report.update(outcome=outcome, rewards=rewards, decisions_applied=applied, completed=bool(completed),
                  termination_tick=termination_tick, timing_known=len(think),
                  task_config=cfg, rubric="binary-win-v1")
    report["tiebreak_reason"] = reason
    if cfg.get("scenario"):
        report.update(benchmark=cfg["benchmark"], task_id=cfg["id"], scenario=cfg["scenario"],
                      setup_hash=ref.setup_hash, planner=cfg["planner"], rubric="scenario-objective-v1")
        rewards.update(spent_elixir=float(ref.spent), tower_damage=float(outcome["tower_damage"]),
                       objective_met=float(ref.success()))
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "reward.json").write_text(json.dumps(rewards, indent=1) + "\n")
        (out_dir / "match_report.json").write_text(json.dumps(report, indent=1) + "\n")
        _, _, _, _, trace = ref.game.finish()
        if trace is not None:
            try:
                from royalegym.replay import save_trace
                save_trace(trace, out_dir / "replay.msgpack")
                from .replay import patched_html
                (out_dir / "replay.html").write_text(patched_html(out_dir / "replay.msgpack", stride=2), encoding="utf-8")
            except Exception as exc:  # the replay is a convenience; never fail grading over it
                report["replay_error"] = f"{type(exc).__name__}: {exc}"
                (out_dir / "match_report.json").write_text(json.dumps(report, indent=1) + "\n")
        if capture:
            capture.finish(ref.game, status="completed" if completed else "partial", result=report)
    return report


def selfplay(cfg: dict, log_path: Path, agent: str) -> None:
    """Play the agent seat with a bot through the same act/log path the server uses."""
    bot = make_opponent(agent)
    ref = make_referee(cfg)
    bot.start(ref.game, ref.team)
    log_path.unlink(missing_ok=True)
    with log_path.open("a") as f:
        while not ref.over:
            idx = bot.decide(ref.game, ref.team, "", ref.moves).index
            f.write(json.dumps({"decision": ref.decision, "tick": ref.tick, "move": idx,
                                "label": ref.moves[idx].label(), "think_s": 5.0}) + "\n")
            ref.act(idx)
    print(ref.final_text())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--config", type=Path, required=True)
    s.add_argument("--state-dir", type=Path, required=True)
    s.add_argument("--socket", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--config", type=Path, required=True)
    v.add_argument("--log", type=Path, required=True)
    v.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("selfplay")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--log", type=Path, default=Path("selfplay_actions.jsonl"))
    p.add_argument("--agent", default="heuristic")
    a = ap.parse_args()
    if a.cmd == "serve":
        serve(a.config, a.state_dir, a.socket)
    elif a.cmd == "verify":
        report = verify(json.loads(a.config.read_text()), a.log, a.out)
        print(json.dumps({k: report[k] for k in ("rewards", "outcome", "decisions_applied", "completed")}, indent=1))
        if "integrity_error" in report:
            print("INTEGRITY ERROR:", report["integrity_error"])
    else:
        selfplay(json.loads(a.config.read_text()), a.log, a.agent)


if __name__ == "__main__":
    main()
