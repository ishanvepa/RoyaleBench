"""Opt-in coordinate protocol. Frozen menu task snapshots are deliberately unchanged."""
from __future__ import annotations

import json
import math
import os
import time

from royalegym.protocol import DeployCommand, DeployStatus

from .game import Move
from .royale_task import LogMismatch
from .scenario_task import ScenarioReferee
from .telemetry import digest

MODE = "coordinates-v1"


def action_schema(action: dict) -> dict:
    """Malformed requests do not advance; well-formed illegal plays do."""
    if not isinstance(action, dict):
        raise ValueError("action must be an object")
    if action == {"cmd": "wait"}:
        return dict(action)
    if set(action) != {"cmd", "slot", "x", "y"} or action.get("cmd") != "play":
        raise ValueError("use cr play SLOT X Y or cr wait; cr act is unavailable in coordinate mode")
    if type(action["slot"]) is not int:
        raise ValueError("slot must be an integer (0-3)")
    for key in ("x", "y"):
        if type(action[key]) not in (int, float) or not math.isfinite(action[key]):
            raise ValueError("coordinates must be finite numbers")
    return dict(action)


class CoordinateReferee(ScenarioReferee):
    def __init__(self, cfg, record=False):
        self.rejected_actions = 0
        super().__init__(cfg, record=record)

    def _advance(self):
        # No numbered-menu filtering or placement oracle drives coordinate decisions.
        # Only explicit scenario action restrictions trigger automatic waits.
        s = self.scenario
        forced = self.decision >= s.get("max_decisions", 10000) or (s.get("only_card") and self.plays)
        self.moves = None if self.over or forced else []
        if forced:
            while not self.over:
                self._step(Move(0, -1, "wait", "WAIT", 0, "-", "-"))

    def prepare_action(self, action):
        if self.over:
            raise ValueError("the scenario is over")
        action = action_schema(action)
        wait = Move(0, -1, "wait", "WAIT", 0, "-", "-")
        metadata = dict(accepted=True, rejection=None, deployment=None, application_tick=self.tick)
        if action["cmd"] == "wait":
            return wait, metadata
        g, slot = self.game, action["slot"]
        x, y = action["x"], action["y"]
        reason = None
        if not 0 <= slot < len(g.state.players[0].hand):
            reason = "INVALID_SLOT"
        elif not (0 <= x < g.arena.tiles_x and 0 <= y < g.arena.tiles_y):
            reason = "OUT_OF_ARENA"
        else:
            card = g.card_by_id.get(g.state.players[0].hand[slot])
            if card is None:
                reason = "EMPTY_SLOT"
            elif self.scenario.get("only_card") and card.name != self.scenario["only_card"]:
                reason = "SCENARIO_CARD_UNAVAILABLE"
            else:
                ex, ey = g.engine_point(0, x, y)  # engine precision only; no placement snapping
                status = g.engine.check_deploy(DeployCommand(0, slot, ex, ey))
                if status != DeployStatus.OK:
                    reason = DeployStatus(status).name
                else:
                    p = g.state.players[0]
                    cost = p.hand_costs[slot] if len(p.hand_costs) == len(p.hand) else card.elixir
                    metadata["deployment"] = dict(team=0, slot=slot, x=ex, y=ey)
                    return Move(-1, slot, card.name, g.kind_of(card), cost,
                                f"({x}, {y})", g.lane_of(x), ex, ey), metadata
        metadata.update(accepted=False, rejection=reason)
        return wait, metadata

    def entry(self, action, think_s):
        _, metadata = self.prepare_action(action)
        return dict(decision=self.decision, tick=self.tick, action=action_schema(action),
                    action_hash=digest(action), think_s=think_s, state_hash=digest(self.game.state), **metadata)

    def act_action(self, action):
        move, metadata = self.prepare_action(action)
        self.game.consume_events(0)
        if self.capture:
            self.capture.emit("events", dict(event="coordinate_attempt", action=action,
                              decision_id=f"0:{self.tick}", tick=self.tick, **metadata))
        source = self.action_source
        if not metadata["accepted"]:
            self.action_source = "rejected_action"
        try:
            result = self._step(move)
        finally:
            self.action_source = source
        self.decision += 1
        if not metadata["accepted"]:
            self.rejected_actions += 1
            result = f"rejected ({metadata['rejection']}); waited for this interval"
        self._advance()
        return result

    def act(self, index):
        # Shared verifier uses act(0) to finish missing decisions as waits.
        if index != 0:
            raise ValueError("numbered actions are unavailable in coordinate mode")
        return self.act_action({"cmd": "wait"})

    def observation(self):
        if self.over:
            return self.final_text()
        g = self.game
        slots = ", ".join(f"{i}: {g.card_name(cid)}" for i, cid in enumerate(g.state.players[0].hand))
        return (f"DECISION {self.decision + 1} (you are BLUE) | action mode: {MODE}\n"
                + g.describe(0, None) + f"\nHAND SLOTS (zero-based): {slots}\n"
                + f"SCENARIO: {self.cfg['title']} | elapsed {(self.tick-self.start_tick)/20:.1f}s / "
                  f"{self.scenario['horizon_s']}s | spent {self.spent} elixir\n"
                + "Visible pre-scenario history: " + ("; ".join(self.scenario.get("visible_history", [])) or "none")
                + f"\nObjective: {self.cfg['objective']}\n"
                + "Play: cr play SLOT X Y (own-frame tiles); cr wait. No automatic placement snapping.")

    def success(self):
        s = self.scenario
        right = sum(p["cost"] for p in self.plays if p["x"] / self.game.sub > 10.5)
        return bool(super().success() and self.spent <= s.get("spend_budget", math.inf)
                    and right <= s.get("right_lane_budget", math.inf))

    def outcome(self):
        return dict(super().outcome(), rejected_actions=self.rejected_actions)


def replay_coordinates(ref, entries):
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict) or any(type(entry.get(k)) is not int for k in ("decision", "tick")):
            raise LogMismatch(f"entry {i}: decision/tick must be integers")
        think = entry.get("think_s")
        if think is not None and (type(think) not in (int, float) or not math.isfinite(think) or think < 0):
            raise LogMismatch(f"entry {i}: invalid think_s")
        expected = ref.entry(entry["action"], think)
        for key, value in expected.items():
            if key not in entry or type(entry[key]) is not type(value) or digest(entry[key]) != digest(value):
                raise LogMismatch(f"entry {i}: {key} differs from replay")
        ref.act_action(entry["action"])
    return len(entries)


def handle_command(server, request):
    ref = server.ref
    try:
        think = (round((time.monotonic_ns() - server.first_shown_ns) / 1e9, 6)
                 if server.first_shown_ns is not None else None)
        entry = ref.entry(request, think)
    except (ValueError, TypeError, OverflowError) as exc:
        server.capture.emit("events", {"event": "invalid_command", "tick": ref.tick,
                                      "error": str(exc), "request": request})
        return {"ok": False, "over": ref.over, "text": f"Not submitted: {exc}. No game time elapsed."}
    entry.update(wall=round(time.time(), 3), segment_id=server.capture.segment,
                 observation_id=getattr(server, "observation_id", None))
    with server.log_path.open("a") as stream:
        stream.write(json.dumps(entry, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    result = ref.act_action(request)
    server.first_shown_ns = None
    response = server.response(f"Your move: {result}\n\n{ref.observation()}")
    response["accepted"] = entry["accepted"]
    return response
