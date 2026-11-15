"""Mid-match continuation protocol shared by the server, calibration and replay grader."""
from __future__ import annotations

import hashlib
import json

from royalegym import RustEngine, deck_ids
from royalegym.protocol import MatchSetup, ShuffleMode, SpawnSpec

from .bots.planner import Planner
from .game import Game, Move
from .royale_task import Referee


def setup_for(cfg: dict) -> MatchSetup:
    """Use public engine setup APIs; never patch the private engine save format."""
    cards = list(RustEngine().cards())
    ids = {c.name: c.card_id for c in cards}
    s = cfg["scenario"]
    sub = RustEngine().arena().subtile
    # Scenarios use blue's view; the data explicitly records this fixed seat.
    assert cfg["agent_team"] == 0
    return MatchSetup(
        decks=[deck_ids(s["order"], cards), deck_ids(s["opponent_order"], cards)],
        shuffle=ShuffleMode.NONE, start_tick=s["start_tick"],
        elixir_milli=[s["elixir"] * 1000, s["opponent_elixir"] * 1000],
        tower_hp=s["tower_hp"],
        spawns=[SpawnSpec(team=u["team"], card_id=ids[u["card"]],
                          x=round(u["x"] * sub), y=round(u["y"] * sub), hp=u.get("hp", -1))
                for u in s["units"]],
    )


class ScheduledPlanner(Planner):
    """The unmodified Planner search, with a disclosed reservation for task 5's attack."""
    reserved: str | None = None

    def candidates(self, team: int, compact: bool = False) -> list:
        plays = super().candidates(team, compact=compact)
        if team != self.team or not self.reserved:
            return plays
        p = self.g.state.players[team]
        reserved_id = next(c.card_id for c in self.g.cards if c.name == self.reserved)
        cost = self.g.card_by_id[reserved_id].elixir
        return [c for c in plays if p.hand[c[1]] != reserved_id and
                self.g.card_by_id[p.hand[c[1]]].elixir + cost <= p.elixir_milli / 1000]


class ScenarioReferee(Referee):
    def __init__(self, cfg: dict, record: bool = False):
        if cfg["opponent"] != "planner":
            raise ValueError("RoyaleBench v1 requires planner on every task")
        self.cfg, self.team, self.opp_team = cfg, 0, 1
        self.scenario = cfg["scenario"]
        self.game = Game(cfg["agent_deck"], cfg["opponent_deck"], cfg["seed"],
                         decision_ticks=cfg["decision_ticks"], record=record, setup=setup_for(cfg))
        self.setup_hash = hashlib.sha256(self.game.engine.save_state()).hexdigest()
        self.start_tick = self.tick
        self.end_tick = self.start_tick + round(self.scenario["horizon_s"] * 1000 / self.game.state.tick_ms)
        self.initial_hp = list(self.game.state.players[0].tower_hp)
        self.decision, self.spent, self.plays = 0, 0, []
        self.opponent_plays = []
        self.scheduled_done = False
        self.moves, self.history = None, []
        self.opponent = ScheduledPlanner(self.game.decks, cfg["seed"], 1, **cfg["planner"])
        self.game.mem[0].events.extend(self.scenario.get("visible_history", []))
        self._advance()

    @property
    def over(self) -> bool:
        return self.game.over or self.tick >= self.end_tick

    def legal_moves(self) -> list[Move]:
        s = self.scenario
        moves = self.game.legal_moves(0)
        budget = s.get("spend_budget", 1000) - self.spent
        moves = [m for m in moves if m.cost <= budget]
        if "right_lane_budget" in s:
            right_spent = sum(p["cost"] for p in self.plays if p["x"] / self.game.sub > 10.5)
            moves = [m for m in moves if m.x / self.game.sub <= 10.5 or
                     m.cost + right_spent <= s["right_lane_budget"]]
        if "only_card" in s:
            moves = [m for m in moves if m.slot < 0 or (m.card == s["only_card"] and not self.plays)]
        if self.decision >= s.get("max_decisions", 10000):
            moves = moves[:1]
        # Labels and indices must describe the *filtered* list, identically in the verifier.
        from dataclasses import replace
        return [replace(m, index=i) for i, m in enumerate(moves)]

    def _advance(self) -> None:
        while not self.over:
            moves = self.legal_moves()
            if len(moves) > 1:
                self.moves = moves
                return
            self.moves = None
            self._step(moves[0])
        self.moves = None

    def _opponent_move(self) -> Move:
        g = self.game
        schedule = self.scenario.get("scheduled_attack")
        self.opponent.reserved = schedule["card"] if schedule and not self.scheduled_done else None
        if schedule and not self.scheduled_done and self.tick >= self.start_tick + schedule["after_s"] * 20:
            card = next(c for c in g.cards if c.name == schedule["card"])
            p = g.state.players[1]
            if card.card_id not in p.hand or p.elixir_milli < card.elixir * 1000:
                raise RuntimeError("scheduled attack was not reserved")
            self.scheduled_done = True
            return Move(-1, p.hand.index(card.card_id), card.name, g.kind_of(card), card.elixir,
                        "disclosed scheduled attack", "left", round(schedule["x"] * g.sub), round(schedule["y"] * g.sub))
        play, _ = self.opponent.act(g.engine.save_state())
        if play is None:
            return Move(0, -1, "wait", "WAIT", 0, "-", "-")
        _, slot, x, y = play
        card = g.card_by_id[g.state.players[1].hand[slot]]
        return Move(-1, slot, card.name, g.kind_of(card), card.elixir, "Planner placement", "-", x, y)

    def _step(self, agent_move: Move) -> str:
        g = self.game
        tick = self.tick
        opp = self._opponent_move()  # both choose from the same frozen state
        if opp.slot >= 0:
            self.opponent_plays.append(dict(tick=self.tick, card=opp.card, x=opp.x, y=opp.y))
        g.decision_ticks = min(self.cfg["decision_ticks"], self.end_tick - self.tick)
        if self.capture:
            self.capture.snapshot(g, phase="pre_step", decision_id=f"0:{tick}")
        results = g.step([agent_move, opp])
        result = results[0]
        if self.capture:
            for team, move in enumerate((agent_move, opp)):
                source = ("forced_wait" if self.moves is None else self.action_source) if team == 0 else "opponent"
                self.capture.command(g, team, f"{team}:{tick}", move, kind="application", tick=tick,
                    end_tick=self.tick, action_source=source,
                    accepted=results[team] == "wait" or results[team].startswith("played"), result=results[team])
            self.capture.snapshot(g, phase="post_step")
        if agent_move.slot >= 0:
            if not result.startswith("played "):
                raise RuntimeError(f"legal scenario move refused: {result}")
            self.spent += agent_move.cost
            self.plays.append({"decision": self.decision, "card": agent_move.card,
                               "x": agent_move.x, "y": agent_move.y, "cost": agent_move.cost})
        return result

    def observation(self) -> str:
        body = super().observation()
        if self.over:
            return body
        history = self.scenario.get("visible_history", [])
        return (body + f"\n\nSCENARIO: {self.cfg['title']} | elapsed {(self.tick-self.start_tick)/20:.1f}s / "
                f"{self.scenario['horizon_s']}s | spent {self.spent} elixir\n"
                + "Visible pre-scenario history: " + ("; ".join(history) if history else "none")
                + "\nObjective: " + self.cfg["objective"])

    def outcome(self) -> dict:
        result = super().outcome()
        p = self.game.state.players[0]
        result.update(tower_damage=sum(max(0, a-b) for a, b in zip(self.initial_hp, p.tower_hp)),
                      spent_elixir=self.spent, plays=self.plays,
                      opponent_plays=self.opponent_plays,
                      elapsed_s=(self.tick-self.start_tick)/20)
        return result

    def success(self) -> bool:
        s, state = self.scenario, self.game.state
        me, enemy = state.players
        objective = s["grading"]
        damage = self.outcome()["tower_damage"]
        alive = all(me.tower_hp[i] > 0 for i in s.get("protect_slots", [1, 2]))
        if objective == "win":
            return bool(state.game_over and state.winner == 0)
        if objective == "first_decision_lethal":
            return bool(state.game_over and state.winner == 0 and self.plays and self.plays[0]["decision"] == 0)
        if objective == "protect_lead":
            return bool(me.crowns > enemy.crowns and (not state.game_over or state.winner == 0))
        if objective == "defend":
            return bool(alive and damage <= s["damage_limit"] and self.spent <= s["spend_budget"]
                        and (not state.game_over or state.winner == 0))
        if objective == "one_spell":
            return bool(alive and damage <= s["damage_limit"] and len(self.plays) == 1)
        raise ValueError(f"unknown grading rule {objective}")

    def final_text(self) -> str:
        o = self.outcome()
        return (f"GAME OVER: scenario {'SUCCESS' if self.success() else 'FAILURE'}. "
                f"Crowns: you {o['crowns_for']} - enemy {o['crowns_against']}; "
                f"tower damage {o['tower_damage']}; spent {self.spent} elixir. The scenario is finished.")
