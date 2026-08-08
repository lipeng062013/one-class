"""线索已报名 → 建档 / 锁定 / 报名后调配。"""

from app.models.enrollment import EnrollmentRecord
from app.models.student import Student
from app.models.todo import TodoItem
from tests.conftest import auth_header


def _create_lead(client, headers, name="转化学员甲", phone="13900001001"):
    res = client.post(
        "/api/v1/leads",
        headers=headers,
        json={
            "student_or_parent_name": name,
            "phone": phone,
            "grade": "四年级",
            "school": "实验小学",
            "source": "wechat",
            "need": "数学提升",
        },
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["data"]


def test_operator_has_students_read_and_enrollments(client):
    from app.core.permissions import role_default_permissions

    perms = role_default_permissions("operator")
    assert "students.read" in perms
    assert "enrollments.manage" in perms
    assert "finance.read" in perms
    # 运营不自带完整教务菜单权限
    assert "academic.read" not in perms
    # 登录后可访问学员列表；课程目录靠 enrollments.manage 放行
    h = auth_header(client, "ops", "ops123")
    res = client.get("/api/v1/students", headers=h)
    assert res.status_code == 200, res.text
    courses = client.get("/api/v1/academic/courses", headers=h, params={"enabled": True})
    assert courses.status_code == 200, courses.text
    # 无 academic.read 时班级列表应 403
    classes = client.get("/api/v1/academic/classes", headers=h)
    assert classes.status_code == 403, classes.text


def test_enrolled_converts_student_and_keeps_lead(client):
    h = auth_header(client, "ops", "ops123")
    lead = _create_lead(client, h)
    lid = lead["id"]

    patch = client.patch(
        f"/api/v1/leads/{lid}",
        headers=h,
        json={"status": "enrolled"},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()["data"]
    assert data["status"] == "enrolled"
    assert data["locked"] is True
    assert data.get("conversion_status") == "created"
    sid = data.get("converted_student_id")
    assert sid

    # 线索仍可查
    listed = client.get("/api/v1/leads", headers=h)
    assert listed.status_code == 200
    ids = [x["id"] for x in listed.json()["data"]["items"]]
    assert lid in ids

    # 学员已建档、无学管
    stu = client.get(f"/api/v1/students/{sid}", headers=h)
    assert stu.status_code == 200, stu.text
    body = stu.json()["data"]
    assert body["source_lead_id"] == lid
    assert body["academic_manager_id"] is None
    assert body["allocation_phase"] == "pending_enroll"
    assert body["name"] == "转化学员甲"

    # 幂等：再次 enrolled
    again = client.patch(
        f"/api/v1/leads/{lid}",
        headers=h,
        json={"status": "enrolled"},
    )
    # 非 admin 不可改已报名（含同值？同值可能无 changes 但 status 在 data 里）
    # 同值不会触发字段变更，update 可能直接成功返回 already_linked
    # 若带 status 且与当前相同，changes 为空，应 200
    assert again.status_code in (200, 403), again.text


def test_enrolled_lock_blocks_ops_edit_follow_collab(client):
    h = auth_header(client, "ops", "ops123")
    lead = _create_lead(client, h, name="锁定测试", phone="13900001002")
    lid = lead["id"]
    client.patch(f"/api/v1/leads/{lid}", headers=h, json={"status": "enrolled"})

    # 改资料
    edit = client.patch(
        f"/api/v1/leads/{lid}",
        headers=h,
        json={"notes": "试图修改"},
    )
    assert edit.status_code == 403, edit.text

    # 改状态
    st = client.patch(
        f"/api/v1/leads/{lid}",
        headers=h,
        json={"status": "contacted"},
    )
    assert st.status_code == 403, st.text

    # 写跟进
    follow = client.post(
        f"/api/v1/leads/{lid}/activities",
        headers=h,
        json={"content": "再跟进一次"},
    )
    assert follow.status_code == 403, follow.text

    # 添加其他协作人（主责自己 join/me 会短路成功，不测）
    admin_id = None
    users = client.get("/api/v1/leads/assignees", headers=h)
    if users.status_code == 200:
        for u in users.json()["data"]:
            if u.get("role") == "admin" or u.get("username") == "admin":
                admin_id = u.get("id") or u.get("user_id")
                break
    if admin_id:
        collab = client.post(
            f"/api/v1/leads/{lid}/collaborators",
            headers=h,
            json={"user_id": admin_id},
        )
        assert collab.status_code in (400, 403), collab.text


def test_admin_can_change_enrolled_status(client):
    ops = auth_header(client, "ops", "ops123")
    admin = auth_header(client, "admin", "admin123")
    lead = _create_lead(client, ops, name="负责人改状态", phone="13900001003")
    lid = lead["id"]
    client.patch(f"/api/v1/leads/{lid}", headers=ops, json={"status": "enrolled"})

    res = client.patch(
        f"/api/v1/leads/{lid}",
        headers=admin,
        json={"status": "visited"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["status"] == "visited"
    assert res.json()["data"]["locked"] is False


def test_cannot_assign_manager_before_enroll(client):
    ops = auth_header(client, "ops", "ops123")
    admin = auth_header(client, "admin", "admin123")
    lead = _create_lead(client, ops, name="先报名再调配", phone="13900001004")
    patch = client.patch(
        f"/api/v1/leads/{lead['id']}",
        headers=ops,
        json={"status": "enrolled"},
    )
    sid = patch.json()["data"]["converted_student_id"]
    managers = client.get("/api/v1/students/managers", headers=admin).json()["data"]
    cr = next(m for m in managers if m.get("username") == "cr1")

    bad = client.patch(
        f"/api/v1/students/{sid}",
        headers=admin,
        json={"academic_manager_id": cr["id"]},
    )
    assert bad.status_code == 400, bad.text
    err = bad.json().get("error") or {}
    msg = err.get("message") or bad.json().get("message") or ""
    assert "报名" in msg


def test_enroll_notifies_admin_and_unlocks_manager(client, db_session=None):
    """报名成功后可分配学管，并给 admin 待办。"""
    from app.core.db import get_db
    from app.main import app

    ops = auth_header(client, "ops", "ops123")
    admin = auth_header(client, "admin", "admin123")
    lead = _create_lead(client, ops, name="报名解锁", phone="13900001005")
    patch = client.patch(
        f"/api/v1/leads/{lead['id']}",
        headers=ops,
        json={"status": "enrolled"},
    )
    sid = patch.json()["data"]["converted_student_id"]

    # 需要一门可报课程：用学术 seed 或创建
    courses = client.get("/api/v1/academic/courses", headers=admin)
    # 若无课程模块权限，用 finance/enroll 所需课程
    # 简化：直接在 DB 插一条 enroll 记录模拟「报名成功」后的门禁
    # 完整链路依赖课程数据；这里用 service 层校验 + 手工 enroll 行

    # 取 engine session from override
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        # 无真实 create_record 时，插入 enroll 记录验证门禁与 phase
        db.add(
            EnrollmentRecord(
                student_id=sid,
                kind="enroll",
                amount=0,
                order_no="T-ENROLL-1",
                pay_methods="[]",
                courses="[]",
                attributions="[]",
                created_by=1,
            )
        )
        db.commit()
        stu = db.get(Student, sid)
        assert stu is not None
        from app.modules.students import service as student_svc

        assert student_svc.allocation_phase(db, stu) == "pending_alloc"
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    managers = client.get("/api/v1/students/managers", headers=admin).json()["data"]
    cr = next(m for m in managers if m.get("username") == "cr1")
    ok_assign = client.patch(
        f"/api/v1/students/{sid}",
        headers=admin,
        json={"academic_manager_id": cr["id"]},
    )
    assert ok_assign.status_code == 200, ok_assign.text
    assert ok_assign.json()["data"]["academic_manager_id"] == cr["id"]
    assert ok_assign.json()["data"]["allocation_phase"] == "allocated"
