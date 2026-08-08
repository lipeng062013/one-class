from tests.conftest import auth_header


def _user_items(client, headers, **params):
    res = client.get("/api/v1/users", headers=headers, params=params)
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert "items" in body and "total" in body
    return body


def test_admin_can_list_users(client):
    headers = auth_header(client, "admin", "admin123")
    body = _user_items(client, headers)
    assert body["total"] >= 3
    assert len(body["items"]) >= 3
    assert body["page"] == 1
    assert body["page_size"] == 20
    for u in body["items"]:
        assert "password" not in u
        assert "password_hash" not in u


def test_admin_list_users_pagination(client):
    headers = auth_header(client, "admin", "admin123")
    page1 = _user_items(client, headers, page=1, page_size=2)
    assert page1["page"] == 1
    assert page1["page_size"] == 2
    assert len(page1["items"]) == 2
    assert page1["total"] >= 3

    page2 = _user_items(client, headers, page=2, page_size=2)
    assert page2["page"] == 2
    assert len(page2["items"]) >= 1
    ids1 = {u["id"] for u in page1["items"]}
    ids2 = {u["id"] for u in page2["items"]}
    assert ids1.isdisjoint(ids2)

    by_role = _user_items(client, headers, role="admin", page=1, page_size=10)
    assert by_role["total"] >= 1
    assert all(u["role"] == "admin" for u in by_role["items"])


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


def test_create_user_duplicate_display_name_rejected(client):
    headers = auth_header(client, "admin", "admin123")
    res = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "ops_dup_name",
            "display_name": "运营",  # seed 用户 ops 的显示名
            "role": "operator",
            "password": "hello12",
        },
    )
    assert res.status_code == 400, res.text
    assert "显示名" in res.json()["error"]["message"]


def test_reset_password(client):
    headers = auth_header(client, "admin", "admin123")
    # ops is id 2 in fixture order
    users = _user_items(client, headers, page_size=100)["items"]
    ops = next(u for u in users if u["username"] == "ops")
    res = client.post(
        f"/api/v1/users/{ops['id']}/reset-password",
        headers=headers,
        json={"new_password": "newpass1"},
    )
    assert res.status_code == 200
    assert client.post("/api/v1/auth/login", json={"username": "ops", "password": "ops123"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "ops", "password": "newpass1"}).status_code == 200


def test_admin_can_reset_any_user_password(client):
    """负责人可重置任意账号密码（含老师），无需对方当前密码。"""
    headers = auth_header(client, "admin", "admin123")
    users = _user_items(client, headers, page_size=100)["items"]
    teacher = next(u for u in users if u["username"] == "teacher1")
    res = client.post(
        f"/api/v1/users/{teacher['id']}/reset-password",
        headers=headers,
        json={"new_password": "resetbyadmin"},
    )
    assert res.status_code == 200, res.text
    assert (
        client.post("/api/v1/auth/login", json={"username": "teacher1", "password": "t123"}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "teacher1", "password": "resetbyadmin"}
        ).status_code
        == 200
    )


def test_non_admin_cannot_reset_others_password(client):
    """运营/老师不能走用户管理重置他人密码。"""
    admin_headers = auth_header(client, "admin", "admin123")
    users = _user_items(client, admin_headers, page_size=100)["items"]
    teacher = next(u for u in users if u["username"] == "teacher1")
    ops_headers = auth_header(client, "ops", "ops123")
    res = client.post(
        f"/api/v1/users/{teacher['id']}/reset-password",
        headers=ops_headers,
        json={"new_password": "hacked1"},
    )
    assert res.status_code == 403
    # 原密码仍可登录
    assert (
        client.post("/api/v1/auth/login", json={"username": "teacher1", "password": "t123"}).status_code
        == 200
    )


def test_deactivate_user_blocks_login(client):
    headers = auth_header(client, "admin", "admin123")
    users = _user_items(client, headers, page_size=100)["items"]
    ops = next(u for u in users if u["username"] == "ops")
    res = client.patch(
        f"/api/v1/users/{ops['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert res.status_code == 200
    login = client.post("/api/v1/auth/login", json={"username": "ops", "password": "ops123"})
    assert login.status_code == 403


def test_admin_can_delete_user(client):
    headers = auth_header(client, "admin", "admin123")
    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "temp_del",
            "display_name": "待删",
            "role": "teacher",
            "password": "temp1234",
        },
    )
    assert created.status_code == 201, created.text
    uid = created.json()["data"]["id"]
    res = client.delete(f"/api/v1/users/{uid}", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["deleted"] is True
    names = [u["username"] for u in _user_items(client, headers, page_size=100)["items"]]
    assert "temp_del" not in names
    assert client.post("/api/v1/auth/login", json={"username": "temp_del", "password": "temp1234"}).status_code == 401


def test_cannot_delete_self(client):
    headers = auth_header(client, "admin", "admin123")
    users = _user_items(client, headers, page_size=100)["items"]
    admin = next(u for u in users if u["username"] == "admin")
    res = client.delete(f"/api/v1/users/{admin['id']}", headers=headers)
    assert res.status_code == 400
    assert "当前登录" in res.json()["error"]["message"]


def test_admin_can_delete_another_admin(client):
    """Default/guessable 负责人 must be removable after creating a replacement admin."""
    headers = auth_header(client, "admin", "admin123")
    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "boss2",
            "display_name": "新负责人",
            "role": "admin",
            "password": "secure99",
        },
    )
    assert created.status_code == 201, created.text

    # Switch to the new admin, then delete the original default admin
    new_headers = auth_header(client, "boss2", "secure99")
    users = _user_items(client, new_headers, page_size=100)["items"]
    old_admin = next(u for u in users if u["username"] == "admin")
    res = client.delete(f"/api/v1/users/{old_admin['id']}", headers=new_headers)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["deleted"] is True

    names = [u["username"] for u in _user_items(client, new_headers, page_size=100)["items"]]
    assert "admin" not in names
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 401

    # Username is freed for re-creation after soft-delete
    recreate = client.post(
        "/api/v1/users",
        headers=new_headers,
        json={
            "username": "admin",
            "display_name": "新admin",
            "role": "admin",
            "password": "fresh99",
        },
    )
    assert recreate.status_code == 201, recreate.text


def test_delete_teacher_keeps_material_and_learning_author(client):
    """Deleting a teacher must not reassign material/learning authorship."""
    from tests.conftest import first_manager_id

    h_t = auth_header(client, "teacher1", "t123")
    mat = client.post(
        "/api/v1/materials",
        headers=h_t,
        json={"title": "老师原作素材", "auth_status": "authorized"},
    )
    assert mat.status_code == 201, mat.text
    mid = mat.json()["data"]["id"]
    uploader_id = mat.json()["data"]["uploader_id"]
    teacher_id = uploader_id

    h_admin = auth_header(client, "admin", "admin123")
    manager_id = first_manager_id(client, h_admin)

    stu = client.post(
        "/api/v1/students",
        headers=h_admin,
        json={
            "name": "署名测试生",
            "grade": "三年级",
            "school": "测试小学",
            "phone": "13800006666",
            "academic_manager_id": manager_id,
            "courses": [{"name": "署名关联课", "type": "一对多", "price_label": "100元/课时"}],
        },
    )
    assert stu.status_code == 201, stu.text
    sid = stu.json()["data"]["id"]

    rec = client.post(
        "/api/v1/learning-records",
        headers=h_t,
        json={
            "student_id": sid,
            "class_status": "attended",
            "subject": "数学",
            "learning_summary": "今天表现不错",
        },
    )
    assert rec.status_code == 201, rec.text
    rid = rec.json()["data"]["id"]
    assert rec.json()["data"]["teacher_id"] == teacher_id
    assert rec.json()["data"]["teacher_name"] == "老师甲"

    # Delete teacher account
    res = client.delete(f"/api/v1/users/{teacher_id}", headers=h_admin)
    assert res.status_code == 200, res.text
    assert "teacher1" not in [
        u["username"] for u in _user_items(client, h_admin, page_size=100)["items"]
    ]
    assert client.post("/api/v1/auth/login", json={"username": "teacher1", "password": "t123"}).status_code == 401

    # Material still points to original uploader
    detail = client.get(f"/api/v1/materials/{mid}", headers=h_admin)
    assert detail.status_code == 200
    assert detail.json()["data"]["uploader_id"] == uploader_id

    # Learning record still shows original teacher name (soft-deleted row kept)
    learning = client.get("/api/v1/learning-records", headers=h_admin, params={"student_id": sid})
    assert learning.status_code == 200
    _ld = learning.json()["data"]
    _items = _ld["items"] if isinstance(_ld, dict) else _ld
    row = next(r for r in _items if r["id"] == rid)
    assert row["teacher_id"] == teacher_id
    assert row["teacher_name"] == "老师甲"

    # 学管师是 CR，删老师不影响学管归属
    student = client.get(f"/api/v1/students/{sid}", headers=h_admin)
    assert student.status_code == 200
    assert student.json()["data"]["academic_manager_id"] == manager_id

    # 老师账号不可再被指派为学管
    bad = client.post(
        "/api/v1/students",
        headers=h_admin,
        json={
            "name": "不可指派",
            "grade": "一年级",
            "school": "A",
            "phone": "13800007777",
            "academic_manager_id": teacher_id,
            "courses": [{"name": "不可指派测试课"}],
        },
    )
    assert bad.status_code == 400
    assert "学管师" in bad.json()["error"]["message"]


def test_delete_cr_clears_academic_manager_assignment(client):
    """删除学管师账号时，应清空其名下学员的学管归属，且不可再选。"""
    from tests.conftest import first_manager_id

    h_admin = auth_header(client, "admin", "admin123")
    manager_id = first_manager_id(client, h_admin)

    stu = client.post(
        "/api/v1/students",
        headers=h_admin,
        json={
            "name": "学管删除测试生",
            "grade": "二年级",
            "school": "测试小学",
            "phone": "13800008888",
            "academic_manager_id": manager_id,
            "courses": [{"name": "学管删除关联课"}],
        },
    )
    assert stu.status_code == 201, stu.text
    sid = stu.json()["data"]["id"]

    res = client.delete(f"/api/v1/users/{manager_id}", headers=h_admin)
    assert res.status_code == 200, res.text

    student = client.get(f"/api/v1/students/{sid}", headers=h_admin)
    assert student.status_code == 200
    assert student.json()["data"]["academic_manager_id"] is None

    managers_after = client.get("/api/v1/students/managers", headers=h_admin).json()["data"]
    assert all(m["id"] != manager_id for m in managers_after)
    managers_all = client.get(
        "/api/v1/students/managers",
        headers=h_admin,
        params={"include_inactive": True},
    ).json()["data"]
    assert all(m["id"] != manager_id for m in managers_all)

    bad = client.post(
        "/api/v1/students",
        headers=h_admin,
        json={
            "name": "不可指派学管",
            "grade": "一年级",
            "school": "A",
            "phone": "13800009999",
            "academic_manager_id": manager_id,
            "courses": [{"name": "不可指派测试课"}],
        },
    )
    assert bad.status_code == 400
    assert "学管师" in bad.json()["error"]["message"]
