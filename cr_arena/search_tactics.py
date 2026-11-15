"""Reproducible root-action probes, distinct from full-game strength results.

After each selected root action, advance 12 seconds with neither side deploying.
This measures the immediate action in isolation, not the search's assumed followups.
"""
from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from royalegym import MatchSetup
from royalegym.protocol import DeployCommand, SpawnSpec

from .decks import DEFAULT_DECK
from .game import Game
from .players import build_player
from .bots.search import SearchBot
from .bots.search_v2 import SearchV2

CASES = {
    'urgent-defense': [('HogRider', 1, 3.5, 10.5)],
    'anti-air': [('Balloon', 1, 3.5, 11.5)],
    'spell-cluster': [('Minions', 1, 3.5, 10), ('Minions', 1, 4, 10), ('Minions', 1, 3, 10)],
    'counterpush': [('Knight', 1, 3.5, 11), ('Giant', 0, 3.5, 13)],
}


def position(name):
    deck = ['Musketeer', 'Knight', 'Minions', 'Fireball', 'Giant', 'Archer', 'Cannon', 'Zap']
    g = Game(deck, DEFAULT_DECK, 1, record=False)
    ids = {c.name: c.card_id for c in g.cards}
    g.engine.reset(1, MatchSetup(decks=g.setup.decks, shuffle=0, start_tick=400, elixir_milli=[10000, 0],
                               spawns=[SpawnSpec(t, ids[n], *g.engine_point(0, x, y))
                                       for n, t, x, y in CASES[name]]))
    return g


def probe(name, spec=None):
    g = position(name)
    root = g.engine.save_state()
    moves = g.legal_moves(0)
    bot = build_player(spec) if spec else SearchV2()
    new, old = bot.decide(g, 0, '', moves), SearchBot().decide(g, 0, '', moves)
    outcomes = {}
    for label, move in [('v2', moves[new.index]), ('v1', moves[old.index]), ('wait', moves[0])]:
        g.engine.load_state(root)
        start = [sum(p.tower_hp) for p in g.state.players]
        g.engine.step([DeployCommand(0, move.slot, move.x, move.y)] if move.slot >= 0 else [], 240)
        outcomes[label] = {'move': move.label(), 'tower_damage_taken': start[0] - sum(g.state.players[0].tower_hp),
                           'tower_damage_dealt': start[1] - sum(g.state.players[1].tower_hp),
                           'tower_hp': [list(p.tower_hp) for p in g.state.players]}
    return {'v2_settings': spec, 'setup': CASES[name], 'outcomes': outcomes, 'v2_search': bot.last_search}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--config', help='optional comparison TOML to select the v2 preset')
    args = parser.parse_args()
    spec = next(p for p in tomllib.loads(Path(args.config).read_text())['players']
                if p['type'] == 'search-v2') if args.config else None
    output = {name: probe(name, spec) for name in CASES}
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + '\n')
    for name, result in output.items():
        print(name, json.dumps(result['outcomes']), flush=True)


if __name__ == '__main__':
    main()
