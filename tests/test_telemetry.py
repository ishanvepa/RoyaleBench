"""Evidence capture must preserve play, timing semantics, and recoverable archives."""
import io
import json
import shutil
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import msgspec
import pytest

from cr_arena.decks import DEFAULT_DECK
from cr_arena.game import Game
from cr_arena.royale_task import GameServer, Referee, verify
from cr_arena.telemetry import Capture, GameTelemetry, Record, schema, usage_metrics
from rb_evals.archive import (
    ArchiveWorker,
    collect,
    harness_records,
    mirror,
    read_jsonl,
    verify_bundle,
)
from rb_evals.valkyrie import Valkyrie


def cfg():
    return {"seed": 1, "agent_team": 0, "agent_deck": DEFAULT_DECK, "opponent_deck": DEFAULT_DECK,
            "opponent": "heuristic", "decision_ticks": 40}


def rows(root, table):
    p = root / f"{table}.jsonl"
    return list(read_jsonl(p)) if p.exists() else []


def test_observations_do_not_reset_decision_timing_and_rejections_are_recorded(tmp_path, monkeypatch):
    clock = [1_000_000_000]
    monkeypatch.setattr("time.monotonic_ns", lambda: clock[0])
    sock = tempfile.mktemp(dir="/tmp", prefix="rb-")
    server = GameServer(sock, Referee(cfg()), tmp_path / "actions.jsonl")
    try:
        server.handle_command({"cmd": "observe"})
        clock[0] += 3_000_000_000
        server.handle_command({"cmd": "observe"})
        assert not server.handle_command({"cmd": "act", "move": 99999})["ok"]
        clock[0] += 2_000_000_000
        server.handle_command({"cmd": "act", "move": 0})
        assert rows(tmp_path, "actions")[0]["think_s"] == 5
        assert len(rows(tmp_path / "capture", "observations")) == 3
        assert any(r["data"].get("event") == "invalid_command" for r in rows(tmp_path / "capture", "events"))
        assert len(rows(tmp_path, "actions")) == 1
    finally:
        server.server_close()


def test_unobserved_actions_have_unknown_timing(tmp_path):
    server = GameServer(tempfile.mktemp(dir="/tmp", prefix="rb-"), Referee(cfg()), tmp_path / "actions.jsonl")
    try:
        server.handle_command({"cmd": "act", "move": 0})
        assert rows(tmp_path, "actions")[0]["think_s"] is None
    finally:
        server.server_close()
    report = verify(cfg(), tmp_path / "actions.jsonl", None)
    assert report["timing_known"] == 0


def test_recorder_does_not_change_game_and_resource_accounting_is_exact(tmp_path):
    original = Game(DEFAULT_DECK, DEFAULT_DECK, seed=1, record=False)
    traced = Game(DEFAULT_DECK, DEFAULT_DECK, seed=1, record=False)
    cap = Capture(tmp_path, source="local", config={})
    traced.telemetry = GameTelemetry(cap, traced)
    # Covers cap overflow, spending, double/triple rates, overtime and the tiebreak.
    while not original.over:
        a = [original.legal_moves(t)[-1] if original.state.tick % 160 == 0 else original.legal_moves(t)[0] for t in (0,1)]
        b = [traced.legal_moves(t)[m.index] for t,m in enumerate(a)]
        assert original.step(a) == traced.step(b)
    assert original.finish()[:4] == traced.finish()[:4]
    cap.close()
    assert not cap.manifest["capture_errors"]
    assert traced.telemetry.exact
    events = rows(tmp_path, "events")
    assert any(resource["overflow_fine"] > 0 for r in events if r["data"].get("event") == "engine_tick"
               for resource in r["data"]["resources"])
    for r in events:
        msgspec.convert(r, type=Record)


def test_partial_and_malformed_logs_keep_grade_and_termination_separate(tmp_path):
    log = tmp_path / "actions.jsonl"
    ref = Referee(cfg())
    e = {"decision": 0, "tick": ref.tick, "move": 0, "label": ref.moves[0].label(), "think_s": 3}
    log.write_text(json.dumps(e) + "\n")
    report = verify(cfg(), log, tmp_path / "out")
    assert not report["completed"]
    assert report["termination_tick"] < report["outcome"]["ticks"]
    assert (tmp_path / "out/replay.msgpack").exists()
    commands = rows(tmp_path / "out/telemetry", "commands")
    assert any(r["data"].get("action_source") == "verifier_wait" for r in commands)
    log.write_text('{broken\n')
    report = verify(cfg(), log, None)
    assert report["rewards"]["reward"] == 0 and report["rewards"]["integrity"] == 0


def test_usage_missing_is_not_zero_and_reasoning_is_not_added():
    assert usage_metrics({})["input_tokens"] is None
    u = usage_metrics({"prompt_tokens": 100, "completion_tokens": 50,
        "prompt_tokens_details": {"cached_tokens": 20}, "completion_tokens_details": {"reasoning_tokens": 30}}, provider="openai")
    assert (u["input_tokens"], u["cache_read_tokens"], u["output_tokens"], u["reasoning_tokens"]) == (100,20,50,30)
    assert u["input_includes_cache"]


def test_capture_resumes_ids_and_config_is_checked(tmp_path):
    c = Capture(tmp_path, source="referee", config={"seed": 1})
    first = c.emit("events", {"event": "first"})
    c.close()
    c2 = Capture(tmp_path, source="referee", config={"seed": 1})
    second = c2.emit("events", {"event": "second"})
    c2.close()
    assert first != second
    assert c.manifest["attempt_id"] == c2.manifest["attempt_id"]
    assert len(c2.manifest["segments"]) == 2
    with pytest.raises(ValueError, match="configuration changed"):
        Capture(tmp_path, source="referee", config={"seed": 2})


def make_tar(path):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(path, arcname="logs")
    return buf.getvalue()


class Remote:
    def __init__(self, data):
        self.data, self.downloads, self.fail = data, 0, False
    def run(self, _): return {"status": "FINISHED", "id": "new-run"}
    def run_tasks(self, _): return [{"task_id": "t1", "status": "FINISHED"}]
    def run_metadata(self, _): return {"benchmark_arguments": {"contract": {"model": "model"}}}
    def results(self, _): return {"evaluation_results": {}}
    def all_run_logs(self, _): return [{"message": str(i)} for i in range(1002)]
    def artifacts(self, _, attempts=False):
        return [] if attempts else [{"path": "t1/verifier_output.tar.gz", "size": len(self.data)}]
    def download_artifact_attempt(self, _, path, dest, attempts=False):
        self.downloads += 1
        if self.fail:
            self.fail = False
            raise ConnectionError("interrupted")
        dest.mkdir(parents=True)
        (dest / "verifier_output.tar.gz").write_bytes(self.data)
        return dest


def test_collection_retry_idempotence_and_restore(tmp_path):
    source = tmp_path / "source"
    ref = Referee(cfg())
    e = {"decision": 0, "tick": ref.tick, "move": 0, "label": ref.moves[0].label(), "think_s": 3}
    log = tmp_path / "actions.jsonl"
    log.write_text(json.dumps(e) + "\n")
    verify(cfg(), log, source)
    remote = Remote(make_tar(source))
    remote.fail = True
    root = tmp_path / "archive"
    report = collect(remote, "new-run", root=root)
    assert not report["complete"]
    assert any(g.get("retryable") for g in report["gaps"])
    report = collect(remote, "new-run", root=root)
    downloads = remote.downloads
    again = collect(remote, "new-run", root=root)
    assert report["counts"] == again["counts"]
    assert remote.downloads == downloads
    bundle = root / "new-run"
    assert len(rows(bundle / "raw", "service_logs")) == 1002
    assert verify_bundle(bundle) == []
    restored = mirror(bundle, tmp_path / "durable")
    assert verify_bundle(restored) == []
    shutil.rmtree(bundle)
    assert verify_bundle(restored) == []
    (restored / "raw/run.json").write_text('tampered')
    assert "raw/run.json" in verify_bundle(restored)


def test_watcher_never_discovers_or_backfills_old_runs(tmp_path):
    remote = Remote(b"")
    # No enrollment means no network calls, including run enumeration.
    remote.run = lambda _: pytest.fail("unexpected historical run access")
    ArchiveWorker(remote, tmp_path).run_once()


def test_schema_document_is_current():
    assert json.loads(Path('docs/telemetry.schema.json').read_text()) == schema()


def test_streamed_message_usage_is_counted_once(tmp_path):
    trajectory = tmp_path / "trajectory.jsonl"
    events = [{"type": "assistant", "message": {"id": mid,
        "usage": {"input_tokens": i, "output_tokens": o}, "content": []}}
        for mid, i, o in (("m1",10,2),("m1",10,5),("m2",20,3))]
    trajectory.write_text("".join(json.dumps(e) + "\n" for e in events))
    calls = list(harness_records(trajectory, {"attempt_id": "a", "match_id": "m"}))
    assert len(calls) == 2
    assert sum(c["data"]["usage"]["output_tokens"] for c in calls) == 8
    assert sum(c["data"]["usage"]["input_tokens"] for c in calls) == 30
    assert all(c["monotonic_ns"] is None for c in calls)
    for c in calls:
        msgspec.convert(c, type=Record)
    trajectory.with_name('metrics_total.json').write_text(json.dumps({'output_tokens':80}))
    partial = list(harness_records(trajectory, {'attempt_id':'a', 'match_id':'m'}))
    assert all(c['data']['usage']['output_tokens'] is None for c in partial)
    assert sum(c['data']['usage']['output_tokens_reported'] for c in partial) == 8


def test_concurrent_provider_events_have_unique_ids(tmp_path):
    c = Capture(tmp_path, source="local", config={})
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda i: c.emit("model_calls", {"request_id": str(i)}), range(100)))
    c.close()
    assert len(set(ids)) == len(ids) == 100
    assert len(rows(tmp_path, "model_calls")) == 100


def test_artifact_pagination_preserves_attempts_flag():
    requests = []
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def page(self, run_id, **kwargs):
            requests.append(kwargs)
            cursor = kwargs['cursor']
            return SimpleNamespace(artifacts=[{'path': 'a' if cursor is None else 'b', 'size': 1}],
                                   next_cursor='next' if cursor is None else None)
        @property
        def artifacts(self): return SimpleNamespace(list=self.page)
    v = Valkyrie(Client)
    entries = v.artifacts('11111111-1111-1111-1111-111111111111', attempts=True)
    assert [e['path'] for e in entries] == ['a','b']
    assert all(r['attempts'] for r in requests)


def test_collection_report_is_checksummed(tmp_path):
    from rb_evals.archive import seal_bundle
    c = Capture(tmp_path, source="local", config={})
    c.close()
    seal_bundle(tmp_path)
    (tmp_path / 'collection_report.json').write_text('{}')
    assert 'collection_report.json' in verify_bundle(tmp_path)


def test_online_referee_carries_full_trace_even_when_play_is_partial(tmp_path):
    from royalegym.replay import load_trace
    ref = Referee(cfg(), record=True)
    server = GameServer(tempfile.mktemp(dir="/tmp", prefix="rb-"), ref, tmp_path / "actions.jsonl")
    try:
        server.handle_command({"cmd": "observe"})
        server.handle_command({"cmd": "act", "move": 0})
        trace = load_trace(tmp_path / "replay.msgpack")
        assert trace.frames[0].tick == 0
        assert trace.frames[-1].tick == ref.tick
        assert trace.result is None  # no invented terminal outcome for partial play
        assert any(r["data"].get("event") == "engine_tick" for r in rows(tmp_path / "capture", "events"))
    finally:
        server.server_close()
