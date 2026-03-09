from __future__ import annotations

from typing import Any, Tuple

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _extract_error(detail: Any, status_code: int) -> Tuple[str, str, Any]:
    """
    Normalize error payloads into (code, message, details).
    Supports string detail or dict with optional code/message/details.
    """
    if isinstance(detail, dict):
        code = detail.get("code") or f"HTTP_{status_code}"
        message = detail.get("message") or detail.get("detail") or "Request failed"
        details = detail.get("details")
        return code, message, details
    return f"HTTP_{status_code}", str(detail), None


def error_response(
    code: str, message: str, details: Any = None, status_code: int = 400
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:  # noqa: ARG001
        code, message, details = _extract_error(exc.detail, exc.status_code)
        return error_response(
            code=code, message=message, details=details, status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:  # noqa: ARG001
        return error_response(
            code="VALIDATION_ERROR",
            message="Invalid request payload",
            details=exc.errors(),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:  # noqa: ARG001
        return error_response(
            code="SERVER_ERROR",
            message="Unexpected server error",
            details=str(exc),
            status_code=500,
        )
