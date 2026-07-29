from tests.conftest import auth_header


def test_admin_can_list_users(client):
    headers = auth_header(client, "admin", "admin123")
    res = client.get("/api/v1/users", headers=headers)
    assert res.status_code == 200
    users = res.json()["data"]
    assert len(users) >= 3
    for u in users:
        assert "password" not in u
        assert "password_hash" not in u


def test_operator_cannot_list_users(client):
    headers = auth_header(client, "ops", "ops123")
    res = client.get("/api/v1/users", headers=headers)
    assert res.status_code == 403


def test_admin_create_user_requires_password_and_can_login(client):
    headers = auth_header(client, "admin", "admin123")
    res = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "ops2",
            "display_name": "运营乙",
            "role": "operator",
            "password": "hello12",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["username"] == "ops2"
    assert "password" not in data

    login = client.post("/api/v1/auth/login", json={"username": "ops2", "password": "hello12"})
    assert login.status_code == 200
    assert login.json()["data"]["user"]["role"] == "operator"


def test_create_user_without_password_rejected(client):
    headers = auth_header(client, "admin", "admin123")
    res = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "ops3", "display_name": "运营丙", "role": "operator"},
    )
    assert res.status_code == 422


def test_reset_password(client):
    headers = auth_header(client, "admin", "admin123")
    # ops is id 2 in fixture order
    users = client.get("/api/v1/users", headers=headers).json()["data"]
    ops = next(u for u in users if u["username"] == "ops")
    res = client.post(
        f"/api/v1/users/{ops['id']}/reset-password",
        headers=headers,
        json={"new_password": "newpass1"},
    )
    assert res.status_code == 200
    assert client.post("/api/v1/auth/login", json={"username": "ops", "password": "ops123"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "ops", "password": "newpass1"}).status_code == 200


def test_deactivate_user_blocks_login(client):
    headers = auth_header(client, "admin", "admin123")
    users = client.get("/api/v1/users", headers=headers).json()["data"]
    ops = next(u for u in users if u["username"] == "ops")
    res = client.patch(
        f"/api/v1/users/{ops['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert res.status_code == 200
    login = client.post("/api/v1/auth/login", json={"username": "ops", "password": "ops123"})
    assert login.status_code == 403
