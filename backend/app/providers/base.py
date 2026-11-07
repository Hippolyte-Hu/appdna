class ProviderError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status
