"""Decks: the classic decks for the fixed-deck track, and the card pool + parser for the
deck-building track (each model builds its own 8-card deck before every game, blind to the
opponent's choice)."""

from __future__ import annotations

import re

# Classic ladder archetypes, written with this engine's card names (its data is ~2018).
# Cards that the engine lacks are swapped for the closest available card (noted).
CLASSIC_DECKS: dict[str, list[str]] = {
    "giant-beatdown": ["Giant", "Musketeer", "Knight", "Archer", "Minions", "Cannon", "Fireball", "Zap"],
    "hog-2.6-cycle": ["HogRider", "Musketeer", "Cannon", "IceGolemite", "IceSpirits", "Skeletons", "Fireball", "Log"],
    "lavaloon": ["LavaHound", "Balloon", "MegaMinion", "Minions", "Tombstone", "Arrows", "Fireball", "Zap"],
    "log-bait": ["GoblinBarrel", "Princess", "GoblinGang", "Knight", "InfernoTower", "Rocket", "Log", "IceSpirits"],
    "golem-beatdown": ["Golem", "BabyDragon", "MegaMinion", "ElectroWizard", "Lightning", "Zap", "Tombstone", "Bats"],
    "xbow-cycle": ["Xbow", "Tesla", "Archer", "Knight", "IceSpirits", "Skeletons", "Fireball", "Log"],
    "pekka-bridge-spam": ["Pekka", "BattleRam", "ElectroWizard", "MiniPekka", "Bats", "Zap", "Poison", "Wizard"],
}
DEFAULT_DECK = CLASSIC_DECKS["giant-beatdown"]

# Deck-building pool: standard cards only (no event/boss/"Super" variants), each checked to
# deploy correctly in this engine (scripts: python -m cr_arena.decks --check).
POOL: list[str] = [
    # troops
    "Knight", "Archer", "Giant", "Minions", "Musketeer", "MiniPekka", "Valkyrie", "BabyDragon", "Wizard",
    "HogRider", "Skeletons", "Barbarians", "Bomber", "Goblins", "SpearGoblins", "GoblinGang", "Princess",
    "IceSpirits", "IceGolemite", "FireSpirits", "Bats", "MegaMinion", "MinionHorde", "SkeletonArmy", "Prince",
    "DarkPrince", "Pekka", "Golem", "LavaHound", "Balloon", "RoyalGiant", "GiantSkeleton", "Witch", "IceWizard",
    "ElectroWizard", "InfernoDragon", "Miner", "Bowler", "Hunter", "MegaKnight", "BattleRam", "RoyalHogs",
    "ThreeMusketeers", "ElectroDragon", "Firecracker", "Fisherman", "RamRider", "ElectroSpirit", "Rascals",
    "BlowdartGoblin", "RoyalRecruits", "ElixirGolem", "BattleHealer", "ElectroGiant", "GoblinGiant",
    "SkeletonDragons", "Wallbreakers", "Ghost", "GoldenKnight", "MightyMiner",
    # buildings
    "Cannon", "Tesla", "InfernoTower", "BombTower", "Tombstone", "GoblinHut", "BarbarianHut", "Mortar", "Xbow",
    "GoblinCage", "FirespiritHut",
    # spells
    "Fireball", "Zap", "Arrows", "Log", "Rocket", "Lightning", "Poison", "Freeze", "Tornado", "Earthquake",
    "GoblinBarrel", "Graveyard", "Rage", "Snowball", "RoyalDelivery", "BarbLog",
]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


ALIASES = {  # common real-game names -> engine names
    "icegolem": "IceGolemite", "thelog": "Log", "giantsnowball": "Snowball", "barbarianbarrel": "BarbLog",
    "dartgoblin": "BlowdartGoblin", "royalghost": "Ghost", "furnace": "FirespiritHut", "xbow": "Xbow",
    "minipekka": "MiniPekka", "pekka": "Pekka", "goblincage": "GoblinCage", "musketeers": "ThreeMusketeers",
    "threemusketeers": "ThreeMusketeers", "electrowiz": "ElectroWizard", "ewiz": "ElectroWizard",
}


def resolve(name: str, pool: list[str] = POOL) -> str | None:
    by_norm = {_norm(c): c for c in pool}
    n = _norm(name)
    if n in by_norm:
        return by_norm[n]
    alias = ALIASES.get(n)
    return alias if alias in pool else None


DECK_RE = re.compile(r"DECK\s*:\s*(.+)", re.IGNORECASE)


def parse_deck(raw: str, pool: list[str] = POOL) -> tuple[list[str] | None, str | None]:
    """Last `DECK: a, b, ...` line -> (8 distinct pool cards, None) or (None, error)."""
    found = DECK_RE.findall(raw or "")
    if not found:
        return None, "no DECK line"
    names = [x.strip().strip("*`[]\"'.") for x in re.split(r"[,;]", found[-1]) if x.strip()]
    deck, unknown = [], []
    for nm in names:
        c = resolve(nm, pool)
        if c is None:
            unknown.append(nm)
        elif c not in deck:
            deck.append(c)
    if unknown:
        return None, f"not in pool: {', '.join(unknown)[:200]}"
    if len(deck) != 8:
        return None, f"need 8 distinct cards, got {len(deck)}"
    return deck, None


def pool_text(cards) -> str:
    """One line per pool card with the engine's stats (cards = engine.cards())."""
    by_name = {c.name: c for c in cards}
    from royalegym.protocol import Placement, card_is_spell

    lines = []
    for name in POOL:
        c = by_name[name]
        if card_is_spell(c):
            kind = "spell"
        elif c.placement == Placement.BUILDING:
            kind = "building"
        else:
            kind = "troop"
        bits = [f"{c.elixir} elixir", kind]
        if kind != "spell":
            if c.count > 1:
                bits.append(f"x{c.count}")
            bits.append(f"{c.hitpoints} hp")
            if c.flying:
                bits.append("flying")
        lines.append(f"- {name}: " + ", ".join(bits))
    return "\n".join(lines)


def _check() -> None:
    """Play every pool card many times (random bots, mixed decks) and report cards that never deploy."""
    import random

    from .game import Game

    rng = random.Random(0)
    played: dict[str, int] = {c: 0 for c in POOL}
    tried: dict[str, int] = {c: 0 for c in POOL}
    names = list(POOL)
    for rnd in range(3):
        rng.shuffle(names)
        for i in range(0, len(names), 8):
            deck = names[i:i + 8]
            if len(deck) < 8:
                deck += [c for c in DEFAULT_DECK if c not in deck][: 8 - len(deck)]
            g = Game(deck, deck, seed=rnd * 100 + i, record=False)
            while not g.over:
                ms = [g.legal_moves(t) for t in (0, 1)]
                ch = [rng.choice(m[1:]) if len(m) > 1 and rng.random() < 0.5 else m[0] for m in ms]
                res = g.step(ch)
                for mv, r in zip(ch, res):
                    if mv.slot >= 0 and mv.card in tried:
                        tried[mv.card] += 1
                        played[mv.card] += r.startswith("played")
    bad = [c for c in POOL if played[c] == 0 or played[c] < tried[c] * 0.8]
    for c in POOL:
        if c in bad:
            print(f"PROBLEM {c}: played {played[c]}/{tried[c]}")
    print(f"{len(POOL) - len(bad)}/{len(POOL)} pool cards OK")
    for name, deck in CLASSIC_DECKS.items():
        missing = [c for c in deck if c not in POOL]
        print(f"{name}: {'OK' if not missing else 'not in pool: ' + ', '.join(missing)}")


if __name__ == "__main__":
    _check()
