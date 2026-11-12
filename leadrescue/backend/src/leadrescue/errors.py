"""Typed API errors mapped to HTTP responses."""

from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | list | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def to_body(self) -> dict:
        body: dict = {"error": {"code": self.code, "message": self.message}}
        if self.details is not None:
            body["error"]["details"] = self.details
        return body


def bad_request(message: str, details=None, code: str = "validation_error") -> ApiError:
    return ApiError(400, code, message, details)


def unauthorized(message: str = "Sign in to continue.", code: str = "unauthorized") -> ApiError:
    return ApiError(401, code, message)


def forbidden(message: str = "You do not have access to this resource.") -> ApiError:
    return ApiError(403, "forbidden", message)


def not_found(message: str = "Not found.") -> ApiError:
    return ApiError(404, "not_found", message)


def conflict(message: str, code: str = "conflict", details=None) -> ApiError:
    return ApiError(409, code, message, details)


class ConflictError(Exception):
    """Raised by stores when a conditional write fails."""


class AnalysisError(Exception):
    """Raised by AI providers. `message` is safe to show to staff."""

    def __init__(self, code: str, message: str, retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
