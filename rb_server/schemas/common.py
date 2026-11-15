from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiErrorBody(BaseModel):
    code: str
    message: str
    detail: Any | None = None


class ApiErrorResponse(BaseModel):
    error: ApiErrorBody


class ActionOut(BaseModel):
    """Result of a run-control action (stop, resume, retry)."""

    status: str


class HealthOut(BaseModel):
    """What the web app needs to know about the server before it offers anything that changes state."""

    status: str = "ok"
    read_only: bool = False  # every endpoint that starts, saves, plays or publishes answers 403 read_only
    fake: bool = False  # Valkyrie is simulated (demo and test mode), so nothing here spends credits
