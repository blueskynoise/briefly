class BrieflyServiceError(Exception):
    """Base class for user-presentable service failures."""


class AuthenticationError(BrieflyServiceError):
    """Raised when an OAuth connection is missing, invalid, or expired."""


class IntegrationError(BrieflyServiceError):
    """Raised when an upstream integration call fails."""
