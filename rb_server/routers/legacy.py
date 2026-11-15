"""/api/legacy: the original arena. Results, overview, jobs, matches, replays and models."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query
from fastapi.responses import HTMLResponse

from ..deps import Ctx, Writable
from ..errors import COMMON_ERRORS
from ..schemas.legacy import (
    ArenaResults,
    ArenaRuns,
    CommandStatus,
    DecisionDetail,
    JobReport,
    JobSummaries,
    MatchList,
    MatchReport,
    ModelsOut,
    Overview,
)
from ..services import legacy as service

router = APIRouter(tags=["legacy"], responses=COMMON_ERRORS)

JobName = Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", description="Arena job name")]
MatchId = Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,200}$", description="Match id")]


@router.get("/results", response_model=ArenaRuns, summary="Runs that have standings (tournaments and battles)")
def get_runs(ctx: Ctx):
    return service.arena_runs(ctx)


@router.get("/results/{job}", response_model=ArenaResults, summary="Standings, performance and games of one run")
def get_results(job: JobName, ctx: Ctx):
    return service.arena_results(ctx, job)


@router.get("/overview", response_model=Overview)
def get_overview(ctx: Ctx):
    return service.overview(ctx)


@router.get("/jobs", response_model=JobSummaries)
def list_jobs(ctx: Ctx):
    return service.job_summaries(ctx)


@router.get("/jobs/{job}", response_model=JobReport)
def get_job(job: JobName, ctx: Ctx):
    return service.job_report(ctx, job)


@router.get("/jobs/{job}/matches", response_model=MatchList)
def list_matches(job: JobName, ctx: Ctx, status: Annotated[list[str] | None, Query()] = None, player: str | None = Query(default=None, max_length=128),
                 page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200)):
    return service.job_matches(ctx, job, status=status, player=player, page=page, page_size=page_size)


@router.get("/jobs/{job}/matches/{match_id}", response_model=MatchReport)
def get_match(job: JobName, match_id: MatchId, ctx: Ctx):
    return service.match_report(ctx, job, match_id)


@router.get("/jobs/{job}/matches/{match_id}/decisions/{step}/{team}", response_model=DecisionDetail,
            summary="The exact board text a model saw and its full reply (loaded on demand)")
def get_decision(job: JobName, match_id: MatchId, step: Annotated[int, Path(ge=0)], team: Annotated[int, Path(ge=0, le=1)], ctx: Ctx):
    return service.decision_detail(ctx, job, match_id, step, team)


@router.get("/jobs/{job}/matches/{match_id}/replay", response_class=HTMLResponse, responses={200: {"content": {"text/html": {}}}},
            summary="The saved game as a self-contained HTML viewer, for a sandboxed iframe")
def get_replay(job: JobName, match_id: MatchId, ctx: Ctx):
    html = service.replay_html(ctx, job, match_id)
    # The viewer runs its own script: confine it to an opaque origin so it can never reach this app's API or storage.
    return HTMLResponse(html, headers={"Content-Security-Policy": "sandbox allow-scripts", "Cache-Control": "private, max-age=300"})


@router.get("/models", response_model=ModelsOut)
def get_models(ctx: Ctx):
    return service.models(ctx)


@router.get("/models/check", response_model=CommandStatus, summary="State and output of the last model check")
def get_model_check(ctx: Ctx):
    return service.check_status(ctx)


@router.post("/models/check", response_model=CommandStatus, dependencies=[Writable], summary="Make one cheap call per configured model, in the background")
def start_model_check(ctx: Ctx):
    return service.start_check(ctx)
