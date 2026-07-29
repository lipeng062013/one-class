import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

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
    db.commit()
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
