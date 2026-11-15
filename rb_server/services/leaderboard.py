"""The Evals leaderboard: finished runs pooled per (model, harness), with cost fetched in the background."""

from __future__ import annotations

from dataclasses import dataclass

from rb_evals import results as R
from rb_evals.benchmarks import discover_local

from ..context import AppContext
from ..schemas.evals import CostsStatus, LeaderboardFilters, LeaderboardOut, LeaderboardRow
from .common import family_of, logo_url


# Historical custom-harness pilot removed from the leaderboard; keep its job evidence.
EXCLUDED_ENTRIES = {("openai/Qwen/Qwen3.8-2.4T-A95B", "mini_swe_agent_modal_qwen")}


@dataclass
class Selection:
    runs: list[dict]  # finished Valkyrie run rows that pass the dataset/smoke filter
    records: list[dict]  # those runs after the revision/harness/full-run filters, with per-task results
    filters: LeaderboardFilters
    smoke: list[str]


def smoke_datasets(ctx: AppContext) -> list[str]:
    return sorted(n for n, b in discover_local(ctx.cfg.benchmarks_dir).items() if b.kind == "smoke")


def select(ctx: AppContext, dataset: str | None, revision: str | None, harness: str | None, include_smoke: bool,
           full_only: bool = False) -> Selection:
    finished = [r for r in ctx.valkyrie.list_runs(ctx.cfg.benchmark) if r.get("status") == "FINISHED"]
    smoke = smoke_datasets(ctx)
    visible = finished if include_smoke else [r for r in finished if r.get("dataset") not in smoke or r.get("dataset") == dataset]
    datasets = sorted({r["dataset"] for r in visible if r.get("dataset")})
    in_scope = [r for r in visible if not dataset or r.get("dataset") == dataset]
    loaded = R.load_records(ctx.valkyrie, ctx.cache, in_scope, fetch_costs=False)  # results JSON only; costs come later
    loaded = [r for r in loaded if (r["model"], r["agent"]) not in EXCLUDED_ENTRIES]
    records = [r for r in loaded if (not revision or r["revision"] == revision) and (not harness or r["agent"] == harness)]
    if full_only:
        records = _full_runs(ctx, records)
    ids = {r["run_id"] for r in records}
    return Selection(
        runs=[r for r in in_scope if str(r["id"]) in ids], records=records, smoke=smoke,
        filters=LeaderboardFilters(datasets=datasets, revisions=sorted({r["revision"] for r in loaded if r["revision"]}, key=_revision_key),
                                   harnesses=sorted({r["agent"] for r in loaded if r["agent"]})))


def _full_runs(ctx: AppContext, records: list[dict]) -> list[dict]:
    """Compare task identities against each run's pinned revision, including task errors as attempts."""
    expected: dict[tuple[str, str], set[str]] = {}
    full = []
    for record in records:
        key = record["dataset"], record["revision"]
        if not all(key):
            continue  # Without a pinned dataset revision, full coverage cannot be verified.
        if key not in expected:
            expected[key] = {t["task_id"] for t in ctx.valkyrie.dataset_tasks(ctx.cfg.benchmark, *key)}
        if expected[key] and {t["task"] for t in record["tasks"]} == expected[key]:
            full.append(record)
    return full


def _revision_key(value: str) -> tuple[int, str]:
    return (0, f"{int(value):09d}") if value.isdigit() else (1, value)


def leaderboard(ctx: AppContext, dataset: str | None, revision: str | None, harness: str | None, include_smoke: bool,
                full_only: bool = False) -> LeaderboardOut:
    sel = select(ctx, dataset, revision, harness, include_smoke, full_only)
    rows = []
    for row in R.leaderboard(sel.records):
        family = family_of(row["model"])
        rows.append(LeaderboardRow(**row, family=family, logo_url=logo_url(family)))
    return LeaderboardOut(
        rows=rows, filters=sel.filters, runs_considered=len(sel.records),
        tasks_considered=sum(len(r["tasks"]) for r in sel.records),
        costs_pending=R.uncached_task_count(ctx.cache, sel.runs), smoke_datasets=sel.smoke)


def costs_status(ctx: AppContext) -> CostsStatus:
    s = ctx.costs.status()
    return CostsStatus(state=s.state, done=s.done, total=s.total, error=s.error)


def start_costs(ctx: AppContext, dataset: str | None, revision: str | None, harness: str | None, include_smoke: bool,
                full_only: bool = False) -> CostsStatus:
    """Download agent output (cost, tokens) for the runs on screen, in the background. Safe to call repeatedly."""
    sel = select(ctx, dataset, revision, harness, include_smoke, full_only)

    def work(progress) -> None:
        R.load_records(ctx.valkyrie, ctx.cache, sel.runs, fetch_costs=True, on_progress=progress)

    ctx.costs.start(work)
    return costs_status(ctx)
