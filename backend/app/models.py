from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    software_name: Mapped[str] = mapped_column(String(200))
    target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    software_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    learning_objective: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="created")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    package_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(40))
    software_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    retrieved_at: Mapped[str] = mapped_column(String(40))
    license: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content_reference: Mapped[str] = mapped_column(Text)
    reliability: Mapped[str] = mapped_column(String(20))


class KnowledgeClaim(Base):
    __tablename__ = "knowledge_claims"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    claim: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(String(40))
    software_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    evidence_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[float] = mapped_column()
    verification_status: Mapped[str] = mapped_column(String(40), default="discovered")


class Capability(Base):
    __tablename__ = "capabilities"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    preconditions_json: Mapped[str] = mapped_column(Text, default="[]")
    inputs_json: Mapped[str] = mapped_column(Text, default="[]")
    expected_outputs_json: Mapped[str] = mapped_column(Text, default="[]")
    related_claims_json: Mapped[str] = mapped_column(Text, default="[]")
    verification_status: Mapped[str] = mapped_column(String(40), default="discovered")
    confidence: Mapped[float] = mapped_column()


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    capability_id: Mapped[str] = mapped_column(ForeignKey("capabilities.id"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    objective: Mapped[str] = mapped_column(Text)
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    observations_json: Mapped[str] = mapped_column(Text, default="[]")
    result: Mapped[str] = mapped_column(String(40), default="pending")
    verification_status: Mapped[str] = mapped_column(String(40), default="discovered")
    object_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    material_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    origin: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    phase: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40))
