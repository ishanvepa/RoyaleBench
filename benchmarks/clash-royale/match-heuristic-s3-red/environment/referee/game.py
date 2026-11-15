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

import msgspec
from royalegym import MatchSetup, RustEngine, deck_ids
from royalegym.protocol import (
    STATUS_ABILITY_ACTIVE,
    STATUS_CHARGED,
    STATUS_GROUNDED,
    STATUS_HIDDEN,
    STATUS_INVISIBLE,
    STATUS_UNDERGROUND,
    DeployCommand,
    DeployStatus,
    EntityKind,
    Placement,
    card_is_spell,
    status_of,
    to_own,
)
from royalegym.replay import ReplayRecorder

TOWER_NAMES = {0: "king tower", 1: "left princess tower", 2: "right princess tower"}
# Tower slots are named from their OWNER's side. Seen from across the board the enemy's slot 1
# ("its left") stands on the observer's right, so enemy towers are named through this map.
ENEMY_SLOT_FOR_VIEW = {0: 0, 1: 2, 2: 1}  # observer's view slot -> enemy's own slot
STATUS_WORDS = (
    (STATUS_UNDERGROUND, "underground"),
    (STATUS_INVISIBLE, "invisible"),
    (STATUS_HIDDEN, "hidden"),
    (STATUS_ABILITY_ACTIVE, "ability active"),
    (STATUS_CHARGED, "charged"),
    (STATUS_GROUNDED, "grounded"),
)

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
MAX_OWN_UNIT_TARGETS = 4  # spell targets placed on own units (Rage, Heal, Freeze around them, ...)


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


def tiebreak_winner(state, seed: int) -> int:
    """Who wins a match that is still level on crowns when overtime ends (0 blue, 1 red).

    The side with more tower HP left, all its towers added up. If that is exactly equal too, the
    seed's parity decides, so a match is never a draw.
    """
    blue, red = (sum(p.tower_hp) for p in state.players)
    if blue != red:
        return 0 if blue > red else 1
    return seed % 2


@dataclass
class SeatMemory:
    """What one player has learned so far (only things visible on their screen)."""

    seen_uids: set[int] = field(default_factory=set)
    enemy_cards_seen: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)  # since last decision
    opponent_plays: list[str] = field(default_factory=list)  # accepted plays since last decision
    announced_cards: set[int] = field(default_factory=set)  # enemy plays reported this interval
    history: list[str] = field(default_factory=list)  # own recent moves with results


class Game:
    def __init__(self, deck_blue: list[str], deck_red: list[str], seed: int,
                 decision_ticks: int = 40, record: bool = True, command_delay_ticks: int = 0,
                 setup: MatchSetup | None = None):
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
        self.rules = self.engine.rules()
        self.decision_ticks = decision_ticks
        self.telemetry = None  # trusted diagnostic observer; never used by a player
        self.seed = seed
        decks = [deck_ids(deck_blue, self.cards), deck_ids(deck_red, self.cards)]
        self.setup = setup if setup is not None else MatchSetup(decks=decks)
        self.engine.reset(seed, self.setup)
        self.recorder = ReplayRecorder(frame_every_tick=True) if record else None
        if self.recorder:
            self.recorder.begin(self.engine, seed, self.setup)
        self.mem = [SeatMemory(), SeatMemory()]
        self._aimed: dict[tuple[int, int], tuple[int, int]] = {}  # (team, card) -> tap, while delayed
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
        s = self.engine.state()
        if s.overtime and s.tick >= s.regular_ticks + s.overtime_ticks and (not s.game_over or s.winner == 2):
            # The engine would now drain the towers until a crown falls, or call a draw. The match
            # ends here instead, on tower HP, so every loop that reads the state sees it over.
            return msgspec.structs.replace(s, game_over=True, winner=tiebreak_winner(s, self.seed))
        return s

    @property
    def over(self) -> bool:
        return self.state.game_over

    def time_left_s(self) -> tuple[float, bool]:
        """Seconds left in regulation or overtime, never below 0 (a level overtime that has run
        out ends the match on tower HP, see ``tiebreak_winner``)."""
        s = self.state
        if s.tick < s.regular_ticks:
            return (s.regular_ticks - s.tick) * s.tick_ms / 1000, False
        return max(0, s.regular_ticks + s.overtime_ticks - s.tick) * s.tick_ms / 1000, True

    def card_name(self, card_id: int) -> str:
        c = self.card_by_id.get(card_id)
        return c.name if c else f"card#{card_id}"

    def kind_of(self, card) -> str:
        if card.card_kind:
            return card.card_kind
        return "SPELL" if card_is_spell(card) else ("BUILDING" if card.placement == Placement.BUILDING else "TROOP")

    # ------------------------------------------------------------------ memory / events
    def _note_play(self, team: int, card_id: int, x: int, y: int) -> None:
        """An accepted enemy play, as the other player sees it land: every card, including a
        spell that resolves at once and leaves nothing on the board."""
        viewer = 1 - team
        m = self.mem[viewer]
        card = self.card_by_id.get(card_id)
        name = self.card_name(card_id)
        tx, ty = self.own_tiles(viewer, x, y)
        m.opponent_plays.append(f"{name}@({tx:.1f},{ty:.1f})")
        verb = "cast" if card is not None and self.kind_of(card) == "SPELL" else "deployed"
        m.events.append(f"enemy {verb} {name} at ({tx:.1f}, {ty:.1f}), {self.lane_of(tx)} lane")
        self._saw_card(m, name)
        m.announced_cards.add(card_id)

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
                    self._saw_card(m, name)
                    if e.card_id in m.announced_cards:
                        continue  # the play that made it was already reported
                    tx, ty = self.own_tiles(team, e.x, e.y)
                    m.events.append(f"enemy {name} appeared at ({tx:.1f}, {ty:.1f}), {self.lane_of(tx)} lane")

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
                tower_targets.append((f"enemy {self.tower_name(team, e)}", tx, ty))

        def units_of(owner: int, label: str, limit: int, nearest_first: bool) -> list[tuple[str, float, float]]:
            out: list[tuple[str, float, float]] = []
            for e in sorted(
                (e for e in s.entities if e.team == owner and e.kind in (EntityKind.TROOP, EntityKind.BUILDING) and e.hp > 0),
                key=lambda e: self.own_tiles(team, e.x, e.y)[1] * (1 if nearest_first else -1),
            ):
                tx, ty = self.own_tiles(team, e.x, e.y)
                if any(abs(tx - ux) < 1.5 and abs(ty - uy) < 1.5 for _, ux, uy in out):
                    continue
                out.append((f"on {label} {self.card_name(e.card_id)} at ({tx:.1f}, {ty:.1f})", tx, ty))
                if len(out) >= limit:
                    break
            return out

        unit_targets = units_of(1 - team, "enemy", MAX_UNIT_TARGETS, nearest_first=True)  # closest to our side first
        own_unit_targets = units_of(team, "your", MAX_OWN_UNIT_TARGETS, nearest_first=False)  # most advanced first
        # A spell may go anywhere: on units (either side), on towers, or at fixed points for
        # predictive casts (a bridge before a push arrives, a lane on the enemy side).
        spell_targets = unit_targets + tower_targets + own_unit_targets + enemy_side + base_targets

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
                targets = spell_targets
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
        if ot:
            phase = " (OVERTIME - next tower destroyed wins; if none falls, the side with more total tower HP wins)"
        else:
            phase = ""
        enemy_slots = [ENEMY_SLOT_FOR_VIEW[i] for i in range(3)]
        lines = [
            f"TIME LEFT: {mins}:{secs:02d}{phase}{mult}",
            f"CROWNS: you {me.crowns} - enemy {en.crowns}",
            f"YOUR ELIXIR: {me.elixir_milli / 1000:.1f} / 10",
            "YOUR TOWERS: " + ", ".join(f"{TOWER_NAMES[i]} {me.tower_hp[i]}/{me.tower_max_hp[i]}" for i in range(3)),
            "ENEMY TOWERS (left/right as you see them): "
            + ", ".join(f"{TOWER_NAMES[i]} {en.tower_hp[j]}/{en.tower_max_hp[j]}" for i, j in enumerate(enemy_slots)),
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
                tags = self.unit_tags(e)
                tag = f" ({', '.join(tags)})" if tags else ""
                shield = f" + shield {e.shield}" if e.shield > 0 else ""
                out.append(f"  - {self.card_name(e.card_id)}{tag} hp {e.hp}/{e.max_hp}{shield} at ({tx:.1f}, {ty:.1f}) {self.lane_of(tx)} lane")
            return out

        mine, theirs = unit_lines(team), unit_lines(1 - team)
        lines.append("YOUR UNITS ON FIELD:" + ("\n" + "\n".join(mine) if mine else " none"))
        lines.append("ENEMY UNITS ON FIELD:" + ("\n" + "\n".join(theirs) if theirs else " none"))
        if mem.opponent_plays:
            lines.append("Opponent plays: " + ", ".join(mem.opponent_plays))
        if mem.history:
            lines.append("YOUR LAST MOVES:\n" + "\n".join(f"  - {h}" for h in mem.history[-5:]))
        lines.append("LEGAL MOVES:\n" + "\n".join(m.label() for m in moves))
        return "\n".join(lines)

    def tower_name(self, team: int, e) -> str:
        """A crown tower named from ``team``'s side of the board."""
        if e.tower_slot == 0:
            return TOWER_NAMES[0]
        tx, _ = self.own_tiles(team, e.x, e.y)
        return TOWER_NAMES[1] if tx < 9 else TOWER_NAMES[2]

    def unit_tags(self, e) -> list[str]:
        """What a player sees on a unit besides its health: flying, deploying, status effects."""
        tags = []
        if e.flying:
            tags.append("flying")
        if e.deploy_ticks > 0:
            tags.append("deploying")
        if e.stun_ticks > 0:
            tags.append("stunned")
        flags = status_of(e)
        if flags:
            tags += [word for bit, word in STATUS_WORDS if flags & bit]
        if e.charge > 0 and not (flags and flags & STATUS_CHARGED):
            tags.append(f"charging {e.charge // 10}%")
        return tags

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
            s = self.state
            if s.game_over:
                break
            tick = s.tick
            send = cmds if first else []
            res = self.engine.step(send, 1)
            if self.telemetry is not None:
                try:
                    self.telemetry.tick(s, self.state, list(send), res)
                except Exception as exc:
                    self.telemetry.capture.manifest["capture_errors"].append(f"engine_tick: {exc}")
                    self.telemetry = None
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
                    if ok and not self.command_delay_ticks:
                        self._note_play(r.team, r.card_id, r.x, r.y)
                    elif ok:
                        self._aimed[(r.team, r.card_id)] = (r.x, r.y)
                first = False
            if self.command_delay_ticks:  # a delayed play is seen when it lands
                for _t, team, kind, card, reason in (self.engine.step_commands_run() or []):
                    aim = self._aimed.pop((team, card), None)
                    if kind == "deploy" and reason == 0 and aim is not None:
                        self._note_play(team, card, *aim)
            self._update_memory()  # every tick, so short-lived units are seen too
        for m in self.mem:
            m.announced_cards.clear()
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
        self.mem[team].opponent_plays.clear()

    def finish(self):
        trace = self.recorder.end(self.engine) if self.recorder else None
        s = self.state
        if trace is not None and trace.result is not None:
            trace.result.winner = s.winner  # the engine never saw the tiebreak, so its own result is stale
        return s.winner, [p.crowns for p in s.players], [list(p.tower_hp) for p in s.players], s.tick, trace
