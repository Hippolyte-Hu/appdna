import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.blender import BlenderAdapter
from app.adapters.script_guard import ScriptRejected
from app.engines.packager import export_package
from app.models import Base, Capability, Evidence, Experiment, KnowledgeClaim, Project
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


def test_package_exports_only_verified_skills(tmp_path):
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
    assert not (unpacked / "skills" / "render-scene.md").exists()
    assert archive.endswith(".zip")
    session.close()
