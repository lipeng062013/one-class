from tests.conftest import auth_header


def test_admin_can_create_knowledge(client):
    h = auth_header(client, "admin", "admin123")
    res = client.post(
        "/api/v1/knowledge",
        headers=h,
        json={"category": "banned", "title": "包过", "content": "禁止承诺包过", "tags": "合规"},
    )
    assert res.status_code == 200


def test_operator_read_only_knowledge(client):
    h_admin = auth_header(client, "admin", "admin123")
    client.post(
        "/api/v1/knowledge",
        headers=h_admin,
        json={"category": "tone", "title": "语气", "content": "温暖专业", "tags": ""},
    )
    h_ops = auth_header(client, "ops", "ops123")
    assert client.get("/api/v1/knowledge", headers=h_ops).status_code == 200
    assert client.post(
        "/api/v1/knowledge",
        headers=h_ops,
        json={"category": "faq", "title": "x", "content": "y"},
    ).status_code == 403


def test_teacher_cannot_read_knowledge(client):
    h = auth_header(client, "teacher1", "t123")
    assert client.get("/api/v1/knowledge", headers=h).status_code == 403
