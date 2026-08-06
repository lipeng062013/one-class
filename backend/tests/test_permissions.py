from tests.conftest import auth_header


def test_permission_catalog_admin_only(client):
    admin = auth_header(client, "admin", "admin123")
    res = client.get("/api/v1/users/permissions/catalog", headers=admin)
    assert res.status_code == 200, res.text
    groups = res.json()["data"]["groups"]
    assert len(groups) >= 4
    codes = {p["code"] for g in groups for p in g["permissions"]}
    assert "users.manage" in codes
    assert "finance.read" in codes
    assert "copies.use" in codes

    ops = auth_header(client, "ops", "ops123")
    assert client.get("/api/v1/users/permissions/catalog", headers=ops).status_code == 403


def test_me_returns_effective_permissions(client):
    admin = auth_header(client, "admin", "admin123")
    me = client.get("/api/v1/auth/me", headers=admin)
    assert me.status_code == 200
    data = me.json()["data"]
    assert "users.manage" in data["permissions"]
    assert data["extra_permissions"] == []

    ops = auth_header(client, "ops", "ops123")
    me_ops = client.get("/api/v1/auth/me", headers=ops).json()["data"]
    assert "copies.use" in me_ops["permissions"]
    assert "users.manage" not in me_ops["permissions"]
    assert "finance.read" not in me_ops["permissions"]


def test_admin_can_grant_and_revoke_extra_permissions(client):
    admin = auth_header(client, "admin", "admin123")
    users = client.get("/api/v1/users", headers=admin, params={"page_size": 100}).json()["data"]["items"]
    ops = next(u for u in users if u["username"] == "ops")

    # Grant finance + enrollments to operator
    put = client.put(
        f"/api/v1/users/{ops['id']}/permissions",
        headers=admin,
        json={"extra_permissions": ["finance.read", "enrollments.manage"]},
    )
    assert put.status_code == 200, put.text
    body = put.json()["data"]
    assert "finance.read" in body["extra_permissions"]
    assert "enrollments.manage" in body["extra_permissions"]
    assert "finance.read" in body["effective_permissions"]
    # Role defaults still present
    assert "copies.use" in body["effective_permissions"]
    # Storing a role-default code is stripped from extras
    assert "copies.use" not in body["extra_permissions"]

    # Operator can now hit enrollments list
    ops_h = auth_header(client, "ops", "ops123")
    me = client.get("/api/v1/auth/me", headers=ops_h).json()["data"]
    assert "finance.read" in me["permissions"]
    enr = client.get("/api/v1/enrollments", headers=ops_h)
    assert enr.status_code == 200, enr.text

    # Revoke all extras
    rev = client.put(
        f"/api/v1/users/{ops['id']}/permissions",
        headers=admin,
        json={"extra_permissions": []},
    )
    assert rev.status_code == 200
    assert rev.json()["data"]["extra_permissions"] == []
    ops_h2 = auth_header(client, "ops", "ops123")
    assert client.get("/api/v1/enrollments", headers=ops_h2).status_code == 403


def test_grant_unknown_permission_rejected(client):
    admin = auth_header(client, "admin", "admin123")
    users = client.get("/api/v1/users", headers=admin, params={"page_size": 100}).json()["data"]["items"]
    ops = next(u for u in users if u["username"] == "ops")
    res = client.put(
        f"/api/v1/users/{ops['id']}/permissions",
        headers=admin,
        json={"extra_permissions": ["not.a.real.perm"]},
    )
    assert res.status_code == 400


def test_teacher_cannot_use_copies_until_granted(client):
    teacher = auth_header(client, "teacher1", "t123")
    assert client.get("/api/v1/copies", headers=teacher).status_code == 403

    admin = auth_header(client, "admin", "admin123")
    users = client.get("/api/v1/users", headers=admin, params={"page_size": 100}).json()["data"]["items"]
    t = next(u for u in users if u["username"] == "teacher1")
    client.put(
        f"/api/v1/users/{t['id']}/permissions",
        headers=admin,
        json={"extra_permissions": ["copies.use"]},
    )
    teacher2 = auth_header(client, "teacher1", "t123")
    assert client.get("/api/v1/copies", headers=teacher2).status_code == 200
