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
