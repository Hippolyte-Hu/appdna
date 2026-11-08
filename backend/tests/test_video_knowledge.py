import asyncio
import json
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Base, Project, Capability, KnowledgeClaim, KnowledgeSource
from app.store import Store
from app.util import utcnow
from app.engines.video_knowledge import ingest_video

@pytest.mark.parametrize("same_product,expected", [(True, 1), (False, 0), ("false", 0)])
def test_video_observations_have_provenance_and_never_become_verified(tmp_path, same_product, expected):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = Project(id="test", software_name="VoiceCue", learning_objective="Review UI", status="understanding", created_at=utcnow(), updated_at=utcnow())
        db.add(project); db.commit()
        (tmp_path / "frame_000.jpg").write_bytes(b"unit fixture only")
        class Reasoner:
            model = "unit-test"
            async def analyze_recording_frame(self, **kwargs):
                assert kwargs["timestamp"] == 8.0
                return {"same_product": same_product, "product_reason": "Test identity fixture", "observations": [{"capability": "Save script", "control": "Save to Script Library", "observation": "A new sample episode appears"}], "limitations": ["No independent test"]}
        media = {"has_video": True, "frames": [{"timestamp": 8.0, "image": "frame_000.jpg"}], "duration": 12.0}
        result = asyncio.run(ingest_video(Store(db), project, Reasoner(), media, [], tmp_path))
        assert db.query(Capability).count() == expected
        assert db.query(KnowledgeSource).count() == expected
        if expected:
            claim = db.query(KnowledgeClaim).one()
            assert claim.verification_status == "observed"
            assert db.query(Capability).one().verification_status == "observed"
            assert len(json.loads(claim.evidence_ids_json)) == 2
            assert "8.000s" in (tmp_path / "observations.md").read_text()
            assert result["sources"][0]["relevant"] is True
        else:
            assert result["sources"] == []
