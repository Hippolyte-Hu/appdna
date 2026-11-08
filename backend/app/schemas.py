from pydantic import BaseModel, Field, model_validator
from app.targets import product_name, validate_web_target


class ProjectCreate(BaseModel):
    software_name: str = Field(min_length=1, max_length=2000)
    software_version: str | None = Field(default=None, max_length=80)
    learning_objective: str = Field(min_length=8, max_length=2000)
    audio_url: str | None = Field(default=None, max_length=2000)
    target_url: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def normalize_target(self):
        self.software_name = self.software_name.strip()
        self.learning_objective = self.learning_objective.strip()
        if not self.software_name or len(self.learning_objective) < 8:
            raise ValueError("Enter an application and an objective of at least 8 characters")
        if ":" in self.software_name or "://" in self.software_name:
            self.target_url = validate_web_target(self.software_name)
            self.software_name = product_name(self.target_url)
        elif len(self.software_name) > 200 or any(c in self.software_name for c in ['"', "\\", "\n", "\r"]):
            raise ValueError("Use the installed application name or a full website URL")
        if self.target_url:
            validate_web_target(self.target_url)
        return self
