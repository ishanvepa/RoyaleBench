"""Deck strength for the classic decks, from CrownScribe archetype win rates: tracked snapshots and a ranking.

    uv run python -m cr_arena.deck_strength        # rank each classic deck's newest snapshot

Each classic deck is mapped to the CrownScribe (crownscribe.com) archetype it belongs to, and
data/deck_strength.csv holds that archetype's win rate and battle count (columns, caveats and refresh steps:
data/README.md). A person copies the numbers from the site. The file is append-only, one row per deck per
capture, so meta shifts stay visible; everything here reads each deck's newest row.

Decks are ranked by the lower bound of the 95% Wilson interval on win rate. Tiers group decks whose intervals
overlap the tier's best deck, so a gap between tiers is one that sampling noise cannot explain. The numbers
describe the archetype (every deck that contains its signature cards), not our exact eight cards.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from .decks import CLASSIC_DECKS

DATA = Path(__file__).resolve().parents[1] / "data" / "deck_strength.csv"
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
    tier, leader = 0, None
    for i, o in enumerate(ranked, 1):
        if leader is None or o["ci_high"] < leader["ci_low"]:  # clear of the tier's best deck: a new tier
            tier, leader = tier + 1, o
        o["rank"], o["tier"] = i, tier
    unranked = [dict(o, rank=None, tier=None) for o in sorted(out, key=lambda o: o["deck"]) if not o["battles"]]
    return ranked + unranked


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


def main() -> None:
    rows = load()
    print(ranking_text(ranking(rows)))
    for captured, filters in sorted({(r["captured"], r["filters"]) for r in latest(rows).values()}):
        print(f"\ncaptured {captured}, CrownScribe filters: {filters}")
    print("Rank = lower bound of the 95% interval. Decks in one tier have overlapping intervals and cannot be told apart.\n"
          "Archetype win rates, not our exact eight cards; intervals count sampling error only.")


if __name__ == "__main__":
    main()
