"""Paired, bots-only search comparison with raw matches and a frozen manifest.

Unlike tournament's classic preset schedule, every requested seed is used for
every requested deck. Each case is played with seats swapped. No credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import random
import subprocess
import time
import tomllib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .decks import CLASSIC_DECKS
from .game import Game
from .match import play_match
from .players import build_player


class EngineMeter:
    """Read-only instrumentation around private engines, applied to both bots."""
    def __init__(self, engine):
        self.engine = engine
        self.ticks = self.loads = 0

    def __getattr__(self, name):
        return getattr(self.engine, name)

    def load_state(self, root):
        self.loads += 1
        return self.engine.load_state(root)

    def step(self, commands, ticks):
        before = self.engine.state().tick
        result = self.engine.step(commands, ticks)
        self.ticks += self.engine.state().tick - before
        return result


def _match(job):
    spec, case, out_dir = job
    blue, red = [build_player(s) for s in spec]
    # v1 has no timing instrumentation; measure at the player boundary for both.
    measurements = [[], []]
    meters = [None, None]
    rollout_counts = [0, 0]
    for team, player in enumerate((blue, red)):
        original_start = player.start
        def start(*args, _start=original_start, _player=player, _team=team):
            _start(*args)
            meters[_team] = EngineMeter(_player.sim.engine)
            _player.sim.engine = meters[_team]
        player.start = start
        original = player.decide
        def timed(*args, _original=original, _team=team, _player=player):
            t0 = time.perf_counter()
            decision = _original(*args)
            decision.latency_s = time.perf_counter() - t0
            measurements[_team].append(decision.latency_s)
            rollout_counts[_team] += (_player.last_search['rollouts'] if hasattr(_player, 'last_search')
                                     else len(args[3]) * _player.rollouts)
            return decision
        player.decide = timed
    result = play_match(blue, red, CLASSIC_DECKS[case['deck_a']], CLASSIC_DECKS[case['deck_b']],
                        case['seed'], case['id'], Path(out_dir), record=True)
    result['simulated_work'] = {p.name: {'ticks': meters[t].ticks, 'state_loads': meters[t].loads,
                                                 'rollouts': rollout_counts[t]}
                                for t, p in enumerate((blue, red))}
    result['case'] = case
    result['decision_latency_s'] = {p.name: measurements[t] for t, p in enumerate((blue, red))}
    return result


def summarize(results, candidate):
    wins = draws = losses = 0
    cases, latency, by_deck = {}, {}, {}
    for r in results:
        seat = 0 if r['blue'] == candidate else 1
        score = .5 if r['winner'] == 2 else float(r['winner'] == seat)
        wins += score == 1
        draws += score == .5
        losses += score == 0
        key = r['case']['pair']
        cases.setdefault(key, []).append(score)
        deck = r['case']['matchup']
        by_deck.setdefault(deck, []).append(score)
        for p, values in r['decision_latency_s'].items():
            latency.setdefault(p, []).extend(values)
    pairs = [sum(v) / len(v) for v in cases.values() if len(v) == 2]
    rng = random.Random(0)
    bootstrap = sorted(sum(rng.choices(pairs, k=len(pairs))) / len(pairs) for _ in range(10000)) if pairs else []
    def percentile(values, p):
        values = sorted(values)
        return values[min(len(values) - 1, int(p * len(values)))] if values else None
    positive = sum(v > .5 for v in pairs)
    negative = sum(v < .5 for v in pairs)
    n = positive + negative
    sign_p = sum(math.comb(n, k) for k in range(positive, n + 1)) / 2**n if n else 1.0
    work = {}
    for r in results:
        for p, counters in r.get('simulated_work', {}).items():
            totals = work.setdefault(p, {k: 0 for k in counters})
            for k, v in counters.items():
                totals[k] += v
    return {'simulated_work': work, 'paired_sign_test_one_sided_p': sign_p, 'positive_pairs': positive, 'negative_pairs': negative,
            'wins': wins, 'draws': draws, 'losses': losses, 'score': (wins + draws / 2) / len(results),
            'completed_pairs': len(pairs),
            'paired_bootstrap_95': [percentile(bootstrap, .025), percentile(bootstrap, .975)],
            'score_by_matchup': {k: sum(v) / len(v) for k, v in by_deck.items()},
            'latency_s': {p: {'mean': sum(v)/len(v), 'p95': percentile(v, .95), 'decisions': len(v)}
                          for p, v in latency.items()},
            'illegal_actions': sum(r[s]['illegal_or_unparsed'] for r in results for s in ('stats_blue', 'stats_red'))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', default='configs/search_v2.toml')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seeds', type=int, nargs='+', default=[1])
    ap.add_argument('--decks', nargs='+', default=['giant-beatdown', 'hog-2.6-cycle', 'lavaloon'], choices=CLASSIC_DECKS)
    ap.add_argument('--cross-decks', action='store_true', help='also compare both deck assignments for distinct decks')
    ap.add_argument('--parallel', type=int, default=2)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = tomllib.loads(Path(args.config).read_text())
    specs = cfg['players']
    if len(specs) != 2 or {s['type'] for s in specs} != {'search', 'search-v2'}:
        ap.error('config must contain exactly search and search-v2')
    if cfg['tournament'].get('decision_ticks', 40) != 40:
        ap.error('comparison currently requires decision_ticks=40')
    if len({s['name'] for s in specs}) != 2 or args.parallel < 1:
        ap.error('require distinct player names and parallel >= 1')
    candidate = next(s['name'] for s in specs if s['type'] == 'search-v2')
    matchups = [(d, d) for d in args.decks]
    if args.cross_decks:
        matchups += [(a, b) for a in args.decks for b in args.decks if a != b]
    jobs = []
    for a, b in matchups:
        for seed in args.seeds:
            pair = f'{a}__{b}__s{seed}'
            for swap in (False, True):
                ordered = specs[::-1] if swap else specs
                da, db = (b, a) if swap else (a, b)
                case = {'pair': pair, 'matchup': f'{a}__{b}', 'seed': seed, 'deck_a': da, 'deck_b': db,
                        'id': f'{pair}__swap{int(swap)}'}
                jobs.append((ordered, case, str(out)))
    engine = Game(CLASSIC_DECKS[args.decks[0]], CLASSIC_DECKS[args.decks[0]], 0, record=False).engine
    manifest = {'engine_identity': engine.engine_identity(), 'card_table_stamp': engine.card_table_stamp(), 'config': cfg, 'seeds': args.seeds, 'matchups': matchups,
                'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'diff_sha256': hashlib.sha256(subprocess.check_output(['git', 'diff', 'HEAD'])).hexdigest(),
                'uv_lock_sha256': hashlib.sha256(Path('uv.lock').read_bytes()).hexdigest(),
                'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                  [*Path('cr_arena').rglob('*.py'), Path('pyproject.toml'), Path(args.config)]},
                'dependencies': {p: importlib.metadata.version(p) for p in ('royalegym', 'royalesim')},
                'python': platform.python_version(), 'engine_meter': 'exact ticks via state reads before/after each private step on both bots', 'decision_ticks': 40, 'command_delay_ticks': 0,
                'information_mode': 'omniscient', 'action_mode': 'numbered',
                'criterion': 'Held-out improvement requires score > 0.5 and one-sided exact paired sign-test p < 0.05; tuning runs remain exploratory.',
                'cases': [j[1] for j in jobs]}
    manifest = json.loads(json.dumps(manifest))  # canonical JSON shapes for resume comparisons
    manifest_path = out / 'manifest.json'
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        provenance = {'commit', 'diff_sha256'}
        if {k: v for k, v in previous.items() if k not in provenance} != {k: v for k, v in manifest.items() if k not in provenance}:
            raise SystemExit('output already has a different manifest; choose a new directory')
        manifest = previous
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    source_dir = out / 'source'
    for name in [*manifest['source_sha256'], 'uv.lock']:
        relative = Path(name).name if Path(name).is_absolute() else name
        dest = source_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(Path(name).read_bytes())
    results_path = out / 'results.json'
    results = json.loads(results_path.read_text()) if results_path.exists() else []
    done = {r['match_id'] for r in results}
    with ProcessPoolExecutor(max_workers=args.parallel) as pool:
        futures = [pool.submit(_match, j) for j in jobs if j[1]['id'] not in done]
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            results.sort(key=lambda r: r['match_id'])
            results_path.write_text(json.dumps(results, indent=2) + '\n')
            summary = summarize(results, candidate)
            (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
            print(f"{len(results)}/{len(jobs)} {r['match_id']}: winner={r['winner']} crowns={r['crowns']} wall={r['wall_s']}s; "
                  f"v2 W/D/L={summary['wins']}/{summary['draws']}/{summary['losses']}", flush=True)


if __name__ == '__main__':
    main()
