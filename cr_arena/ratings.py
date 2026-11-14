"""Bradley-Terry ratings on the Elo scale, fitted on all games at once, with bootstrap intervals.

Draws count as half a win for each side. One player can be pinned (default: random-bot = 400)
so the scale has a fixed zero point, like chess benchmarks pin a random mover.
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from pathlib import Path


def load_results(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _games(results: list[dict]) -> list[tuple[str, str, float]]:
    """(a, b, score_of_a) per match."""
    out = []
    for r in results:
        s = {0: 1.0, 1: 0.0, 2: 0.5}[r["winner"]]
        out.append((r["blue"], r["red"], s))
    return out


def fit_bt(games, players, iters: int = 2000, prior: float = 0.5) -> dict[str, float]:
    """Minorize-maximize (Hunter 2004) with a small symmetric prior (a virtual draw vs every
    other player) so ratings stay finite for undefeated or winless players."""
    wins = defaultdict(float)
    pair_n = defaultdict(float)
    for a, b, s in games:
        wins[a] += s
        wins[b] += 1 - s
        pair_n[(a, b)] += 1
        pair_n[(b, a)] += 1
    for a in players:
        for b in players:
            if a != b:
                wins[a] += prior / 2
                pair_n[(a, b)] += prior / 2
    p = {x: 1.0 for x in players}
    for _ in range(iters):
        new = {}
        for a in players:
            denom = sum(pair_n[(a, b)] / (p[a] + p[b]) for b in players if b != a and pair_n[(a, b)] > 0)
            new[a] = wins[a] / denom if denom > 0 else p[a]
        g = math.exp(sum(math.log(v) for v in new.values()) / len(new))
        new = {k: v / g for k, v in new.items()}
        if max(abs(new[k] - p[k]) for k in p) < 1e-10:
            p = new
            break
        p = new
    return {k: 400 * math.log10(v) for k, v in p.items()}


def ratings(results: list[dict], anchor: str | None = "random-bot", anchor_value: float = 400.0,
            bootstrap: int = 500, seed: int = 0) -> list[dict]:
    games = _games(results)
    players = sorted({x for g in games for x in g[:2]})
    if len(players) < 2:
        return []

    def shifted(r):
        if anchor in r:
            off = anchor_value - r[anchor]
        else:
            off = 1500 - sum(r.values()) / len(r)
        return {k: v + off for k, v in r.items()}

    point = shifted(fit_bt(games, players))
    rng = random.Random(seed)
    samples = defaultdict(list)
    for _ in range(bootstrap):
        bs = [games[rng.randrange(len(games))] for _ in games]
        for k, v in shifted(fit_bt(bs, players, iters=500)).items():
            samples[k].append(v)
    rec = defaultdict(lambda: [0, 0, 0])  # W D L
    for a, b, s in games:
        i = {1.0: 0, 0.5: 1, 0.0: 2}[s]
        rec[a][i] += 1
        rec[b][2 - i] += 1
    out = []
    for k in players:
        xs = sorted(samples[k])
        lo, hi = xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs)) - 1]
        w, d, l = rec[k]
        out.append({"player": k, "rating": round(point[k]), "ci_low": round(lo), "ci_high": round(hi),
                    "games": w + d + l, "W": w, "D": d, "L": l,
                    "score": round((w + 0.5 * d) / max(1, w + d + l), 3)})
    out.sort(key=lambda r: -r["rating"])
    return out


def leaderboard_text(rows: list[dict], anchor: str | None = "random-bot") -> str:
    lines = [f"{'#':>2}  {'player':<28} {'rating':>6}  {'95% CI':>13}  {'games':>5}  {'W-D-L':>9}  {'score':>5}"]
    for i, r in enumerate(rows, 1):
        pin = " (pinned)" if r["player"] == anchor else ""
        lines.append(f"{i:>2}  {r['player']:<28} {r['rating']:>6}  [{r['ci_low']:>5},{r['ci_high']:>5}]  "
                     f"{r['games']:>5}  {r['W']:>2}-{r['D']}-{r['L']:<3}  {r['score']:>5}{pin}")
    return "\n".join(lines)


def head_to_head(results: list[dict]) -> str:
    players = sorted({r["blue"] for r in results} | {r["red"] for r in results})
    score = defaultdict(float)
    n = defaultdict(int)
    for a, b, s in _games(results):
        score[(a, b)] += s
        score[(b, a)] += 1 - s
        n[(a, b)] += 1
        n[(b, a)] += 1
    w = max(len(p) for p in players)
    head = " " * (w + 2) + "  ".join(f"{p[:10]:>10}" for p in players)
    rows = [head]
    for a in players:
        cells = [f"{'-':>10}" if a == b else (f"{score[(a, b)]:.1f}/{n[(a, b)]}".rjust(10) if n[(a, b)] else f"{'':>10}")
                 for b in players]
        rows.append(f"{a:<{w}}  " + "  ".join(cells))
    return "\n".join(rows)


def standings(results: list[dict]) -> list[dict]:
    """Plain round-robin table: sorted by wins, then fewer losses, then crown difference."""
    import json as _json

    t: dict[str, dict] = {}
    for r in results:
        crowns = r.get("crowns")
        crowns = _json.loads(crowns) if isinstance(crowns, str) else (crowns or [0, 0])
        for team, name in ((0, r["blue"]), (1, r["red"])):
            row = t.setdefault(name, {"player": name, "games": 0, "W": 0, "D": 0, "L": 0, "crowns_for": 0, "crowns_against": 0})
            row["games"] += 1
            row["crowns_for"] += crowns[team]
            row["crowns_against"] += crowns[1 - team]
            if r["winner"] == 2:
                row["D"] += 1
            elif r["winner"] == team:
                row["W"] += 1
            else:
                row["L"] += 1
    rows = sorted(t.values(), key=lambda x: (-x["W"], x["L"], -(x["crowns_for"] - x["crowns_against"]), x["player"]))
    for i, row in enumerate(rows, 1):
        row["rank"] = i
        row["win_rate"] = row["W"] / row["games"] if row["games"] else 0.0
    return rows


def standings_text(rows: list[dict]) -> str:
    out = [f"{'#':>2}  {'player':<28} {'games':>5}  {'W':>3} {'D':>3} {'L':>3}  {'win %':>6}  crowns +/-"]
    for r in rows:
        out.append(f"{r['rank']:>2}  {r['player']:<28} {r['games']:>5}  {r['W']:>3} {r['D']:>3} {r['L']:>3}  "
                   f"{r['win_rate'] * 100:>5.1f}%  {r['crowns_for']}/{r['crowns_against']}")
    return "\n".join(out)
