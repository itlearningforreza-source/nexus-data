from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, error_id: str | None = None,
                 detail: dict[str, Any] | None = None):
        self.message = message
        self.error_id = error_id
        self.detail = detail or {}
        super().__init__(message)


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class DataProcessingError(AppError):
    status_code = 400
    code = "data_processing_error"


class SQLSafetyError(AppError):
    status_code = 400
    code = "sql_safety_violation"