from app.engines.report import render_report


def sample():
    return {"id": "project_test", "software_name": "VoiceCue", "software_version": None,
      "status": "failed", "learning_objective": "Review procurement suitability", "error_message": "No app window",
      "updated_at": "2026-11-07", "capabilities": [{"name": "Scroll", "verification_status": "observed", "summary": "Recorded only", "control": "Start", "id": "cap_1", "related_claims": []}],
      "sources": [], "evidence": [], "transcripts": [], "frames": [], "checks": {}, "media": None,
      "outcome": {"evaluation": {"verdict": "Incomplete", "summary": "Not fully covered", "strengths": [], "gaps": ["Untested controls"]}}}


def test_stopped_recorded_run_cannot_claim_procurement_approval():
    report = render_report(sample())
    assert "Not ready for approval" in report
    assert "Recorded observation" in report
    assert "Untested controls" in report
    assert "Security, legal and commercial due diligence" in report
    assert "Not assessed" in report


def test_report_escapes_untrusted_sources_and_app_strings():
    detail = sample(); detail["software_name"] = '<script>alert(1)</script>'
    detail["sources"] = [{"id": "source_1", "title": '<img src=x onerror=alert(1)>', "url": 'javascript:alert(1)', "is_relevant": True}]
    report = render_report(detail)
    assert '<script>' not in report and '<img src=x' not in report
    assert 'href="javascript:' not in report
    assert '&lt;script&gt;' in report


def test_report_retains_all_capabilities_and_source_relevance():
    detail = sample()
    detail["sources"] = [{"id": "wrong", "title": "Kitchen blender", "url": "https://example.com", "is_relevant": False}]
    report = render_report(detail)
    assert "Different product — excluded" in report
    assert "cap_1" in report

def test_report_route_reads_actual_project(monkeypatch):
    from contextlib import contextmanager
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db import Base
    from app.models import Project
    from app import main
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine)
    project = Project(id="report_test", software_name="VoiceCue", status="failed", learning_objective="Pre-UAT", error_message="No window", created_at="now", updated_at="now")
    db.add(project); db.commit()
    @contextmanager
    def scope():
        yield db
    monkeypatch.setattr(main, "session_scope", scope)
    response = main.project_report(project.id)
    assert response.status_code == 200
    assert "VoiceCue" in response.body.decode()
    assert "Evidence verdict: Incomplete" in response.body.decode()
    assert "Not ready for approval" in response.body.decode()


def test_report_uses_live_api_relevance_field_and_displays_evidence_verdict():
    detail = sample()
    detail["sources"] = [{"id": "real-contract", "title": "VoiceCue demo", "url": "https://example.com", "relevant": True}]
    report = render_report(detail)
    assert "Matched product" in report
    assert "Evidence verdict: Incomplete" in report


def test_stopped_run_is_incomplete_without_promoting_recorded_capabilities():
    from app.engines.outcome import build_outcome
    outcome = build_outcome(software_name="VoiceCue", objective="Review the recorded workflow", capabilities=[{"id":"c","name":"Edit script","verification_status":"observed","description":"Visible editor","related_claims":["q"],"confidence":0.6}], claims=[{"id":"q","claim":"An editor is visible","evidence_ids":["video"]}], frames=[], source_count=1, source_relevance={"checked":True,"sources":[{"id":"video","relevant":True,"title":"Authorized recording"}]}, run_status="failed", run_error="No native window available")
    assert outcome["evaluation"]["verdict"] == "Incomplete"
    assert "No native window available" in outcome["evaluation"]["gaps"]
    assert outcome["skills"][0]["status"] == "observed"
