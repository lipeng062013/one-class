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


def test_teacher_can_change_own_password(client):
    """非负责人也可自助修改密码（不再只能负责人改）。"""
    headers = auth_header(client, "teacher1", "t123")
    res = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "t123", "new_password": "teacher99"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["changed"] is True
    assert (
        client.post("/api/v1/auth/login", json={"username": "teacher1", "password": "t123"}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "teacher1", "password": "teacher99"}
        ).status_code
        == 200
    )


def test_change_password_rejects_same_as_current(client):
    headers = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "ops123", "new_password": "ops123"},
    )
    assert res.status_code == 400
    assert "相同" in res.json()["error"]["message"]


def test_change_password_wrong_current(client):
    headers = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "wrong", "new_password": "ops4567"},
    )
    assert res.status_code == 400


def test_password_help_public(client):
    res = client.get("/api/v1/auth/password-help")
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["supports_self_reset"] is False
    assert data["method"] == "admin_reset"
    assert isinstance(data["steps"], list) and len(data["steps"]) >= 3
    assert isinstance(data["admins"], list)
    assert any(a.get("display_name") for a in data["admins"])
    # 不泄露敏感字段
    for a in data["admins"]:
        assert "username" not in a
        assert "password" not in a
        assert "id" not in a


def test_forgot_password_notifies_admin_todo(client):
    res = client.post(
        "/api/v1/auth/forgot-password",
        json={"username": "ops", "note": "微信：小王"},
    )
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["accepted"] is True
    assert "负责人" in body["message"] or "重置" in body["message"]

    admin = auth_header(client, "admin", "admin123")
    todos = client.get("/api/v1/todos", headers=admin)
    assert todos.status_code == 200, todos.text
    items = todos.json()["data"]
    hit = [t for t in items if not t["is_done"] and "ops" in (t.get("content") or "")]
    assert hit, items
    assert "密码重置" in hit[0]["title"] or "重置" in hit[0]["title"]
    assert "小王" in hit[0]["content"]


def test_forgot_password_unknown_user_still_ok(client):
    """未知用户名也返回成功，避免账号枚举。"""
    res = client.post(
        "/api/v1/auth/forgot-password",
        json={"username": "no_such_user_xyz", "note": ""},
    )
    assert res.status_code == 200
    assert res.json()["data"]["accepted"] is True


def test_forgot_password_dedupes_within_cooldown(client):
    first = client.post(
        "/api/v1/auth/forgot-password",
        json={"username": "teacher1", "note": "第一次"},
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/auth/forgot-password",
        json={"username": "teacher1", "note": "第二次补充"},
    )
    assert second.status_code == 200

    admin = auth_header(client, "admin", "admin123")
    items = client.get("/api/v1/todos", headers=admin).json()["data"]
    open_hits = [
        t
        for t in items
        if not t["is_done"] and "teacher1" in (t.get("content") or "") and "pwd-reset-request" in (t.get("content") or "")
    ]
    # 冷却期内同一账号只保留一条未完成待办
    assert len(open_hits) == 1
    assert "第二次补充" in open_hits[0]["content"]
