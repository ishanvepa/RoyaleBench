"""/api/evals: environment and jobs (one job = one Valkyrie run)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Query

from ..deps import Ctx, RunId, TaskId, Writable
from ..errors import COMMON_ERRORS
from ..schemas.common import ActionOut
from ..schemas.evals import (
    ConcurrencyIn,
    ConcurrencyOut,
    EnvironmentOut,
    ErrorsOut,
    JobDetail,
    JobList,
    JobPreviewOut,
    JobSpecIn,
    JobStartOut,
    LogsOut,
    ResumeIn,
    TaskDetail,
    TaskList,
    TraceOut,
)
from ..services import environment as env_service
from ..services import jobs as jobs_service

router = APIRouter(tags=["evals: jobs"], responses=COMMON_ERRORS)


@router.get("/environment", response_model=EnvironmentOut, summary="Valkyrie/Modal connection and what a job can use")
def get_environment(ctx: Ctx):
    return env_service.environment(ctx)


@router.get("/jobs", response_model=JobList, summary="Runs on the royalebench benchmark, newest first")
def list_jobs(ctx: Ctx, status: Annotated[list[str] | None, Query()] = None, dataset: str | None = None,
              model: str | None = None, mine: bool = False):
    return jobs_service.list_jobs(ctx, status=status, dataset=dataset, model=model, mine=mine)


@router.post("/jobs/preview", response_model=JobPreviewOut, summary="Validate a job without starting it")
def preview_job(body: JobSpecIn, ctx: Ctx):
    return jobs_service.preview_job(ctx, body)


@router.post("/jobs", response_model=JobStartOut, status_code=201, dependencies=[Writable],
             summary="Start a job (a Valkyrie run on Modal)")
def start_job(body: JobSpecIn, ctx: Ctx):
    return jobs_service.start_job(ctx, body)


@router.get("/jobs/{run_id}", response_model=JobDetail)
def get_job(run_id: RunId, ctx: Ctx):
    return jobs_service.job_detail(ctx, run_id)


@router.patch("/jobs/{run_id}", response_model=ConcurrencyOut, dependencies=[Writable], summary="Change a run's concurrency")
def set_concurrency(run_id: RunId, body: ConcurrencyIn, ctx: Ctx):
    return ConcurrencyOut(concurrency=ctx.valkyrie.set_concurrency(run_id, body.concurrency))


@router.get("/jobs/{run_id}/tasks", response_model=TaskList)
def list_tasks(run_id: RunId, ctx: Ctx):
    return jobs_service.list_tasks(ctx, run_id)


@router.get("/jobs/{run_id}/tasks/{task_id}", response_model=TaskDetail)
def get_task(run_id: RunId, task_id: TaskId, ctx: Ctx):
    return jobs_service.task_detail(ctx, run_id, task_id)


@router.get("/jobs/{run_id}/tasks/{task_id}/trace", response_model=TraceOut,
            summary="The agent's trajectory and cost for one task (downloaded on demand, then cached)")
def get_trace(run_id: RunId, task_id: TaskId, ctx: Ctx):
    return jobs_service.task_trace(ctx, run_id, task_id)


@router.get("/jobs/{run_id}/logs", response_model=LogsOut)
def get_logs(run_id: RunId, ctx: Ctx, task_id: str | None = Query(default=None, max_length=128),
             q: str | None = Query(default=None, max_length=200), limit: int = Query(default=500, ge=1, le=2000)):
    return jobs_service.job_logs(ctx, run_id, task_id=task_id, query=q, limit=limit)


@router.get("/jobs/{run_id}/errors", response_model=ErrorsOut)
def get_errors(run_id: RunId, ctx: Ctx):
    return jobs_service.job_errors(ctx, run_id)


@router.post("/jobs/{run_id}/stop", response_model=ActionOut, dependencies=[Writable])
def stop_job(run_id: RunId, ctx: Ctx, force: bool = False):
    return ActionOut(status=ctx.valkyrie.stop_run(run_id, force=force))


@router.post("/jobs/{run_id}/resume", response_model=ActionOut, dependencies=[Writable], summary="Resume stopped tasks")
def resume_job(run_id: RunId, ctx: Ctx, body: Annotated[ResumeIn | None, Body()] = None):
    return ActionOut(status=ctx.valkyrie.resume_run(run_id, concurrency=body.concurrency if body else None))


@router.post("/jobs/{run_id}/retry", response_model=ActionOut, dependencies=[Writable], summary="Retry errored tasks")
def retry_job(run_id: RunId, ctx: Ctx, body: Annotated[ResumeIn | None, Body()] = None):
    return ActionOut(status=ctx.valkyrie.retry_run(run_id, concurrency=body.concurrency if body else None))
