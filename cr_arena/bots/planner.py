"""Planner bot: the strong reference player for live (real-time) play.

How it decides, several times a second:

1. CANDIDATES. Every card it can afford, at many exact spots: lanes, bridges, behind towers, and
   spots worked out from the enemy units on the board (on top of them, behind them, to the side);
   spells on every enemy unit, pair of units and tower. Not the short menu of named zones.
2. LOOK AHEAD. Each candidate is played on a private copy of the engine and the battle is run
   forward ~10 s. The engine is deterministic, so this is exact, not a noisy sample.
3. THE OPPONENT ANSWERS. For the best few candidates (and for waiting) the opponent's own
   candidates are tried as a reply, and the candidate is worth what is left after the reply that
   hurts most.
4. WE ANSWER BACK. Against the few replies that hurt most, its own candidates are tried as an answer
   once the reply has landed, so a push is not judged as if its counter could never be defended.
5. It plays the best candidate only if that beats waiting by a margin; otherwise it keeps its elixir.

The position score is in tower hit points: damage dealt minus damage taken, fallen towers, and
elixir (in the bank and standing on the board as units) converted at ELIXIR_HP per elixir.

Information: like search-bot v1 it reads the true engine state, so it knows the opponent's hand
and elixir when it works out their reply.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from multiprocessing import get_context

from royalegym.protocol import DeployCommand, DeployStatus, EntityKind

from ..game import Game

WIN = 1_000_000.0
ELIXIR_HP = 150.0  # what one elixir is worth, in tower hit points
UNIT_KEEP = 0.85  # a unit still standing at the end of the look-ahead is worth this share of its elixir
PRINCESS_BONUS, KING_WEIGHT = 2500.0, 0.4
_UNITS = (EntityKind.TROOP, EntityKind.BUILDING)
_TOWERS = (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER)

Play = tuple[int, int, int, int]  # team, hand slot, x, y (engine frame)


def _center(v: float) -> float:
    return min(17.5, max(0.5, int(v) + 0.5))


class Planner:
    def __init__(self, decks: list[list[str]], seed: int, team: int, delay: int = 0, horizon_s: float = 10.0,
                 top_k: int = 4, margin: float = 40.0, two_ply: bool = True, workers: int = 0,
                 elixir_hp: float = ELIXIR_HP, prefilter: bool = True, three_ply: bool = True, answer_k: int = 3):
        self.args = dict(decks=decks, seed=seed, team=team, delay=delay, horizon_s=horizon_s, top_k=top_k,
                         margin=margin, two_ply=two_ply, elixir_hp=elixir_hp, prefilter=prefilter,
                         three_ply=three_ply, answer_k=answer_k)
        # three_ply: after the opponent's reply we answer it, for the `answer_k` replies that hurt most.
        self.three_ply, self.answer_k = three_ply, answer_k
        # prefilter=True is the original rule: only plays that already beat waiting by `margin` without
        # any reply are checked against the opponent's reply. False checks a shortlist instead (see shortlist).
        self.prefilter = prefilter
        self.g = Game(decks[0], decks[1], seed=seed, record=False, command_delay_ticks=delay)
        self.e = self.g.engine
        self.team = team
        self.horizon = int(horizon_s * 1000 / self.g.state.tick_ms)
        self.react = delay + 10  # the opponent answers once the card has landed, plus half a second
        self.top_k, self.margin, self.two_ply, self.ev = top_k, margin, two_ply, elixir_hp
        self.pool = None
        if workers > 0:
            self.pool = ProcessPoolExecutor(workers, mp_context=get_context("spawn"), initializer=_pool_init,
                                            initargs=(self.args, os.getpid()))
            self.workers = workers

    def close(self) -> None:
        if self.pool:
            self.pool.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ position score
    def evaluate(self) -> float:
        """Score of the loaded position for self.team, in tower hit points."""
        g, team = self.g, self.team
        s = g.state
        if s.game_over and s.winner != 2:
            return WIN if s.winner == team else -WIN
        me, en = s.players[team], s.players[1 - team]
        left = (s.regular_ticks - s.tick if s.tick < s.regular_ticks else s.regular_ticks + s.overtime_ticks - s.tick)
        ev = self.ev * min(1.0, max(0.2, left * s.tick_ms / 1000 / 45.0))  # elixir is worth little when time is nearly up
        v = 0.0
        for side, sign in ((en, 1.0), (me, -1.0)):
            for i in range(3):
                mx = side.tower_max_hp[i]
                if not mx:
                    continue
                lost = (mx - max(0, side.tower_hp[i])) / mx
                dmg = lost * mx * (1.0 + 0.6 * lost)  # the same hit matters more on a tower that is nearly down
                if i == 0:
                    v += sign * (dmg * KING_WEIGHT if lost < 1 else WIN / 2)
                else:
                    v += sign * (dmg + (PRINCESS_BONUS if lost >= 1 else 0.0))
        v += ev * ((me.elixir_milli - en.elixir_milli) / 1000 - (me.pending_cost - en.pending_cost))
        for u in s.entities:
            if u.hp <= 0 or u.kind not in _UNITS or not u.max_hp:
                continue
            card = g.card_by_id.get(u.card_id)
            cost = card.elixir / max(1, card.count) if card else 0.4
            val = UNIT_KEEP * ev * cost * (u.hp / u.max_hp)
            v += val if u.team == team else -val
        return v

    # ------------------------------------------------------------------ candidates
    def candidates(self, team: int, compact: bool = False) -> list[Play]:
        """Plays worth trying for `team` in the loaded position."""
        g, e = self.g, self.e
        s = g.state
        if s.game_over:
            return []
        p = s.players[team]
        avail = p.elixir_milli - p.pending_cost * 1000
        waiting = {q[0] for q in p.pending}
        foes, towers = [], []
        for u in s.entities:
            if u.team == team or u.hp <= 0:
                continue
            tx, ty = g.own_tiles(team, u.x, u.y)
            if u.kind in _UNITS:
                foes.append((ty, tx))
            elif u.kind in _TOWERS:
                towers.append((tx, ty, u.kind))
        foes.sort()
        open_lanes = {3.5, 14.5} - {3.5 if tx < 9 else 14.5 for tx, _ty, k in towers if k == EntityKind.PRINCESS_TOWER}

        if compact:
            troop = [(3.5, 14.5), (14.5, 14.5), (8.5, 9.5), (3.5, 3.5), (14.5, 3.5)]
            build = [(8.5, 9.5), (7.5, 10.5), (9.5, 10.5)]
        else:
            troop = [(3.5, 14.5), (14.5, 14.5), (3.5, 9.5), (14.5, 9.5), (8.5, 9.5), (3.5, 3.5), (14.5, 3.5),
                     (8.5, 0.5), (0.5, 0.5), (17.5, 0.5)]
            build = [(8.5, 9.5), (7.5, 10.5), (9.5, 10.5), (5.5, 9.5), (11.5, 9.5), (8.5, 6.5), (3.5, 13.5), (14.5, 13.5)]
        for ty, tx in foes[: 3 if compact else 5]:  # the enemy units closest to our side
            if ty > 21:
                continue
            cy = min(ty, 14.5)
            troop += [(tx, cy), (tx, cy - 2.5), (tx - 2.5, cy - 1), (tx + 2.5, cy - 1)]
            if not compact:
                troop += [(tx, cy - 5), (8.5, cy - 3)]
        for lane in open_lanes:  # the pocket behind a fallen tower
            troop += [(lane, 19.5), (lane, 17.5)]
        spell = [(tx, ty) for tx, ty, _k in towers]
        near = foes[: 4 if compact else 7]
        for ty, tx in near:
            spell += [(tx, ty), (tx, ty - 1.5)]  # where it is, and a little ahead of it
            if not compact:
                spell.append((tx, ty - 4.0))  # for spells that roll forward from where they are dropped
        for (ay, ax), (by, bx) in list(combinations(near, 2))[:8]:
            if abs(ax - bx) < 4 and abs(ay - by) < 4:
                spell.append(((ax + bx) / 2, (ay + by) / 2 - 0.75))

        out: list[Play] = []
        for slot, cid in enumerate(p.hand):
            card = g.card_by_id.get(cid)
            if card is None or slot in waiting:
                continue
            cost = p.hand_costs[slot] if len(p.hand_costs) == len(p.hand) else card.elixir
            if cost < 0 or avail < cost * 1000:
                continue
            kind = g.kind_of(card)
            spots = spell if kind == "SPELL" else build if kind == "BUILDING" else troop
            seen = set()
            for tx, ty in spots:
                x, y = g.engine_point(team, _center(tx), min(31.5, max(0.5, int(ty) + 0.5)))
                if (x, y) in seen:
                    continue
                seen.add((x, y))
                if e.check_deploy(DeployCommand(team, slot, x, y)) == DeployStatus.OK:
                    out.append((team, slot, x, y))
        return out

    # ------------------------------------------------------------------ look-ahead
    def rollout(self, root: bytes, play: Play | None, horizon: int) -> float | None:
        """Play `play` (or nothing) in `root`, run `horizon` ticks, score. None if the play is refused."""
        e = self.e
        e.load_state(root)
        if play is not None:
            res = e.step([DeployCommand(*play)], 1)
            if not res or res[0].status != DeployStatus.OK:
                return None
            horizon -= 1
        if horizon > 0:
            e.step([], horizon)
        return self.evaluate()

    def after_reply(self, root: bytes, play: Play | None) -> float:
        """What `play` (None = wait) is worth once the opponent has made the reply that hurts most."""
        e = self.e
        e.load_state(root)
        e.step([DeployCommand(*play)] if play else [], 1)
        e.step([], self.react - 1)
        mid = e.save_state()
        rest = self.horizon - self.react
        replies = self.candidates(1 - self.team, compact=True)
        scored = [(self.rollout(mid, None, rest), None)]
        for r in replies:
            v = self.rollout(mid, r, rest)
            if v is not None:
                scored.append((v, r))
        if not self.three_ply:
            return min(v for v, _r in scored)
        # Third ply: against the replies that hurt most, we answer too. Every other reply keeps its
        # unanswered score, which is a lower bound on its answered one, so the result stays conservative.
        scored.sort(key=lambda t: t[0])
        answered = [self.answer(mid, r, rest) for _v, r in scored[: self.answer_k]]
        return min(answered + [v for v, _r in scored[self.answer_k:]])

    def answer(self, mid: bytes, reply: Play | None, rest: int) -> float:
        """Best we can do in `mid` after the opponent plays `reply` (None = waits) and we answer it."""
        e = self.e
        e.load_state(mid)
        e.step([DeployCommand(*reply)] if reply else [], 1)
        e.step([], self.react - 1)
        mid2 = e.save_state()
        rest -= self.react
        best = self.rollout(mid2, None, rest)
        for a in self.candidates(self.team, compact=True):
            v = self.rollout(mid2, a, rest)
            if v is not None and v > best:
                best = v
        return best

    def _map(self, fn: str, root: bytes, items: list) -> list:
        if not self.pool or len(items) < 4:
            return [getattr(self, fn)(root, it, self.horizon) if fn == "rollout" else getattr(self, fn)(root, it) for it in items]
        n = min(self.workers, len(items))
        chunks = [items[i::n] for i in range(n)]
        parts = list(self.pool.map(_pool_run, [(fn, root, c) for c in chunks]))
        out = [None] * len(items)
        for i, part in enumerate(parts):
            out[i::n] = part
        return out

    # ------------------------------------------------------------------ the decision
    def shortlist(self, scored: list[tuple[float, Play]]) -> list[tuple[float, Play]]:
        """Candidates that go on to face the opponent's reply: the best `top_k` by quiet score, plus the
        best spot of every other card in hand. None is dropped for failing to beat waiting yet: a
        defensive play (a building before a Hog arrives) is only worth something once the opponent
        moves, so judging it on the quiet rollout alone would throw it away before that is checked."""
        top = scored[: self.top_k]
        slots = {c[1] for _v, c in top}
        for v, c in scored[self.top_k:]:
            if c[1] not in slots:
                slots.add(c[1])
                top.append((v, c))
        return top

    def act(self, root: bytes) -> tuple[Play | None, str]:
        """The play to make now in `root` (None = wait), and a short note for the log."""
        g = self.g
        self.e.load_state(root)
        cands = self.candidates(self.team)
        if not cands:
            return None, ""
        t0 = time.perf_counter()
        quiet = self._map("rollout", root, [None] + cands)
        wait_q = quiet[0]
        scored = sorted(((v, c) for v, c in zip(quiet[1:], cands) if v is not None), key=lambda t: -t[0])
        if self.prefilter or not self.two_ply:
            top = [(v, c) for v, c in scored if v - wait_q > self.margin][: self.top_k]
        else:
            top = self.shortlist(scored)
        if not top:
            return None, f"wait (best alternative {scored[0][0] - wait_q:+.0f})" if scored else ""
        if self.two_ply:
            replied = self._map("after_reply", root, [None] + [c for _v, c in top])
            wait_v = min(wait_q, replied[0])
            final = sorted(((min(v, rv) - wait_v, c) for (v, c), rv in zip(top, replied[1:])), key=lambda t: -t[0])
        else:
            final = [(v - wait_q, c) for v, c in top]
        self.e.load_state(root)
        hand = g.state.players[self.team].hand

        def label(c: Play) -> str:
            tx, ty = g.own_tiles(self.team, c[2], c[3])
            return f"{g.card_name(hand[c[1]])} @ ({tx:.1f}, {ty:.1f})"

        note = "; ".join(f"{label(c)} = {gain:+.0f}" for gain, c in final[:3])
        note += f"; [{len(cands)} plays tried in {(time.perf_counter() - t0) * 1000:.0f} ms]"
        gain, best = final[0]
        return (best if gain > self.margin else None), note


# ---------------------------------------------------------------- worker processes (one engine each)
_P: Planner | None = None


def _pool_init(args: dict, parent: int) -> None:
    global _P
    _P = Planner(**args, workers=0)

    def watch() -> None:  # do not outlive the process that owns this pool
        while os.getppid() == parent:
            time.sleep(1.0)
        os._exit(0)

    threading.Thread(target=watch, daemon=True).start()


def _pool_run(job: tuple) -> list:
    fn, root, items = job
    if fn == "rollout":
        return [_P.rollout(root, it, _P.horizon) for it in items]
    return [_P.after_reply(root, it) for it in items]
