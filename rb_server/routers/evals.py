"""Everything under /api/evals."""

from __future__ import annotations

from fastapi import APIRouter

from . import evals_benchmarks, evals_jobs, evals_leaderboard

router = APIRouter(prefix="/api/evals")
router.include_router(evals_jobs.router)
router.include_router(evals_benchmarks.router)
router.include_router(evals_leaderboard.router)
