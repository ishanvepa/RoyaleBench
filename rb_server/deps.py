"""FastAPI dependencies shared by the routers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Path, Request

from .context import AppContext
from .errors import ApiError


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


Ctx = Annotated[AppContext, Depends(get_ctx)]


def require_writable(ctx: Ctx) -> None:
    """Start, stop, resume, retry and publish spend organisation credits: refuse them in read-only mode."""
    if ctx.cfg.read_only:
        raise ApiError(403, "read_only", "This server is read-only (ROYALEBENCH_EVALS_READONLY is set).")


Writable = Depends(require_writable)

# Ids end up in cache paths and upstream calls, so constrain them where they enter the API.
RunId = Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$", description="Valkyrie run id")]
TaskId = Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", description="Task id (the task folder name)")]
BenchmarkName = Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$", description="Benchmark folder name")]
