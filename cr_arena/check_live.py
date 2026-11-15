"""Exercise real WebSocket matches and check capacity and response timing.

    uv run --frozen python -m cr_arena.check_live --seconds 30
    uv run --frozen python -m cr_arena.check_live --full-games --output /tmp/live-check.json

Run against a disposable public-mode server: this starts unranked games and saves
completed replays without changing the leaderboard. By default it fills every advertised slot; --sessions selects a smaller load.
It needs that many free slots. The scripted human simply cycles affordable
cards into valid positions; it is a transport/load check, not a bot benchmark.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from contextlib import AsyncExitStack
from pathlib import Path

from websockets.asyncio.client import connect

from .decks import CLASSIC_DECKS


def percentile(values: list[float], p: float) -> float:
    return round(sorted(values)[max(0, math.ceil(len(values) * p) - 1)], 2) if values else 0.0


async def until(ws, kind: str) -> dict:
    async with asyncio.timeout(15):
        while True:
            message = json.loads(await ws.recv())
            if message['t'] == kind:
                return message
            if message['t'] in ('error', 'invalid', 'busy'):
                raise RuntimeError(message)


async def play(ws, init: dict, seconds: float) -> dict:
    start = time.perf_counter()
    last_play = start
    hand_masks = {}
    first_tick = first_at = last_tick = last_at = None
    gaps, accepted, bot_decisions, bot_ages = [], [], [], []
    pending_play = None
    ended, saved = False, None
    actions = mask_updates = bot_actions = 0
    half = init['arena']['half']
    async with asyncio.timeout(seconds + 20):
        while time.perf_counter() - start < seconds:
            message = json.loads(await ws.recv())
            now = time.perf_counter()
            kind = message['t']
            if kind == 'over':
                if not message.get('saved'):
                    raise RuntimeError(f'Match was not saved: {message}')
                ended, saved = True, message['saved']
                break
            if kind in ('error', 'invalid', 'busy'):
                raise RuntimeError(message)
            if kind == 's':
                state = message
                updates = state.get('masks', [])
                mask_updates += len(updates)
                hand_masks.update((m['slot'], m) for m in updates)
                for slot, (cid, _cost) in enumerate(state['me']['hand']):
                    mask = hand_masks.get(slot)
                    if mask is None or mask['card'] != cid:
                        raise RuntimeError('Hand was displayed without its preloaded placement mask')
                    if len(mask['m']) != mask['width'] * mask['height']:
                        raise RuntimeError('Invalid preloaded placement mask dimensions')
                # Discard connection/process startup and queued initial snapshots.
                if now - start > 2:
                    if first_at is None:
                        first_at, first_tick = now, state['k']
                    if last_at is not None:
                        gaps.append((now - last_at) * 1000)
                    last_at, last_tick = now, state['k']
                if pending_play is not None:
                    slot, sent = pending_play
                    if any(p[0] == slot for p in state['me']['pend']):
                        accepted.append((now - sent) * 1000)
                        pending_play = None
                if pending_play is None and now - last_play >= .45:
                    choices = [(cost, slot) for slot, (cid, cost) in enumerate(state['me']['hand'])
                               if cid >= 0 and cost * 1000 <= state['me']['e']
                               and not any(p[0] == slot for p in state['me']['pend'])]
                    if choices:
                        _, slot = choices[actions % len(choices)]
                        mask = hand_masks[slot]
                        card = init['cards'][str(mask['card'])]
                        target_y = 24 if card[1] == 'SPELL' else 10
                        points = [(abs((i // mask['width'] + .5) / half - target_y), i)
                                  for i, valid in enumerate(mask['m']) if valid == '1']
                        if points:
                            _, index = min(points)
                            await ws.send(json.dumps({'t': 'play', 'slot': slot,
                                                      'x': (index % mask['width'] + .5) / half,
                                                      'y': (index // mask['width'] + .5) / half}))
                            pending_play = (slot, time.perf_counter())
                            last_play = now
                            actions += 1
            elif kind == 'bot_timing':
                bot_decisions.append(message['decision_ms'])
                bot_ages.append(message['source_age_ticks'])
            elif kind == 'ev':
                if message['who'] == 0 and not message['ok']:
                    pending_play = None
                elif message['who'] == 1 and message['ok']:
                    bot_actions += 1
    if first_at is None or last_at is None or last_at <= first_at or not mask_updates or not accepted:
        raise RuntimeError('Insufficient game frames or accepted plays to measure responsiveness')
    return {'completed': ended, 'saved': saved, 'elapsed_s': round(time.perf_counter() - start, 2),
            'actions': actions, 'bot_actions': bot_actions,
            'opponent': init['opp'], 'opponent_deck': init['decks'][1],
            'ticks_per_second': round((last_tick - first_tick) / (last_at - first_at), 2),
            'snapshot_gap_p95_ms': percentile(gaps, .95),
            'snapshot_gap_max_ms': round(max(gaps, default=0), 2),
            'mask_updates_received': mask_updates, 'preloaded_masks_ready': True,
            'bot_decisions': len(bot_decisions),
            'bot_decision_p95_ms': percentile(bot_decisions, .95) if bot_decisions else None,
            'bot_decision_max_ms': max(bot_decisions) if bot_decisions else None,
            'bot_source_age_p95_ticks': percentile(bot_ages, .95) if bot_ages else None,
            'bot_source_age_max_ticks': max(bot_ages) if bot_ages else None,
            'input_to_pending_p95_ms': percentile(accepted, .95)}


async def check(url: str, seconds: float, full_games: bool, sessions: int | None = None) -> dict:
    socket_url = url.rstrip('/').replace('https://', 'wss://').replace('http://', 'ws://') + '/ws'
    async with AsyncExitStack() as stack:
        first = await stack.enter_async_context(connect(socket_url))
        hello = await until(first, 'hello')
        capacity = hello['max_games']
        count = capacity if sessions is None else sessions
        if not 1 <= count <= capacity:
            raise ValueError(f'--sessions must be between 1 and the advertised capacity ({capacity})')
        sockets = [first]
        for _ in range(count):  # one extra connection checks refusal and slot reuse
            ws = await stack.enter_async_context(connect(socket_url))
            await until(ws, 'hello')
            sockets.append(ws)
        for i, ws in enumerate(sockets[:count]):
            deck = list(CLASSIC_DECKS)[i % len(CLASSIC_DECKS)]
            await ws.send(json.dumps({'t': 'start', 'deck': deck, 'seed': i + 11, 'ranked': False}))
        initial = await asyncio.gather(*(until(ws, 'init') for ws in sockets[:count]))
        extra = sockets[-1]
        refused_at_capacity = None
        if count == capacity:
            await extra.send(json.dumps({'t': 'start', 'deck': 'giant-beatdown', 'ranked': False}))
            refused = await until(extra, 'busy')
            if refused['n'] != capacity:
                raise RuntimeError(f'Expected {capacity} occupied slots: {refused}')
            refused_at_capacity = True
        # Reuse a slot while the other matches are still active, before any finish.
        await sockets[0].send(json.dumps({'t': 'quit'}))
        for _ in range(50):
            await extra.send(json.dumps({'t': 'start', 'deck': list(CLASSIC_DECKS)[0], 'seed': 11, 'ranked': False}))
            response = json.loads(await extra.recv())
            if response['t'] == 'init':
                initial[0] = response
                break
            if response['t'] != 'busy':
                raise RuntimeError(response)
            await asyncio.sleep(.1)
        else:
            raise RuntimeError('Quit did not release a slot')
        await sockets[0].close()
        players = [extra, *sockets[1:count]]
        results = await asyncio.gather(*(play(ws, init, seconds) for ws, init in zip(players, initial)))
        for ws in players:
            await ws.send(json.dumps({'t': 'quit'}))
        await asyncio.gather(*(ws.close() for ws in players))
        gameplay_passed = (min(r['ticks_per_second'] for r in results) >= 19 and
                           all(r['preloaded_masks_ready'] and r['bot_actions'] > 0 and
                               r['bot_decisions'] > 0 for r in results) and
                           (not full_games or all(r['completed'] for r in results)))
        latency_target_met = max(r['input_to_pending_p95_ms'] for r in results) < 150
        return {'passed': gameplay_passed and latency_target_met, 'gameplay_passed': gameplay_passed,
                'latency_target_met': latency_target_met, 'input_p95_target_ms': 150,
                'url': url, 'seconds_limit': seconds, 'sessions': count,
                'server_capacity': capacity, 'capacity_refused': refused_at_capacity,
                'slot_reused': True, 'matches': results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8600')
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--sessions', type=int, help='number of matches (default: fill advertised capacity)')
    parser.add_argument('--full-games', action='store_true', help='allow 10 minutes and require every game to finish')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.seconds < 5:
        parser.error('--seconds must be at least 5')
    if args.sessions is not None and args.sessions < 1:
        parser.error('--sessions must be positive')
    result = asyncio.run(check(args.url, 600 if args.full_games else args.seconds, args.full_games, args.sessions))
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + '\n')
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
