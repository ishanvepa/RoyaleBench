"""Live play: a human plays a bot in real time, in the browser.

    uv run python -m cr_arena.live            # then open http://localhost:8600

The engine runs at its real speed (20 ticks a second) and never waits for anyone. You drop cards
anywhere a card may go, at any moment. The bot thinks in its own process on snapshots of the game
(so its thinking never stalls the clock) and its move is applied when it is ready. Search v2
revalidates the source card and discards answers older than four seconds. The page draws at the screen's refresh rate by
interpolating between engine ticks. Finished games are saved under the job "human-play".
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import multiprocessing as mp
import os
import random
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import uvicorn
from royalegym.action import PlacementOracle
from royalegym.protocol import BIT_NO_DEPLOY, BIT_WATER, DeployCommand, DeployStatus, EntityKind, Placement, SpellMotion
from royalegym.replay import save_trace
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketDisconnected

from .db import DB
from .decks import CLASSIC_DECKS
from .game import Game
from .leaderboard import Leaderboard, guest_name, player_name as validate_player_name
from .rendering import embed_renderer
from .bots import human_bot_specs

HUMAN, BOT = 0, 1
BOT_SPECS = human_bot_specs("live")
COMMAND_DELAY_TICKS = 21  # a play lands about 1 s after it is made, for both sides, as measured on the real client
MAX_GAMES = 10  # one server process; visitors choosing decks do not occupy a slot
PUBLIC_BOT = "planner"
PUBLIC_DECK = "hog-2.6-cycle"
PUBLIC_PLANNER_WORKERS = 2  # a fixed budget per match, independent of connection order
ACTIVE: set = set()
MAX_SESSION_SECONDS = 15 * 60  # includes pauses, so abandoned tabs cannot hold a slot forever
SEND_TIMEOUT_SECONDS = 1.0
log = logging.getLogger(__name__)
SEARCH_V2_MAX_AGE_TICKS = 80  # discard answers older than four seconds
BOT_EVERY_TICKS = 5  # the bot is shown a fresh snapshot at most every 0.25 s of game time
OUT_DIR = Path(os.getenv("CR_ARENA_REPLAY_DIR", "runs/round_robin/human-play"))
PAGE = Path(__file__).with_name("live.html")
PLAYER_COOKIE = "cr_player"
_NOT_YET = {DeployStatus.NOT_ENOUGH_ELIXIR, DeployStatus.TOO_EARLY}


def _bot_worker(conn, decks: list[list[str]], seed: int, spec: dict, delay: int, shutdown) -> None:
    """Runs in its own process: receives an engine snapshot, answers with the bot's move."""
    import os
    import threading

    parent = os.getppid()

    def watch() -> None:  # never outlive the server (this process is not a daemon: it owns worker processes)
        while os.getppid() == parent:
            time.sleep(1.0)
        os._exit(0)

    threading.Thread(target=watch, daemon=True).start()
    from .bots.live import LiveBot

    bot = LiveBot(spec, decks, seed, BOT, delay)
    try:
        conn.send(None)  # ready (starting a process takes a second or two)
        while not shutdown.is_set():
            if not conn.poll(0.1):
                continue
            root = conn.recv()
            if root is None:
                return
            conn.send(bot.act(root))
    except (EOFError, OSError):
        return  # browser disconnected while the bot was starting or thinking
    finally:
        bot.close()


def bot_answer_command(game: Game, answer: tuple) -> tuple[DeployCommand | None, str]:
    """Revalidate v2's timestamp and card identity on the current real battle."""
    slot, x, y, raw = answer[:4]
    if slot < 0:
        return None, raw
    command = DeployCommand(BOT, slot, x, y)
    if len(answer) > 4:
        source_tick, card_id = answer[4:]
        state = game.state
        player = state.players[BOT]
        if not 0 <= state.tick - source_tick <= SEARCH_V2_MAX_AGE_TICKS:
            return None, raw + " (discarded: stale answer)"
        if not 0 <= slot < len(player.hand) or player.hand[slot] != card_id:
            return None, raw + " (discarded: hand changed)"
        if any(p[0] == 0 and p[1] == card_id for p in player.pending):
            return None, raw + " (discarded: card already pending)"
        if game.engine.check_deploy(command) != DeployStatus.OK:
            return None, raw + " (discarded: move no longer legal)"
    return command, raw


class Session:
    """One real-time game for one browser tab."""

    def __init__(self, ws: WebSocket, my_deck: str, opp_deck: str, seed: int, bot: str = "heuristic",
                 *, spec: dict | None = None, leaderboard: Leaderboard | None = None,
                 player_id: str | None = None, player_name: str | None = None, ranked: bool = True):
        self.ws = ws
        self.match_id = uuid.uuid4().hex
        # Scripted checks may save replays without contributing public scores.
        self.leaderboard = leaderboard if ranked and player_name is not None else None
        self.player_id = player_id or uuid.uuid4().hex
        self.player_name = guest_name(self.player_id) if player_name is None else validate_player_name(player_name)
        self.bot_spec = spec if spec is not None else BOT_SPECS[bot]
        self.deck_names = (my_deck, opp_deck)
        self.decks = [CLASSIC_DECKS[my_deck], CLASSIC_DECKS[opp_deck]]
        self.seed = seed
        self.delay = COMMAND_DELAY_TICKS
        self.game = Game(self.decks[0], self.decks[1], seed=seed, record=True, command_delay_ticks=self.delay)
        self.aim: dict[tuple[int, int], tuple[float, float]] = {}  # (team, card) -> where its waiting play was aimed
        self.sub = self.game.sub
        self.placement = PlacementOracle(self.game.arena, self.game.engine.rules(), self.game.cards)
        self.mask_cache: dict[int, tuple[tuple, dict]] = {}
        self.cmds: deque[DeployCommand] = deque()
        self.paused = False
        self.t0 = time.time()
        self.started_at = time.monotonic()
        self.last_mask_at = -math.inf
        self.closed = False
        # share the machine's cores between the games in progress
        worker_spec = self.bot_spec
        if spec is None and worker_spec.get("type") == "planner" and worker_spec.get("workers"):
            worker_spec = {**worker_spec, "workers": max(2, 8 // (len(ACTIVE) + 1))}
        ctx = mp.get_context("spawn")
        self.shutdown = ctx.Event()
        self.conn, child = ctx.Pipe()
        self.proc = ctx.Process(target=_bot_worker, args=(child, self.decks, seed, worker_spec, self.delay, self.shutdown), daemon=False)
        try:
            self.proc.start()
        except BaseException:
            self.conn.close()
            raise
        finally:
            child.close()
        ACTIVE.add(self)
        self.bot_busy = True  # until the worker reports it is ready
        self.bot_asked_tick = -10_000
        self.bot_send: asyncio.Future | None = None
        self.bot_sent_at = 0.0
        self.bot_source_tick = 0

    # ------------------------------------------------------------------ messages out
    def init_msg(self) -> dict:
        g = self.game
        return {"t": "init", "opp": self.bot_spec["name"], "seed": self.seed, "decks": list(self.deck_names),
                "player_name": self.player_name,
                "cards": {c.card_id: [c.name, g.kind_of(c), c.elixir, c.footprint_tiles or 0] for c in g.cards},
                "lockout": g.engine.rules().deploy_lockout_ticks, "delay": self.delay,
                "arena": {"tiles_x": g.arena.tiles_x, "tiles_y": g.arena.tiles_y,
                          "half": g.arena.half, "grid": g.arena.grid,
                          "water_half_rows": list(g.arena.water_half_rows),
                          "bits": {"WATER": BIT_WATER, "NO_DEPLOY": BIT_NO_DEPLOY}}}

    def snapshot(self) -> dict:
        g, sub = self.game, self.sub
        s = g.state
        me, op = s.players[HUMAN], s.players[BOT]
        left, ot = g.time_left_s()
        costs = me.hand_costs if len(me.hand_costs) == len(me.hand) else [-1] * len(me.hand)
        ents = []
        units = self.unit_types()
        for e in s.entities:
            if e.hp <= 0:
                continue
            flags = (1 if e.flying else 0) | (2 if e.deploy_ticks > 0 else 0)
            ents.append([e.uid, e.team, int(e.kind), e.card_id, round(e.x / sub, 3), round(e.y / sub, 3), e.hp, e.max_hp,
                         round(e.radius / sub, 3), flags, e.tower_slot, e.facing[0], e.facing[1], e.stun_ticks,
                         [v / sub for v in e.footprint] if e.footprint is not None else None,
                         e.shield, e.status_flags, e.charge,
                         units[e.unit_type] if 0 <= e.unit_type < len(units) else None])
        return {
            "t": "s", "k": s.tick, "left": round(left, 2), "ot": ot, "rate": s.elixir_rate, "paused": self.paused,
            # elixir shown net of plays that are on their way; "pend" = [slot, card, x, y, ticks left]
            "me": {"e": me.elixir_milli - me.pending_cost * 1000,
                   "pend": self.pending_plays(me),
                   "hand": [[cid, costs[i]] for i, cid in enumerate(me.hand)],
                   "next": me.next_card, "crowns": me.crowns},
            "op": {"crowns": op.crowns},
            "en": ents,
            "sp": [[sp.team, sp.card_id, round(sp.x / sub, 2), round(sp.y / sub, 2), round(sp.aim_x / sub, 2),
                    round(sp.aim_y / sub, 2), SpellMotion(sp.motion).name] for sp in s.spells],
            "pr": [[p.team, round(p.x / sub, 2), round(p.y / sub, 2)] for p in s.projectiles],
            # All four masks arrive with the first hand; later snapshots carry only updates.
            "masks": self.placement_updates(s),
        }

    def placement_updates(self, state) -> list[dict]:
        """Preload masks and invalidate them when the hand or deployment geometry changes."""
        updates = []
        player = state.players[HUMAN]
        own_princesses = tuple((e.uid, e.hp > 0, tuple(e.footprint or ())) for e in state.entities
                              if e.team == HUMAN and e.kind == EntityKind.PRINCESS_TOWER)
        for slot, cid in enumerate(player.hand):
            card = self.game.card_by_id.get(cid)
            if card and card.placement == Placement.MIRROR:
                card = self.game.card_by_id.get(player.mirror_target)
            geometry = self.placement.grid_key(state, HUMAN, card, self.game.arena.half) if card else ()
            # Unknown placement classes are deliberately recomputed rather than cached unsafely.
            if geometry is None:
                geometry = ("tick", state.tick)
            pending = any(p[0] == 0 and p[1] == cid for p in player.pending)
            key = (cid, card.card_id if card else None, geometry, own_princesses, pending, state.game_over)
            cached = self.mask_cache.get(slot)
            if cached is None or cached[0] != key:
                mask = self.mask(slot)
                self.mask_cache[slot] = (key, mask)
                updates.append(mask)
        return updates

    def unit_types(self) -> list[str]:
        """The engine's unit-type names, so the page can tell a Golem from its Golemites."""
        names = getattr(self, "_unit_types", None)
        if names is None:
            said = getattr(self.game.engine, "unit_types", None)
            names = self._unit_types = list(said()) if callable(said) else []
        return names

    def pending_plays(self, me) -> list[list]:
        """The human's plays on their way, each [hand slot, card, x, y, ticks left]. The engine's
        rows are [kind, card, x, y, ticks left, cost] with kind 0 for a play: they name the card,
        not the slot, so the slot is the one still holding that card (the hand only changes once
        the play lands, and a deck holds each card once)."""
        out, taken = [], set()
        for kind, card, x, y, ticks, *_ in me.pending:
            if kind != 0:
                continue  # a button press, not a card
            slot = next((i for i, cid in enumerate(me.hand) if cid == card and i not in taken), -1)
            taken.add(slot)
            out.append([slot, card, round(x / self.sub, 2), round(y / self.sub, 2), ticks])
        return out

    def mask(self, slot: int) -> dict:
        """Spatial eligibility at half-cell centres, independent of elixir and cooldown."""
        g, sub = self.game, self.sub
        state = g.state
        hand = state.players[HUMAN].hand
        card = g.card_by_id.get(hand[slot]) if 0 <= slot < len(hand) else None
        half = g.arena.half
        width, height = g.arena.tiles_x * half, g.arena.tiles_y * half
        reply = {"t": "mask", "slot": slot, "card": card.card_id if card else -1,
                 "half": half, "width": width, "height": height, "m": "0" * (width * height)}
        if card is None:
            return reply
        if card.placement == Placement.MIRROR:
            card = g.card_by_id.get(state.players[HUMAN].mirror_target)
            if card is None:
                return reply
        # The oracle tests the actual tap geometry, without spending resources or
        # advancing the game. It also excludes taps the engine would clamp back
        # from enemy territory, so the highlighted cell is where the player aimed.
        legal = self.placement.point_grid(state, HUMAN, card, half).copy()
        if g.kind_of(card) in ("TROOP", "BUILDING"):
            # The engine accepts taps on an own princess tower by relocating
            # them. The UI must not offer its occupied footprint as a drop site.
            # King towers retain their separate arena-defined no-deploy block.
            px, py = self.placement.points(half)
            for entity in state.entities:
                if entity.team != HUMAN or entity.kind != EntityKind.PRINCESS_TOWER or entity.hp <= 0:
                    continue
                if entity.footprint is None:
                    raise ValueError("princess tower is missing its placement footprint")
                x0, y0, x1, y1 = entity.footprint
                legal &= ~((px >= x0) & (px < x1) & (py >= y0) & (py < y1))
        for cy, cx in zip(*legal.nonzero(), strict=True):
            x, y = int((cx + 0.5) * sub / half), int((cy + 0.5) * sub / half)
            if card.placement == Placement.BUILDING:
                # Relocation may fail on a crowded board. This query ignores
                # elixir/cooldown too, unlike check_deploy.
                legal[cy, cx] = g.engine.building_placement(HUMAN, card.name, x, y) is not None
            else:
                status = g.engine.check_deploy(DeployCommand(HUMAN, slot, x, y))
                legal[cy, cx] = status == DeployStatus.OK or status in _NOT_YET
        reply["m"] = "".join("1" if ok else "0" for ok in legal.flat)
        return reply

    async def send(self, msg: dict) -> None:
        # A stalled browser may lose its own game, but cannot pin a slot indefinitely.
        await asyncio.wait_for(self.ws.send_text(json.dumps(msg, separators=(",", ":"))),
                               timeout=SEND_TIMEOUT_SECONDS)

    # ------------------------------------------------------------------ messages in
    def on_message(self, m: dict) -> dict | None:
        kind = m.get("t")
        if kind == "play":
            slot = m.get("slot")
            if type(slot) is not int or not 0 <= slot < 4:
                raise ValueError("Choose a card in your hand.")
            x, y = float(m["x"]), float(m["y"])
            if not (math.isfinite(x) and math.isfinite(y) and
                    0 <= x < self.game.arena.tiles_x and 0 <= y < self.game.arena.tiles_y):
                raise ValueError("Choose a position inside the arena.")
            x, y = int(x * self.sub), int(y * self.sub)
            if len(self.cmds) < 4:
                self.cmds.append(DeployCommand(HUMAN, slot, x, y))
        elif kind == "mask":
            slot = m.get("slot")
            if type(slot) is not int or not 0 <= slot < 4:
                raise ValueError("Choose a card in your hand.")
            now = time.monotonic()
            if now - self.last_mask_at >= 0.1:
                self.last_mask_at = now
                return self.mask(slot)
        elif kind == "pause":
            self.paused = bool(m.get("on"))
        return None

    # ------------------------------------------------------------------ the clock
    async def run(self) -> None:
        try:
            await self._run()
        except (WebSocketDisconnect, WebSocketDisconnected, ConnectionError):
            pass
        except Exception:
            log.exception("live game stopped")
            with suppress(Exception):
                await self.send({"t": "error", "message": "Game stopped. Please start a new game."})
            with suppress(Exception):
                await self.ws.close(code=1011)
        finally:
            # A finished game must free its slot even if its browser stays open.
            ACTIVE.discard(self)
            await asyncio.to_thread(self.close)

    async def _run(self) -> None:
        g = self.game
        e = g.engine
        loop = asyncio.get_running_loop()
        tick_s = g.state.tick_ms / 1000
        due = loop.time()
        await self.send(self.init_msg())
        await self.send(self.snapshot())
        while not g.over:
            if time.monotonic() - self.started_at >= MAX_SESSION_SECONDS:
                await self.send({"t": "error", "message": "Game expired. Please start a new game."})
                return
            if not self.paused:
                cmds = []
                if self.cmds:
                    cmds.append(self.cmds.popleft())
                if self.bot_send is not None and self.bot_send.done():
                    self.bot_send.result()  # propagate a failed pipe write instead of leaving a silent bot
                    self.bot_send = None
                if not self.proc.is_alive():
                    raise RuntimeError("bot worker exited")
                if self.bot_busy and self.conn.poll():
                    answer = self.conn.recv()
                    self.bot_busy = False
                    if answer is not None:  # None = the worker's "ready"
                        await self.send({"t": "bot_timing",
                                         "decision_ms": round((loop.time() - self.bot_sent_at) * 1000, 2),
                                         "source_age_ticks": g.state.tick - self.bot_source_tick})
                        command, raw = bot_answer_command(g, answer)
                        if command is not None:
                            cmds.append(command)
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
                    self.bot_sent_at, self.bot_source_tick = loop.time(), g.state.tick
                    self.bot_send = loop.run_in_executor(None, self.conn.send, e.save_state())
                    self.bot_send.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
                    self.bot_busy, self.bot_asked_tick = True, tick
            await self.send(self.snapshot())
            due += tick_s
            delay = due - loop.time()
            if delay < -0.25:  # fell badly behind (machine asleep, tab stalled): do not sprint to catch up
                due = loop.time()
            await asyncio.sleep(max(0.0, delay))
        ACTIVE.discard(self)
        await asyncio.to_thread(self.close)
        await self.send({"t": "over", **await asyncio.to_thread(self.save)})

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
            mid = f"human__vs__{self.bot_spec['name']}__{self.match_id}"
            (OUT_DIR / "replays").mkdir(parents=True, exist_ok=True)
            rp = OUT_DIR / "replays" / f"{mid}.msgpack"
            if trace is not None:
                save_trace(trace, rp)
            db = DB()
            try:
                self._save_match(db, mid, rp, winner, crowns, towers, ticks, out)
            finally:
                db.close()
        except Exception as exc:  # the game itself is over either way; say why it was not saved
            log.exception("could not save live game")
            out["save_error"] = f"{type(exc).__name__}: {exc}"
        # A replay/storage failure should not discard a legitimately completed result.
        if self.leaderboard is not None and g.over:
            try:
                self.leaderboard.record(self.match_id, self.player_id, self.player_name, int(winner))
            except Exception:
                log.exception("could not update leaderboard")
                out["leaderboard_error"] = True
        return out

    def _save_match(self, db, mid, rp, winner, crowns, towers, ticks, out):
        # SQLite serializes simultaneous completions; update the count in the same transaction.
        with db.transaction():
            jid = db.get_or_create_job("human-play", "", ["human"], [], self.game.decision_ticks, 0,
                                       "Games played by a human on the Play page")
            db.queue_matches(jid, [{"match_id": mid, "blue": "human", "red": self.bot_spec["name"], "seed": self.seed,
                                    "deck": {"blue": self.decks[0], "red": self.decks[1]}}])
            db.match_started(jid, mid, "", str(rp))
            db.set_match_decks(jid, mid, self.decks[0], self.decks[1])
            db.match_finished(jid, {"match_id": mid, "winner": int(winner), "crowns": crowns, "tower_hp": towers,
                                    "ticks": ticks, "wall_s": round(time.time() - self.t0, 1),
                                    "stats_blue": {"mode": "live"}, "stats_red": {}})
            db.execute("UPDATE jobs SET total_matches = (SELECT COUNT(*) FROM matches WHERE job_id = ?), "
                       "status = 'done' WHERE id = ?", (jid, jid))
            out["saved"] = mid
        return out

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        ACTIVE.discard(self)
        # Give Planner a chance to close its process pool instead of leaking its semaphores.
        # This runs off the event loop and does not block the other matches' clocks.
        self.shutdown.set()
        self.proc.join(timeout=2.0)
        if self.proc.is_alive():
            self.proc.terminate()
            self.proc.join(timeout=0.5)
        self.conn.close()


def player_identity(request) -> str:
    value = request.cookies.get(PLAYER_COOKIE, "") if request is not None else ""
    return value if len(value) == 32 and all(c in "0123456789abcdef" for c in value) else uuid.uuid4().hex


def remember_player(response, request, player_id):
    response.set_cookie(PLAYER_COOKIE, player_id, max_age=365 * 24 * 60 * 60,
                        httponly=True, samesite="lax", secure=request is not None and request.url.scheme == "https")
    return response


async def page(request) -> HTMLResponse:
    response = HTMLResponse(embed_renderer(PAGE.read_text(encoding="utf-8")), headers={"Cache-Control": "no-store"})
    return remember_player(response, request, player_identity(request))


async def leaderboard(request) -> JSONResponse:
    player_id = player_identity(request)
    try:
        result = await asyncio.to_thread(request.app.state.leaderboard.standings, player_id)
        response = JSONResponse(result, headers={"Cache-Control": "no-store"})
    except Exception:
        log.exception("could not read leaderboard")
        response = JSONResponse({"error": "Leaderboard unavailable. Please try again."}, status_code=503,
                                headers={"Cache-Control": "no-store"})
    return remember_player(response, request, player_id)


async def socket(ws: WebSocket) -> None:
    await ws.accept()
    player_id = player_identity(ws)
    session: Session | None = None
    task: asyncio.Task | None = None

    async def stop() -> None:
        nonlocal session, task
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if session:
            ACTIVE.discard(session)
            await asyncio.to_thread(session.close)
        session = task = None

    try:
        specs, fixed = ws.app.state.bot_specs, ws.app.state.fixed_opponent
        await ws.send_json({"t": "hello", "decks": CLASSIC_DECKS, "bots": specs, "max_games": MAX_GAMES,
                            "fixed_opponent": fixed})
        while True:
            try:
                raw = await ws.receive_text()
                if len(raw) > 4096:
                    raise ValueError("Game message is too large.")
                m = json.loads(raw)
                if not isinstance(m, dict):
                    raise ValueError("Expected an object.")
            except ValueError:
                await ws.send_json({"t": "invalid", "message": "Invalid game message."})
                continue
            if m.get("t") == "start":
                try:
                    ranked = m.get("ranked", True)
                    if type(ranked) is not bool:
                        raise ValueError("ranked must be true or false.")
                    name = validate_player_name(m.get("player_name")) if ranked or "player_name" in m else None
                except ValueError as exc:
                    await ws.send_json({"t": "invalid", "message": str(exc)})
                    continue
                mine, theirs = m.get("deck"), m.get("opp_deck", m.get("deck"))
                bot, seed = m.get("bot", next(iter(specs))), m.get("seed", random.randrange(1, 10_000))
                if fixed:
                    bot, theirs = fixed["bot"], fixed["deck"]
                if (not isinstance(mine, str) or mine not in CLASSIC_DECKS or
                        not isinstance(theirs, str) or theirs not in CLASSIC_DECKS or
                        not isinstance(bot, str) or bot not in specs or type(seed) is not int or not 0 <= seed < 2**32):
                    await ws.send_json({"t": "invalid", "message": "Choose a valid bot and decks."})
                    continue
                await stop()
                if len(ACTIVE) >= MAX_GAMES:
                    await ws.send_json({"t": "busy", "n": len(ACTIVE),
                                        "message": "Server at capacity — please try again shortly."})
                    continue
                try:
                    session = Session(ws, mine, theirs, seed, bot, spec=specs[bot] if fixed else None,
                                      leaderboard=ws.app.state.leaderboard, player_id=player_id, player_name=name,
                                      ranked=ranked)
                except Exception:
                    log.exception("could not start live game")
                    await ws.send_json({"t": "error", "message": "Could not start a game. Please try again."})
                    continue
                task = asyncio.create_task(session.run())
            elif m.get("t") == "quit":
                await stop()
            elif session and task and not task.done():
                try:
                    reply = session.on_message(m)
                except (ValueError, TypeError, KeyError, OverflowError):
                    await ws.send_json({"t": "invalid", "message": "Invalid card or arena position."})
                    continue
                if reply:
                    await session.send(reply)
    except (WebSocketDisconnect, WebSocketDisconnected):
        pass
    finally:
        await stop()


async def health(_request) -> JSONResponse:
    return JSONResponse({"ok": True, "active_games": len(ACTIVE), "max_games": MAX_GAMES})


@asynccontextmanager
async def lifespan(_app):
    # Initialize once before concurrent completions can try to create the SQLite schema.
    def initialize():
        DB().close()
    await asyncio.to_thread(initialize)
    yield


def create_app(*, public: bool = False, leaderboard_path: Path | None = None) -> Starlette:
    app = Starlette(routes=[Route("/", page), Route("/health", health), Route("/leaderboard", leaderboard),
                            WebSocketRoute("/ws", socket)],
                    lifespan=lifespan)
    app.state.leaderboard = Leaderboard(leaderboard_path or Path(os.getenv("CR_ARENA_LEADERBOARD", OUT_DIR / "leaderboard.csv")))
    app.state.bot_specs = {PUBLIC_BOT: {**BOT_SPECS[PUBLIC_BOT], "workers": PUBLIC_PLANNER_WORKERS}} if public else BOT_SPECS
    app.state.fixed_opponent = {"bot": PUBLIC_BOT, "deck": PUBLIC_DECK} if public else None
    return app


app = create_app()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8600)
    ap.add_argument("--public", action="store_true", help="play Planner with its fixed Hog Cycle deck (ten games)")
    a = ap.parse_args()
    print(f"Live play: http://{a.host}:{a.port}")
    uvicorn.run(create_app(public=a.public), host=a.host, port=a.port, log_level="warning",
                workers=1, ws_max_size=4096, ws_max_queue=8)


if __name__ == "__main__":
    main()
