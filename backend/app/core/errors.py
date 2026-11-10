"""One error shape for the whole API.

Every failure leaves the backend as:

    { "error": { "code": "upstream_unavailable", "message": "..." } }

The frontend reads `code` to decide what to show and `message` to tell the user.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base class for failures we expect and want to report clearly."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class InvalidSignature(AppError):
    status_code = 401
    code = "invalid_signature"


class IntegrationNotConfigured(AppError):
    status_code = 503
    code = "integration_not_configured"


class UpstreamUnavailable(AppError):
    """The external system could not be reached, timed out, or answered 5xx."""

    status_code = 502
    code = "upstream_unavailable"


class UpstreamAuthFailed(AppError):
    """The external system rejected our credentials."""

    status_code = 502
    code = "upstream_auth_failed"


class UpstreamRejected(AppError):
    """The external system understood the request and refused it (4xx)."""

    status_code = 502
    code = "upstream_rejected"


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", []) if part != "body")
        detail = first.get("msg", "Invalid request.")
        message = f"{field}: {detail}" if field else detail
        return JSONResponse(error_body("validation_error", message), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(error_body(code, str(exc.detail)), status_code=exc.status_code)
