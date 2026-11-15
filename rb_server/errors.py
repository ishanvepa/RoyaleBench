"""One error shape for the whole API: ``{"error": {"code", "message", "detail"}}``.

The React client reads ``code`` to decide what to show (for example ``valkyrie_auth`` tells the user to
run ``valkyrie login``), so codes are part of the contract and listed in ``ERROR_CODES``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from rb_evals.valkyrie import ValkyrieError

from .schemas.common import ApiErrorResponse

log = logging.getLogger("rb_server")

ERROR_CODES = ("valkyrie_auth", "valkyrie_network", "valkyrie_rejected", "valkyrie_error", "read_only", "forbidden",
               "not_found", "validation_error", "conflict", "confirmation_required", "has_problems", "database_unavailable", "bad_gateway", "internal")
KIND_TO_ERROR = {"auth": (401, "valkyrie_auth"), "network": (503, "valkyrie_network"), "not_found": (404, "not_found"),
                 "rejected": (400, "valkyrie_rejected"), "other": (502, "valkyrie_error")}
STATUS_TO_CODE = {400: "validation_error", 401: "valkyrie_auth", 403: "forbidden", 404: "not_found", 409: "conflict",
                  422: "validation_error", 502: "bad_gateway", 503: "valkyrie_network"}

# Documented on every router so the generated TypeScript types include the error body.
COMMON_ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": ApiErrorResponse, "description": desc}
    for status, desc in ((400, "Rejected"), (401, "Not signed in to Valkyrie"), (403, "Read-only mode"), (404, "Not found"),
                         (409, "Conflict"), (422, "Invalid input"), (502, "Upstream error"), (503, "Valkyrie unreachable"))
}


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, detail: Any = None):
        super().__init__(message)
        self.status_code, self.code, self.message, self.detail = status_code, code, message, detail


def not_found(message: str) -> ApiError:
    return ApiError(404, "not_found", message)


def body(code: str, message: str, detail: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "detail": detail}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(body(exc.code, exc.message, exc.detail), status_code=exc.status_code)

    @app.exception_handler(ValkyrieError)
    async def _valkyrie_error(_: Request, exc: ValkyrieError) -> JSONResponse:
        status, code = KIND_TO_ERROR.get(exc.kind, KIND_TO_ERROR["other"])
        return JSONResponse(body(code, str(exc)), status_code=status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"field": ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path")), "message": e["msg"]}
                  for e in exc.errors()]
        message = "; ".join(f"{f['field']}: {f['message']}" if f["field"] else f["message"] for f in fields) or "Invalid request"
        return JSONResponse(body("validation_error", message, fields), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = STATUS_TO_CODE.get(exc.status_code, "internal" if exc.status_code >= 500 else "validation_error")
        return JSONResponse(body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(body("internal", "Unexpected server error. Check the server log."), status_code=500)
