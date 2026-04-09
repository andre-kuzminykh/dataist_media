"""
Custom exception hierarchy for the arXiv processing pipeline.

Every exception carries structured context (code, message, stage, retriable)
so that error handlers and API responses can surface actionable information.

Feature IDs: F-CORE-EXCEPTIONS
"""


class AppException(Exception):
    """Base exception for all application-level errors.

    Attributes:
        code: Machine-readable error code (e.g. "PARSE_001").
        message: Human-readable description.
        stage: Pipeline stage where the error occurred.
        retriable: Whether the caller may safely retry the operation.
    """

    def __init__(
        self,
        code: str,
        message: str,
        stage: str,
        retriable: bool = False,
    ) -> None:
        self.code = code
        self.message = message
        self.stage = stage
        self.retriable = retriable
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"code={self.code!r}, message={self.message!r}, "
            f"stage={self.stage!r}, retriable={self.retriable})"
        )


class ValidationError(AppException):
    """Raised when input data fails validation checks."""


class ParseError(AppException):
    """Raised when arXiv page or feed content cannot be parsed."""


class GenerationError(AppException):
    """Raised when LLM or image generation fails."""


class PublishError(AppException):
    """Raised when asset storage or publishing fails."""


class DeliveryError(AppException):
    """Raised when Telegram delivery fails."""
