"""Exceptions raised by the ninetile client.

Request errors (non-2xx) are raised from the API error envelope
``{"error": {"code", "message", "param", "request_id"}}`` and carry the
``code``, the HTTP ``status`` and the ``request_id`` (also in the response's
``X-Request-Id`` header) so it can be quoted to support.
"""


class NinetileError(Exception):
    """Base error for everything the client raises on its own behalf."""

    def __init__(self, message, *, code=None, status=None, request_id=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.request_id = request_id


class AuthenticationError(NinetileError):
    """401: the API key is missing, malformed, unknown or revoked."""


class InsufficientCredits(NinetileError):
    """402: the balance (or the key's own spend limit) does not cover the call."""


class RateLimited(NinetileError):
    """429: an account, sitekey or IP rate limit was hit. Carries ``retry_after``."""

    def __init__(self, message, *, retry_after=None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class SolveFailed(NinetileError):
    """The solve ended without a token (status failed / cancelled / expired).

    Carries ``retryable`` and ``reason`` from the solve's error object. Only
    retry when ``retryable`` is true; failed work is never charged.
    """

    def __init__(self, message, *, retryable=False, reason=None, **kwargs):
        super().__init__(message, **kwargs)
        self.retryable = bool(retryable)
        self.reason = reason


class SolveTimeout(NinetileError):
    """The client-side deadline passed while waiting for the solve to finish."""

    def __init__(self, message, **kwargs):
        kwargs.setdefault("code", "timeout")
        super().__init__(message, **kwargs)
