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
import fcntl
import json
import os
import socketserver
import sys
import time
from pathlib import Path

from .game import Game, Move
from .bots.baselines import HeuristicBot, RandomBot
from .player_types import Player

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

    def __init__(self, cfg: dict, record: bool = False):
        self.cfg = cfg
        self.team = int(cfg["agent_team"])
        self.opp_team = 1 - self.team
        decks: list[list[str]] = [[], []]
        decks[self.team] = list(cfg["agent_deck"])
        decks[self.opp_team] = list(cfg["opponent_deck"])
        self.game = Game(decks[0], decks[1], seed=int(cfg["seed"]),
                         decision_ticks=int(cfg["decision_ticks"]), record=record)
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
        return g.step(chosen)[self.team]

    def _advance(self) -> None:
        """Run forced waits until the agent has a real choice or the match ends."""
        while not self.game.over:
            moves = self.game.legal_moves(self.team)
            if len(moves) > 1:
                self.moves = moves
                return
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
            break
        expected = (ref.decision, ref.tick)
        if (e.get("decision"), e.get("tick")) != expected:
            raise LogMismatch(f"entry {applied}: logged decision/tick {(e.get('decision'), e.get('tick'))}, "
                              f"replay is at {expected}")
        mv = ref.check_move(int(e["move"]))
        if e.get("label") != mv.label():
            raise LogMismatch(f"entry {applied}: logged move {e.get('label')!r}, replay offers {mv.label()!r}")
        ref.act(int(e["move"]))
        applied += 1
    return applied


# ------------------------------------------------------------------------------------- server

class GameServer(socketserver.UnixStreamServer):
    """Single-threaded on purpose: requests are applied one at a time, in order."""

    def __init__(self, sock_path: str, ref: Referee, log_path: Path):
        self.ref = ref
        self.log_path = log_path
        self.shown_at = time.time()
        if os.path.exists(sock_path):
            os.unlink(sock_path)
        super().__init__(sock_path, Handler)
        os.chmod(sock_path, 0o666)

    def handle_command(self, req: dict) -> dict:
        ref = self.ref
        cmd = req.get("cmd", "observe")
        if cmd == "observe":
            self.shown_at = time.time()
            return {"ok": True, "over": ref.over, "text": ref.observation()}
        if cmd == "act":
            try:
                index = int(req["move"])
                mv = ref.check_move(index)
            except (KeyError, TypeError, ValueError) as exc:
                return {"ok": False, "over": ref.over, "text": f"Not played: {exc}. Run `cr` to see the legal moves."}
            now = time.time()
            entry = {"decision": ref.decision, "tick": ref.tick, "move": index, "label": mv.label(),
                     "think_s": round(now - self.shown_at, 3), "wall": round(now, 3)}
            with self.log_path.open("a") as f:  # logged before it takes effect: the log is the source of truth
                f.write(json.dumps(entry) + "\n")
                f.flush()
                os.fsync(f.fileno())
            result = ref.act(index)
            self.shown_at = time.time()
            text = f"Your move: {result}\n\n{ref.observation()}"
            return {"ok": True, "over": ref.over, "text": text}
        return {"ok": False, "over": ref.over, "text": f"unknown command {cmd!r}"}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline(65536)
        try:
            req = json.loads(line or b"{}")
            resp = self.server.handle_command(req if isinstance(req, dict) else {})
        except Exception as exc:  # never let one bad request kill the match
            resp = {"ok": False, "over": False, "text": f"referee error: {type(exc).__name__}: {exc}"}
        self.wfile.write((json.dumps(resp) + "\n").encode())


def serve(config: Path, state_dir: Path, sock: str) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = open(state_dir / "server.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("server already running", file=sys.stderr)
        return
    cfg = json.loads(config.read_text())
    ref = Referee(cfg)
    log_path = state_dir / "actions.jsonl"
    resumed = replay_entries(ref, read_log(log_path))  # a restarted server continues the same match
    print(f"serving seed={cfg['seed']} team={ref.team} resumed={resumed}", file=sys.stderr, flush=True)
    with GameServer(sock, ref, log_path) as server:
        server.serve_forever()


# ----------------------------------------------------------------------------------- verifier

def verify(cfg: dict, log_path: Path, out_dir: Path | None) -> dict:
    ref = Referee(cfg, record=out_dir is not None)
    entries = read_log(log_path)
    report: dict = {"seed": cfg["seed"], "agent_team": ref.team, "opponent": cfg["opponent"],
                    "log_entries": len(entries)}
    try:
        applied = replay_entries(ref, entries)
        integrity = 1
    except (LogMismatch, ValueError, KeyError) as exc:
        report["integrity_error"] = str(exc)
        applied, integrity = 0, 0
    completed = int(ref.over)
    while not ref.over:  # decisions never made count as waits
        ref.act(0)
    outcome = ref.outcome()
    think = [float(e.get("think_s", 0)) for e in entries[:applied]]
    rewards = {
        "reward": float(outcome["result"] == "win" and integrity),  # 1 or 0: a draw is not a win
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
    report.update(outcome=outcome, rewards=rewards, decisions_applied=applied, completed=bool(completed))
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
    return report


def selfplay(cfg: dict, log_path: Path, agent: str) -> None:
    """Play the agent seat with a bot through the same act/log path the server uses."""
    bot = make_opponent(agent)
    ref = Referee(cfg)
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
