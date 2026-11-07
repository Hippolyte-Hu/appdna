import httpx

from app.providers.base import ProviderError


class LinkupProvider:
    """Linkup POST /v1/search. Replace this class to swap search providers."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> list[dict]:
        if not self.api_key:
            raise ProviderError("LINKUP_API_KEY is not configured")
        body: dict = {
            "q": query,
            "depth": "fast",
            "outputType": "searchResults",
            "maxResults": max_results,
        }
        if include_domains:
            body["includeDomains"] = include_domains
        if exclude_domains:
            body["excludeDomains"] = exclude_domains
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                f"{self.base_url}/v1/search",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"Linkup search failed ({response.status_code})",
                status=response.status_code,
            )
        payload = response.json()
        results = payload.get("results")
        if not isinstance(results, list):
            raise ProviderError("Linkup response did not include results")
        hits = []
        for item in results:
            if not isinstance(item, dict) or item.get("type") == "image":
                continue
            url = item.get("url") or ""
            content = item.get("content") or item.get("snippet") or ""
            title = item.get("name") or url
            if url and content:
                hits.append({"title": title, "url": url, "content": content})
        return hits
