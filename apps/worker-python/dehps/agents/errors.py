class AgentAuthorityError(ValueError):
    """Base error for Agent Authority validation and lifecycle failures."""


class AgentAuthorizationError(AgentAuthorityError):
    """Raised when a role is not authorized for an operation."""


class AgentRequestConflictError(AgentAuthorityError):
    """Raised when a request conflicts with persisted state."""


class AgentRequestNotFoundError(AgentAuthorityError):
    """Raised when an Agent Request or execution cannot be found."""


class AgentRequestTransitionError(AgentAuthorityError):
    """Raised for invalid Agent Request lifecycle transitions."""


class AgentRequestValidationError(AgentAuthorityError):
    """Raised when a typed request contract is incomplete or invalid."""
