from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def ensure_data_dir() -> None:
    settings = get_settings()
    if settings.database_url.startswith("sqlite:///"):
        raw = settings.database_url.replace("sqlite:///", "", 1)
        path = Path(raw)
        if not path.is_absolute():
            # Resolve relative to backend/ working directory expectation
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
    Path(settings.storage_root).mkdir(parents=True, exist_ok=True)


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
