from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/app.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    storage_root: str = "./data/uploads"

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    image_api_base_url: str = ""
    image_api_key: str = ""
    image_model: str = ""

    seed_admin_username: str = "admin"
    seed_admin_password: str = "admin123"
    seed_ops_username: str = "ops"
    seed_ops_password: str = "ops123"
    seed_teacher_username: str = "teacher1"
    seed_teacher_password: str = "t123"


@lru_cache
def get_settings() -> Settings:
    return Settings()
