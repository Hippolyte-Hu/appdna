from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    hcompany_api_key: str = ""
    hcompany_base_url: str = "https://api.hcompany.ai/v1"
    hcompany_model: str = "holo4-27b"
    linkup_api_key: str = ""
    linkup_base_url: str = "https://api.linkup.so"
    gladia_api_key: str = ""
    gladia_base_url: str = "https://api.gladia.io"
    blender_bin: str = "blender"

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def data_dir(self) -> Path:
        path = BACKEND_ROOT / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def artifacts_dir(self) -> Path:
        path = self.data_dir / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_path(self) -> Path:
        return self.data_dir / "appdna.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
