"""Benchmarks: local Harbor task folders merged with what is published on Valkyrie."""

from __future__ import annotations

import re
from collections import defaultdict

from rb_evals import results as R
from rb_evals.benchmarks import (
    IN_SYNC,
    PUBLISHED_ONLY,
    BenchmarkInfo,
    LocalTask,
    collect_benchmarks,
    task_problems,
)

from ..context import AppContext
from ..errors import ApiError, not_found
from ..schemas.evals import (
    BenchmarkDetail,
    BenchmarkList,
    BenchmarkRow,
    FileInfo,
    PublishIn,
    PublishOut,
    ReplayOut,
    TaskDetailOut,
    TaskInfo,
    TaskModelSummary,
    TaskResultRow,
    TaskResultsOut,
    VersionOut,
)
from .common import family_of, logo_url

TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _run_stats(ctx: AppContext) -> dict[str, dict]:
    stats: dict[str, dict] = defaultdict(lambda: {"runs": 0, "best": None})
    try:
        runs = ctx.valkyrie.list_runs(ctx.cfg.benchmark)
    except Exception:  # noqa: BLE001 - run counts are decoration; the benchmark list must still render
        return stats
    for run in runs:
        s = stats[run.get("dataset") or ""]
        s["runs"] += 1
        score = run.get("final_score")
        if run.get("status") == "FINISHED" and score is not None:
            s["best"] = score if s["best"] is None else max(s["best"], score)
    return stats


def _info_problems(info: BenchmarkInfo) -> dict[str, list[str]]:
    return {tid: p for tid, t in (info.local.tasks.items() if info.local else []) if (p := task_problems(t))}


def _version_out(v: dict) -> VersionOut:
    return VersionOut(revision=v["revision"], digest=v["digest"], task_count=v["task_count"], tags=v.get("tags") or [],
                      created_by=v.get("created_by_email"), created_at=v.get("created_at"))


def _row(info: BenchmarkInfo, stats: dict[str, dict]) -> BenchmarkRow:
    s = stats[info.name]
    problems = sum(len(p) for p in _info_problems(info).values()) + (len(info.local.errors) if info.local else 0)
    return BenchmarkRow(
        name=info.name, title=info.title, description=info.description, kind=info.kind, state=info.state,
        local=info.local is not None, task_count=len(info.task_ids), versions=len(info.versions),
        latest_revision=info.latest["revision"] if info.latest else None, tags=info.tags, runs=s["runs"],
        best_score=s["best"], problems=problems)


def _task_info(info: BenchmarkInfo, task_id: str) -> TaskInfo:
    sync = info.task_states.get(task_id, "not published")
    task: LocalTask | None = info.local.tasks.get(task_id) if info.local else None
    if task is None:
        return TaskInfo(id=task_id, sync=sync if sync == PUBLISHED_ONLY else PUBLISHED_ONLY, local=False)
    return TaskInfo(id=task_id, name=task.name, description=task.description, category=task.category,
                    difficulty=task.difficulty, agent_timeout_s=task.agent_timeout_s,
                    verifier_timeout_s=task.verifier_timeout_s, resources={k: float(v) for k, v in task.resources.items()},
                    sync=sync, local=True, problems=task_problems(task))


def list_benchmarks(ctx: AppContext) -> BenchmarkList:
    infos, error = collect_benchmarks(ctx.cfg, ctx.valkyrie)
    stats = _run_stats(ctx)
    return BenchmarkList(benchmarks=[_row(i, stats) for i in infos], valkyrie_error=error)


def _find(ctx: AppContext, name: str) -> tuple[BenchmarkInfo, str | None]:
    infos, error = collect_benchmarks(ctx.cfg, ctx.valkyrie, only=name)
    if not infos:
        raise not_found(f"No benchmark named {name!r}. Local benchmarks live in {ctx.cfg.benchmarks_dir.name}/<name>/.")
    return infos[0], error


def benchmark_detail(ctx: AppContext, name: str) -> BenchmarkDetail:
    info, error = _find(ctx, name)
    stats = _run_stats(ctx)
    return BenchmarkDetail(
        benchmark=_row(info, stats), dataset_ref=ctx.cfg.dataset_ref(name),
        folder=f"{ctx.cfg.benchmarks_dir.name}/{name}" if info.local else None,
        versions=[_version_out(v) for v in info.versions], tasks=[_task_info(info, t) for t in info.task_ids],
        errors=list(info.local.errors) if info.local else [], valkyrie_error=error)


def task_detail(ctx: AppContext, name: str, task_id: str) -> TaskDetailOut:
    info, _ = _find(ctx, name)
    task = info.local.tasks.get(task_id) if info.local else None
    if task is None:
        raise not_found(f"Task {task_id!r} is not in the local folder for {name!r}.")
    return TaskDetailOut(
        benchmark=name, task=_task_info(info, task_id), instruction=task.instruction,
        config_toml=task.read("task.toml") or "", files=[FileInfo(path=p, size=s) for p, s in task.files()],
        dockerfile=task.read("environment/Dockerfile"), test_script=task.read("tests/test.sh"),
        solution_script=task.read("solution/solve.sh"))


def task_resolution(ctx: AppContext, name: str, task_id: str) -> ReplayOut:
    from rb_evals.resolutions import resolution_replay

    info, _ = _find(ctx, name)
    task = info.local.tasks.get(task_id) if info.local else None
    if task is None:
        raise not_found(f"Task {task_id!r} is not in the local folder for {name!r}.")
    evidence_root = ctx.cfg.benchmarks_dir.parent / "runs" / name
    try:
        return ReplayOut(**resolution_replay(task.path, evidence_root))
    except Exception as exc:
        raise ApiError(502, "bad_gateway", f"Could not render this resolution: {type(exc).__name__}: {exc}") from exc


def task_results(ctx: AppContext, name: str, task_id: str) -> TaskResultsOut:
    runs = [r for r in ctx.valkyrie.list_runs(ctx.cfg.benchmark) if r.get("dataset") == name and r.get("status") == "FINISHED"]
    records = R.load_records(ctx.valkyrie, ctx.cache, runs, fetch_costs=False)
    rows = []
    for h in R.task_history(records, name, task_id):
        family = family_of(h["model"])
        rows.append(TaskResultRow(run_id=h["run_id"], job=h["job"], model=h["model"], family=family, logo_url=logo_url(family),
                                  harness=h["harness"], revision=h["revision"], reward=h["reward"], solved=h["solved"],
                                  agent_s=h["agent_s"], cost=h["cost"], error=h["error"],
                                  failure_category=h["failure_category"], started_at=h["started_at"]))
    groups: dict[tuple[str, str], list[TaskResultRow]] = defaultdict(list)
    for r in rows:
        groups[(r.model, r.harness)].append(r)
    summary = []
    for (model, harness), rs in groups.items():
        family = family_of(model)
        solved = sum(1 for r in rs if r.solved)
        summary.append(TaskModelSummary(model=model, family=family, logo_url=logo_url(family), harness=harness,
                                        attempts=len(rs), solved=solved, pass_rate=solved / len(rs)))
    summary.sort(key=lambda s: (-(s.pass_rate or 0), -s.attempts, s.model))
    return TaskResultsOut(results=rows, summary=summary)


def publish(ctx: AppContext, name: str, body: PublishIn) -> PublishOut:
    info, _ = _find(ctx, name)
    if info.local is None:
        raise not_found(f"{name!r} exists only on Valkyrie; there is no local folder to publish.")
    bad_tags = [t for t in body.tags if not TAG_RE.fullmatch(t) or t.isdigit() or t == "latest"]
    if bad_tags:
        raise ApiError(422, "validation_error",
                       f"Invalid tag(s): {', '.join(bad_tags)}. Use letters, digits, '.', '_' or '-'; not only digits (those are "
                       "revision numbers) and not 'latest'.", [{"field": "tags", "message": t} for t in bad_tags])
    problems = _info_problems(info)
    if (problems or info.local.errors) and not body.allow_problems:
        detail = [{"task": t, "problems": p} for t, p in problems.items()] + [{"task": "", "problems": list(info.local.errors)}] * bool(info.local.errors)
        raise ApiError(409, "has_problems", "Some tasks have problems that will probably make them fail on Valkyrie. "
                       "Fix them, or publish anyway.", detail)
    previous = info.latest["revision"] if info.latest else None
    out = ctx.valkyrie.push_dataset(ctx.cfg.benchmark, name, info.local.path, body.tags)
    version = out["version"]
    return PublishOut(version=_version_out(version), changed=previous is None or version["revision"] != previous,
                      stored=out.get("stored", []), created=out.get("created", []), warnings=out.get("warnings", []),
                      left_out={k: list(v) for k, v in (out.get("left_out") or {}).items()})
