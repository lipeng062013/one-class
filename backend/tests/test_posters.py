from tests.conftest import auth_header


def _system_poster_template_id(client, headers) -> int:
    res = client.get("/api/v1/templates/posters", headers=headers)
    assert res.status_code == 200, res.text
    items = res.json()["data"]
    assert len(items) >= 1
    system = next((t for t in items if t.get("is_system") is True), items[0])
    return system["id"]


def test_generate_layout_poster_png(client):
    h = auth_header(client, "ops", "ops123")
    tid = _system_poster_template_id(client, h)

    res = client.post(
        "/api/v1/posters/generate",
        headers=h,
        json={
            "template_id": tid,
            "mode": "layout",
            "title": "嘉壹启航试听",
            "payload": {"subtitle": "嘉定新城", "footer": "扫码预约"},
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["file_path"]
    assert data["mode"] == "layout"
    assert data["title"] == "嘉壹启航试听"
    file_id = data["id"]

    dl = client.get(f"/api/v1/files/posters/{file_id}", headers=h)
    assert dl.status_code == 200, dl.text
    assert dl.headers["content-type"].startswith("image/")
    assert dl.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_ai_image_mock(client, monkeypatch):
    minimal_png = b"\x89PNG\r\n\x1a\n" + b"0" * 64

    def fake_generate_image(**kwargs):
        return minimal_png

    monkeypatch.setattr("app.integrations.image_api.generate_image", fake_generate_image)

    h = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/posters/generate",
        headers=h,
        json={
            "mode": "ai_image",
            "title": "AI 海报",
            "payload": {"subtitle": "测试"},
            "prompt": "绿色教育海报",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["mode"] == "ai_image"
    assert data["file_path"]
    assert data["file_path"].startswith("posters/")


def test_ai_image_without_config_falls_back_to_layout(client, monkeypatch):
    # Force "unconfigured" even if developer .env has IMAGE_* set.
    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("IMAGE_API_KEY", "")
    from app.core.config import clear_settings_cache

    clear_settings_cache()

    def boom(**kwargs):
        from app.integrations.image_api import ImageApiUnavailable

        raise ImageApiUnavailable(
            "IMAGE_API not configured (set IMAGE_API_BASE_URL and IMAGE_API_KEY in .env, then restart backend)"
        )

    monkeypatch.setattr("app.integrations.image_api.generate_image", boom)

    h = auth_header(client, "ops", "ops123")
    tid = _system_poster_template_id(client, h)
    res = client.post(
        "/api/v1/posters/generate",
        headers=h,
        json={
            "template_id": tid,
            "mode": "ai_image",
            "title": "未配置AI时也应出图",
            "payload": {"subtitle": "回退版式", "footer": "本地导出"},
            "prompt": "should-fallback",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["file_path"]
    assert data.get("image_error")
    assert data["mode"] == "layout"
    dl = client.get(f"/api/v1/files/posters/{data['id']}", headers=h)
    assert dl.status_code == 200
    assert dl.content[:8] == b"\x89PNG\r\n\x1a\n"

    clear_settings_cache()


def test_teacher_cannot_generate_poster(client):
    h_ops = auth_header(client, "ops", "ops123")
    tid = _system_poster_template_id(client, h_ops)

    h_teacher = auth_header(client, "teacher1", "t123")
    res = client.post(
        "/api/v1/posters/generate",
        headers=h_teacher,
        json={
            "template_id": tid,
            "mode": "layout",
            "title": "试听",
            "payload": {},
        },
    )
    assert res.status_code == 403
