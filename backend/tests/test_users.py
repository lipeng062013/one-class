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
    names = [u["username"] for u in client.get("/api/v1/users", headers=headers).json()["data"]]
    assert "temp_del" not in names
    assert client.post("/api/v1/auth/login", json={"username": "temp_del", "password": "temp1234"}).status_code == 401


def test_cannot_delete_self(client):
    headers = auth_header(client, "admin", "admin123")
    users = client.get("/api/v1/users", headers=headers).json()["data"]
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
    users = client.get("/api/v1/users", headers=new_headers).json()["data"]
    old_admin = next(u for u in users if u["username"] == "admin")
    res = client.delete(f"/api/v1/users/{old_admin['id']}", headers=new_headers)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["deleted"] is True

    names = [u["username"] for u in client.get("/api/v1/users", headers=new_headers).json()["data"]]
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
    h_t = auth_header(client, "teacher1", "t123")
    mat = client.post(
        "/api/v1/materials",
        headers=h_t,
        json={"title": "老师原作素材", "auth_status": "authorized"},
    )
    assert mat.status_code == 201, mat.text
    mid = mat.json()["data"]["id"]
    uploader_id = mat.json()["data"]["uploader_id"]

    h_admin = auth_header(client, "admin", "admin123")
    managers = client.get("/api/v1/students/managers", headers=h_admin).json()["data"]
    teacher_id = next(m["id"] for m in managers if m["username"] == "teacher1")
    assert teacher_id == uploader_id

    stu = client.post(
        "/api/v1/students",
        headers=h_admin,
        json={
            "name": "署名测试生",
            "grade": "三年级",
            "school": "测试小学",
            "academic_manager_id": teacher_id,
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
        u["username"] for u in client.get("/api/v1/users", headers=h_admin).json()["data"]
    ]
    assert client.post("/api/v1/auth/login", json={"username": "teacher1", "password": "t123"}).status_code == 401

    # Material still points to original uploader
    detail = client.get(f"/api/v1/materials/{mid}", headers=h_admin)
    assert detail.status_code == 200
    assert detail.json()["data"]["uploader_id"] == uploader_id

    # Learning record still shows original teacher name (soft-deleted row kept)
    learning = client.get("/api/v1/learning-records", headers=h_admin, params={"student_id": sid})
    assert learning.status_code == 200
    row = next(r for r in learning.json()["data"] if r["id"] == rid)
    assert row["teacher_id"] == teacher_id
    assert row["teacher_name"] == "老师甲"

    # Current 学管 assignment cleared (operational, not historical authorship)
    student = client.get(f"/api/v1/students/{sid}", headers=h_admin)
    assert student.status_code == 200
    assert student.json()["data"]["academic_manager_id"] is None

    # 新建学生 / 改学管下拉：已删除老师不可再选
    managers_after = client.get("/api/v1/students/managers", headers=h_admin).json()["data"]
    assert all(m["id"] != teacher_id for m in managers_after)
    assert all(m.get("username") != "teacher1" for m in managers_after)
    # 即使带 include_inactive 也不应出现
    managers_all = client.get(
        "/api/v1/students/managers",
        headers=h_admin,
        params={"include_inactive": True},
    ).json()["data"]
    assert all(m["id"] != teacher_id for m in managers_all)

    # 后端也拒绝把已删除老师指派为学管
    bad = client.post(
        "/api/v1/students",
        headers=h_admin,
        json={
            "name": "不可指派",
            "grade": "一年级",
            "school": "A",
            "academic_manager_id": teacher_id,
        },
    )
    assert bad.status_code == 400
    assert "学管师" in bad.json()["error"]["message"]
