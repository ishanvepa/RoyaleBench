"""Deck strength for the classic decks, from CrownScribe archetype win rates: tracked snapshots and rankings.

    uv run python -m cr_arena.deck_strength        # overall ranking, within-set ranking and matchup matrix

Each classic deck is mapped to the CrownScribe (crownscribe.com) archetype it belongs to. Two tracked files hold
that archetype's numbers (columns, caveats and refresh steps: data/README.md):

- data/deck_strength.csv: win rate and battle count against the whole meta.
- data/deck_matchups.csv: win rate and battle count of each deck against each other classic deck.

Both are append-only, one row per deck (or pair) per capture, so meta shifts stay visible; everything here reads
the newest row. Decks are ranked by the lower bound of the 95% interval, and tiers group decks whose intervals
overlap the tier's best deck, so a gap between tiers is one that sampling noise cannot explain. The numbers
describe the archetype (every deck that contains its signature cards), not our exact eight cards.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from .decks import CLASSIC_DECKS

DATA = Path(__file__).resolve().parents[1] / "data" / "deck_strength.csv"
MATCHUPS = Path(__file__).resolve().parents[1] / "data" / "deck_matchups.csv"
Z95 = 1.96


def load(path: Path = DATA) -> list[dict]:
    """Every snapshot row: win_rate and usage as fractions, battles as an int, `signature` as a list of engine
    card names, and `missing` = the signature cards our deck does not contain (empty when it fits)."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["win_rate"] = float(r["win_rate_pct"]) / 100
        r["usage"] = float(r["usage_pct"]) / 100
        r["battles"] = int(r["battles"])
        r["signature"] = r["signature"].split("|") if r["signature"] else []
        r["missing"] = sorted(set(r["signature"]) - set(CLASSIC_DECKS.get(r["deck"], [])))
    return rows


def load_matchups(path: Path = MATCHUPS) -> list[dict]:
    """Every matchup row: win_rate as a fraction (of `deck` against `opponent`) and battles as an int."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["win_rate"] = float(r["win_rate_pct"]) / 100
        r["battles"] = int(r["battles"])
    return rows


def wilson(p: float, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a win rate `p` over `n` > 0 battles."""
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centre - half, centre + half


def latest(rows: list[dict] | None = None) -> dict[str, dict]:
    """Each deck's newest snapshot. ISO dates sort as text, and a later row wins a tie."""
    newest: dict[str, dict] = {}
    for r in sorted(load() if rows is None else rows, key=lambda r: r["captured"]):
        newest[r["deck"]] = r
    return newest


def _tiers(entries: list[dict]) -> None:
    """Set rank and tier on entries already sorted best first by interval lower bound. A deck whose interval is
    clear of the tier's best deck starts a new tier."""
    tier, leader = 0, None
    for i, o in enumerate(entries, 1):
        if leader is None or o["ci_high"] < leader["ci_low"]:
            tier, leader = tier + 1, o
        o["rank"], o["tier"] = i, tier


def ranking(rows: list[dict] | None = None) -> list[dict]:
    """Decks best first, then decks with no battles (rank and tier None).

    Entry keys: deck, archetype, rank (by interval lower bound), tier, win_rate, ci_low, ci_high, battles, usage,
    missing (signature cards our deck lacks), captured."""
    out = []
    for deck, r in latest(rows).items():
        low, high = wilson(r["win_rate"], r["battles"]) if r["battles"] else (None, None)
        out.append({"deck": deck, "archetype": r.get("archetype", ""), "win_rate": r["win_rate"], "ci_low": low,
                    "ci_high": high, "battles": r["battles"], "usage": r.get("usage"), "missing": r.get("missing"),
                    "captured": r["captured"]})
    ranked = sorted((o for o in out if o["battles"]), key=lambda o: (-o["ci_low"], o["deck"]))
    _tiers(ranked)
    unranked = [dict(o, rank=None, tier=None) for o in sorted(out, key=lambda o: o["deck"]) if not o["battles"]]
    return ranked + unranked


def head_to_head(rows: list[dict] | None = None) -> dict[tuple[str, str], tuple[float, float]]:
    """(deck, opponent) -> (win rate of deck, battles), from each pair's newest rows. CrownScribe lists a pair on
    both decks' pages (the same battles, read a moment apart), so each direction is averaged with the other's
    complement."""
    newest: dict[tuple[str, str], dict] = {}
    for r in sorted(load_matchups() if rows is None else rows, key=lambda r: r["captured"]):
        newest[(r["deck"], r["opponent"])] = r
    out = {}
    for (a, b), r in newest.items():
        back = newest.get((b, a))
        out[(a, b)] = (((r["win_rate"] + 1 - back["win_rate"]) / 2, (r["battles"] + back["battles"]) / 2)
                       if back else (r["win_rate"], r["battles"]))
    return out


def within_set(rows: list[dict] | None = None) -> list[dict]:
    """Decks ranked by mean win rate against every other deck in the set, each opponent counting equally: the
    strength a task designer sees when choosing opponents from this set.

    Entry keys: deck, rank, tier, win_rate (the mean), ci_low, ci_high (95%, from each matchup's sampling error),
    vs (opponent -> head-to-head win rate)."""
    h2h = head_to_head(rows)
    decks = sorted({a for a, _ in h2h})
    out = []
    for a in decks:
        vs = {b: h2h[(a, b)] for b in decks if b != a}
        mean = sum(p for p, _ in vs.values()) / len(vs)
        se = math.sqrt(sum(p * (1 - p) / n for p, n in vs.values())) / len(vs)
        out.append({"deck": a, "win_rate": mean, "ci_low": mean - Z95 * se, "ci_high": mean + Z95 * se,
                    "vs": {b: p for b, (p, _) in vs.items()}})
    out.sort(key=lambda o: (-o["ci_low"], o["deck"]))
    _tiers(out)
    return out


def ranking_text(entries: list[dict]) -> str:
    out = [f"{'rank':>4} {'tier':>4}  {'deck':<18} {'win %':>6}  {'95% interval':<12} {'battles':>8} {'usage':>6}  "
           "signature cards in our deck"]
    for e in entries:
        fit = "-" if e["missing"] is None else "yes" if not e["missing"] else "no, missing " + ", ".join(e["missing"])
        if e["rank"] is None:
            out.append(f"{'-':>4} {'-':>4}  {e['deck']:<18} {'n/a':>6}  {'no battles':<12} {0:>8} {'-':>6}  {fit}")
        else:
            interval = f"{e['ci_low'] * 100:.1f}-{e['ci_high'] * 100:.1f}%"
            out.append(f"{e['rank']:>4} {e['tier']:>4}  {e['deck']:<18} {e['win_rate'] * 100:>5.1f}%  {interval:<12} "
                       f"{e['battles']:>8} {e['usage'] * 100:>5.1f}%  {fit}")
    return "\n".join(out)


def within_set_text(entries: list[dict]) -> str:
    out = [f"{'rank':>4} {'tier':>4}  {'deck':<18} {'win %':>6}  95% interval"]
    for e in entries:
        out.append(f"{e['rank']:>4} {e['tier']:>4}  {e['deck']:<18} {e['win_rate'] * 100:>5.1f}%  "
                   f"{e['ci_low'] * 100:.1f}-{e['ci_high'] * 100:.1f}%")
    return "\n".join(out)


def matrix_text(entries: list[dict]) -> str:
    """Head-to-head win % of the row deck against the column deck, in the order of `entries`."""
    names = [e["deck"] for e in entries]
    short = {n: n.split("-")[0] for n in names}
    out = [f"{'':10}" + "".join(f"{short[b]:>9}" for b in names)]
    for e in entries:
        cells = "".join(f"{'-':>9}" if b == e["deck"] else f"{e['vs'][b] * 100:>9.1f}" for b in names)
        out.append(f"{short[e['deck']]:10}" + cells)
    return "\n".join(out)


def main() -> None:
    rows = load()
    print("Overall win rate (against the whole meta)")
    print(ranking_text(ranking(rows)))
    for captured, filters in sorted({(r["captured"], r["filters"]) for r in latest(rows).values()}):
        print(f"captured {captured}, CrownScribe filters: {filters}")
    inner = within_set()
    print(f"\nWithin the set: mean win rate against the other {len(inner) - 1} decks, each counting equally")
    print(within_set_text(inner))
    print("\nHead-to-head win % of the row deck against the column deck")
    print(matrix_text(inner))
    print("\nRank = lower bound of the 95% interval. Decks in one tier have overlapping intervals and cannot be told "
          "apart.\nArchetype win rates, not our exact eight cards; intervals count sampling error only.")


if __name__ == "__main__":
    main()
