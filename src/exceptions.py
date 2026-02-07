"""Custom exception hierarchy for the MTBO scraper.

Provides structured exceptions with error context and correction hints
to enable AI agents to understand and recover from failures.
"""

from typing import Any


class ScraperError(Exception):
    """Base exception for all scraper errors.

    Attributes:
        message: Human-readable error message.
        error_data: Structured error information for agents.
        suggestion: Hint for how to resolve the error.
    """

    def __init__(
        self,
        message: str,
        error_data: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        """Initialize the scraper error.

        Args:
            message: Human-readable error message.
            error_data: Structured context (URLs, IDs, fields, etc.).
            suggestion: Actionable correction hint for agents.
        """
        super().__init__(message)
        self.message = message
        self.error_data = error_data or {}
        self.suggestion = suggestion

    def __str__(self) -> str:
        """Return formatted error message with suggestion if available."""
        base = self.message
        if self.suggestion:
            return f"{base}\nSuggestion: {self.suggestion}"
        return base

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to structured dictionary for logging.

        Returns:
            Dictionary with error type, message, data, and suggestion.
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_data": self.error_data,
            "suggestion": self.suggestion,
        }


class NetworkError(ScraperError):
    """HTTP/connection failures that may be retryable.

    Examples:
        - Connection timeout
        - HTTP 500/502/503 errors
        - DNS resolution failures
    """

    def __init__(
        self,
        message: str,
        url: str | None = None,
        status_code: int | None = None,
        retryable: bool = True,
        error_data: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        """Initialize network error.

        Args:
            message: Human-readable error message.
            url: The URL that failed.
            status_code: HTTP status code if applicable.
            retryable: Whether retrying might succeed.
            error_data: Additional context.
            suggestion: How to resolve the error.
        """
        data = error_data or {}
        data.update({"url": url, "status_code": status_code, "retryable": retryable})

        default_suggestion = suggestion or (
            "Check network connectivity and retry the request. "
            "If the error persists, the server may be temporarily unavailable."
            if retryable
            else "This error is not retryable. Check the URL and request parameters."
        )

        super().__init__(message, data, default_suggestion)
        self.url = url
        self.status_code = status_code
        self.retryable = retryable


class CloudflareError(ScraperError):
    """Cloudflare bypass or challenge resolution failures.

    Examples:
        - Managed challenge detection failed
        - Browser automation failed
        - Cookie extraction failed
    """

    def __init__(
        self,
        message: str,
        url: str | None = None,
        challenge_type: str | None = None,
        error_data: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        """Initialize Cloudflare error.

        Args:
            message: Human-readable error message.
            url: The URL that triggered the challenge.
            challenge_type: Type of Cloudflare challenge (if detected).
            error_data: Additional context.
            suggestion: How to resolve the error.
        """
        data = error_data or {}
        data.update({"url": url, "challenge_type": challenge_type})

        default_suggestion = suggestion or (
            "Ensure Chrome and Xvfb are installed. "
            "Check that undetected-chromedriver can launch a browser. "
            "The challenge may require manual intervention."
        )

        super().__init__(message, data, default_suggestion)
        self.url = url
        self.challenge_type = challenge_type


class ParseError(ScraperError):
    """HTML parsing failures (structure doesn't match expectations).

    Examples:
        - Missing expected HTML elements
        - Invalid data format in scraped content
        - Unexpected page structure
    """

    def __init__(
        self,
        message: str,
        event_id: str | None = None,
        field: str | None = None,
        selector: str | None = None,
        html_snippet: str | None = None,
        error_data: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        """Initialize parse error.

        Args:
            message: Human-readable error message.
            event_id: Event ID being parsed (if applicable).
            field: Field name that failed to parse.
            selector: CSS selector or XPath that failed.
            html_snippet: Relevant HTML snippet (truncated).
            error_data: Additional context.
            suggestion: How to resolve the error.
        """
        data = error_data or {}
        data.update(
            {
                "event_id": event_id,
                "field": field,
                "selector": selector,
                "html_snippet": html_snippet[:500] if html_snippet else None,
            }
        )

        default_suggestion = suggestion or (
            f"The HTML structure may have changed. "
            f"Check the selector '{selector}' in the source page. "
            f"Consider updating the parser logic."
            if selector
            else (
                "The HTML structure may have changed. Review the parser implementation."
            )
        )

        super().__init__(message, data, default_suggestion)
        self.event_id = event_id
        self.field = field
        self.selector = selector


class ValidationError(ScraperError):
    """Data validation failures (data doesn't meet schema requirements).

    Examples:
        - Invalid date format
        - Missing required fields
        - Schema validation failure
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        expected: str | None = None,
        received: Any = None,
        error_data: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        """Initialize validation error.

        Args:
            message: Human-readable error message.
            field: Field name that failed validation.
            expected: Expected data type or format.
            received: Actual value received.
            error_data: Additional context.
            suggestion: How to resolve the error.
        """
        data = error_data or {}
        data.update(
            {
                "field": field,
                "expected": expected,
                "received": str(received)[:200] if received else None,
            }
        )

        default_suggestion = suggestion or (
            f"Expected {expected} for field '{field}', but received: {received}. "
            f"Check the data source or update validation rules."
            if field and expected
            else "Review the data against the JSON schema."
        )

        super().__init__(message, data, default_suggestion)
        self.field = field
        self.expected = expected
        self.received = received


class ConfigurationError(ScraperError):
    """Invalid configuration or CLI arguments.

    Examples:
        - Invalid date format in arguments
        - Missing required configuration
        - Invalid file paths
    """

    def __init__(
        self,
        message: str,
        parameter: str | None = None,
        expected_format: str | None = None,
        example: str | None = None,
        error_data: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        """Initialize configuration error.

        Args:
            message: Human-readable error message.
            parameter: Parameter name that's invalid.
            expected_format: Expected format for the parameter.
            example: Example of valid value.
            error_data: Additional context.
            suggestion: How to resolve the error.
        """
        data = error_data or {}
        data.update(
            {
                "parameter": parameter,
                "expected_format": expected_format,
                "example": example,
            }
        )

        default_suggestion = suggestion or (
            f"Parameter '{parameter}' must be in format: {expected_format}. "
            f"Example: {example}"
            if parameter and expected_format and example
            else "Check the command-line arguments and configuration."
        )

        super().__init__(message, data, default_suggestion)
        self.parameter = parameter
        self.expected_format = expected_format
        self.example = example
