from tests.conftest import auth_header


def test_integrations_status_for_ops(client):
    h = auth_header(client, "ops", "ops123")
    res = client.get("/api/v1/system/integrations", headers=h)
    assert res.status_code == 200
    data = res.json()["data"]
    assert "llm" in data
    assert "image" in data
    assert isinstance(data["llm"]["configured"], bool)
    assert isinstance(data["image"]["configured"], bool)
    assert "app_env" in data
    assert "seed_demo_data" in data
    assert isinstance(data["seed_demo_data"], bool)


def test_teacher_cannot_see_integrations(client):
    h = auth_header(client, "teacher1", "t123")
    assert client.get("/api/v1/system/integrations", headers=h).status_code == 403
