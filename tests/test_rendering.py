"""Regression checks for portable replays and the live rendering contract.

Run with: uv run python -m unittest discover -s tests
"""

import asyncio
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import msgspec
from royalegym.render import extract_view, parse_page
from royalegym.action import PlacementOracle
from royalegym.replay import load_trace, save_trace

import re

from cr_arena.decks import CLASSIC_DECKS, DEFAULT_DECK
from cr_arena.game import Game
from cr_arena.live import Session, page
from cr_arena.rendering import embed_renderer
from cr_arena.replay import patched_html

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'runs/samples/heuristic-bot__vs__random-bot__s2.msgpack'


class RenderingTests(unittest.TestCase):
    def test_live_and_replay_embed_identical_graphics(self):
        source = (ROOT / 'cr_arena/battle_renderer.js').read_text()
        live = asyncio.run(page(None)).body.decode()
        replay = patched_html(SAMPLE, stride=100)
        self.assertIn(source, live)
        self.assertIn(source, replay)
        self.assertNotIn('__BATTLE_RENDERER__', live + replay)
        self.assertNotIn('<script src=', replay)
        payload = extract_view(replay)
        trace = load_trace(SAMPLE)
        self.assertEqual(payload['frames'][0][0], trace.frames[0].tick)
        self.assertEqual(payload['frames'][-1][0], trace.frames[-1].tick)
        self.assertEqual(payload['projectile_fields'], list(trace.header.projectile_fields))

    def test_replay_escapes_trace_text_and_title_without_resubstitution(self):
        trace = load_trace(SAMPLE)
        hostile = '</script><script>window.injected=1</script>__TITLE__'
        trace.header.cards[0] = msgspec.structs.replace(trace.header.cards[0], name=hostile)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trace.msgpack'
            save_trace(trace, path)
            replay = patched_html(path, title=hostile, stride=100)
        self.assertNotIn(hostile, replay)
        self.assertIn('&lt;/script&gt;', replay)
        self.assertEqual(extract_view(replay)['cards'][0]['name'], hostile)

    def test_live_supplies_arena_and_optional_entity_state(self):
        # Build no worker processes or sockets: these messages only read the engine.
        session = Session.__new__(Session)
        session.game = Game(DEFAULT_DECK, DEFAULT_DECK, seed=2, record=False)
        session.sub = session.game.sub
        session.delay = 0
        session.seed = 2
        session.bot_spec = {'name': 'test'}
        session.deck_names = ('test', 'test')
        session.paused = False
        session.placement = PlacementOracle(session.game.arena, session.game.engine.rules(), session.game.cards)
        session.mask_cache = {}
        init = session.init_msg()
        snapshot = session.snapshot()
        self.assertEqual(len(snapshot['masks']), 4)
        json.dumps([init, snapshot])
        self.assertEqual(init['arena']['grid'], session.game.arena.grid)
        self.assertEqual(init['arena']['half'], session.game.arena.half)
        for row, entity in zip(snapshot['en'], session.game.state.entities, strict=True):
            self.assertEqual(row[4], round(entity.x / session.sub, 3))
            self.assertEqual(row[13], entity.stun_ticks)
            self.assertEqual(row[14], [v / session.sub for v in entity.footprint])
            # spawned units keep their card's ID, so the page also gets the unit's own type
            self.assertEqual(row[18], session.game.engine.unit_types()[entity.unit_type]
                             if entity.unit_type >= 0 else None)

        for cid, (name, kind, cost, footprint) in init['cards'].items():
            card = session.game.card_by_id[cid]
            self.assertEqual((name, kind, cost), (card.name, session.game.kind_of(card), card.elixir))
            self.assertEqual(footprint, card.footprint_tiles or 0)
            self.assertEqual(footprint > 0, kind == 'BUILDING', name)

    def test_live_hand_art_covers_exactly_the_classic_deck_cards(self):
        art = (ROOT / 'cr_arena/card_art.js').read_text()
        faces = re.findall(r'^    (\w+): \["(?:common|rare|epic|legendary)",', art, re.M)
        classic = {card for deck in CLASSIC_DECKS.values() for card in deck}
        self.assertEqual(len(classic), 35)
        self.assertEqual(set(faces), classic)
        self.assertEqual(len(faces), len(classic))
        if shutil.which('node'):
            result = subprocess.run(['node'], input=art + '\nconsole.log(JSON.stringify('
                                    'CardArt.names.map(name => CardArt.svg(name))));',
                                    text=True, check=True, capture_output=True)
            portraits = json.loads(result.stdout)
            self.assertEqual(len(set(portraits)), len(classic), 'each card needs its own portrait')
        live = asyncio.run(page(None)).body.decode()
        self.assertIn(art, live)
        self.assertNotIn('__CARD_ART__', live)
        self.assertNotIn('<script src=', live)

    def test_replay_names_unit_types_for_spawned_units(self):
        view = extract_view(patched_html(SAMPLE, stride=100))
        self.assertEqual(view['unit_types'], list(load_trace(SAMPLE).header.unit_types))
        self.assertIn('unit_type', view['entity_fields'])

    def test_invalid_stride_and_missing_renderer_marker_fail_explicitly(self):
        with self.assertRaises(ValueError):
            patched_html(SAMPLE, stride=0)
        with self.assertRaises(ValueError):
            embed_renderer('<html></html>')

    @unittest.skipUnless(shutil.which('node'), 'Node is required to execute the replay scripts')
    def test_exported_replay_scripts_can_seek_flip_and_interpolate(self):
        scripts = parse_page(patched_html(SAMPLE, stride=2)).scripts
        subprocess.run(['node', str(ROOT / 'tests/check_replay_page.cjs')],
                       input=json.dumps(scripts), text=True, check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
