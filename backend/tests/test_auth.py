from tests.conftest import auth_header


def test_login_success(client):
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    data = body["data"]
    assert data["access_token"]
    assert data["user"]["role"] == "admin"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_login_ops_success(client):
    res = client.post("/api/v1/auth/login", json={"username": "ops", "password": "ops123"})
    assert res.status_code == 200
    assert res.json()["data"]["user"]["role"] == "operator"


def test_login_teacher_success(client):
    res = client.post("/api/v1/auth/login", json={"username": "teacher1", "password": "t123"})
    assert res.status_code == 200
    assert res.json()["data"]["user"]["role"] == "teacher"


def test_login_failure(client):
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})
    assert res.status_code == 401
    assert res.json()["error"]["message"] == "账号或密码错误"


def test_me(client):
    headers = auth_header(client, "ops", "ops123")
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    user = res.json()["data"]
    assert user["username"] == "ops"
    assert "password_hash" not in user


def test_change_password(client):
    headers = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "ops123", "new_password": "ops4567"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["changed"] is True

    bad = client.post("/api/v1/auth/login", json={"username": "ops", "password": "ops123"})
    assert bad.status_code == 401

    good = client.post("/api/v1/auth/login", json={"username": "ops", "password": "ops4567"})
    assert good.status_code == 200


def test_change_password_wrong_current(client):
    headers = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "wrong", "new_password": "ops4567"},
    )
    assert res.status_code == 400
