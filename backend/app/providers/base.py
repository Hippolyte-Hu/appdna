class ProviderError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ProviderTimeout(ProviderError):
    """A model request timed out without returning a completion."""
