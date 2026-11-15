"""Deterministic, budgeted root search on the benchmark's numbered moves.

Omniscient, zero-delay benchmark adapter only. Uses the frozen v1 evaluator so
allocation/policy/horizon changes can be measured without changing its weights.
No policy uses SeatMemory or mutable RNG state across branches.
"""
from __future__ import annotations

import hashlib
import math
import random
import time
from collections import defaultdict

from ..game import Game
from ..player_types import Decision, Player
from .baselines import HeuristicBot
from .search import SearchBot, evaluate

POLICIES = {"aggressive": 5.0, "defensive": 8.0, "patient": 9.5, "legacy": 8.0}



class SearchV2(Player):
    def __init__(self, name="search-v2", *, budget_ticks=60000, max_rollouts=240,
                 screen_horizon_s=6.0, horizon_s=24.0, shortlist_size=10,
                 max_candidates=64, opponent_mix=("aggressive", "defensive", "patient"),
                 seed=0, workers=1, information_mode="omniscient", continuation_policy="defensive"):
        if workers != 1:
            raise ValueError("search-v2 currently supports workers=1 only")
        if information_mode != "omniscient":
            raise ValueError("search-v2 currently requires information_mode=omniscient")
        for key, value in (("budget_ticks", budget_ticks), ("max_rollouts", max_rollouts),
                           ("max_candidates", max_candidates), ("shortlist_size", shortlist_size)):
            if type(value) is not int or value < 1:
                raise ValueError(f"{key} must be a positive integer")
        if not (math.isfinite(screen_horizon_s) and math.isfinite(horizon_s)
                and 0 < screen_horizon_s <= horizon_s):
            raise ValueError("require finite 0 < screen_horizon_s <= horizon_s")
        if not opponent_mix or any(p not in POLICIES for p in opponent_mix):
            raise ValueError(f"opponent_mix must contain policies from {tuple(POLICIES)}")
        if shortlist_size < 2 or max_candidates < shortlist_size:
            raise ValueError("require 2 <= shortlist_size <= max_candidates")
        if continuation_policy not in POLICIES:
            raise ValueError("unknown continuation_policy")
        self.continuation_policy = continuation_policy
        self.name, self.seed = name, seed
        self.budget_ticks, self.max_rollouts = budget_ticks, max_rollouts
        self.screen_horizon_s, self.horizon_s = screen_horizon_s, horizon_s
        self.shortlist_size, self.max_candidates = shortlist_size, max_candidates
        self.opponent_mix = tuple(opponent_mix)
        self.policies = {p: HeuristicBot(p, attack_elixir=v) for p, v in POLICIES.items()}
        self.sim = None
        self.last_search = {}

    def start(self, game, team):
        if game.command_delay_ticks:
            raise ValueError("search-v2 benchmark mode requires zero command delay")
        self._initialize(game)

    def _initialize(self, game, *, game_class=Game, command_delay_ticks=0):
        self.sim = game_class(*game.decks, seed=game.seed, decision_ticks=game.decision_ticks,
                              record=False, command_delay_ticks=command_delay_ticks)
        self.screen_ticks = max(1, int(self.screen_horizon_s * 1000 / game.state.tick_ms))
        self.horizon_ticks = max(1, int(self.horizon_s * 1000 / game.state.tick_ms))
        n = len(self.opponent_mix)
        # Reserve enough work for screening and a complete long-horizon mixture.
        if (self.max_rollouts < (self.max_candidates + self.shortlist_size) * n
                or self.budget_ticks < n * (self.max_candidates * self.screen_ticks
                                            + self.shortlist_size * self.horizon_ticks)):
            raise ValueError("budget must cover screening max_candidates and one complete shortlist round")

    def _search_more(self):
        # Live adapters may stop after a completed comparison round.
        return True

    @staticmethod
    def _key(m):
        return (m.slot, m.x, m.y)

    def _policy(self, game, team, policy, rng):
        moves = game.legal_moves(team)
        if policy == "legacy":
            r = rng.random()
            if r >= 0.85 and len(moves) > 1:
                return rng.choice(moves[1:])
            if r >= 0.6:
                return moves[0]
            return moves[self.policies["legacy"].decide(game, team, "", moves).index]
        # Small seeded variation changes the continuation without random spell waste.
        threshold = POLICIES[policy]
        if rng.random() < 0.12:
            threshold = max(4.0, threshold - 2)
        bot = self.policies[policy] if threshold == POLICIES[policy] else HeuristicBot(attack_elixir=threshold)
        return moves[bot.decide(game, team, "", moves).index]

    def _rollout(self, root, team, move, policy, seed, horizon):
        game = self.sim
        game.engine.load_state(root)
        # Independent streams: our policy's choices cannot shift the enemy's draws.
        own_rng, enemy_rng = random.Random(seed), random.Random(seed ^ 0x5A17)
        start_tick = game.state.tick
        elapsed = 0
        first = True
        while elapsed < horizon and not game.over:
            a = move if first else self._policy(game, team, self.continuation_policy, own_rng)
            b = self._policy(game, 1 - team, policy, enemy_rng)
            # Both actions have been selected before either is applied.
            dt = min(game.decision_ticks, horizon - elapsed)
            game.engine.step(SearchBot._cmds((team, a), (1 - team, b)), dt)
            elapsed = game.state.tick - start_tick
            first = False
        return evaluate(game, team), elapsed

    def _reservations(self, game, team, candidates, scores):
        """Bounded reservations, priority: wait, urgent defense, air, spell, cards.

        At most shortlist_size-1 are protected, leaving one competitive slot.
        Best screened placement of a card is used; these are never forced plays.
        """
        reasons = {candidates[0].index: "wait"}
        ranked = sorted(candidates, key=lambda m: (-scores[m.index], self._key(m)))
        threats = [e for e in game.state.entities if e.team != team and e.kind in (0, 1)
                   and e.hp > 0 and game.own_tiles(team, e.x, e.y)[1] < 18]
        limit = self.shortlist_size - 1

        def reserve(items, reason):
            if len(reasons) < limit:
                m = next((m for m in items if m.index not in reasons), None)
                if m is not None:
                    reasons[m.index] = reason

        if threats:
            urgent = min(threats, key=lambda e: game.own_tiles(team, e.x, e.y)[1])
            lane = game.lane_of(game.own_tiles(team, urgent.x, urgent.y)[0])
            reserve([m for m in ranked if m.kind in ("TROOP", "BUILDING")
                     and m.target in (f"in front of {lane} tower", "center (between towers)")], "tower-threat")
        if any(e.flying for e in threats):
            # CardInfo has no attack-target field in the locked engine; flying troops
            # and known ranged defenders are conservative candidates, not proof of a counter.
            reserve([m for m in ranked if m.card in ("Musketeer", "Archer", "MegaMinion", "Minions",
                                                    "Wizard", "BabyDragon", "Tesla", "InfernoTower")], "air-response")
        spell = [m for m in ranked if m.kind == "SPELL" and m.target.startswith("on enemy")]
        reserve(spell, "unit-spell")
        for card in sorted({m.card for m in candidates if m.slot >= 0}):
            if any(m.card == card and m.index in reasons for m in candidates):
                continue
            reserve([m for m in ranked if m.card == card], "card-diversity")
        return reasons

    def decide(self, game, team, text, moves):
        t0 = time.perf_counter()
        if self.sim is None:
            self.start(game, team)
        root = game.engine.save_state()
        # A decision identifier derived solely from the configured seed and root state.
        digest = hashlib.sha256(str(self.seed).encode() + root).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big"))
        unique = {self._key(m): m for m in reversed(moves)}
        candidates = sorted(unique.values(), key=self._key)
        # Deterministic round-robin cap across cards/slots, retaining wait.
        groups = defaultdict(list)
        for m in candidates:
            groups[m.slot].append(m)
        capped = []
        while groups and len(capped) < self.max_candidates:
            for slot in sorted(list(groups)):
                if len(capped) == self.max_candidates:
                    break
                capped.append(groups[slot].pop(0))
                if not groups[slot]:
                    del groups[slot]
        candidates = sorted(capped, key=self._key)
        used_ticks = rolls = 0
        scenarios = []
        screen, samples = defaultdict(list), defaultdict(list)
        policy_scores = defaultdict(lambda: defaultdict(list))
        active = candidates

        def round_(items, horizon, destination, phase):
            nonlocal used_ticks, rolls
            n = len(items) * len(self.opponent_mix)
            if rolls + n > self.max_rollouts or used_ticks + n * horizon > self.budget_ticks:
                return False
            schedule = [(p, rng.randrange(1 << 63)) for p in self.opponent_mix]
            scenarios.append({"phase": phase, "horizon_ticks": horizon, "scenarios": schedule,
                              "candidates": [m.index for m in items]})
            for m in items:
                for policy, seed in schedule:
                    score, ticks = self._rollout(root, team, m, policy, seed, horizon)
                    destination[m.index].append(score)
                    if phase != "screen":
                        policy_scores[m.index][policy].append(score)
                    used_ticks += ticks
                    rolls += 1
            return True

        if not round_(candidates, self.screen_ticks, screen, "screen"):
            raise RuntimeError("minimum screening round does not fit validated budget")
        means = {m.index: sum(screen[m.index]) / len(screen[m.index]) for m in candidates}
        reasons = self._reservations(game, team, candidates, means)
        active = [m for m in candidates if m.index in reasons]
        ranked = sorted(candidates, key=lambda m: (-means[m.index], self._key(m)))
        active += [m for m in ranked if m.index not in reasons][:self.shortlist_size - len(active)]
        active.sort(key=self._key)
        if not round_(active, self.horizon_ticks, samples, "full"):
            raise RuntimeError("minimum full round does not fit validated budget")

        def mean(m):
            return sum(samples[m.index]) / len(samples[m.index])

        while self._search_more():
            ranked = sorted(active, key=lambda m: (-mean(m), self._key(m)))
            target = max(len(reasons) + 1, math.ceil(len(active) / 2))
            survivors = [m for m in active if m.index in reasons]
            survivors += [m for m in ranked if m.index not in reasons][:target - len(survivors)]
            survivors.sort(key=self._key)
            # Only publish an elimination if the next matched round fits.
            if not round_(survivors, self.horizon_ticks, samples, "full"):
                break
            active = survivors
        best = min(active, key=lambda m: (-mean(m), self._key(m)))
        latency = time.perf_counter() - t0
        self.last_search = {
            "source_tick": game.state.tick, "information_mode": "omniscient", "action_mode": "numbered",
            "evaluator": "search-v1", "continuation_policy": self.continuation_policy, "selected": best.index, "legal_candidates": len(moves),
            "unique_candidates": len(unique), "searched_candidates": len(candidates),
            "reservations": reasons, "scenarios": scenarios, "rollouts": rolls, "simulated_ticks": used_ticks,
            "budget_ticks": self.budget_ticks, "max_rollouts": self.max_rollouts,
            "budget_exhausted": True, "latency_s": latency,
            "wait_score": mean(candidates[0]),
            "candidates": [{"index": m.index, "label": m.label(), "screen_mean": means[m.index],
                            "samples": len(samples[m.index]),
                            "mean": mean(m) if samples[m.index] else None,
                            "worst": min(samples[m.index]) if samples[m.index] else None,
                            "per_policy": {p: sum(v) / len(v) for p, v in policy_scores[m.index].items()}}
                           for m in candidates],
        }
        raw = (f"search-v2: {best.label()} = {mean(best):.0f}; wait = {mean(candidates[0]):.0f}; "
               f"{rolls} rollouts, {used_ticks} ticks")
        return Decision(best.index, raw=raw, diagnostics=self.last_search, latency_s=latency)
