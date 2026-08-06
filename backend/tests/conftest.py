import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import hash_password
from app.core.storage import LocalStorage, get_storage
from app.main import app
from app.models.user import User
from app.seed import seed_sample_knowledge, seed_system_templates


@pytest.fixture()
def client(tmp_path: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    storage_root = tmp_path / "uploads"
    storage_root.mkdir(parents=True, exist_ok=True)
    test_storage = LocalStorage(str(storage_root))

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    def override_get_storage():
        return test_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage

    db = TestingSession()
    db.add(
        User(
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="负责人",
            role="admin",
        )
    )
    db.add(
        User(
            username="ops",
            password_hash=hash_password("ops123"),
            display_name="运营",
            role="operator",
        )
    )
    db.add(
        User(
            username="teacher1",
            password_hash=hash_password("t123"),
            display_name="老师甲",
            role="teacher",
        )
    )
    db.add(
        User(
            username="cr1",
            password_hash=hash_password("cr11234"),
            display_name="学管甲",
            role="cr",
        )
    )
    db.commit()
    seed_system_templates(db)
    seed_sample_knowledge(db)
    db.close()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def auth_header(client: TestClient, username: str, password: str) -> dict:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def first_manager_id(client: TestClient, headers: dict, username: str = "cr1") -> int:
    """Return a CR 学管师 id from /students/managers (default demo cr1)."""
    managers = client.get("/api/v1/students/managers", headers=headers).json()["data"]
    match = next((m for m in managers if m.get("username") == username), None)
    assert match is not None, f"manager {username} not found in {managers}"
    return int(match["id"])
