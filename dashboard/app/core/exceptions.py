"""Domain & application exception hierarchy."""

from __future__ import annotations


class AppError(Exception):
    """Base application error."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthenticated"


class AuthorizationError(AppError):
    status_code = 403
    code = "forbidden"


class GenerationError(AppError):
    """AI generation failed after exhausting retries."""

    status_code = 502
    code = "generation_failed"


class OrchestrationError(AppError):
    """A task orchestration operation could not be completed."""

    status_code = 409
    code = "orchestration_error"
