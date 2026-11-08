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
    chatwoot_base_url: str = "http://127.0.0.1:3001"
    chatwoot_account_id: int = 1
    chatwoot_inbox_id: int = 1
    chatwoot_api_token: str = ""
    chatwoot_version: str = "4.8.0"
    chatwoot_storage_state: str = ""
    chatwoot_test_environment: bool = False
    browser_headless: bool = True

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

    @property
    def browser_state_path(self) -> Path:
        path = Path(self.chatwoot_storage_state or "data/chatwoot-session.json")
        return path if path.is_absolute() else BACKEND_ROOT / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
