"""Custom application exceptions.

Keeping exceptions typed and centralized lets API routes translate them
into consistent HTTP responses instead of leaking implementation details.
"""


class AppError(Exception):
    """Base class for all application-specific errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidShareUrlError(AppError):
    """Raised when the provided ChatGPT share URL is malformed or unsupported."""


class ConversationFetchError(AppError):
    """Raised when the shared conversation page cannot be retrieved."""


class ConversationParseError(AppError):
    """Raised when a fetched page cannot be parsed into structured messages."""


class PdfGenerationError(AppError):
    """Raised when PDF rendering fails."""
