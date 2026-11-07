from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    software_name: str = Field(min_length=1, max_length=200)
    software_version: str | None = Field(default=None, max_length=80)
    learning_objective: str = Field(min_length=8, max_length=2000)
    audio_url: str | None = Field(default=None, max_length=2000)
