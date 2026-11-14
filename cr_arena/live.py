"""Live play: a human plays a search or planning bot in real time, in the browser.

    uv run python -m cr_arena.live            # then open http://localhost:8600

The engine runs at its real speed (20 ticks a second) and never waits for anyone. You drop cards
anywhere a card may go, at any moment. The bot thinks in its own process on snapshots of the game
(so its thinking never stalls the clock) and its move is applied the moment it is ready, about
0.3 s after the snapshot it was computed on. The page draws at the screen's refresh rate by
interpolating between engine ticks. Finished games are saved under the job "human-play".
"""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing as mp
import random
import time
from collections import deque
from pathlib import Path

import uvicorn
from royalegym.protocol import DeployCommand, DeployStatus, EntityKind
from royalegym.replay import save_trace
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from .db import DB
from .decks import CLASSIC_DECKS
from .game import Game

HUMAN, BOT = 0, 1
BOT_SPECS = {
    "planner": {"name": "planner-bot", "type": "planner", "workers": 6},
    "search": {"name": "search-bot", "type": "search", "rollouts": 4, "horizon_s": 12.0},
}
COMMAND_DELAY_TICKS = 21  # a play lands about 1 s after it is made, for both sides, as measured on the real client
MAX_GAMES = 3  # games at once (each one runs its own bot processes); a fourth player is asked to wait
ACTIVE: set = set()
BOT_EVERY_TICKS = 5  # the bot is shown a fresh snapshot at most every 0.25 s of game time
OUT_DIR = Path("runs/round_robin/human-play")
PAGE = Path(__file__).with_name("live.html")
# Statuses that say "this spot is not allowed" (everything else is about timing or elixir).
_BAD_SPOT = {DeployStatus.WATER, DeployStatus.NO_DEPLOY, DeployStatus.OUT_OF_TERRITORY, DeployStatus.OUT_OF_ARENA}
_NOT_YET = {DeployStatus.NOT_ENOUGH_ELIXIR, DeployStatus.TOO_EARLY}


def _bot_worker(conn, decks: list[list[str]], seed: int, spec: dict, delay: int) -> None:
    """Runs in its own process: receives an engine snapshot, answers with the bot's move."""
    import os
    import threading

    parent = os.getppid()

    def watch() -> None:  # never outlive the server (this process is not a daemon: it owns worker processes)
        while os.getppid() == parent:
            time.sleep(1.0)
        os._exit(0)

    threading.Thread(target=watch, daemon=True).start()
    planner = sim = bot = None
    if spec.get("type") == "planner":
        from .planner_bot import Planner

        planner = Planner(decks, seed, BOT, delay=delay, workers=spec.get("workers", 0))
    else:
        from .players import build_player

        sim = Game(decks[0], decks[1], seed=seed, record=False, command_delay_ticks=delay)
        bot = build_player(spec)
        bot.sim = sim  # search on this private engine
    try:
        conn.send(None)  # ready (starting a process takes a second or two)
    except OSError:  # the player left before the bot was up
        if planner:
            planner.close()
        return
    while True:
        try:
            root = conn.recv()
        except (EOFError, OSError):
            root = None
        if root is None:
            if planner:
                planner.close()
            return
        if planner:
            play, raw = planner.act(root)
            conn.send((play[1], play[2], play[3], raw) if play else (-1, 0, 0, raw))
            continue
        sim.engine.load_state(root)
        moves = sim.legal_moves(BOT)
        if len(moves) > 1:
            d = bot.decide(sim, BOT, "", moves)
            mv, raw = moves[d.index], d.raw
        else:
            mv, raw = moves[0], ""
        conn.send((mv.slot, mv.x, mv.y, raw))


class Session:
    """One real-time game for one browser tab."""

    def __init__(self, ws: WebSocket, my_deck: str, opp_deck: str, seed: int, bot: str = "planner"):
        self.ws = ws
        self.bot_spec = BOT_SPECS[bot]
        self.deck_names = (my_deck, opp_deck)
        self.decks = [CLASSIC_DECKS[my_deck], CLASSIC_DECKS[opp_deck]]
        self.seed = seed
        self.delay = COMMAND_DELAY_TICKS
        self.game = Game(self.decks[0], self.decks[1], seed=seed, record=True, command_delay_ticks=self.delay)
        self.aim: dict[tuple[int, int], tuple[float, float]] = {}  # (team, card) -> where its waiting play was aimed
        self.sub = self.game.sub
        self.cmds: deque[DeployCommand] = deque()
        self.paused = False
        self.t0 = time.time()
        # share the machine's cores between the games in progress
        spec = {**self.bot_spec, "workers": max(2, 8 // (len(ACTIVE) + 1))} if self.bot_spec.get("workers") else self.bot_spec
        ACTIVE.add(self)
        ctx = mp.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self.proc = ctx.Process(target=_bot_worker, args=(child, self.decks, seed, spec, self.delay), daemon=False)
        self.proc.start()
        child.close()
        self.bot_busy = True  # until the worker reports it is ready
        self.bot_asked_tick = -10_000

    # ------------------------------------------------------------------ messages out
    def init_msg(self) -> dict:
        g = self.game
        return {"t": "init", "opp": self.bot_spec["name"], "seed": self.seed, "decks": list(self.deck_names),
                "cards": {c.card_id: [c.name, g.kind_of(c), c.elixir] for c in g.cards},
                "lockout": g.engine.rules().deploy_lockout_ticks, "delay": self.delay}

    def snapshot(self) -> dict:
        g, sub = self.game, self.sub
        s = g.state
        me, op = s.players[HUMAN], s.players[BOT]
        left, ot = g.time_left_s()
        costs = me.hand_costs if len(me.hand_costs) == len(me.hand) else [-1] * len(me.hand)
        ents = []
        for e in s.entities:
            if e.hp <= 0:
                continue
            flags = (1 if e.flying else 0) | (2 if e.deploy_ticks > 0 else 0)
            ents.append([e.uid, e.team, int(e.kind), e.card_id, round(e.x / sub, 3), round(e.y / sub, 3), e.hp, e.max_hp,
                         round(e.radius / sub, 3), flags, e.tower_slot, e.facing[0], e.facing[1]])
        return {
            "t": "s", "k": s.tick, "left": round(left, 2), "ot": ot, "rate": s.elixir_rate, "paused": self.paused,
            # elixir shown net of plays that are on their way; "pend" = [slot, card, x, y, ticks left]
            "me": {"e": me.elixir_milli - me.pending_cost * 1000,
                   "pend": [[p[0], p[1], round(p[2] / sub, 2), round(p[3] / sub, 2), p[4]] for p in me.pending],
                   "hand": [[cid, costs[i]] for i, cid in enumerate(me.hand)],
                   "next": me.next_card, "crowns": me.crowns},
            "op": {"crowns": op.crowns},
            "en": ents,
            "sp": [[sp.team, sp.card_id, round(sp.x / sub, 2), round(sp.y / sub, 2), round(sp.aim_x / sub, 2),
                    round(sp.aim_y / sub, 2)] for sp in s.spells],
            "pr": [[p.team, round(p.x / sub, 2), round(p.y / sub, 2)] for p in s.projectiles],
        }

    def mask(self, slot: int) -> dict:
        """Which tiles the card in `slot` may be dropped on (row-major from the human's back edge)."""
        g, sub = self.game, self.sub
        hand = g.state.players[HUMAN].hand
        card = g.card_by_id.get(hand[slot]) if 0 <= slot < len(hand) else None
        if card is None:
            return {"t": "mask", "slot": slot, "m": ""}
        kind = g.kind_of(card)
        spell = kind == "SPELL"
        # Lanes whose enemy princess tower still stands (x < 9 tiles = the human's left lane).
        closed = {e.x < 9 * sub for e in g.state.entities
                  if e.team == BOT and e.kind == EntityKind.PRINCESS_TOWER and e.hp > 0}
        out = []
        for ty in range(32):
            for tx in range(18):
                st = g.engine.check_deploy(DeployCommand(HUMAN, slot, int((tx + 0.5) * sub), int((ty + 0.5) * sub)))
                if st in _NOT_YET:  # the engine answers "not yet" before it looks at the spot: assume own half
                    ok = spell or ty < 15
                else:
                    ok = st not in _BAD_SPOT
                # The engine accepts a troop tapped across the river by moving it back to the legal edge.
                # Show the real territory instead: own half, plus the pocket behind a fallen tower.
                if ok and kind == "TROOP" and ty >= 15:
                    ok = (tx < 9) not in closed and ty <= 20
                out.append("1" if ok else "0")
        return {"t": "mask", "slot": slot, "card": card.card_id, "m": "".join(out)}

    async def send(self, msg: dict) -> None:
        await self.ws.send_text(json.dumps(msg, separators=(",", ":")))

    # ------------------------------------------------------------------ messages in
    def on_message(self, m: dict) -> dict | None:
        kind = m.get("t")
        if kind == "play":
            x, y = int(float(m["x"]) * self.sub), int(float(m["y"]) * self.sub)
            if len(self.cmds) < 4:
                self.cmds.append(DeployCommand(HUMAN, int(m["slot"]), x, y))
        elif kind == "mask":
            return self.mask(int(m["slot"]))
        elif kind == "pause":
            self.paused = bool(m.get("on"))
        return None

    # ------------------------------------------------------------------ the clock
    async def run(self) -> None:
        g = self.game
        e = g.engine
        loop = asyncio.get_running_loop()
        tick_s = g.state.tick_ms / 1000
        due = loop.time()
        await self.send(self.init_msg())
        await self.send(self.snapshot())
        while not g.over:
            if not self.paused:
                cmds = []
                if self.cmds:
                    cmds.append(self.cmds.popleft())
                if self.bot_busy and self.conn.poll():
                    answer = self.conn.recv()
                    self.bot_busy = False
                    if answer is not None:  # None = the worker's "ready"
                        slot, x, y, raw = answer
                        if slot >= 0:
                            cmds.append(DeployCommand(BOT, slot, x, y))
                        if raw:
                            await self.send({"t": "bot", "raw": raw})
                tick = g.state.tick
                res = e.step(cmds, 1)
                g.recorder.record_step(tick, 1, list(cmds), res)
                g.recorder.record_frame(e)
                for r in res:  # the answer to a command made this tick
                    ok = r.status == DeployStatus.OK
                    spot = (round(r.x / self.sub, 2), round(r.y / self.sub, 2))
                    if ok and self.delay:
                        self.aim[(r.team, r.card_id)] = spot  # it lands later: reported below when it does
                    elif ok or r.team == HUMAN:
                        await self.send(self.event(r.team, r.card_id, ok, r.status, spot, tick))
                for _t, team, kind, card, reason in (e.step_commands_run() or []):  # delayed plays that landed
                    if kind == "deploy" and (reason == 0 or team == HUMAN):
                        try:  # the engine's own reason code -> DeployStatus
                            status = e._status(reason) if reason else 0
                        except Exception:
                            status = -1
                        await self.send(self.event(team, card, reason == 0, status, self.aim.pop((team, card), None), tick))
                if not self.bot_busy and tick - self.bot_asked_tick >= BOT_EVERY_TICKS:
                    loop.run_in_executor(None, self.conn.send, e.save_state())  # a pipe write can block: keep it off the clock
                    self.bot_busy, self.bot_asked_tick = True, tick
            await self.send(self.snapshot())
            due += tick_s
            delay = due - loop.time()
            if delay < -0.25:  # fell badly behind (machine asleep, tab stalled): do not sprint to catch up
                due = loop.time()
            await asyncio.sleep(max(0.0, delay))
        await self.send({"t": "over", **self.save()})

    def event(self, team: int, card: int, ok: bool, status: int, spot, tick: int) -> dict:
        try:
            why = DeployStatus(status).name.replace("_", " ").lower()
        except ValueError:
            why = "refused"
        # "flying": the spell is now travelling to its target (if not, it struck at once)
        flying = any(sp.team == team and sp.card_id == card for sp in self.game.state.spells)
        return {"t": "ev", "who": team, "card": card, "ok": ok, "k": tick, "why": why,
                "x": spot[0] if spot else None, "y": spot[1] if spot else None, "flying": flying}

    def save(self) -> dict:
        g = self.game
        winner, crowns, towers, ticks, trace = g.finish()
        out = {"winner": int(winner), "crowns": crowns, "saved": None}
        try:
            mid = f"human__vs__{self.bot_spec['name']}__{time.strftime('%Y%m%d-%H%M%S')}"
            (OUT_DIR / "replays").mkdir(parents=True, exist_ok=True)
            rp = OUT_DIR / "replays" / f"{mid}.msgpack"
            if trace is not None:
                save_trace(trace, rp)
            db = DB()
            jid = db.get_or_create_job("human-play", "", ["human"], [], g.decision_ticks, 0,
                                       "Games played by a human on the Play page")
            db.queue_matches(jid, [{"match_id": mid, "blue": "human", "red": self.bot_spec["name"], "seed": self.seed,
                                    "deck": {"blue": self.decks[0], "red": self.decks[1]}}])
            db.match_started(jid, mid, "", str(rp))
            db.set_match_decks(jid, mid, self.decks[0], self.decks[1])
            db.match_finished(jid, {"match_id": mid, "winner": int(winner), "crowns": crowns, "tower_hp": towers,
                                    "ticks": ticks, "wall_s": round(time.time() - self.t0, 1),
                                    "stats_blue": {"mode": "live"}, "stats_red": {}})
            n = db.query("SELECT COUNT(*) AS n FROM matches WHERE job_id = ?", (jid,))[0]["n"]
            db.execute("UPDATE jobs SET total_matches = ?, status = 'done' WHERE id = ?", (n, jid))
            out["saved"] = mid
        except Exception as exc:  # the game itself is over either way; say why it was not saved
            out["save_error"] = f"{type(exc).__name__}: {exc}"
        return out

    def close(self) -> None:
        ACTIVE.discard(self)
        try:
            self.conn.send(None)
        except (OSError, ValueError):
            pass
        self.conn.close()
        self.proc.join(timeout=0.5)
        if self.proc.is_alive():
            self.proc.terminate()


async def page(_request) -> HTMLResponse:
    return HTMLResponse(PAGE.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store"})


async def socket(ws: WebSocket) -> None:
    await ws.accept()
    session: Session | None = None
    task: asyncio.Task | None = None

    def stop() -> None:
        nonlocal session, task
        if task:
            task.cancel()
        if session:
            session.close()
        session = task = None

    try:
        await ws.send_text(json.dumps({"t": "hello", "decks": CLASSIC_DECKS, "bots": BOT_SPECS}))
        while True:
            m = json.loads(await ws.receive_text())
            if m.get("t") == "start":
                stop()
                if len(ACTIVE) >= MAX_GAMES:
                    await ws.send_text(json.dumps({"t": "busy", "n": len(ACTIVE)}))
                    continue
                mine = m.get("deck") if m.get("deck") in CLASSIC_DECKS else next(iter(CLASSIC_DECKS))
                theirs = m.get("opp_deck") if m.get("opp_deck") in CLASSIC_DECKS else mine
                bot = m.get("bot") if m.get("bot") in BOT_SPECS else "planner"
                session = Session(ws, mine, theirs, int(m.get("seed") or random.randrange(1, 10_000)), bot)
                task = asyncio.create_task(session.run())
            elif m.get("t") == "quit":
                stop()
            elif session:
                reply = session.on_message(m)
                if reply:
                    await session.send(reply)
    except WebSocketDisconnect:
        pass
    finally:
        stop()


app = Starlette(routes=[Route("/", page), WebSocketRoute("/ws", socket)])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8600)
    a = ap.parse_args()
    print(f"Live play: http://{a.host}:{a.port}")
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
