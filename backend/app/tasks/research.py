from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.providers.base import ProviderError
from app.providers.linkup import LinkupProvider
from app.util import html_to_text, new_id, utcnow

DOMAINS = ["www.chatwoot.com", "chatwoot.com", "developers.chatwoot.com"]
OFFICIAL = [
    "https://www.chatwoot.com/hc/user-guide/articles/1677689800-how-to-use-automation",
    "https://www.chatwoot.com/hc/user-guide/articles/1682679737-how-to-assign-a-priority",
]


async def research(query: str) -> tuple[list[dict], list[str]]:
    settings = get_settings()
    hits, errors = [], []
    if settings.linkup_api_key:
        try:
            hits = await LinkupProvider(settings.linkup_api_key, settings.linkup_base_url).search(
                query[:600], include_domains=DOMAINS, max_results=3)
        except ProviderError as exc:
            errors.append(str(exc))
    if not hits:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for url in OFFICIAL:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    if urlsplit(str(response.url)).hostname not in DOMAINS:
                        continue
                    content = html_to_text(response.text)
                    if content:
                        hits.append({"url": url, "title": "Chatwoot: " + url.rsplit("/", 1)[-1].replace("-", " "), "content": content})
                except httpx.HTTPError:
                    errors.append(f"Could not retrieve {url}.")
    sources = [{"id": new_id("source"), "url": hit["url"], "title": hit["title"],
                "query": query[:600], "finding": hit["content"][:9000], "retrieved_at": utcnow(),
                "type": "official_documentation"} for hit in hits
               if urlsplit(hit["url"]).hostname in DOMAINS]
    return sources[:3], errors
