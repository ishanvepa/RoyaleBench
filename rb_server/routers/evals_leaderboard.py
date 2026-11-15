"""/api/evals: the leaderboard and its background cost download."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..deps import Ctx
from ..errors import COMMON_ERRORS
from ..schemas.evals import CostsStatus, LeaderboardOut
from ..services import leaderboard as service

router = APIRouter(tags=["evals: leaderboard"], responses=COMMON_ERRORS)

Dataset = Query(default=None, max_length=64, description="Only this benchmark (default: all except smoke tests)")
Revision = Query(default=None, max_length=64, description="Only this published revision")
Harness = Query(default=None, max_length=128, description="Only this agent harness")


@router.get("/leaderboard", response_model=LeaderboardOut)
def get_leaderboard(ctx: Ctx, dataset: str | None = Dataset, revision: str | None = Revision,
                    harness: str | None = Harness, include_smoke: bool = False):
    return service.leaderboard(ctx, dataset, revision, harness, include_smoke)


@router.get("/leaderboard/costs", response_model=CostsStatus, summary="Progress of the background cost download")
def get_costs_status(ctx: Ctx):
    return service.costs_status(ctx)


@router.post("/leaderboard/costs", response_model=CostsStatus,
             summary="Start downloading agent-reported cost for the runs on screen (idempotent)")
def start_costs(ctx: Ctx, dataset: str | None = Dataset, revision: str | None = Revision,
                harness: str | None = Harness, include_smoke: bool = False):
    return service.start_costs(ctx, dataset, revision, harness, include_smoke)
