"""Referee for the Valkyrie match tasks: the verifier's replay must reproduce the played match,
reject logs that do not fit the match, and treat missing decisions as waits."""

import json
import socket
import tempfile
import threading
from pathlib import Path

import pytest

from cr_arena.decks import CLASSIC_DECKS
from cr_arena.royale_task import GameServer, Referee, read_log, verify

DECK = CLASSIC_DECKS["giant-beatdown"]


def cfg(seed=1, team=1, opponent="heuristic"):
    return {"seed": seed, "agent_team": team, "agent_deck": DECK, "opponent_deck": DECK,
            "opponent": opponent, "decision_ticks": 40}


def play(c, chooser, log_path, limit=None):
    """Play the agent seat, logging exactly as the server does; returns the referee."""
    ref = Referee(c)
    with log_path.open("w") as f:
        while not ref.over and (limit is None or ref.decision < limit):
            idx = chooser(ref)
            f.write(json.dumps({"decision": ref.decision, "tick": ref.tick, "move": idx,
                                "label": ref.moves[idx].label(), "think_s": 3.0}) + "\n")
            ref.act(idx)
    return ref


def first_card(ref):
    return 1 if len(ref.moves) > 1 else 0


@pytest.mark.parametrize("team", [0, 1])
def test_replay_reproduces_played_match(tmp_path, team):
    log = tmp_path / "actions.jsonl"
    ref = play(cfg(team=team), first_card, log)
    report = verify(cfg(team=team), log, None)
    assert report["outcome"] == ref.outcome()
    assert report["rewards"]["integrity"] == 1.0
    assert report["rewards"]["completed"] == 1.0
    assert report["decisions_applied"] == len(read_log(log))


def test_tampered_log_scores_zero(tmp_path):
    log = tmp_path / "actions.jsonl"
    play(cfg(), first_card, log)
    entries = read_log(log)
    entries[3]["move"] = 0  # a different move than the one logged at that state
    log.write_text("".join(json.dumps(e) + "\n" for e in entries))
    report = verify(cfg(), log, None)
    assert report["rewards"]["integrity"] == 0.0
    assert report["rewards"]["reward"] == 0.0
    assert "integrity_error" in report


def test_missing_and_partial_logs_wait_out_the_match(tmp_path):
    missing = verify(cfg(), tmp_path / "absent.jsonl", None)
    assert missing["rewards"]["completed"] == 0.0 and missing["rewards"]["decisions"] == 0.0
    assert missing["outcome"]["result"] in {"win", "loss", "draw"}  # the match was still decided

    log = tmp_path / "partial.jsonl"
    play(cfg(), first_card, log, limit=5)
    partial = verify(cfg(), log, None)
    assert partial["rewards"]["completed"] == 0.0 and partial["rewards"]["decisions"] == 5.0
    assert partial["rewards"]["integrity"] == 1.0


def test_verify_writes_reward_files(tmp_path):
    log = tmp_path / "actions.jsonl"
    play(cfg(), first_card, log, limit=3)
    verify(cfg(), log, tmp_path / "out")
    rewards = json.loads((tmp_path / "out" / "reward.json").read_text())
    assert set(rewards) >= {"reward", "integrity", "completed", "fast_decision_frac"}
    assert all(isinstance(v, (int, float)) for v in rewards.values())


def test_server_logs_what_it_plays_and_rejects_bad_moves(tmp_path):
    sock = str(Path(tempfile.mkdtemp(dir="/tmp")) / "cr.sock")  # AF_UNIX paths are short on macOS
    log = tmp_path / "actions.jsonl"
    server = GameServer(sock, Referee(cfg()), log)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    def req(payload):
        with socket.socket(socket.AF_UNIX) as s:
            s.connect(sock)
            s.sendall((json.dumps(payload) + "\n").encode())
            return json.loads(s.makefile().readline())

    try:
        assert req({"cmd": "observe"})["text"].startswith("DECISION 1")
        assert not req({"cmd": "act", "move": 9999})["ok"]
        assert not log.exists()  # a refused move is not logged
        for _ in range(4):
            assert req({"cmd": "act", "move": 1})["ok"]
    finally:
        server.shutdown()
        server.server_close()
    assert len(read_log(log)) == 4
    assert verify(cfg(), log, None)["rewards"]["integrity"] == 1.0
