"""Unified error codes and exception definitions."""

from uuid import uuid4


class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    GRAPH_QUERY_TOO_LARGE = "GRAPH_QUERY_TOO_LARGE"
    GRAPH_DEPTH_EXCEEDED = "GRAPH_DEPTH_EXCEEDED"
    SEARCH_QUERY_TOO_SHORT = "SEARCH_QUERY_TOO_SHORT"
    COMPARE_TOO_FEW_MEMBERS = "COMPARE_TOO_FEW_MEMBERS"
    PREDICTION_INSUFFICIENT_DATA = "PREDICTION_INSUFFICIENT_DATA"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class AppError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.request_id = f"req_{uuid4().hex[:8]}"

    def to_dict(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "request_id": self.request_id,
        }


class NotFoundError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCode.NOT_FOUND, message, 404, details)


class GraphQueryTooLargeError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCode.GRAPH_QUERY_TOO_LARGE, message, 400, details)


class GraphDepthExceededError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCode.GRAPH_DEPTH_EXCEEDED, message, 400, details)


class SearchQueryTooShortError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCode.SEARCH_QUERY_TOO_SHORT, message, 400, details)


class CompareTooFewMembersError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCode.COMPARE_TOO_FEW_MEMBERS, message, 400, details)


class PredictionInsufficientDataError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCode.PREDICTION_INSUFFICIENT_DATA, message, 200, details)


class InternalError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCode.INTERNAL_ERROR, message, 500, details)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCode.SERVICE_UNAVAILABLE, message, 503, details)
