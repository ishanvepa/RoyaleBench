"""Shared test helpers: task fixtures and a fully faked API (no network, no credentials)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from cr_arena.db import DB
from rb_evals.config import EvalsConfig, ModelPreset
from rb_evals.fake import FakeValkyrie
from rb_server.app import create_app
from rb_server.context import AppContext, ArenaHandle, build_context
from rb_server.settings import Settings

T0 = 1_800_000_000.0  # a realistic epoch: the fake derives timestamps from it
GOOD_TEST = "#!/bin/bash\nmkdir -p /logs/verifier\necho 1 > /logs/verifier/reward.txt\n"
GOOD_TOML = ('[task]\nname = "royalebench/{name}"\ndescription = "A task"\n[metadata]\ncategory = "c"\ndifficulty = "easy"\n'
             '[agent]\ntimeout_sec = 60\n[verifier]\ntimeout_sec = 10\n[environment]\ncpus = 1\nmemory_mb = 512\n')


def write(path: Path, text: str | bytes = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, newline="\n")  # text mode would write CRLF on Windows
    return path


def make_task(folder: Path, *, instruction: str | None = "Do the thing.", tests: str | bytes | None = GOOD_TEST,
              toml: str | None = None) -> Path:
    write(folder / "task.toml", toml if toml is not None else GOOD_TOML.format(name=folder.name))
    if instruction is not None:
        write(folder / "instruction.md", instruction)
    if tests is not None:
        write(folder / "tests" / "test.sh", tests)
    write(folder / "environment" / "Dockerfile", "FROM python:3.12-slim\n")
    write(folder / "solution" / "solve.sh", "#!/bin/bash\necho solved\n")
    return folder


class ApiCase(unittest.TestCase):
    """A TestClient over the real app, wired to FakeValkyrie and throw-away benchmark and cache folders.

    Benchmarks on disk: ``smoke`` (kind smoke, task elixir-check), ``alpha`` (t1, t2, t3) and ``draft`` (d1, never published).
    The fake also publishes ``arena-lite`` (remote only) and seeds finished runs on ``smoke`` and ``arena-lite``.
    """

    read_only = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.benchmarks = root / "benchmarks"
        write(self.benchmarks / "smoke" / "benchmark.toml", '[benchmark]\ntitle = "Smoke"\nkind = "smoke"\n')
        make_task(self.benchmarks / "smoke" / "elixir-check")
        write(self.benchmarks / "alpha" / "benchmark.toml", '[benchmark]\ntitle = "Alpha"\ndescription = "Lanes"\nkind = "eval"\n')
        for task in ("t1", "t2", "t3"):
            make_task(self.benchmarks / "alpha" / task)
        make_task(self.benchmarks / "draft" / "d1")
        self.now = [T0]
        self.fake = FakeValkyrie(self.benchmarks, clock=lambda: self.now[0], user="me@example.com")
        self.cfg = EvalsConfig(benchmarks_dir=self.benchmarks, cache_dir=root / "cache", read_only=self.read_only,
                               max_concurrency=4, confirm_over_tasks=2,
                               models=(ModelPreset("anthropic/claude-sonnet-4-6", "ANTHROPIC_API_KEY"),))
        self.settings = Settings(static_dir=root / "no-web")
        self.ctx: AppContext = build_context(self.settings, valkyrie=self.fake, cfg=self.cfg)
        self.db = DB(root / "arena.db")  # a throw-away arena database; the real one is never touched
        self.addCleanup(self.db.close)
        self.ctx.arena = ArenaHandle(db=self.db)
        self.app = create_app(self.settings, ctx=self.ctx)
        self.client = TestClient(self.app, headers={"x-rb-client": "web"})
        self.addCleanup(self.client.close)

    def advance(self, seconds: float) -> None:
        self.now[0] += seconds

    def spec(self, **overrides) -> dict:
        body = {"dataset": "alpha", "revision": "latest", "agent": "claude_code-v1.0.0", "model": "anthropic/claude-sonnet-4-6",
                "secret_name": "anthropic-api-key-demo", "concurrency": 2, "label": "my job", "task_ids": ["t1"]}
        return {**body, **overrides}

    def start(self, **overrides) -> str:
        r = self.client.post("/api/evals/jobs", json=self.spec(**{"confirm": True, **overrides}))
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["run_id"]


SAMPLE_REPLAY = Path(__file__).resolve().parents[1] / "runs" / "samples" / "random-bot__vs__heuristic-bot__s2.msgpack"
ARENA_CONFIG = """
[tournament]
decision_ticks = 40
seeds = [1]
anchor = "bot"
[[players]]
name = "model-a"
provider = "anthropic"
model = "claude-x"
price_in = 3
price_out = 15
[[players]]
name = "model-b"
provider = "openai"
model = "gpt-x"
[[players]]
name = "bot"
type = "random"
"""


def seed_arena(db: DB) -> dict[str, int]:
    """A tournament (one finished match with a replay, one running, one queued), a finished battle and a human game."""
    tid = db.get_or_create_job("tourney", ARENA_CONFIG, ["model-a", "model-b", "bot"], [1], 40, 3, "a note")
    db.set_job_status(tid, "running")
    db.queue_matches(tid, [
        {"match_id": "a-b__s1", "blue": "model-a", "red": "model-b", "seed": 1, "deck": ["x"]},
        {"match_id": "b-bot__s1", "blue": "model-b", "red": "bot", "seed": 1, "deck": {"blue": ["x"], "red": ["y"]}},
        {"match_id": "a-bot__s1", "blue": "model-a", "red": "bot", "seed": 1, "deck": ["x"]},
    ])
    db.match_started(tid, "a-b__s1", "log", str(SAMPLE_REPLAY))
    db.match_finished(tid, {"match_id": "a-b__s1", "winner": 0, "crowns": [3, 0], "tower_hp": [[1, 1, 1], [0, 0, 0]], "ticks": 900,
                            "wall_s": 12.0, "stats_blue": {"errors": 1, "illegal_or_unparsed": 2}, "stats_red": {}})
    db.match_started(tid, "b-bot__s1", "log", "")
    rows = []
    for step in range(3):
        for team, player in ((0, "model-a"), (1, "model-b")):
            rows.append((tid, "a-b__s1", step, team, player, 170.0 - step, 5.0, 3000, 3000, 4, 1, "wait", "wait", 1, "", 1.5, 1000, 100, 0, 0,
                         "I will wait.\nMOVE: 0", "THE BOARD", 0.0))
    db.add_decisions(rows)
    bid = db.get_or_create_job("battle-1", ARENA_CONFIG, ["model-a", "model-b"], [1], 40, 1)
    db.queue_matches(bid, [{"match_id": "x__vs__y__s1", "blue": "model-a", "red": "model-b", "seed": 1, "deck": {"blue": ["x"], "red": ["y"]}}])
    db.match_started(bid, "x__vs__y__s1", "log", "")
    db.match_finished(bid, {"match_id": "x__vs__y__s1", "winner": 1, "crowns": [0, 1], "tower_hp": [[1, 1, 1], [1, 1, 0]], "ticks": 3000,
                            "wall_s": 5.0, "stats_blue": {}, "stats_red": {}})
    db.set_job_status(bid, "done")
    hid = db.get_or_create_job("human-play", "", ["human"], [], 40, 0)
    return {"tourney": tid, "battle": bid, "human": hid}
