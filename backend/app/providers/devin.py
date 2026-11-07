class DevinProvider:
    """Optional engineering provider. Remote Devin access is not configured."""

    def available(self) -> bool:
        return False

    async def request_engineering(self, task: str) -> dict:
        return {
            "status": "unavailable",
            "task": task,
            "detail": "Devin remote API is not configured. Generated code stays in the local sandbox.",
        }
