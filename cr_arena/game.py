"""One battle on RoyaleGym's engine, seen by each player as text plus a numbered move list.

The engine is stepped in fixed decision intervals. At each decision point both players get
their own view (only what that player could see: no enemy hand or elixir), pick one move
from the list, and both moves are applied together before the next interval runs.

Positions are shown in the player's OWN frame, in tiles: x 0..17 (left to right as the
player looks at the board), y 0..31 (0 = the player's back edge, 31 = the enemy's back
edge). The river is around y 15-16.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from royalegym import MatchSetup, RustEngine, deck_ids
from royalegym.protocol import (
    DeployCommand,
    DeployStatus,
    EntityKind,
    Placement,
    card_is_spell,
    to_own,
)
from royalegym.replay import ReplayRecorder

TOWER_NAMES = {0: "king tower", 1: "left princess tower", 2: "right princess tower"}

# Placement zones in the player's own frame, in tiles (x, y). Points that are illegal for a
# given card are snapped to the nearest legal point within SNAP_TILES.
OWN_ZONES: dict[str, tuple[float, float]] = {
    "left bridge": (3.5, 13.5),
    "right bridge": (14.5, 13.5),
    "in front of left tower": (3.5, 10.5),
    "in front of right tower": (14.5, 10.5),
    "behind left tower": (3.5, 3.5),
    "behind right tower": (14.5, 3.5),
    "center (between towers)": (9.0, 10.5),
    "behind king tower": (9.0, 0.5),
}
# Enemy-side points: spells always; troops only once an enemy princess tower is down.
ENEMY_ZONES: dict[str, tuple[float, float]] = {
    "enemy side, left lane": (3.5, 18.5),
    "enemy side, right lane": (14.5, 18.5),
}
SNAP_TILES = 2.0
MAX_UNIT_TARGETS = 6  # spell targets placed on enemy units


@dataclass
class Move:
    index: int
    slot: int  # hand slot, -1 for wait
    card: str
    kind: str  # TROOP / BUILDING / SPELL / WAIT
    cost: int
    target: str  # human description of where
    lane: str  # left / right / center / -
    x: int = 0  # engine frame subtiles
    y: int = 0

    def label(self) -> str:
        if self.slot < 0:
            return f"{self.index}. wait (save elixir)"
        return f"{self.index}. {self.card} ({self.cost} elixir, {self.kind.lower()}) @ {self.target}"


@dataclass
class SeatMemory:
    """What one player has learned so far (only things visible on their screen)."""

    seen_uids: set[int] = field(default_factory=set)
    seen_spell_keys: set[tuple] = field(default_factory=set)
    enemy_cards_seen: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)  # since last decision
    history: list[str] = field(default_factory=list)  # own recent moves with results


class Game:
    def __init__(self, deck_blue: list[str], deck_red: list[str], seed: int,
                 decision_ticks: int = 40, record: bool = True, command_delay_ticks: int = 0):
        self.engine = RustEngine()
        if command_delay_ticks:
            # A play lands this many ticks after it is made, as on the real client (about 21). Live play only:
            # the benchmark keeps 0, where a move is applied at once.
            self.engine.set_command_delay_ticks(command_delay_ticks)
        self.command_delay_ticks = command_delay_ticks
        self.cards = list(self.engine.cards())
        self.card_by_id = {c.card_id: c for c in self.cards}
        self.arena = self.engine.arena()
        self.sub = self.arena.subtile
        self.decision_ticks = decision_ticks
        self.seed = seed
        decks = [deck_ids(deck_blue, self.cards), deck_ids(deck_red, self.cards)]
        self.setup = MatchSetup(decks=decks)
        self.engine.reset(seed, self.setup)
        self.recorder = ReplayRecorder(frame_every_tick=True) if record else None
        if self.recorder:
            self.recorder.begin(self.engine, seed, self.setup)
        self.mem = [SeatMemory(), SeatMemory()]
        self.decks = [list(deck_blue), list(deck_red)]
        self._update_memory()  # towers are seen from the start
        for m in self.mem:
            m.events.clear()

    # ------------------------------------------------------------------ geometry
    def own_tiles(self, team: int, x: int, y: int) -> tuple[float, float]:
        ox, oy = to_own(self.arena, team, x, y)
        return ox / self.sub, oy / self.sub

    def engine_point(self, team: int, tx: float, ty: float) -> tuple[int, int]:
        # The own<->engine transform is a 180-degree rotation for red, so it is its own inverse.
        return to_own(self.arena, team, int(round(tx * self.sub)), int(round(ty * self.sub)))

    @staticmethod
    def lane_of(tx: float) -> str:
        if tx < 7.5:
            return "left"
        if tx > 10.5:
            return "right"
        return "center"

    # ------------------------------------------------------------------ state
    @property
    def state(self):
        return self.engine.state()

    @property
    def over(self) -> bool:
        return self.state.game_over

    def time_left_s(self) -> tuple[float, bool]:
        s = self.state
        if s.tick < s.regular_ticks:
            return (s.regular_ticks - s.tick) * s.tick_ms / 1000, False
        return (s.regular_ticks + s.overtime_ticks - s.tick) * s.tick_ms / 1000, True

    def card_name(self, card_id: int) -> str:
        c = self.card_by_id.get(card_id)
        return c.name if c else f"card#{card_id}"

    def kind_of(self, card) -> str:
        if card.card_kind:
            return card.card_kind
        return "SPELL" if card_is_spell(card) else ("BUILDING" if card.placement == Placement.BUILDING else "TROOP")

    # ------------------------------------------------------------------ memory / events
    def _update_memory(self) -> None:
        s = self.state
        for team in (0, 1):
            m = self.mem[team]
            for e in s.entities:
                if e.uid in m.seen_uids:
                    continue
                m.seen_uids.add(e.uid)
                if e.team != team and e.kind in (EntityKind.TROOP, EntityKind.BUILDING):
                    name = self.card_name(e.card_id)
                    tx, ty = self.own_tiles(team, e.x, e.y)
                    m.events.append(f"enemy deployed {name} at ({tx:.1f}, {ty:.1f}), {self.lane_of(tx)} lane")
                    self._saw_card(m, name)
            for sp in s.spells:
                key = (sp.team, sp.card_id, sp.aim_x, sp.aim_y)
                if key in m.seen_spell_keys:
                    continue
                m.seen_spell_keys.add(key)
                if sp.team != team:
                    name = self.card_name(sp.card_id)
                    tx, ty = self.own_tiles(team, sp.aim_x, sp.aim_y)
                    m.events.append(f"enemy cast {name} aimed at ({tx:.1f}, {ty:.1f})")
                    self._saw_card(m, name)

    @staticmethod
    def _saw_card(m: SeatMemory, name: str) -> None:
        # Spawned sub-units (e.g. skeletons from a card) can show up under their own name;
        # the list is "cards/units seen", which is what a player sees on screen.
        if name not in m.enemy_cards_seen:
            m.enemy_cards_seen.append(name)

    # ------------------------------------------------------------------ legal moves
    def legal_moves(self, team: int) -> list[Move]:
        s = self.state
        moves = [Move(0, -1, "wait", "WAIT", 0, "-", "-")]
        if s.game_over:
            return moves
        p = s.players[team]
        enemy = s.players[1 - team]
        enemy_left_down = enemy.tower_hp[1] == 0
        enemy_right_down = enemy.tower_hp[2] == 0

        # Candidate targets in own-frame tiles.
        base_targets: list[tuple[str, float, float]] = [(k, *v) for k, v in OWN_ZONES.items()]
        enemy_side = [(k, *v) for k, v in ENEMY_ZONES.items()]
        tower_targets = []
        for e in s.entities:
            if e.team != team and e.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER) and e.hp > 0:
                tx, ty = self.own_tiles(team, e.x, e.y)
                tower_targets.append((f"enemy {TOWER_NAMES[e.tower_slot]}", tx, ty))
        unit_targets = []
        for e in sorted(
            (e for e in s.entities if e.team != team and e.kind in (EntityKind.TROOP, EntityKind.BUILDING) and e.hp > 0),
            key=lambda e: self.own_tiles(team, e.x, e.y)[1],  # closest to our side first
        ):
            tx, ty = self.own_tiles(team, e.x, e.y)
            if any(abs(tx - ux) < 1.5 and abs(ty - uy) < 1.5 for _, ux, uy in unit_targets):
                continue
            unit_targets.append((f"on enemy {self.card_name(e.card_id)} at ({tx:.1f}, {ty:.1f})", tx, ty))
            if len(unit_targets) >= MAX_UNIT_TARGETS:
                break

        idx = 1
        for slot, cid in enumerate(p.hand):
            card = self.card_by_id.get(cid)
            if card is None:
                continue
            cost = p.hand_costs[slot] if len(p.hand_costs) == len(p.hand) else card.elixir
            # elixir already promised to plays that have not landed yet (command delay) is not spendable
            if cost < 0 or p.elixir_milli - p.pending_cost * 1000 < cost * 1000:
                continue
            kind = self.kind_of(card)
            if kind == "SPELL":
                targets = unit_targets + tower_targets
            else:
                targets = list(base_targets)
                if enemy_left_down or enemy_right_down:
                    targets += enemy_side
            seen_points: set[tuple[int, int]] = set()
            for name, tx, ty in targets:
                pt = self._legal_point(team, slot, tx, ty, snap=(kind != "SPELL"))
                if pt is None or pt in seen_points:
                    continue
                seen_points.add(pt)
                moves.append(Move(idx, slot, card.name, kind, cost, name, self.lane_of(tx), pt[0], pt[1]))
                idx += 1
        return moves

    def _legal_point(self, team: int, slot: int, tx: float, ty: float, snap: bool) -> tuple[int, int] | None:
        x, y = self.engine_point(team, tx, ty)
        st = self.engine.check_deploy(DeployCommand(team, slot, x, y))
        if st == DeployStatus.OK:
            return (x, y)
        if not snap or st not in (DeployStatus.NO_DEPLOY, DeployStatus.OCCUPIED, DeployStatus.WATER,
                                  DeployStatus.OUT_OF_TERRITORY, DeployStatus.OUT_OF_ARENA):
            return None
        best = None
        r = 0.5
        while r <= SNAP_TILES and best is None:
            steps = int(r * 2)
            for dx in range(-steps, steps + 1):
                for dy in range(-steps, steps + 1):
                    if max(abs(dx), abs(dy)) != steps:
                        continue
                    nx, ny = self.engine_point(team, tx + dx * 0.5, ty + dy * 0.5)
                    if self.engine.check_deploy(DeployCommand(team, slot, nx, ny)) == DeployStatus.OK:
                        d = dx * dx + dy * dy
                        if best is None or d < best[0]:
                            best = (d, nx, ny)
            r += 0.5
        return None if best is None else (best[1], best[2])

    # ------------------------------------------------------------------ text view
    def describe(self, team: int, moves: list[Move]) -> str:
        s = self.state
        me, en = s.players[team], s.players[1 - team]
        left, ot = self.time_left_s()
        mins, secs = divmod(int(left), 60)
        mult = f", elixir x{s.elixir_rate}" if s.elixir_rate > 1 else ""
        lines = [
            f"TIME LEFT: {mins}:{secs:02d}{' (OVERTIME - next tower destroyed wins)' if ot else ''}{mult}",
            f"CROWNS: you {me.crowns} - enemy {en.crowns}",
            f"YOUR ELIXIR: {me.elixir_milli / 1000:.1f} / 10",
            "YOUR TOWERS: " + ", ".join(f"{TOWER_NAMES[i]} {me.tower_hp[i]}/{me.tower_max_hp[i]}" for i in range(3)),
            "ENEMY TOWERS: " + ", ".join(f"{TOWER_NAMES[i]} {en.tower_hp[i]}/{en.tower_max_hp[i]}" for i in range(3)),
        ]
        hand = []
        for slot, cid in enumerate(me.hand):
            c = self.card_by_id.get(cid)
            if c:
                cost = me.hand_costs[slot] if len(me.hand_costs) == len(me.hand) else c.elixir
                hand.append(f"{c.name} ({cost})")
        lines.append("YOUR HAND: " + ", ".join(hand) + f" | next card: {self.card_name(me.next_card)}")
        mem = self.mem[team]
        lines.append("ENEMY CARDS SEEN SO FAR: " + (", ".join(mem.enemy_cards_seen) or "none"))

        def unit_lines(owner: int) -> list[str]:
            out = []
            for e in s.entities:
                if e.team != owner or e.kind not in (EntityKind.TROOP, EntityKind.BUILDING) or e.hp <= 0:
                    continue
                tx, ty = self.own_tiles(team, e.x, e.y)
                tag = " (flying)" if e.flying else ""
                dep = " (deploying)" if e.deploy_ticks > 0 else ""
                out.append(f"  - {self.card_name(e.card_id)}{tag}{dep} hp {e.hp}/{e.max_hp} at ({tx:.1f}, {ty:.1f}) {self.lane_of(tx)} lane")
            return out

        mine, theirs = unit_lines(team), unit_lines(1 - team)
        lines.append("YOUR UNITS ON FIELD:" + ("\n" + "\n".join(mine) if mine else " none"))
        lines.append("ENEMY UNITS ON FIELD:" + ("\n" + "\n".join(theirs) if theirs else " none"))
        if mem.events:
            lines.append("SINCE YOUR LAST DECISION:\n" + "\n".join(f"  - {ev}" for ev in mem.events[-8:]))
        if mem.history:
            lines.append("YOUR LAST MOVES:\n" + "\n".join(f"  - {h}" for h in mem.history[-5:]))
        lines.append("LEGAL MOVES:\n" + "\n".join(m.label() for m in moves))
        return "\n".join(lines)

    def deck_summary(self, team: int) -> str:
        out = []
        for name in self.decks[team]:
            c = next(c for c in self.cards if c.name == name)
            kind = self.kind_of(c)
            if kind == "SPELL":
                out.append(f"- {c.name}: {c.elixir} elixir, spell")
            else:
                fly = ", flying" if c.flying else ""
                n = f" x{c.count}" if c.count > 1 else ""
                out.append(f"- {c.name}: {c.elixir} elixir, {kind.lower()}{n}, {c.hitpoints} hp each{fly}")
        return "\n".join(out)

    # ------------------------------------------------------------------ stepping
    def step(self, chosen: list[Move]) -> list[str]:
        """Apply both players' moves (index = team) and run one decision interval."""
        cmds, owners = [], []
        for team, mv in enumerate(chosen):
            if mv.slot >= 0:
                cmds.append(DeployCommand(team, mv.slot, mv.x, mv.y))
                owners.append(team)
        results_text = ["wait", "wait"]
        first = True
        for _ in range(self.decision_ticks):
            if self.engine.state().game_over:
                break
            tick = self.engine.state().tick
            send = cmds if first else []
            res = self.engine.step(send, 1)
            if self.recorder:
                self.recorder.record_step(tick, 1, list(send), res)
                self.recorder.record_frame(self.engine)
            if first:
                for team, r in zip(owners, res):
                    mv = chosen[team]
                    ok = r.status == DeployStatus.OK
                    results_text[team] = (
                        f"played {mv.card} @ {mv.target}" if ok
                        else f"tried {mv.card} @ {mv.target} -> refused ({DeployStatus(r.status).name})"
                    )
                first = False
        left, _ = self.time_left_s()
        for team in (0, 1):
            if results_text[team] != "wait":  # history = actual plays/refusals, not the many waits
                self.mem[team].history.append(f"[{int(left) // 60}:{int(left) % 60:02d}] {results_text[team]}")
        self._update_memory()
        return results_text

    def consume_events(self, team: int) -> None:
        """Called once the player has actually been shown its events (so events seen during
        forced waits, when the player is not asked, are kept for the next real decision)."""
        self.mem[team].events.clear()

    def finish(self):
        trace = self.recorder.end(self.engine) if self.recorder else None
        s = self.state
        return s.winner, [p.crowns for p in s.players], [list(p.tower_hp) for p in s.players], s.tick, trace
