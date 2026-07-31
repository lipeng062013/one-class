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

    # 列表缩略图：JPEG、体积更小，且可缓存
    thumb = client.get(f"/api/v1/files/posters/{file_id}", headers=h, params={"thumb": True})
    assert thumb.status_code == 200, thumb.text
    assert "jpeg" in (thumb.headers.get("content-type") or "").lower()
    assert thumb.content[:2] == b"\xff\xd8"  # JPEG SOI
    assert len(thumb.content) < len(dl.content)
    # 第二次应命中缓存，内容一致
    thumb2 = client.get(f"/api/v1/files/posters/{file_id}", headers=h, params={"thumb": 1, "w": 640})
    assert thumb2.status_code == 200
    assert thumb2.content == thumb.content


def test_upload_poster_manual(client):
    h = auth_header(client, "ops", "ops123")
    # Minimal valid-looking PNG header + padding
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128
    res = client.post(
        "/api/v1/posters/upload",
        headers=h,
        data={"title": "手工海报"},
        files={"file": ("hand.png", png, "image/png")},
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["mode"] == "upload"
    assert data["title"] == "手工海报"
    assert data["file_path"].startswith("posters/")
    dl = client.get(f"/api/v1/files/posters/{data['id']}", headers=h)
    assert dl.status_code == 200
    assert dl.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_upload_poster_requires_title(client):
    h = auth_header(client, "ops", "ops123")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    res = client.post(
        "/api/v1/posters/upload",
        headers=h,
        data={"title": "  "},
        files={"file": ("a.png", png, "image/png")},
    )
    assert res.status_code == 400
    assert "标题" in (res.json().get("detail") or "")


def test_teacher_cannot_upload_poster(client):
    h = auth_header(client, "teacher1", "t123")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    res = client.post(
        "/api/v1/posters/upload",
        headers=h,
        data={"title": "x"},
        files={"file": ("a.png", png, "image/png")},
    )
    assert res.status_code == 403


def test_bulk_delete_posters(client):
    h = auth_header(client, "ops", "ops123")
    tid = _system_poster_template_id(client, h)
    ids = []
    for i in range(2):
        res = client.post(
            "/api/v1/posters/generate",
            headers=h,
            json={
                "template_id": tid,
                "mode": "layout",
                "title": f"批量删{i}",
                "payload": {"subtitle": "t", "footer": "f"},
            },
        )
        assert res.status_code == 200, res.text
        ids.append(res.json()["data"]["id"])
    bulk = client.post("/api/v1/posters/bulk-delete", headers=h, json={"ids": ids})
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["data"]["deleted_count"] == 2
    listed = client.get("/api/v1/posters", headers=h).json()["data"]
    listed_ids = {p["id"] for p in listed}
    assert not set(ids) & listed_ids


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
