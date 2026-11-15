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
import tempfile
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager, suppress
from functools import lru_cache
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
from .scenario_task import setup_for

HUMAN, BOT = 0, 1
BOT_SPECS = human_bot_specs("live")
COMMAND_DELAY_TICKS = 21  # a play lands about 1 s after it is made, for both sides, as measured on the real client
MAX_GAMES = 7  # one server process; visitors choosing decks do not occupy a slot
PUBLIC_BOT = "planner"
PUBLIC_DECK = "hog-2.6-cycle"
# Planner has no time budget: fewer workers means slower answers on staler positions, not shallower
# search. A lone local game gets this many, and every public match gets the same, so shared play
# matches local strength. Hosting reserves about nine cores per match (eight workers plus the bot).
PLANNER_WORKERS = 8
PUBLIC_PLANNER_WORKERS = PLANNER_WORKERS  # a fixed budget per match, independent of connection order
ACTIVE: set = set()
MAX_SESSION_SECONDS = 15 * 60  # abandoned tabs cannot hold a slot forever
SEND_TIMEOUT_SECONDS = 1.0
# The clock holds at tick 0 until the bot and its search pool are ready, so a cold start cannot
# cost the bot the opening; a worker that never reports ready cannot hold the match past this.
BOT_READY_TIMEOUT_SECONDS = 20.0
# A quit during warm-up must let the bot finish starting its pool and close it, or the killed
# process leaks the pool's semaphores. The slot is already free; this wait runs off the event loop.
BOT_EXIT_SECONDS = 15.0
log = logging.getLogger(__name__)
SEARCH_V2_MAX_AGE_TICKS = 80  # discard answers older than four seconds
BOT_EVERY_TICKS = 5  # the bot is shown a fresh snapshot at most every 0.25 s of game time
OUT_DIR = Path(os.getenv("CR_ARENA_REPLAY_DIR", "runs/round_robin/human-play"))
PAGE = Path(__file__).with_name("live.html")
BENCHMARK_TASK = Path(__file__).resolve().parent.parent / "benchmarks/royalebench-tactics/05-hog-body-block/environment/task.json"
HOG_PRELUDE_TICKS = 10  # show the empty board for 0.5 s before the scripted red placement
HOG_REFERENCE = {10: (0, 1.5, 12.5), 20: (1, 3.5, 12.5)}  # ticks after the Hog command
PLAYER_COOKIE = "cr_player"
_NOT_YET = {DeployStatus.NOT_ENOUGH_ELIXIR, DeployStatus.TOO_EARLY}


def _bot_worker(conn, decks: list[list[str]], seed: int, spec: dict, delay: int, shutdown,
                team: int = BOT) -> None:
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

    bot = LiveBot(spec, decks, seed, team, delay)
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


def bot_answer_command(game: Game, answer: tuple, team: int = BOT) -> tuple[DeployCommand | None, str]:
    """Revalidate v2's timestamp and card identity on the current real battle."""
    slot, x, y, raw = answer[:4]
    if slot < 0:
        return None, raw
    command = DeployCommand(team, slot, x, y)
    if len(answer) > 4:
        source_tick, card_id = answer[4:]
        state = game.state
        player = state.players[team]
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
        self.t0 = time.time()
        self.started_at = time.monotonic()
        self.last_mask_at = -math.inf
        self.closed = False
        # share the machine's cores between the games in progress
        worker_spec = self.bot_spec
        if spec is None and worker_spec.get("type") == "planner" and worker_spec.get("workers"):
            worker_spec = {**worker_spec, "workers": max(2, PLANNER_WORKERS // (len(ACTIVE) + 1))}
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
        self.starting = True  # the clock has not started: waiting for the bot to be ready
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
            "t": "s", "k": s.tick, "left": round(left, 2), "ot": ot, "rate": s.elixir_rate,
            "starting": self.starting,
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

    async def _wait_for_bot(self) -> None:
        """Hold the clock at tick 0 until the bot worker reports ready (it warms its search pool first)."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + BOT_READY_TIMEOUT_SECONDS
        while self.bot_busy and loop.time() < deadline:
            if time.monotonic() - self.started_at >= MAX_SESSION_SECONDS:
                return  # the clock loop reports the expiry
            if self.conn.poll():
                self.conn.recv()  # the worker's "ready"
                self.bot_busy = False
            elif not self.proc.is_alive():
                raise RuntimeError("bot worker exited")
            else:
                await asyncio.sleep(0.02)
        if self.bot_busy:
            log.warning("bot not ready after %.0f s; starting the clock anyway", BOT_READY_TIMEOUT_SECONDS)

    async def _run(self) -> None:
        g = self.game
        e = g.engine
        loop = asyncio.get_running_loop()
        tick_s = g.state.tick_ms / 1000
        await self.send(self.init_msg())
        await self.send(self.snapshot())
        await self._wait_for_bot()
        self.starting = False
        due = loop.time()
        while not g.over:
            if time.monotonic() - self.started_at >= MAX_SESSION_SECONDS:
                await self.send({"t": "error", "message": "Game expired. Please start a new game."})
                return
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
            if not g.over and not self.bot_busy and tick - self.bot_asked_tick >= BOT_EVERY_TICKS:
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
        # Stop new bot work now, but let run()'s finally wait for its processes only after
        # the saved result reaches the browser. Planner cleanup can take up to 15 seconds.
        self.shutdown.set()
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
        self.proc.join(timeout=BOT_EXIT_SECONDS)
        if self.proc.is_alive():
            self.proc.terminate()
            self.proc.join(timeout=0.5)
        self.conn.close()


class LiveHogChallenge:
    """Real-time Share Play variant of the packaged one-HP Tactics position."""

    def __init__(self, cfg: dict, record: bool = True):
        scenario = cfg["scenario"]
        enemy = ["HogRider", *cfg["opponent_deck"][:7]]
        live_cfg = dict(cfg, opponent_deck=enemy, scenario=dict(
            scenario, opponent_order=enemy, opponent_elixir=4, units=[],
            start_tick=scenario["start_tick"] - HOG_PRELUDE_TICKS))
        self.game = Game(cfg["agent_deck"], enemy, cfg["seed"], record=record,
                         command_delay_ticks=0, setup=setup_for(live_cfg))
        self.start_tick = self.game.state.tick
        self.hog_tick = scenario["start_tick"]
        self.hog_id = next(c.card_id for c in self.game.cards if c.name == "HogRider")
        self.initial_hp = list(self.game.state.players[HUMAN].tower_hp)
        self.budget = scenario["spend_budget"]
        self.spent = 0
        self.hog_seen = False
        self.outcome: str | None = None

    @property
    def damage(self) -> int:
        return sum(max(0, before - after) for before, after in
                   zip(self.initial_hp, self.game.state.players[HUMAN].tower_hp))

    @property
    def success(self) -> bool:
        return (self.outcome == "hog" and self.damage == 0 and self.spent <= self.budget and
                all(hp > 0 for hp in self.game.state.players[HUMAN].tower_hp))

    def step(self, player_commands: list[DeployCommand] | None = None):
        if self.outcome is not None:
            raise ValueError("The challenge is finished")
        g = self.game
        tick = g.state.tick
        commands = list(player_commands or [])
        if tick == self.hog_tick:
            commands.append(DeployCommand(BOT, 0, round(2.5 * g.sub), round(18.5 * g.sub)))
        results = g.engine.step(commands, 1)
        if g.recorder:
            g.recorder.record_step(tick, 1, commands, results)
            g.recorder.record_frame(g.engine)
        for result in results:
            if result.team == BOT and result.card_id == self.hog_id:
                if result.status != DeployStatus.OK:
                    raise RuntimeError(f"Scripted Hog placement rejected: {result.status}")
            if result.team == HUMAN and result.status == DeployStatus.OK:
                self.spent += g.card_by_id[result.card_id].elixir
        state = g.state
        hog_alive = any(e.team == BOT and e.card_id == self.hog_id and e.hp > 0 for e in state.entities)
        self.hog_seen |= hog_alive
        if state.players[HUMAN].tower_hp[1] <= 0:
            self.outcome = "tower"
        elif self.hog_seen and not hog_alive:
            self.outcome = "hog"
        elif state.game_over:
            self.outcome = "match"
        return results


class BenchmarkSession(Session):
    """A live, event-ended Hog challenge using the same hand, tower HP and three-elixir budget."""

    def __init__(self, ws: WebSocket, cfg: dict, player_id: str, player_name: str | None):
        self.ws = ws
        self.challenge = LiveHogChallenge(cfg)
        self.game = self.challenge.game
        self.match_id = uuid.uuid4().hex
        self.player_id = player_id
        self.player_name = guest_name(player_id) if player_name is None else player_name
        self.bot_spec = {"name": "Hog Rider"}
        self.deck_names = ("Benchmark defense", "Scenario Hog")
        self.decks = self.game.decks
        self.seed = cfg["seed"]
        self.delay = 0
        self.sub = self.game.sub
        self.placement = PlacementOracle(self.game.arena, self.game.engine.rules(), self.game.cards)
        self.mask_cache = {}
        self.last_mask_at = -math.inf
        self.started_at = time.monotonic()
        self.closed = False
        self.starting = False
        self.cmds: deque[DeployCommand] = deque()
        ACTIVE.add(self)

    def init_msg(self) -> dict:
        return dict(super().init_msg(), mode="benchmark")

    def snapshot(self) -> dict:
        result = super().snapshot()
        challenge = self.challenge
        state = self.game.state
        # Regeneration still powers the engine, but the player has a fixed three-elixir
        # allowance. Show only what can actually be spent in this challenge.
        result["me"]["e"] = min(result["me"]["e"],
                                max(0, challenge.budget - challenge.spent) * 1000)
        incoming = state.tick < challenge.hog_tick
        result["left"] = round((challenge.hog_tick - state.tick if incoming else state.tick - challenge.hog_tick)
                               * state.tick_ms / 1000, 2)
        result["ot"] = False
        hog = next((e for e in state.entities if e.team == BOT and e.card_id == challenge.hog_id and e.hp > 0), None)
        result["benchmark"] = {"phase": "incoming" if incoming else "defending", "hog_hp": hog.hp if hog else None,
                               "spent": challenge.spent, "budget": challenge.budget}
        return result

    def on_message(self, m: dict) -> dict | None:
        if m.get("t") == "play":
            slot = m.get("slot")
            if type(slot) is int and 0 <= slot < 4:
                hand = self.game.state.players[HUMAN].hand
                reserved = sum(self.game.card_by_id[hand[c.hand_slot]].elixir for c in self.cmds)
                cost = self.game.card_by_id[hand[slot]].elixir
                if self.challenge.spent + reserved + cost > self.challenge.budget:
                    raise ValueError("Only 3 elixir may be spent in this challenge.")
        return super().on_message(m)

    async def _run(self) -> None:
        await self.send(self.init_msg())
        await self.send(self.snapshot())
        loop = asyncio.get_running_loop()
        due = loop.time()
        tick_s = self.game.state.tick_ms / 1000
        while self.challenge.outcome is None:
            if time.monotonic() - self.started_at >= MAX_SESSION_SECONDS:
                await self.send({"t": "error", "message": "Challenge expired. Please start again."})
                return
            tick = self.game.state.tick
            commands = [self.cmds.popleft()] if self.cmds else []
            for result in self.challenge.step(commands):
                ok = result.status == DeployStatus.OK
                await self.send(self.event(result.team, result.card_id, ok, result.status,
                                           (round(result.x / self.sub, 2), round(result.y / self.sub, 2)), tick))
            await self.send(self.snapshot())
            due += tick_s
            if due - loop.time() < -0.25:
                due = loop.time()
            await asyncio.sleep(max(0, due - loop.time()))
        await self.send({"t": "over", "mode": "benchmark", **await asyncio.to_thread(self.save)})

    def save(self) -> dict:
        challenge = self.challenge
        _, crowns, _, _, trace = self.game.finish()
        result = {"success": challenge.success, "outcome": challenge.outcome, "crowns": crowns,
                  "tower_damage": challenge.damage, "spent": challenge.spent, "budget": challenge.budget,
                  "saved": None}
        try:
            if trace is not None:
                folder = OUT_DIR / "replays"
                folder.mkdir(parents=True, exist_ok=True)
                name = f"benchmark-hog-{self.match_id}.msgpack"
                save_trace(trace, folder / name)
                result["saved"] = name
        except Exception:
            log.exception("could not save benchmark replay")
        return result

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        ACTIVE.discard(self)


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


@lru_cache(maxsize=1)
def benchmark_resolution_html() -> str:
    """Replay a successful three-elixir policy in the live Share Play variant."""
    from .replay import patched_html

    cfg = json.loads(BENCHMARK_TASK.read_text())
    challenge = LiveHogChallenge(cfg)
    game = challenge.game
    decisions = []
    while challenge.outcome is None:
        tick = game.state.tick
        commands = []
        if tick == challenge.hog_tick:
            decisions.append({"team": BOT, "tick": tick, "label": "Hog Rider enters",
                              "steps": [{"kind": "action", "title": "Scripted attack",
                                         "text": "Hog Rider at (2.5, 18.5)"}]})
        if tick - challenge.hog_tick in HOG_REFERENCE:
            slot, x, y = HOG_REFERENCE[tick - challenge.hog_tick]
            card = game.card_name(game.state.players[HUMAN].hand[slot])
            commands.append(DeployCommand(HUMAN, slot, round(x * game.sub), round(y * game.sub)))
            decisions.append({"team": HUMAN, "tick": tick, "label": f"Play {card}",
                              "steps": [{"kind": "action", "title": f"{(tick - challenge.hog_tick) / 20:.1f} s after Hog placement",
                                         "text": f"{card} at ({x}, {y})"}]})
        results = challenge.step(commands)
        if any(r.team == HUMAN and r.status != DeployStatus.OK for r in results):
            raise RuntimeError("Live Hog reference placement was rejected")
        if tick - challenge.start_tick > 1200:
            raise RuntimeError("Live Hog reference did not finish")
    if not challenge.success or challenge.spent != challenge.budget:
        raise RuntimeError("Live Hog reference did not clear the challenge")
    _, _, _, _, trace = game.finish()
    with tempfile.TemporaryDirectory(prefix="royalebench-resolution-") as folder:
        path = Path(folder) / "reference.msgpack"
        save_trace(trace, path)
        return patched_html(path, title="RoyaleBench · Live Hog defense resolution", decisions=decisions,
                            decisions_note="Live Share Play challenge based on Tactics @5. The Hog enters after "
                                           "a half-second prelude; play continues until the Hog or tower falls.",
                            scenario_result="Challenge cleared: Hog defeated, zero tower damage, "
                                            "three elixir spent, left tower survives at 1 HP.")


async def benchmark_resolution(_request) -> HTMLResponse:
    return HTMLResponse(await asyncio.to_thread(benchmark_resolution_html), headers={"Cache-Control": "no-store"})


async def socket(ws: WebSocket) -> None:
    await ws.accept()
    player_id = player_identity(ws)
    session: Session | BenchmarkSession | None = None
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
        challenge = ws.app.state.benchmark
        await ws.send_json({"t": "hello", "decks": CLASSIC_DECKS, "bots": specs, "max_games": MAX_GAMES,
                            "fixed_opponent": fixed,
                            "benchmark": {"title": challenge["title"], "objective": challenge["objective"],
                                          "prompt": "A Hog Rider enters shortly after the clock starts. "
                                                    "Your left tower has 1 HP. Stop the Hog before it lands a hit, "
                                                    "using at most 3 elixir. The game ends when the Hog or tower falls.",
                                          "deck": challenge["agent_deck"],
                                          "budget": challenge["scenario"]["spend_budget"]}})
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
                benchmark = m.get("mode") == "benchmark"
                try:
                    ranked = m.get("ranked", True) if not benchmark else False
                    if type(ranked) is not bool:
                        raise ValueError("ranked must be true or false.")
                    name = validate_player_name(m.get("player_name")) if ranked or m.get("player_name") else None
                except ValueError as exc:
                    await ws.send_json({"t": "invalid", "message": str(exc)})
                    continue
                if not benchmark:
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
                    session = (BenchmarkSession(ws, ws.app.state.benchmark, player_id, name) if benchmark else
                               Session(ws, mine, theirs, seed, bot, spec=specs[bot] if fixed else None,
                                       leaderboard=ws.app.state.leaderboard, player_id=player_id, player_name=name,
                                       ranked=ranked))
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
                            Route("/benchmark/resolution", benchmark_resolution),
                            WebSocketRoute("/ws", socket)],
                    lifespan=lifespan)
    app.state.leaderboard = Leaderboard(leaderboard_path or Path(os.getenv("CR_ARENA_LEADERBOARD", OUT_DIR / "leaderboard.csv")))
    app.state.bot_specs = {PUBLIC_BOT: {**BOT_SPECS[PUBLIC_BOT], "workers": PUBLIC_PLANNER_WORKERS}} if public else BOT_SPECS
    app.state.fixed_opponent = {"bot": PUBLIC_BOT, "deck": PUBLIC_DECK} if public else None
    app.state.benchmark = json.loads(BENCHMARK_TASK.read_text())
    return app


app = create_app()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8600)
    ap.add_argument("--public", action="store_true", help="play Planner with its fixed Hog Cycle deck (seven games)")
    a = ap.parse_args()
    print(f"Live play: http://{a.host}:{a.port}")
    uvicorn.run(create_app(public=a.public), host=a.host, port=a.port, log_level="warning",
                workers=1, ws_max_size=4096, ws_max_queue=8)


if __name__ == "__main__":
    main()
