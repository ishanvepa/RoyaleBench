"""/api/evals: benchmarks (local Harbor task folders + published Valkyrie versions) and their tasks."""

from __future__ import annotations

from fastapi import APIRouter

from ..deps import BenchmarkName, Ctx, TaskId, Writable
from ..errors import COMMON_ERRORS
from ..schemas.evals import (
    BenchmarkDetail,
    BenchmarkList,
    PublishIn,
    PublishOut,
    TaskDetailOut,
    TaskResultsOut,
)
from ..services import benchmarks as service

router = APIRouter(tags=["evals: benchmarks"], responses=COMMON_ERRORS)


@router.get("/benchmarks", response_model=BenchmarkList)
def list_benchmarks(ctx: Ctx):
    return service.list_benchmarks(ctx)


@router.get("/benchmarks/{name}", response_model=BenchmarkDetail)
def get_benchmark(name: BenchmarkName, ctx: Ctx):
    return service.benchmark_detail(ctx, name)


@router.get("/benchmarks/{name}/tasks/{task_id}", response_model=TaskDetailOut)
def get_task(name: BenchmarkName, task_id: TaskId, ctx: Ctx):
    return service.task_detail(ctx, name, task_id)


@router.get("/benchmarks/{name}/tasks/{task_id}/results", response_model=TaskResultsOut,
            summary="How each model did on this task, across finished runs")
def get_task_results(name: BenchmarkName, task_id: TaskId, ctx: Ctx):
    return service.task_results(ctx, name, task_id)


@router.post("/benchmarks/{name}/publish", response_model=PublishOut, dependencies=[Writable],
             summary="Publish the local folder as a new Valkyrie dataset version (a no-op when unchanged)")
def publish_benchmark(name: BenchmarkName, body: PublishIn, ctx: Ctx):
    return service.publish(ctx, name, body)
