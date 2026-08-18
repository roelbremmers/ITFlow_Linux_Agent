class AgentError(Exception):
    """Base class for expected agent failures."""


class ConfigurationError(AgentError):
    pass


class InventoryError(AgentError):
    pass


class IdentityError(AgentError):
    pass


class APIError(AgentError):
    pass


class AmbiguousMatchError(AgentError):
    pass
