from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    assert body["data"]["status"] == "ok"
