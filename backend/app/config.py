"""Application settings, loaded from environment variables (or a .env file)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), extra="ignore", case_sensitive=False
    )

    # Comma separated provider keys, e.g. "AIza...,AIza...". Never logged or returned.
    llm_api_keys: str = ""
    llm_model: str = "gemini/gemini-2.0-flash"
    database_url: str = "sqlite:///./app.db"
    allowed_origins: str = "http://localhost:3000"
    enable_failure_simulation: bool = False
    llm_timeout_seconds: float = 30.0
    default_system_prompt: str = "You are a helpful assistant."

    @property
    def api_keys(self) -> list[str]:
        return [k.strip() for k in self.llm_api_keys.split(",") if k.strip()]

    @property
    def key_ids(self) -> list[str]:
        """key_1, key_2, ... in the same order as the keys."""
        return [f"key_{i}" for i in range(1, len(self.api_keys) + 1)]

    @property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
