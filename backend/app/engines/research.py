from pathlib import Path

import httpx

from app.models import KnowledgeSource, Project
from app.providers.base import ProviderError
from app.providers.linkup import LinkupProvider
from app.store import Store
from app.util import RELIABILITY_RANK, classify_url, html_to_text, infer_version, new_id, utcnow

BLENDER_FALLBACK_URLS = [
    "https://docs.blender.org/manual/en/latest/modeling/meshes/primitives.html",
    "https://docs.blender.org/manual/en/latest/render/materials/introduction.html",
]


def research_queries(
    software_name: str,
    software_version: str,
    objective: str,
) -> list[tuple[str, list[str] | None, list[str] | None]]:
    name = software_name.strip() or "application"
    version = software_version.strip()
    label = f"{name} {version}".strip()
    goal = objective.strip() or f"how to use {label}"
    if name.lower() == "blender":
        manual = version or "current"
        return [
            (
                f"Blender {manual} official manual create a mesh cube primitive and assign a material",
                ["docs.blender.org"],
                None,
            ),
            (
                f"Blender {manual} tutorial create a cube and assign a material",
                None,
                ["docs.blender.org"],
            ),
            (
                "Blender Python example create a cube and assign a material",
                ["github.com"],
                None,
            ),
            (
                f"Blender {manual} video tutorial create a cube and assign a material",
                None,
                None,
            ),
        ]
    return [
        (f"{label} official documentation {goal}", None, None),
        (f"{label} user manual {goal}", None, None),
        (f"{name} source code documentation", ["github.com"], None),
        (f"{label} tutorial {goal}", None, None),
    ]


def relevant_hits(hits: list[dict], software_name: str) -> list[dict]:
    name = software_name.strip().lower()
    if name == "blender":
        return hits
    compact = name.replace(" ", "")
    kept = []
    for hit in hits:
        url = str(hit.get("url") or "")
        title = str(hit.get("title") or "")
        if "blender.org" in f"{url} {title}".lower():
            continue
        blob = f"{url} {title} {str(hit.get('content') or '')[:800]}".lower()
        if name in blob or (compact and compact in blob.replace(" ", "")):
            kept.append(hit)
    return kept


async def collect_sources(
    store: Store,
    project: Project,
    linkup: LinkupProvider,
    artifact_dir: Path,
) -> int:
    hits: list[dict] = []
    errors: list[str] = []
    for query, include, exclude in research_queries(
        project.software_name,
        project.software_version or "",
        project.learning_objective or "",
    ):
        try:
            found = await linkup.search(
                query,
                include_domains=include,
                exclude_domains=exclude,
                max_results=4,
            )
            hits.extend(found)
        except ProviderError as exc:
            errors.append(str(exc))
    hits = relevant_hits(hits, project.software_name)
    used_fallback = False
    if not hits and project.software_name.lower() == "blender":
        used_fallback = True
        hits = await _fetch_official_pages()
        store.log(
            project.id,
            "researching",
            "Linkup did not return sources. Fell back to the official Blender manual.",
        )
    if not hits:
        if project.software_name.lower() == "blender":
            detail = "; ".join(errors) or "no sources"
            raise ProviderError(f"Research produced no sources ({detail})")
        store.log(
            project.id,
            "researching",
            f"No public documentation found for {project.software_name}.",
        )
        return 0

    ranked = []
    seen: set[str] = set()
    for hit in hits:
        url = hit["url"].strip()
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        source_type, reliability = classify_url(url)
        ranked.append((RELIABILITY_RANK.get(reliability, 9), source_type != "official_documentation", hit, source_type, reliability))
    ranked.sort(key=lambda item: (item[0], item[1]))

    artifact_dir.mkdir(parents=True, exist_ok=True)
    kept = 0
    for _, _, hit, source_type, reliability in ranked[:10]:
        source_id = new_id("source")
        path = artifact_dir / f"{source_id}.txt"
        path.write_text(hit["content"][:20000], encoding="utf-8")
        store.db.add(
            KnowledgeSource(
                id=source_id,
                project_id=project.id,
                title=hit["title"][:300],
                url=hit["url"],
                source_type=source_type,
                software_version=infer_version(hit["url"], hit["title"], hit["content"][:500]),
                retrieved_at=utcnow(),
                license=None,
                content_reference=str(path),
                reliability=reliability,
            )
        )
        kept += 1
    store.db.commit()
    note = f"Saved {kept} sources."
    if used_fallback:
        note += " Official-manual fallback was used."
    elif errors:
        note += " Some Linkup queries failed and were skipped."
    store.log(project.id, "researching", note)
    return kept


async def _fetch_official_pages() -> list[dict]:
    hits = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in BLENDER_FALLBACK_URLS:
            try:
                response = await client.get(url, headers={"User-Agent": "AppDNA/1.0"})
            except httpx.HTTPError:
                continue
            if response.status_code >= 400:
                continue
            text = html_to_text(response.text)
            if text:
                hits.append({"title": url.rsplit("/", 1)[-1], "url": url, "content": text})
    return hits
