from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from several common locations (backend cwd, project root, backend/.env)
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = _BACKEND_DIR.parent
_ENV_FILES = (
    str(_PROJECT_ROOT / ".env"),
    str(_BACKEND_DIR / ".env"),
    ".env",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/app.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    storage_root: str = "./data/uploads"

    # OpenAI-compatible chat API (many 中转站 / 国内兼容接口)
    # Client calls: {LLM_BASE_URL}/v1/chat/completions
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # OpenAI-compatible images API
    # Client calls: {IMAGE_API_BASE_URL}/v1/images/generations
    image_api_base_url: str = ""
    image_api_key: str = ""
    image_model: str = "dall-e-3"

    seed_admin_username: str = "admin"
    seed_admin_password: str = "admin123"
    seed_ops_username: str = "ops"
    seed_ops_password: str = "ops123"
    seed_teacher_username: str = "teacher1"
    seed_teacher_password: str = "t123"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    """Call after changing env in tests."""
    get_settings.cache_clear()
