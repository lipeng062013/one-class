from tests.conftest import auth_header


def test_list_includes_system_copy_template_after_seed(client):
    h = auth_header(client, "ops", "ops123")
    res = client.get("/api/v1/templates/copies", headers=h)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) >= 1
    assert any(t.get("is_system") is True for t in data)


def test_cannot_delete_system_template(client):
    h = auth_header(client, "admin", "admin123")
    res = client.get("/api/v1/templates/copies", headers=h)
    assert res.status_code == 200
    system = next(t for t in res.json()["data"] if t.get("is_system") is True)
    delete_res = client.delete(f"/api/v1/templates/copies/{system['id']}", headers=h)
    assert delete_res.status_code == 400


def test_ops_can_create_custom_copy_template(client):
    h = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/templates/copies",
        headers=h,
        json={
            "name": "我的老带新",
            "scene": "referral",
            "body": "欢迎{{referrer}}推荐，孩子{{grade}}在学{{subject}}。",
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["is_system"] is False


def test_get_copy_template_detail(client):
    h = auth_header(client, "ops", "ops123")
    created = client.post(
        "/api/v1/templates/copies",
        headers=h,
        json={"name": "详情测", "scene": "xhs_script", "body": "痛点{{pain_point}}"},
    )
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["id"]

    detail = client.get(f"/api/v1/templates/copies/{tid}", headers=h)
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert data["id"] == tid
    assert data["name"] == "详情测"
    assert "pain_point" in data["body"]

    missing = client.get("/api/v1/templates/copies/999999", headers=h)
    assert missing.status_code == 404


def test_get_poster_template_detail(client):
    h = auth_header(client, "ops", "ops123")
    listed = client.get("/api/v1/templates/posters", headers=h)
    assert listed.status_code == 200
    items = listed.json()["data"]
    assert len(items) >= 1
    tid = items[0]["id"]

    detail = client.get(f"/api/v1/templates/posters/{tid}", headers=h)
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert data["id"] == tid
    assert data.get("layout_json") is not None
