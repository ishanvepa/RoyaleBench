"""Capacity admission, worker lifecycle, and concurrent live-game persistence."""

import asyncio
import json
import tempfile
import time
import unittest
from contextlib import ExitStack, suppress
from pathlib import Path
import unittest.mock
from unittest.mock import patch

import msgspec
from starlette.testclient import TestClient

from cr_arena import live
from cr_arena.db import DB
from cr_arena.leaderboard import Leaderboard


START = {"t": "start", "deck": "giant-beatdown", "seed": 11, "ranked": False}


def receive(ws, kind):
    for _ in range(100):
        message = ws.receive_json()
        if message["t"] == kind:
            return message
        if message["t"] in ("error", "invalid", "busy"):
            raise AssertionError(message)
    raise AssertionError(f"Did not receive {kind}")


class MemorySocket:
    def __init__(self):
        self.messages = []
        self.closed = False

    async def send_text(self, text):
        self.messages.append(json.loads(text))

    async def close(self, **_kwargs):
        self.closed = True


class PublicPlayTests(unittest.TestCase):
    def tearDown(self):
        for session in list(live.ACTIVE):
            session.close()

    def test_capacity_games_next_refused_and_quit_disconnect_release_slots(self):
        cap = live.MAX_GAMES
        with ExitStack() as stack:
            client = stack.enter_context(TestClient(live.create_app(public=True)))
            sockets = [stack.enter_context(client.websocket_connect('/ws')) for _ in range(cap + 2)]
            for ws in sockets:
                hello = ws.receive_json()
                self.assertEqual(hello['max_games'], cap)
                self.assertEqual(list(hello['bots']), ['planner'])
                self.assertEqual(hello['fixed_opponent'], {'bot': 'planner', 'deck': 'hog-2.6-cycle'})
            self.assertEqual(client.get('/health').json()['active_games'], 0)
            for ws in sockets[:cap]:
                ws.send_json(START)
                init = receive(ws, 'init')
                self.assertEqual(init['opp'], 'planner-bot')
                self.assertEqual(init['decks'], ['giant-beatdown', 'hog-2.6-cycle'])
            self.assertEqual(client.get('/health').json()['active_games'], cap)
            sockets[cap].send_json(START)
            busy = receive(sockets[cap], 'busy')
            self.assertEqual(busy['n'], cap)
            self.assertEqual(busy['message'], 'Server at capacity — please try again shortly.')
            sockets[0].send_json({'t': 'quit'})
            self.wait_count(client, cap - 1)
            sockets[cap].send_json(START)
            receive(sockets[cap], 'init')
            sockets[1].close()
            self.wait_count(client, cap - 1)
            sockets[cap + 1].send_json(START)
            receive(sockets[cap + 1], 'init')
            self.assertEqual(client.get('/health').json()['active_games'], cap)
        self.assertEqual(len(live.ACTIVE), 0)

    def test_public_planner_gets_the_same_workers_as_a_lone_local_game(self):
        # Planner has no time budget, so fewer workers means staler answers: keep the two modes equal.
        public = live.create_app(public=True).state.bot_specs['planner']
        self.assertEqual(public['workers'], live.PLANNER_WORKERS)
        launched = []

        class Proc:
            def __init__(self, target, args, daemon):
                launched.append(args[3])

            def start(self):
                pass

        class Ctx:
            Process = Proc

            def Event(self):
                return None

            def Pipe(self):
                return unittest.mock.Mock(), unittest.mock.Mock()

        with patch.object(live.mp, 'get_context', lambda _kind: Ctx()), patch.object(live, 'ACTIVE', set()):
            live.Session(MemorySocket(), 'giant-beatdown', 'hog-2.6-cycle', 11, 'planner')
        self.assertEqual(launched[0]['workers'], live.PLANNER_WORKERS)

    def wait_count(self, client, count):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if client.get('/health').json()['active_games'] == count:
                return
            time.sleep(.01)
        self.fail(f'Expected {count} active games')

    def test_public_mode_pins_opponent_and_deck_and_rejects_malformed_input(self):
        with ExitStack() as stack:
            client = stack.enter_context(TestClient(live.create_app(public=True)))
            client.get('/')
            player_id = client.cookies[live.PLAYER_COOKIE]
            ws = stack.enter_context(client.websocket_connect('/ws'))
            ws.receive_json()
            for message in ([], {**START, 'seed': -1},
                            {**START, 'deck': []}):
                ws.send_json(message)
                self.assertEqual(ws.receive_json()['t'], 'invalid')
            self.assertEqual(len(live.ACTIVE), 0)
            ws.send_json({**START, 'bot': 'heuristic', 'opp_deck': 'lavaloon'})
            init = receive(ws, 'init')
            self.assertEqual(init['opp'], 'planner-bot')
            self.assertEqual(init['decks'][1], 'hog-2.6-cycle')
            initial = receive(ws, 's')
            self.assertEqual(len(initial['masks']), 4)
            for mask in initial['masks']:
                self.assertEqual(mask['card'], initial['me']['hand'][mask['slot']][0])
            for message in ({'t': 'mask', 'slot': -1}, {'t': 'play', 'slot': 0, 'x': 'NaN', 'y': 8}):
                ws.send_json(message)
                receive(ws, 'invalid')
            self.assertEqual(len(live.ACTIVE), 1)
            self.assertEqual(next(iter(live.ACTIVE)).player_id, player_id)
            self.assertIsNone(next(iter(live.ACTIVE)).leaderboard)
            receive(ws, 's')

    def test_unranked_completions_save_replays_without_recording_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'arena.db'
            DB(db_path).close()
            board = Leaderboard(Path(tmp) / 'leaderboard.csv')
            with patch.object(live, 'OUT_DIR', Path(tmp)), patch.object(live, 'DB', lambda: DB(db_path)):
                for name in (None, 'Load check'):
                    session = live.Session(MemorySocket(), 'giant-beatdown', 'giant-beatdown', 11,
                                           leaderboard=board, player_name=name, ranked=False)
                    try:
                        hp = [list(player.tower_hp) for player in session.game.state.players]
                        hp[0][1] = 1000
                        setup = msgspec.structs.replace(session.game.setup, tower_hp=hp)
                        session.game.engine.reset(session.seed, setup)
                        session.game.recorder.begin(session.game.engine, session.seed, setup)
                        session.game.engine.step([], 20_000)
                        self.assertTrue(session.game.over)
                        result = session.save()
                        self.assertEqual(result['winner'], 1)
                        self.assertTrue(result['saved'], result)
                    finally:
                        session.close()
            self.assertEqual(board.standings('test')['total'], 0)
            self.assertFalse(board.path.exists())
            self.assertEqual(len(list((Path(tmp) / 'replays').glob('*.msgpack'))), 2)

    def test_worker_failure_slow_socket_and_expiry_free_slot(self):
        async def scenario(kind):
            ws = MemorySocket()
            session = live.Session(ws, 'giant-beatdown', 'giant-beatdown', 11)
            if kind == 'worker':
                session.proc.terminate()
                session.proc.join(timeout=5)
            elif kind == 'expired':
                session.started_at -= live.MAX_SESSION_SECONDS + 1
            else:
                async def blocked(_text):
                    await asyncio.Event().wait()
                ws.send_text = blocked
            with patch.object(live, 'SEND_TIMEOUT_SECONDS', .02), self.assertLogs(live.log, level='ERROR') if kind != 'expired' else ExitStack():
                await asyncio.wait_for(session.run(), timeout=5)
            self.assertNotIn(session, live.ACTIVE)
            self.assertFalse(session.proc.is_alive())
            self.assertTrue(session.closed)
            if kind == 'expired':
                self.assertIn('expired', ws.messages[-1]['message'])
            else:
                self.assertTrue(ws.closed)
        for kind in ('worker', 'expired', 'slow'):
            with self.subTest(kind=kind):
                asyncio.run(scenario(kind))

    def test_bot_timing_reports_response_time_and_source_age(self):
        async def scenario():
            ws = MemorySocket()
            session = live.Session(ws, 'giant-beatdown', 'giant-beatdown', 11)
            task = asyncio.create_task(session.run())
            try:
                async with asyncio.timeout(15):
                    while not any(m['t'] == 'bot_timing' for m in ws.messages):
                        if task.done():
                            self.fail(f'Game stopped before a bot decision: {ws.messages}')
                        await asyncio.sleep(.01)
                timing = next(m for m in ws.messages if m['t'] == 'bot_timing')
                self.assertGreater(timing['decision_ms'], 0)
                self.assertGreaterEqual(timing['source_age_ticks'], 0)
                self.assertLessEqual(timing['source_age_ticks'], session.game.state.tick)
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            self.assertNotIn(session, live.ACTIVE)
            self.assertFalse(session.proc.is_alive())
        asyncio.run(scenario())

    def test_clock_holds_at_tick_zero_until_the_bot_is_ready(self):
        class Gated:  # hides the worker's "ready" until the test opens the gate
            def __init__(self, conn):
                self.conn, self.open = conn, False

            def poll(self):
                return self.open and self.conn.poll()

            def __getattr__(self, name):
                return getattr(self.conn, name)

        async def scenario(timeout_s):
            ws = MemorySocket()
            session = live.Session(ws, 'giant-beatdown', 'giant-beatdown', 11)
            session.conn = gate = Gated(session.conn)
            with patch.object(live, 'BOT_READY_TIMEOUT_SECONDS', timeout_s), \
                    self.assertLogs(live.log, level='WARNING') if timeout_s < 1 else ExitStack():
                task = asyncio.create_task(session.run())
                try:
                    await asyncio.sleep(.5)
                    snaps = [m for m in ws.messages if m['t'] == 's']
                    if timeout_s >= 1:
                        # Held: one tick-0 snapshot marked as starting, and nothing more.
                        self.assertEqual([(m['k'], m['starting']) for m in snaps], [(0, True)])
                        gate.open = True
                    async with asyncio.timeout(15):
                        while not any(m['t'] == 's' and m['k'] > 0 for m in ws.messages):
                            if task.done():
                                self.fail(f'Game stopped: {ws.messages}')
                            await asyncio.sleep(.01)
                    started = next(m for m in ws.messages if m['t'] == 's' and m['k'] > 0)
                    self.assertFalse(started['starting'])
                finally:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
            self.assertNotIn(session, live.ACTIVE)

        for timeout_s in (30.0, 0.1):  # released by the bot's ready; started anyway after the limit
            with self.subTest(timeout_s=timeout_s):
                asyncio.run(scenario(timeout_s))

    def test_ten_natural_completions_save_unique_replays_and_release_open_sockets(self):
        async def finish_games(board):
            sessions = [live.Session(MemorySocket(), 'giant-beatdown', 'giant-beatdown', seed,
                                     leaderboard=board, player_id='test-player', player_name='Alice, the Great')
                        for seed in range(10)]
            for index, session in enumerate(sessions):
                hp = [list(player.tower_hp) for player in session.game.state.players]
                if index:  # Five wins and four losses on tower HP; level seed 0 goes to blue by parity.
                    hp[index % 2][1] = 1000
                setup = msgspec.structs.replace(session.game.setup, tower_hp=hp)
                session.game.engine.reset(session.seed, setup)
                session.game.recorder.begin(session.game.engine, session.seed, setup)
                session.game.engine.step([], 20_000)
                self.assertTrue(session.game.over)
            await asyncio.gather(*(session.run() for session in sessions))
            self.assertEqual(len(live.ACTIVE), 0)
            for session in sessions:
                self.assertFalse(session.proc.is_alive())
                self.assertFalse(session.ws.closed)
                self.assertEqual(session.ws.messages[-1]['t'], 'over')
                self.assertTrue(session.ws.messages[-1]['saved'], session.ws.messages[-1])
            return [session.ws.messages[-1]['saved'] for session in sessions]

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'arena.db'
            # Create the schema once, as the deployed process does before serving traffic.
            DB(db_path).close()
            with patch.object(live, 'OUT_DIR', Path(tmp)), patch.object(live, 'DB', lambda: DB(db_path)):
                board = Leaderboard(Path(tmp) / 'leaderboard.csv')
                ids = asyncio.run(finish_games(board))
                # Finished engine outcomes, rather than client-submitted scores, feed the CSV.
                db = DB(db_path)
                try:
                    winners = [r['winner'] for r in db.query('SELECT winner FROM matches')]
                finally:
                    db.close()
                you = Leaderboard(board.path).standings('test-player')['you']
                self.assertEqual(you['wins'], winners.count(0))
                self.assertEqual(you['losses'], winners.count(1))
                self.assertEqual((you['wins'], you['losses']), (6, 4))  # all ten games have a winner
                self.assertEqual(you['name'], 'Alice, the Great')
            self.assertEqual(len(set(ids)), 10)
            self.assertEqual(len(list((Path(tmp) / 'replays').glob('*.msgpack'))), 10)
            db = DB(db_path)
            try:
                self.assertEqual(db.query('SELECT COUNT(*) AS n FROM matches WHERE status = ?', ('done',))[0]['n'], 10)
                self.assertEqual(db.query('SELECT total_matches FROM jobs')[0]['total_matches'], 10)
            finally:
                db.close()


if __name__ == '__main__':
    unittest.main()
