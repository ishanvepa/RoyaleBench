"""Human-play registration, delayed simulations, and stale live answer handling."""
import unittest
from pathlib import Path

from royalegym.protocol import DeployCommand, DeployStatus
from starlette.testclient import TestClient

from cr_arena.decks import DEFAULT_DECK
from cr_arena.live import BOT, BOT_SPECS, Session, app, bot_answer_command
from cr_arena.live_search_v2 import LiveSearchGame, LiveSearchV2
from cr_arena.search_v2 import frozen_search_v2_spec
from cr_arena.play_session import opponents

ROOT = Path(__file__).resolve().parents[1]


class HumanSearchV2Tests(unittest.TestCase):
    def game(self):
        game = LiveSearchGame(DEFAULT_DECK, DEFAULT_DECK, 11, record=False, command_delay_ticks=21)
        game.engine.step([], 160)
        return game

    def answer(self, game):
        move = next(m for m in game.legal_moves(BOT) if m.slot >= 0)
        return (move.slot, move.x, move.y, 'v2 choice', game.state.tick,
                game.state.players[BOT].hand[move.slot])

    def test_both_selectors_use_frozen_preset_and_websocket_advertises_it(self):
        spec = frozen_search_v2_spec()
        self.assertEqual(opponents(ROOT)['search-v2'], spec)
        self.assertEqual(BOT_SPECS['search-v2'], spec)
        self.assertEqual(spec['workers'], 1)
        with TestClient(app) as client, client.websocket_connect('/ws') as ws:
            hello = ws.receive_json()
            self.assertEqual(hello['bots']['search-v2'], spec)

    def test_live_search_keeps_delay_and_finishes_with_completed_comparison(self):
        game = self.game()
        bot = LiveSearchV2(**{k: v for k, v in frozen_search_v2_spec().items() if k != 'type'},
                           deadline_ms=0.001)
        bot.start(game, BOT)
        root = game.engine.save_state()
        decision = bot.decide(game, BOT, '', game.legal_moves(BOT))
        self.assertIsNot(bot.sim, game)
        self.assertEqual(bot.sim.command_delay_ticks, 21)
        self.assertEqual(game.engine.save_state(), root)
        self.assertEqual(decision.diagnostics['action_mode'], 'numbered-live')
        self.assertTrue(decision.diagnostics['deadline_reached'])
        self.assertFalse(decision.diagnostics['budget_exhausted'])
        self.assertEqual(len(decision.diagnostics['scenarios']), 2)
        self.assertEqual(decision.diagnostics['scenarios'][1]['phase'], 'full')
        self.assertIn(decision.index, [m.index for m in game.legal_moves(BOT)])

    def test_delayed_card_is_excluded_until_it_lands(self):
        game = self.game()
        answer = self.answer(game)
        command, _ = bot_answer_command(game, answer)
        result = game.engine.step([command], 1)
        self.assertEqual(result[0].status, DeployStatus.OK)
        self.assertTrue(game.state.players[BOT].pending)
        self.assertFalse(any(m.slot == answer[0] for m in game.legal_moves(BOT)))
        self.assertEqual([m.index for m in game.legal_moves(BOT)], list(range(len(game.legal_moves(BOT)))))
        command, raw = bot_answer_command(game, answer)
        self.assertIsNone(command)
        self.assertIn('pending', raw)

    def test_pending_card_in_nonzero_slot_is_filtered_and_rejected(self):
        game = self.game()
        move = next(m for m in game.legal_moves(BOT) if m.slot > 0)
        card = game.state.players[BOT].hand[move.slot]
        answer = (move.slot, move.x, move.y, 'v2 choice', game.state.tick, card)
        command, _ = bot_answer_command(game, answer)
        self.assertEqual(game.engine.step([command], 1)[0].status, DeployStatus.OK)
        self.assertEqual(game.state.players[BOT].pending[0][0:2], [0, card])
        self.assertFalse(any(m.slot == move.slot for m in game.legal_moves(BOT)))
        command, raw = bot_answer_command(game, answer)
        self.assertIsNone(command)
        self.assertIn('pending', raw)

    def test_fresh_answer_accepted_changed_card_illegal_and_stale_answers_discarded(self):
        game = self.game()
        answer = self.answer(game)
        command, _ = bot_answer_command(game, answer)
        self.assertEqual(game.engine.check_deploy(command), DeployStatus.OK)
        changed = (*answer[:5], -999)
        self.assertIsNone(bot_answer_command(game, changed)[0])
        illegal = (answer[0], -1000000, -1000000, *answer[3:])
        self.assertIsNone(bot_answer_command(game, illegal)[0])
        game.engine.step([], 81)
        command, raw = bot_answer_command(game, answer)
        self.assertIsNone(command)
        self.assertIn('stale', raw)

    def test_live_session_worker_returns_source_card_and_deploys_then_exits(self):
        session = Session(None, 'giant-beatdown', 'giant-beatdown', 11, 'search-v2')
        game = session.game
        game.engine.step([], 160)
        parent, process = session.conn, session.proc
        try:
            self.assertTrue(parent.poll(15), 'worker did not initialize')
            self.assertIsNone(parent.recv())
            root = game.engine.save_state()
            parent.send(root)
            self.assertTrue(parent.poll(15), 'worker did not finish searching')
            answer = parent.recv()
            self.assertEqual(len(answer), 6)
            self.assertEqual(answer[4], game.state.tick)
            self.assertEqual(game.engine.save_state(), root)
            self.assertGreaterEqual(answer[0], 0, 'expected a playable opening at this fixture')
            self.assertEqual(answer[5], game.state.players[BOT].hand[answer[0]])
            command, _ = bot_answer_command(game, answer)
            self.assertIsNotNone(command)
            result = game.engine.step([command], 1)
            self.assertEqual(result[0].status, DeployStatus.OK)
            self.assertTrue(game.state.players[BOT].pending)
            game.engine.step([], 21)
            self.assertFalse(game.state.players[BOT].pending)
            parent.send(None)
            process.join(timeout=5)
            self.assertEqual(process.exitcode, 0)
        finally:
            session.close()
        self.assertFalse(process.is_alive())


if __name__ == '__main__':
    unittest.main()
