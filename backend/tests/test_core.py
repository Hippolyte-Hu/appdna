import asyncio
import io
import json

import httpx
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.blender import BlenderAdapter
from app.adapters.script_guard import ScriptRejected
from app.engines.packager import export_package
from app.models import Base, Capability, Evidence, Experiment, KnowledgeClaim, Project
from app.providers.base import ProviderError
from app.providers.gladia import extract_segments
from app.providers.hcompany import HCompanyProvider
from app.store import Store
from app.engines.research import relevant_hits, research_queries
from app.util import classify_url, html_to_text, infer_version, utcnow


def test_classify_and_version():
    assert classify_url("https://docs.blender.org/manual/en/latest/")[0] == "official_documentation"
    assert classify_url("https://github.com/blender/blender")[0] == "github_repository"
    assert classify_url("https://www.youtube.com/watch?v=abc")[0] == "video"
    assert infer_version("https://docs.blender.org/manual/en/4.2/") == "4.2"
    assert html_to_text("<html><style>x</style><p>Cube primitive</p></html>") == "Cube primitive"


def test_research_follows_the_named_application():
    voice = research_queries("VoiceCue", "1.0", "Learn the main controls by clicking them")
    assert all("VoiceCue" in query for query, _, _ in voice)
    assert all("docs.blender.org" not in (include or []) for _, include, _ in voice)
    blender = research_queries("Blender", "5.2", "create a cube")
    assert any(include == ["docs.blender.org"] for _, include, _ in blender)
    hits = [
        {"title": "Mesh Primitives - Blender Manual", "url": "https://docs.blender.org/manual/primitives.html", "content": "cube"},
        {"title": "VoiceCue controls", "url": "https://example.com/voicecue", "content": "VoiceCue listens with Whisper"},
    ]
    kept = relevant_hits(hits, "VoiceCue")
    assert len(kept) == 1
    assert "VoiceCue" in kept[0]["title"]


def test_outcome_links_each_skill_to_the_app_and_its_tool():
    from app.engines.outcome import build_outcome

    outcome = build_outcome(
        software_name="VoiceCue",
        objective="Learn the main controls",
        capabilities=[
            {
                "id": "capability_control",
                "name": "Open controls",
                "description": "Open the control panel.",
                "preconditions": ["The app is focused."],
                "inputs": ["控制"],
                "expected_outputs": ["The panel is visible."],
                "related_claims": ["claim_control"],
                "verification_status": "experimented",
            }
        ],
        claims=[{"id": "claim_control", "claim": "控制 opens the panel."}],
        frames=[{"action": "click", "executed": True, "text": "控制", "learned": "The control panel opened."}],
        source_count=1,
    )
    assert outcome["evaluation"]["verdict"] == "Observed"
    assert outcome["skills"][0]["tools"] == ["控制"]
    assert any(step.startswith("Use 控制") for step in outcome["skills"][0]["steps"])
    assert {"source": "app", "target": "skill:capability_control", "label": "offers"} in outcome["graph"]["edges"]
    assert any(edge["label"] == "uses" and edge["target"].startswith("tool:") for edge in outcome["graph"]["edges"])


def test_unrelated_articles_stay_out_of_the_skills_and_the_graph():
    from app.engines.outcome import build_outcome

    outcome = build_outcome(
        software_name="VoiceCue",
        objective="Learn the main controls",
        capabilities=[
            {
                "id": "capability_other",
                "name": "Upload a podcast",
                "description": "A different product uploads audio to the cloud.",
                "preconditions": [],
                "inputs": ["Audio file"],
                "expected_outputs": [],
                "related_claims": ["claim_other"],
                "verification_status": "discovered",
            },
            {
                "id": "capability_live",
                "name": "Edit script",
                "description": "Switch into the script editor.",
                "preconditions": [],
                "inputs": ["编辑文稿"],
                "expected_outputs": [],
                "related_claims": ["claim_other"],
                "verification_status": "experimented",
            },
        ],
        claims=[
            {
                "id": "claim_other",
                "claim": "VoiceCue uploads podcasts to the cloud.",
                "evidence_ids": ["source_other"],
            }
        ],
        frames=[{"action": "click", "executed": True, "text": "编辑文稿", "learned": "The editor opened."}],
        source_count=4,
        source_relevance={"checked": True, "sources": [{"id": "source_other", "relevant": False, "summary": ""}]},
    )
    assert [item["name"] for item in outcome["skills"]] == ["Edit script"]
    labels = " ".join(node["label"] for node in outcome["graph"]["nodes"])
    assert "podcast" not in labels.lower()
    assert "left out" in " ".join(outcome["evaluation"]["gaps"])


def test_relevant_articles_are_summarized_into_the_graph():
    from app.engines.outcome import build_outcome

    outcome = build_outcome(
        software_name="VoiceCue",
        objective="Learn the main controls",
        capabilities=[
            {
                "id": "capability_live",
                "name": "Edit script",
                "description": "Switch into the script editor.",
                "preconditions": [],
                "inputs": ["编辑文稿"],
                "expected_outputs": [],
                "related_claims": ["claim_local"],
                "verification_status": "experimented",
            }
        ],
        claims=[
            {
                "id": "claim_local",
                "claim": "Scripts stay on this Mac.",
                "evidence_ids": ["source_real"],
            }
        ],
        frames=[{"action": "click", "executed": True, "text": "编辑文稿", "learned": "The editor opened."}],
        source_count=2,
        source_relevance={
            "checked": True,
            "sources": [
                {
                    "id": "source_real",
                    "relevant": True,
                    "summary": "VoiceCue follows the script by listening locally.",
                },
                {"id": "source_other", "relevant": False, "summary": "A different VoiceCue hosts podcasts."},
            ],
        },
    )
    labels = [node["label"] for node in outcome["graph"]["nodes"]]
    assert "VoiceCue follows the script by listening locally." in labels
    assert "Scripts stay on this Mac." in labels
    assert "podcasts" not in " ".join(labels)


def test_clicks_when_the_screen_and_the_documents_disagree():
    from app.engines.learning import needs_click

    assert not needs_click(True, True)
    assert needs_click(True, False)
    assert needs_click(False, True)


def test_gladia_segments_keep_speaker_and_time():
    payload = {
        "status": "done",
        "result": {
            "transcription": {
                "utterances": [
                    {"start": 1.25, "end": 2.5, "speaker": 1, "text": "Add a material", "language": "en"}
                ]
            }
        },
    }
    segments = extract_segments(payload)
    assert segments[0]["speaker"] == 1
    assert segments[0]["start"] == 1.25
    assert segments[0]["text"] == "Add a material"


def test_hcompany_request_uses_configured_model():
    provider = HCompanyProvider("test-key", "https://api.example.test/v1", "configured-model")
    body = provider.build_chat_request(
        [{"role": "user", "content": "hello"}],
        {"type": "object"},
        "capability_graph",
    )
    assert body["model"] == "configured-model"
    assert body["response_format"]["json_schema"]["name"] == "capability_graph"
    assert "holo" not in json.dumps(body["messages"])


def test_hcompany_json_can_be_recovered_from_extra_text():
    from app.providers.hcompany import _parse_json

    parsed = _parse_json('Looking now.\n{"controls": [], "more": "none"}\nThanks.')
    assert parsed["more"] == "none"


def test_hcompany_timeout_names_the_reason(monkeypatch):
    provider = HCompanyProvider("test-key", "https://api.example.test/v1", "configured-model")

    class Client:
        def __init__(self, timeout=None):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            raise httpx.ReadTimeout("")

    monkeypatch.setattr("app.providers.hcompany.httpx.AsyncClient", Client)
    with pytest.raises(ProviderError, match="too long"):
        asyncio.run(provider.complete_json("hello", {"type": "object"}, "capability_graph"))


def test_vision_retries_once_after_a_timeout(monkeypatch):
    provider = HCompanyProvider("test-key", "https://api.example.test/v1", "configured-model")
    calls = {"n": 0}

    class Response:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": '{"controls": [], "more": "none"}'}}]}

    class Client:
        def __init__(self, timeout=None):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ReadTimeout("")
            return Response()

    image = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(image, format="PNG")
    monkeypatch.setattr("app.providers.hcompany.httpx.AsyncClient", Client)
    controls, more = asyncio.run(
        provider.list_controls(software="VoiceCue", objective="learn the controls", image_bytes=image.getvalue(), already=[])
    )
    assert calls["n"] == 2
    assert controls == []
    assert more == "none"


def test_control_inventory_has_room_for_twelve_complete_controls(monkeypatch):
    provider = HCompanyProvider("test-key", "https://api.example.test/v1", "configured-model")
    requests = []

    async def post(body, timeout=120):
        requests.append(body)
        return '{"controls": [], "more": "none"}'

    monkeypatch.setattr(provider, "_post", post)
    image = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(image, format="PNG")
    asyncio.run(provider.list_controls(software="Blender", objective="learn", image_bytes=image.getvalue(), already=[]))
    assert requests[0]["max_tokens"] >= 1800


def test_document_comparison_includes_every_collected_source(tmp_path):
    from types import SimpleNamespace
    from app.orchestrator import _document_brief

    sources = []
    for index in range(10):
        path = tmp_path / f"source_{index}.md"
        path.write_text(f"Application documentation {index}." + "x" * 1000 + "FINAL CONTROL")
        sources.append(SimpleNamespace(id=f"source_{index}", title=f"Article {index}", url=f"https://example.test/{index}", content_reference=str(path)))
    store = SimpleNamespace(sources=lambda project_id: sources)
    brief, ids = _document_brief(store, SimpleNamespace(id="project_test"))
    assert len(ids) == 10
    assert "[source_9]" in brief
    assert brief.count("FINAL CONTROL") == 10


def test_script_guard_rejects_shell_import(tmp_path):
    adapter = BlenderAdapter("blender")
    script = 'import os\nname = "AppDNACube"\nmaterial = "AppDNAMaterial"\nos.system("echo")\n'
    with pytest.raises(ScriptRejected):
        adapter.run_experiment(script, tmp_path, "AppDNACube", "AppDNAMaterial")


def test_passed_checks_cover_cube_and_material():
    from types import SimpleNamespace

    from app.engines.verification import _covered_capabilities

    cube = SimpleNamespace(id="c", name="Add Cube", description="Adds a cube mesh")
    material = SimpleNamespace(id="m", name="Assign Material", description="Assigns a material")
    render = SimpleNamespace(id="r", name="Render", description="Render the view")
    report = {"passed": True, "checks": {"object_type_mesh": True, "material_assigned": True}}
    covered = {item.id for item in _covered_capabilities([cube, material, render], cube, report)}
    assert covered == {"c", "m"}


def test_evaluation_exposes_incomplete_interface_coverage():
    from app.engines.outcome import build_outcome

    outcome = build_outcome(software_name="Blender", objective="learn", capabilities=[], claims=[], source_count=0,
                            frames=[{"action": "wait", "thought": "Coverage incomplete: Mask, Face Sets"}])
    assert "Coverage incomplete: Mask, Face Sets" in outcome["evaluation"]["gaps"]
    verified = build_outcome(software_name="Blender", objective="learn", capabilities=[{"id": "cube", "name": "Create cube", "verification_status": "verified"}], claims=[], source_count=1,
                            frames=[{"action": "wait", "thought": "Coverage incomplete: Mask, Face Sets"}])
    assert verified["evaluation"]["verdict"] == "Incomplete"


def test_graph_does_not_drop_articles_or_leave_dangling_edges():
    from app.engines.outcome import build_outcome

    capabilities = [{"id": f"cap_{i}", "name": f"Control {i}", "description": "Observed", "verification_status": "experimented"} for i in range(32)]
    outcome = build_outcome(software_name="Blender", objective="learn", capabilities=capabilities, claims=[], frames=[], source_count=1,
                            source_relevance={"checked": True, "sources": [{"id": "source_manual", "relevant": True, "summary": "Blender manual"}]})
    ids = {node["id"] for node in outcome["graph"]["nodes"]}
    assert "source:source_manual" in ids
    assert all(edge["source"] in ids and edge["target"] in ids for edge in outcome["graph"]["edges"])


def test_controls_keep_all_relevant_documentation(monkeypatch):
    provider = HCompanyProvider("test-key", "https://api.example.test/v1", "configured-model")
    prompts = []
    async def look(instructions, *args, **kwargs):
        prompts.append(instructions)
        return {"controls": [], "more": "none"}
    monkeypatch.setattr(provider, "_look", look)
    asyncio.run(provider.list_controls(software="Blender", objective="learn", image_bytes=b"image", already=[], covered="x" * 5000 + "FINAL DOCUMENTED CONTROL"))
    assert "FINAL DOCUMENTED CONTROL" in prompts[0]


def test_screen_mismatch_does_not_reject_same_product_plugin(monkeypatch):
    provider = HCompanyProvider("test-key", "https://api.example.test/v1", "configured-model")
    async def look(*args, **kwargs):
        return {"matches": False, "complete": False, "note": "Not visible in this workspace", "sources": [{"id": "source_plugin", "relevant": False, "summary": ""}]}
    async def text(instructions, schema, schema_name):
        assert "blender-craft" in instructions
        return {"sources": [{"id": "source_plugin", "relevant": True, "summary": "A plugin for Blender 3D."}]}
    monkeypatch.setattr(provider, "_look", look)
    monkeypatch.setattr(provider, "complete_json", text)
    result = asyncio.run(provider.compare_with_documents(software="Blender", objective="learn", image_bytes=b"image", documents="[source_plugin] blender-craft\nCreates 3D models in Blender from VSCode."))
    assert result["sources"][0]["relevant"] is True


def test_source_identity_check_batches_and_keeps_full_ids(monkeypatch):
    provider = HCompanyProvider("test-key", "https://api.example.test/v1", "configured-model")
    prompts = []

    async def look(instructions, images, schema, schema_name, max_tokens=700):
        import re
        prompts.append(instructions)
        ids = re.findall(r"\[(source_\d+)\]", instructions)
        assert len(ids) <= 3
        return {"matches": True, "complete": False, "note": "Same product, different screen", "sources": [{"id": sid, "relevant": True, "summary": "Documentation for this application"} for sid in ids]}

    monkeypatch.setattr(provider, "_look", look)
    documents = "\n\n".join(f"[source_{i}] Article {i}\nhttps://example.test/{i}\nSame application, different feature." for i in range(10))
    result = asyncio.run(provider.compare_with_documents(software="Blender", objective="learn", image_bytes=b"test image", documents=documents))
    assert len(result["sources"]) == 10
    assert all(item["relevant"] for item in result["sources"])


def test_article_details_keep_collected_text_beyond_the_excerpt(tmp_path):
    from app.main import _source_payload
    from app.models import KnowledgeSource

    path = tmp_path / "article.txt"
    text = "Documentation. " * 100 + "FINAL PARAGRAPH"
    path.write_text(text)
    source = KnowledgeSource(id="source_test", title="Manual", url="https://example.test/manual", source_type="article", content_reference=str(path), reliability="high")
    payload = _source_payload(source)
    assert payload["content"] == text
    assert len(payload["excerpt"]) == 400
    assert payload["url"] == source.url


def test_scene_check_does_not_verify_click_learned_skills():
    from types import SimpleNamespace
    from app.engines.verification import _covered_capabilities

    cube = SimpleNamespace(id="cube", name="Create cube", description="Create a mesh", verification_status="discovered")
    clicked = SimpleNamespace(id="sculpt", name="Sculpt Mode", description="Shows a cube and material toolbar", verification_status="experimented")
    report = {"passed": True, "checks": {"object_type_mesh": True, "material_assigned": True}}
    assert [item.id for item in _covered_capabilities([cube, clicked], cube, report)] == ["cube"]


def test_package_exports_tool_skills_and_an_evaluation(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    now = utcnow()
    project = Project(
        id="project_test",
        software_name="Blender",
        software_version="5.2",
        learning_objective="Create a cube and assign a material",
        status="verifying",
        error_message=None,
        audio_url=None,
        audio_path=None,
        package_path=None,
        created_at=now,
        updated_at=now,
    )
    session.add(project)
    session.add(
        KnowledgeClaim(
            id="claim_test",
            project_id=project.id,
            claim="A mesh can receive a material.",
            claim_type="capability",
            software_version="5.2",
            evidence_ids_json='["source_test"]',
            confidence=0.8,
            verification_status="verified",
        )
    )
    session.add(
        Capability(
            id="capability_verified",
            project_id=project.id,
            name="Create Material",
            description="Assign a material to a mesh.",
            preconditions_json='["A mesh exists."]',
            inputs_json='["object"]',
            expected_outputs_json='["material assigned"]',
            related_claims_json='["claim_test"]',
            verification_status="verified",
            confidence=0.9,
        )
    )
    session.add(
        Capability(
            id="capability_open",
            project_id=project.id,
            name="Render Scene",
            description="Render the scene.",
            preconditions_json="[]",
            inputs_json="[]",
            expected_outputs_json="[]",
            related_claims_json="[]",
            verification_status="discovered",
            confidence=0.4,
        )
    )
    session.add(
        Experiment(
            id="experiment_test",
            capability_id="capability_verified",
            project_id=project.id,
            objective="Assign a material",
            actions_json=json.dumps([{"script": "import bpy\n"}]),
            observations_json="[]",
            result="success",
            verification_status="verified",
            object_name="AppDNACube",
            material_name="AppDNAMaterial",
            created_at=now,
        )
    )
    session.add(
        Evidence(
            id="evidence_test",
            project_id=project.id,
            origin="https://docs.blender.org/manual/",
            kind="test_result",
            summary="passed",
            payload_json="{}",
            artifact_path=None,
            created_at=now,
        )
    )
    session.commit()
    archive = export_package(Store(session), project, tmp_path, tmp_path / "out")
    unpacked = tmp_path / "out" / "appdna-package"
    manifest = json.loads((unpacked / "manifest.json").read_text())
    assert manifest["software_name"] == "Blender"
    assert (unpacked / "skills" / "create-material.md").exists()
    assert "import bpy" in (unpacked / "skills" / "create-material.md").read_text()
    assert (unpacked / "skills" / "render-scene.md").exists()
    assert "import bpy" not in (unpacked / "skills" / "render-scene.md").read_text()
    graph = json.loads((unpacked / "knowledge-graph.json").read_text())
    assert any(node["kind"] == "app" for node in graph["nodes"])
    assert "Verdict:" in (unpacked / "evaluation.md").read_text()
    assert archive.endswith(".zip")
    session.close()
