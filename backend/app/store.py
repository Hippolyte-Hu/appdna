import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Capability, Evidence, Experiment, KnowledgeClaim, KnowledgeSource, Project
from app.util import new_id, utcnow


class Store:
    def __init__(self, db: Session) -> None:
        self.db = db

    def project(self, project_id: str) -> Project | None:
        return self.db.get(Project, project_id)

    def set_status(self, project: Project, status: str, error: str | None = None) -> None:
        project.status = status
        project.updated_at = utcnow()
        if error is not None:
            project.error_message = error
        self.db.commit()

    def log(self, project_id: str, phase: str, message: str) -> None:
        self.db.add(
            Activity(
                id=new_id("activity"),
                project_id=project_id,
                phase=phase,
                message=message[:1000],
                created_at=utcnow(),
            )
        )
        self.db.commit()

    def add_evidence(
        self,
        project_id: str,
        *,
        origin: str,
        kind: str,
        summary: str,
        payload: dict | None = None,
        artifact_path: str | None = None,
    ) -> Evidence:
        row = Evidence(
            id=new_id("evidence"),
            project_id=project_id,
            origin=origin,
            kind=kind,
            summary=summary[:1000],
            payload_json=json.dumps(payload or {}),
            artifact_path=artifact_path,
            created_at=utcnow(),
        )
        self.db.add(row)
        self.db.commit()
        return row

    def sources(self, project_id: str) -> list[KnowledgeSource]:
        return list(
            self.db.scalars(
                select(KnowledgeSource).where(KnowledgeSource.project_id == project_id)
            )
        )

    def claims(self, project_id: str) -> list[KnowledgeClaim]:
        return list(self.db.scalars(select(KnowledgeClaim).where(KnowledgeClaim.project_id == project_id)))

    def capabilities(self, project_id: str) -> list[Capability]:
        return list(self.db.scalars(select(Capability).where(Capability.project_id == project_id)))

    def experiments(self, project_id: str) -> list[Experiment]:
        return list(self.db.scalars(select(Experiment).where(Experiment.project_id == project_id)))

    def evidence(self, project_id: str) -> list[Evidence]:
        return list(self.db.scalars(select(Evidence).where(Evidence.project_id == project_id)))

    def activities(self, project_id: str) -> list[Activity]:
        return list(
            self.db.scalars(
                select(Activity).where(Activity.project_id == project_id).order_by(Activity.created_at)
            )
        )
