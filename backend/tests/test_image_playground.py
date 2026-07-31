from tests.conftest import auth_header


def test_image_playground_config_for_ops(client, monkeypatch):
    monkeypatch.setenv("IMAGE_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("IMAGE_API_KEY", "sk-from-env")
    monkeypatch.setenv("IMAGE_MODEL", "gpt-image-2")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    h = auth_header(client, "ops", "ops123")
    res = client.get("/api/v1/image-playground/config", headers=h)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["ready"] is True
    assert data["model"] == "gpt-image-2"
    # Must be a path whose only /v1 is at the end (playground normalizeBaseUrl)
    assert data["api_base_path"] == "/image-api/v1"
    assert "api.example.com" not in str(data)
    assert "sk-from-env" not in str(data)
    clear_settings_cache()


def test_teacher_cannot_use_image_playground(client):
    h = auth_header(client, "teacher1", "t123")
    assert client.get("/api/v1/image-playground/config", headers=h).status_code == 403
    assert client.post(
        "/image-api/v1/images/generations",
        headers=h,
        json={"model": "gpt-image-2", "prompt": "x"},
    ).status_code == 403


def test_proxy_rejects_disallowed_path(client, monkeypatch):
    monkeypatch.setenv("IMAGE_API_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("IMAGE_API_KEY", "sk-test")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    h = auth_header(client, "ops", "ops123")
    res = client.get("/image-api/v1/secret/admin", headers=h)
    assert res.status_code == 404
    clear_settings_cache()


def test_proxy_unconfigured_returns_503(client, monkeypatch):
    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("IMAGE_API_KEY", "")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    h = auth_header(client, "ops", "ops123")
    res = client.post(
        "/image-api/v1/images/generations",
        headers=h,
        json={"model": "gpt-image-2", "prompt": "x"},
    )
    assert res.status_code == 503
    clear_settings_cache()
