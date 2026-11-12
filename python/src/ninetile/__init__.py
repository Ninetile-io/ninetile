"""Official Python client for the Ninetile API."""

from .client import DEFAULT_BASE_URL, Client
from .errors import (
    AuthenticationError,
    InsufficientCredits,
    NinetileError,
    RateLimited,
    SolveFailed,
    SolveTimeout,
)
from .models import RecognitionResult, Solve

__version__ = "0.1.0"

__all__ = [
    "Client",
    "DEFAULT_BASE_URL",
    "Solve",
    "RecognitionResult",
    "NinetileError",
    "AuthenticationError",
    "InsufficientCredits",
    "RateLimited",
    "SolveFailed",
    "SolveTimeout",
    "__version__",
]
