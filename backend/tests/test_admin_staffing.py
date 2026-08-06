"""负责人同时可作为授课老师与学管师，须出现在相关下拉/搜索中。"""

from tests.conftest import auth_header
from tests.test_academic_finance import _admin, _create_course, _create_student


def test_admin_appears_in_teachers_list_and_search(client):
    admin = auth_header(client, "admin", "admin123")
    res = client.get("/api/v1/academic/teachers", headers=admin, params={"page_size": 100})
    assert res.status_code == 200, res.text
    items = res.json()["data"]["items"]
    names = {i["username"] for i in items}
    assert "admin" in names
    assert "teacher1" in names
    assert "cr1" in names
    # 运营不在授课老师列表
    assert "ops" not in names

    admin_row = next(i for i in items if i["username"] == "admin")
    assert admin_row["name"] == "负责人"
    assert admin_row["role"] == "负责人"

    # 按显示名搜索
    q = client.get(
        "/api/v1/academic/teachers",
        headers=admin,
        params={"q": "负责", "page_size": 50},
    )
    assert q.status_code == 200
    q_names = {i["username"] for i in q.json()["data"]["items"]}
    assert "admin" in q_names


def test_admin_appears_in_schedule_availability(client):
    admin = _admin(client)
    avail = client.post(
        "/api/v1/academic/schedules/availability",
        headers=admin,
        json={
            "start_at": "2026-10-01T09:00:00",
            "end_at": "2026-10-01T10:00:00",
        },
    )
    assert avail.status_code == 200, avail.text
    teachers = avail.json()["data"]["teachers"]
    ids = {t["id"] for t in teachers}
    names = {t.get("name") for t in teachers}
    assert 1 in ids  # admin fixture id
    assert "负责人" in names
    assert "老师甲" in names


def test_admin_appears_in_managers_and_can_be_assigned(client):
    admin_h = auth_header(client, "admin", "admin123")
    managers = client.get("/api/v1/students/managers", headers=admin_h)
    assert managers.status_code == 200
    mgr_list = managers.json()["data"]
    assert any(m["username"] == "admin" for m in mgr_list)
    assert any(m["username"] == "cr1" for m in mgr_list)
    assert all(m["username"] != "teacher1" for m in mgr_list)
    assert all(m["username"] != "ops" for m in mgr_list)

    admin_id = next(m["id"] for m in mgr_list if m["username"] == "admin")
    res = client.post(
        "/api/v1/students",
        headers=admin_h,
        json={
            "name": "负责人学管生",
            "grade": "一年级",
            "school": "实验小学",
            "phone": "13900001111",
            "academic_manager_id": admin_id,
            "courses": [{"name": "负责人学管关联课", "type": "一对多", "price_label": "单价"}],
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["academic_manager_id"] == admin_id
    assert data["academic_manager_name"] == "负责人"


def test_schedule_can_use_admin_as_teacher(client):
    admin = _admin(client)
    course = _create_course(client, admin, name="负责人授课课", course_type="group", price=200)
    student = _create_student(client, admin, name="负责人授课生", course=course)
    created = client.post(
        "/api/v1/academic/classes",
        headers=admin,
        json={
            "name": "负责人授课班",
            "mode": "group",
            "course_id": course["id"],
            "capacity": 8,
            "teacher_ids": [1],
        },
    )
    assert created.status_code == 201, created.text
    members = client.post(
        f"/api/v1/academic/classes/{created.json()['data']['id']}/students",
        headers=admin,
        json={"student_ids": [student["id"]]},
    )
    assert members.status_code == 200, members.text
    cls = members.json()["data"]
    assert 1 in (cls.get("teacher_ids") or [])

    sch = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_at": "2026-11-02T14:00:00",
            "end_at": "2026-11-02T15:30:00",
            "room": "小学部10教",
            "teacher_ids": [1],
            "remark": "负责人亲自上",
        },
    )
    assert sch.status_code == 201, sch.text
    body = sch.json()["data"]
    assert 1 in (body.get("teacher_ids") or [])
    assert "负责人" in (body.get("teachers") or "")
