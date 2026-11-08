"""Manual, paid-API acceptance using collected articles and a real negative control.

Run from backend with PYTHONPATH=. .venv/bin/python tests/verify_live_identity.py PROJECT_ID
Does not modify a project, start services, or touch credentials.
"""
import asyncio
import json
from pathlib import Path
import sys
from urllib.request import urlopen

from app.config import get_settings
from app.engines.outcome import build_outcome
from app.providers.hcompany import HCompanyProvider


def main():
    project_id = sys.argv[1]
    project = json.load(urlopen(f"http://127.0.0.1:8787/api/projects/{project_id}"))
    selected = [project["sources"][0], project["sources"][-1]]
    blocks = [f"[{source['id']}] {source['title']}\n{source['url']}\n{source['content']}" for source in selected]
    blocks.append(
        "[source_control_kitchen] BL660 Series Ninja Professional Blender with Single Serve - Owner's Guide\n"
        "https://support.ninjakitchen.com/hc/en-us/articles/4402159497618-BL660-Series-Ninja-Professional-Blender-with-Single-Serve-Owner-s-Guide\n"
        "Product Information & Support > Countertop Appliances > Blenders. "
        "This article contains the Owner's Guide for the BL660 Series Ninja Professional Blender with Single Serve. "
        "This supports the following product SKUs BL660, BL660A, BL660B, BL660CO, BL660WM, BL663, BL663CO, "
        "BL660C, BL660CO, BL660QCN, BL660QPL, BL661BBYC and BL663CCO."
    )
    settings = get_settings()
    provider = HCompanyProvider(settings.hcompany_api_key, settings.hcompany_base_url, settings.hcompany_model)
    folder = settings.artifacts_dir / project_id / "identity-acceptance"
    folder.mkdir(parents=True, exist_ok=True)
    documents = "\n\n".join(blocks)
    (folder / "sources.md").write_text(documents)
    result = asyncio.run(provider.compare_with_documents(
        software="Blender", objective="Learn the main controls",
        image_bytes=(settings.artifacts_dir / project_id / "explore" / "step_01.png").read_bytes(),
        documents=documents,
    ))
    (folder / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    decisions = {item["id"]: item["relevant"] for item in result["sources"]}
    assert decisions[selected[0]["id"]] is True
    assert decisions[selected[1]["id"]] is True
    assert decisions["source_control_kitchen"] is False
    outcome = build_outcome(
        software_name="Blender", objective="learn", capabilities=[], claims=[], frames=[], source_count=3,
        source_relevance={"checked": True, "sources": result["sources"]},
    )
    nodes = {node["id"] for node in outcome["graph"]["nodes"]}
    assert "source:source_control_kitchen" not in nodes
    assert all("source:" + source["id"] in nodes for source in selected)
    print("LIVE IDENTITY AND GRAPH ADMISSION ACCEPTANCE: PASS")


if __name__ == "__main__":
    main()
