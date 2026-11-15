"""Jobs: one Valkyrie run each. Listing, monitoring, starting and controlling them."""

from __future__ import annotations

from rb_evals import jobs as J
from rb_evals import results as R
from rb_evals.config import secret_env_for
from rb_evals.jobs import JobSpec
from rb_evals.valkyrie import ValkyrieError

from ..context import AppContext
from ..errors import ApiError
from ..schemas.evals import (
    ErrorsOut,
    JobDetail,
    JobList,
    JobPreviewOut,
    JobRow,
    JobSpecIn,
    JobStartOut,
    LogLine,
    LogsOut,
    QueueInfo,
    TaskDetail,
    TaskList,
    TaskRow,
    TraceOut,
    TraceStep,
)
from .common import family_of, logo_url, secret_name

LOG_LIMIT = 2000


def job_row_out(run: dict, now: float | None = None, costs: dict | None = None) -> JobRow:
    row = J.job_row(run, now)
    family = family_of(row["model"])
    return JobRow(**{k: row[k] for k in JobRow.model_fields if k in row}, family=family, logo_url=logo_url(family),
                  **(costs or {}))


def _run_costs(ctx: AppContext, runs: list[dict]) -> dict[str, dict]:
    """Read cached task costs without downloading agent outputs. Include all billed tasks, even errors."""
    records = R.load_records(ctx.valkyrie, ctx.cache, runs, fetch_costs=False)
    out = {}
    for record in records:
        costs = [t["cost"] for t in record["tasks"] if t["cost"] is not None]
        out[record["run_id"]] = dict(cost_usd=sum(costs) if costs else None,
            cost_per_task=sum(costs) / len(costs) if costs else None, cost_known=len(costs))
    for run in runs:
        out.setdefault(str(run["id"]), {})["costs_pending"] = R.uncached_task_count(ctx.cache, [run])
    return out


def start_job_costs(ctx: AppContext, run_ids: list[str]):
    from .leaderboard import costs_status

    # Resolve only runs in this benchmark; the client supplies the visible rows.
    wanted = set(run_ids)
    runs = [r for r in ctx.valkyrie.list_runs(ctx.cfg.benchmark) if str(r["id"]) in wanted]
    ctx.costs.start(lambda progress: R.load_records(ctx.valkyrie, ctx.cache, runs,
                                                  fetch_costs=True, on_progress=progress))
    return costs_status(ctx)


def _my_email(ctx: AppContext) -> str | None:
    try:
        return ctx.valkyrie.identity().get("email")
    except ValkyrieError:
        return None


# ---------------------------------------------------------------------- reading
def list_jobs(ctx: AppContext, *, status: list[str] | None = None, dataset: str | None = None, model: str | None = None,
              mine: bool = False) -> JobList:
    now = ctx.now()
    runs = ctx.valkyrie.list_runs(ctx.cfg.benchmark)
    costs = _run_costs(ctx, runs)
    rows = [job_row_out(r, now, costs.get(str(r["id"]))) for r in runs]
    me = _my_email(ctx)
    shown = [r for r in rows
             if (not status or r.status in status) and (not dataset or r.dataset == dataset)
             and (not model or r.model == model) and (not mine or (me is not None and r.started_by == me))]
    return JobList(jobs=shown, total=len(rows), datasets=sorted({r.dataset for r in rows if r.dataset}),
                   models=sorted({r.model for r in rows if r.model}), me=me)


def job_detail(ctx: AppContext, run_id: str) -> JobDetail:
    run = ctx.valkyrie.run(run_id)
    now = ctx.now()
    meta = ctx.valkyrie.run_metadata(run_id)
    args = meta.get("benchmark_arguments") or {}
    contract = args.get("contract") or {}
    active = run.get("status") in J.ACTIVE_STATUSES
    queue = None
    if active:
        try:
            q = ctx.valkyrie.queue(run_id)
            queue = QueueInfo(waiting=q["waiting"], active=q["active"], position=q["position"])
        except ValkyrieError:
            queue = None  # the queue is a nicety; never fail the page for it
    return JobDetail(
        job=job_row_out(run, now, _run_costs(ctx, [run]).get(str(run["id"]))), provider=args.get("sandbox_provider") or "modal", concurrency=args.get("concurrency"),
        dataset_version=(args.get("dataset_version") or {}).get("id") or "", task_ids=args.get("task_ids"),
        secrets={env: secret_name(ref) for env, ref in (contract.get("secrets") or {}).items()},
        project=(meta.get("project") or {}).get("handle"), eta_s=J.eta_seconds(run, now), queue=queue, active=active)


def list_tasks(ctx: AppContext, run_id: str) -> TaskList:
    run = ctx.valkyrie.run(run_id)
    rows = J.task_rows(ctx.valkyrie.run_tasks(run_id), ctx.now())
    finished = [r["task"] for r in rows if r["status"] == "FINISHED"]
    details = ctx.task_results.get_many(run_id, finished, lambda t: ctx.valkyrie.task(run_id, t))
    out = []
    for r in rows:
        reward = R.reward_of((details.get(r["task"]) or {}).get("evaluation_result") or {})
        out.append(TaskRow(task=r["task"], status=r["status"], category=r["category"], error=r["error"],
                           duration_s=r["duration_s"], started_at=r["started_at"], finished_at=r["finished_at"],
                           reward=reward, solved=reward is not None and reward >= R.SOLVED_AT))
    return TaskList(tasks=out, counts=dict(run.get("task_state_counts") or {}))


def task_detail(ctx: AppContext, run_id: str, task_id: str) -> TaskDetail:
    t = ctx.valkyrie.task(run_id, task_id)
    evaluation = t.get("evaluation_result") or {}
    reward = R.reward_of(evaluation)
    breakdown = t.get("task_breakdown") or {}
    return TaskDetail(
        task=t["task_id"], status=t["status"], category=t.get("failure_category") or "", error=t.get("error_message") or "",
        reward=reward, solved=reward is not None and reward >= R.SOLVED_AT,
        rewards={k: float(v) for k, v in (evaluation.get("rewards") or {}).items() if isinstance(v, (int, float))},
        verifier_output=(evaluation.get("metadata") or {}).get("verifier_output", ""),
        agent_s=breakdown.get("agent_run_duration"), sandbox_s=breakdown.get("sandbox_run_duration"),
        build_s=breakdown.get("sandbox_build_duration"), eval_s=breakdown.get("evaluation_run_duration"),
        exit_reason=t.get("agent_caused_exit_reason"))


def task_trace(ctx: AppContext, run_id: str, task_id: str) -> TraceOut:
    """Download (once) and read the agent's output for one task: its trajectory, final message and cost."""
    final = ctx.valkyrie.run(run_id).get("status") == "FINISHED"
    folder = R.fetch_task_files(ctx.valkyrie, ctx.cache, run_id, task_id, final=final)
    if folder is None:
        return TraceOut(available=False)
    trace = R.read_trace(folder)
    m = trace["metrics"] or {}
    return TraceOut(available=True, final_message=trace["final_message"], steps=[TraceStep(**s) for s in trace["steps"]],
                    steps_total=trace["steps_total"], cost_usd=m.get("cost"), input_tokens=m.get("input_tokens"),
                    output_tokens=m.get("output_tokens"), cache_read_tokens=m.get("cache_read_tokens"))


def job_logs(ctx: AppContext, run_id: str, *, task_id: str | None, query: str | None, limit: int) -> LogsOut:
    lines = ctx.valkyrie.run_logs(run_id, task_id=task_id, query=query or None, limit=max(1, min(limit, LOG_LIMIT)))
    return LogsOut(lines=[LogLine(**line) for line in lines])


def job_errors(ctx: AppContext, run_id: str) -> ErrorsOut:
    return ErrorsOut(**ctx.valkyrie.run_errors(run_id))


# ---------------------------------------------------------------------- starting
def _resolve_revision(versions: list[dict], wanted: str) -> str | None:
    wanted = (wanted or "latest").strip()
    if not versions:
        return None
    if wanted == "latest":
        return str(versions[0]["revision"])
    for v in versions:
        if wanted == str(v["revision"]) or wanted in (v.get("tags") or []):
            return str(v["revision"])
    return None


def inspect_spec(ctx: AppContext, body: JobSpecIn) -> tuple[JobSpec, list[str], list[str], list[str]]:
    """Validate a job request against Valkyrie. Returns (spec, known task ids, errors, warnings).

    Auth and network failures raise (the caller cannot do anything useful); everything the user can fix is
    reported in ``errors`` so the form can show all of it at once.
    """
    cfg, v = ctx.cfg, ctx.valkyrie
    errors: list[str] = []
    warnings: list[str] = []
    try:
        versions = v.dataset_versions(cfg.benchmark, body.dataset)
    except ValkyrieError as exc:
        if exc.kind in ("auth", "network"):
            raise
        versions = []
        errors.append(f"{cfg.benchmark}/{body.dataset} is not published on Valkyrie. Publish it from the Benchmarks page first.")
    revision = _resolve_revision(versions, body.revision)
    if versions and revision is None:
        errors.append(f"Revision {body.revision!r} does not exist (the latest is {versions[0]['revision']}).")
    known = sorted(t["task_id"] for t in v.dataset_tasks(cfg.benchmark, body.dataset, revision)) if revision else []
    agents, secrets = v.agent_names(), v.secret_names()
    if agents and body.agent not in agents:
        errors.append(f"Harness {body.agent!r} is not installed. Installed: {', '.join(agents)}.")
    if secrets and body.secret_name not in secrets:
        errors.append(f"Secret {body.secret_name!r} does not exist in this organisation.")
    if body.model.strip() and body.model.strip() not in {m.id for m in cfg.models}:
        warnings.append("This model key is not in evals.toml, so it has not been verified. Start with a one-task job.")
    spec = JobSpec(dataset=body.dataset, revision=revision or body.revision, agent=body.agent, model=body.model.strip(),
                   secret_name=body.secret_name, secret_env=secret_env_for(body.model.strip(), cfg.models),
                   concurrency=body.concurrency, label=body.label.strip(), task_ids=body.task_ids,
                   benchmark=cfg.benchmark, provider=cfg.provider)
    try:
        spec.validate(cfg, known_tasks=known if known else None)
    except ValueError as exc:
        errors.append(str(exc))
    return spec, known, errors, warnings


def preview_job(ctx: AppContext, body: JobSpecIn) -> JobPreviewOut:
    spec, known, errors, warnings = inspect_spec(ctx, body)
    ok = not errors
    return JobPreviewOut(
        valid=ok, errors=errors, warnings=warnings, task_count=spec.task_count(known) if known else 0,
        needs_confirmation=bool(known) and spec.needs_confirmation(ctx.cfg, known),
        cli_command=spec.cli_command() if ok else None, secret_env=spec.secret_env,
        resolved_revision=spec.revision if known else None, dataset_ref=f"{ctx.cfg.benchmark}/{spec.dataset}@{spec.revision}" if known else None,
        known_tasks=known)


def start_job(ctx: AppContext, body: JobSpecIn) -> JobStartOut:
    spec, known, errors, _ = inspect_spec(ctx, body)
    if errors:
        raise ApiError(422, "validation_error", "; ".join(errors), [{"field": "", "message": e} for e in errors])
    if spec.needs_confirmation(ctx.cfg, known) and not body.confirm:
        raise ApiError(409, "confirmation_required",
                       f"This job runs {spec.task_count(known)} tasks (more than {ctx.cfg.confirm_over_tasks}). "
                       "Confirm to start it.")
    out = ctx.valkyrie.start_run(**spec.start_kwargs())
    if not ctx.fake:
        from rb_evals.archive import enroll
        try:
            enroll(out["run_id"], config={"benchmark": spec.benchmark, "dataset": spec.dataset,
                "revision": spec.revision, "agent": spec.agent, "model": spec.model,
                "concurrency": spec.concurrency, "task_ids": spec.task_ids or known,
                "provider": spec.provider, "label": spec.label,
                "cohort_id": f"{spec.benchmark}/{spec.dataset}@{spec.revision}"})
        except OSError as exc:
            out["warning"] = f"Run started, but archive enrollment failed: {exc}"
    return JobStartOut(run_id=out["run_id"], task_count=out["task_count"], warning=out.get("warning"))
