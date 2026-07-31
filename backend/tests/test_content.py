from tests.conftest import auth_header


def _create_material(client, headers, pain_point="应用题慢"):
    res = client.post(
        "/api/v1/materials",
        headers=headers,
        json={
            "title": "课堂进步",
            "grade": "四年级",
            "subject": "数学",
            "pain_point": pain_point,
            "teacher_action": "拆步骤示范",
            "next_step": "预约试听",
            "auth_status": "authorized",
        },
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["data"]["id"]


def _create_template(client, headers, body="孩子痛点：{{pain_point}}，我们这样帮：{{teacher_action}}"):
    res = client.post(
        "/api/v1/templates/copies",
        headers=headers,
        json={
            "name": "测试文案模板",
            "scene": "xhs_script",
            "body": body,
        },
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["data"]["id"]


def test_generate_copy_template_only(client):
    h = auth_header(client, "ops", "ops123")
    mid = _create_material(client, h, pain_point="应用题慢")
    tid = _create_template(client, h, body="痛点是{{pain_point}}，加油！")

    res = client.post(
        "/api/v1/copies/generate",
        headers=h,
        json={"material_id": mid, "template_id": tid, "mode": "template", "platform": "xhs"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert "应用题" in data["body"]
    assert data["mode"] == "template"
    assert data["platform"] == "xhs"


def test_get_copy_detail(client):
    h = auth_header(client, "ops", "ops123")
    mid = _create_material(client, h, pain_point="应用题慢")
    tid = _create_template(client, h, body="痛点是{{pain_point}}，加油！")
    res = client.post(
        "/api/v1/copies/generate",
        headers=h,
        json={"material_id": mid, "template_id": tid, "mode": "template", "platform": "xhs"},
    )
    assert res.status_code == 200, res.text
    cid = res.json()["data"]["id"]

    detail = client.get(f"/api/v1/copies/{cid}", headers=h)
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert data["id"] == cid
    assert "应用题" in data["body"]
    assert data["mode"] == "template"
    assert data["platform"] == "xhs"
    assert data["material_id"] == mid
    assert isinstance(data.get("banned_hits"), list)

    missing = client.get("/api/v1/copies/999999", headers=h)
    assert missing.status_code == 404


def test_bulk_delete_copies(client):
    h = auth_header(client, "ops", "ops123")
    mid = _create_material(client, h)
    tid = _create_template(client, h)
    ids = []
    for _ in range(2):
        res = client.post(
            "/api/v1/copies/generate",
            headers=h,
            json={"material_id": mid, "template_id": tid, "mode": "template", "platform": "xhs"},
        )
        assert res.status_code == 200, res.text
        ids.append(res.json()["data"]["id"])
    bulk = client.post("/api/v1/copies/bulk-delete", headers=h, json={"ids": ids})
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["data"]["deleted_count"] == 2
    listed = client.get("/api/v1/copies", headers=h).json()["data"]
    listed_ids = {c["id"] for c in listed}
    assert not set(ids) & listed_ids


def test_generate_with_llm_mock(client, monkeypatch):
    def fake_chat(messages, **kwargs):
        return "【润色】测试文案"

    monkeypatch.setattr("app.integrations.llm.chat_completion", fake_chat)

    h = auth_header(client, "ops", "ops123")
    mid = _create_material(client, h)
    tid = _create_template(client, h)

    res = client.post(
        "/api/v1/copies/generate",
        headers=h,
        json={
            "material_id": mid,
            "template_id": tid,
            "mode": "template_then_llm",
            "platform": "xhs",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert "润色" in data["body"]
    assert data["mode"] == "template_then_llm"
    assert data.get("llm_error") in (None, "")


def test_banned_words_reported(client):
    h_admin = auth_header(client, "admin", "admin123")
    banned_res = client.post(
        "/api/v1/knowledge",
        headers=h_admin,
        json={"category": "banned", "title": "包过", "content": "禁止承诺包过", "tags": "合规"},
    )
    assert banned_res.status_code == 200, banned_res.text

    h = auth_header(client, "ops", "ops123")
    mid = _create_material(client, h)
    tid = _create_template(client, h, body="本机构包过考试，欢迎咨询。")

    res = client.post(
        "/api/v1/copies/generate",
        headers=h,
        json={"material_id": mid, "template_id": tid, "mode": "template", "platform": "xhs"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert "包过" in data["banned_hits"]
    assert "包过" in data["body"]


def test_teacher_cannot_generate(client):
    h_ops = auth_header(client, "ops", "ops123")
    mid = _create_material(client, h_ops)
    tid = _create_template(client, h_ops)

    h_teacher = auth_header(client, "teacher1", "t123")
    res = client.post(
        "/api/v1/copies/generate",
        headers=h_teacher,
        json={"material_id": mid, "template_id": tid, "mode": "template", "platform": "xhs"},
    )
    assert res.status_code == 403


def test_llm_mode_without_config_falls_back(client):
    """Direct LLM mode must not 503 when keys missing — return draft + llm_error."""
    h = auth_header(client, "ops", "ops123")
    mid = _create_material(client, h)
    tid = _create_template(client, h)
    res = client.post(
        "/api/v1/copies/generate",
        headers=h,
        json={
            "material_id": mid,
            "template_id": tid,
            "mode": "llm",
            "platform": "xhs",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["body"]
    assert data.get("llm_error")
    assert "未配置" in data["llm_error"] or "LLM" in data["llm_error"] or "大模型" in data["llm_error"]
