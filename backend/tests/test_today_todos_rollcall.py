"""今日待办：课表点名完成后自动 is_done。"""

from datetime import date, datetime, time, timedelta

from tests.conftest import auth_header, first_manager_id
from tests.test_academic_finance import _admin, _create_course, _create_student
from tests.test_schedules import _ensure_class


def _today_slot(hour: int = 15):
    d = date.today()
    start = datetime.combine(d, time(hour, 0))
    end = start + timedelta(hours=1)
    return start, end


def test_schedule_todo_auto_completes_after_roll_call(client):
    admin = _admin(client)
    cls, course = _ensure_class(client, admin, name="待办点名自动完成班")
    detail = client.get(f"/api/v1/academic/classes/{cls['id']}", headers=admin).json()["data"]
    student_id = detail["student_ids"][0]
    manager_id = first_manager_id(client, admin)
    assert (
        client.patch(
            f"/api/v1/students/{student_id}",
            headers=admin,
            json={"academic_manager_id": manager_id},
        ).status_code
        == 200
    )

    # 报名课时，保证点名可扣课
    en = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student_id,
            "kind": "enroll",
            "amount": 1000,
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "hours": 5,
                    "unit_price": 200,
                }
            ],
            "pay_methods": ["微信"],
            "attributions": [{"user_id": 1, "amount": 1000}],
        },
    )
    assert en.status_code == 201, en.text

    start, end = _today_slot(16)
    sch = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "room": "待办教室",
            "teacher_ids": [3],
        },
    )
    assert sch.status_code == 201, sch.text
    schedule_id = sch.json()["data"]["id"]

    # 点名前：负责人待办未完成
    before = client.get("/api/v1/dashboard/today-todos", headers=admin)
    assert before.status_code == 200, before.text
    course_todos = [
        t
        for t in before.json()["data"]
        if t.get("source") == "schedule" and t.get("ref_id") == schedule_id
    ]
    assert len(course_todos) == 1
    assert course_todos[0]["is_done"] is False
    assert course_todos[0]["title"] == "班级点名"
    assert "已点名" not in (course_todos[0].get("content") or "")

    # 学管师视角同样有未完成点名待办
    cr = auth_header(client, "cr1", "cr11234")
    cr_before = client.get("/api/v1/dashboard/today-todos", headers=cr)
    assert cr_before.status_code == 200
    cr_todos = [
        t
        for t in cr_before.json()["data"]
        if t.get("source") == "schedule" and t.get("ref_id") == schedule_id
    ]
    assert len(cr_todos) == 1
    assert cr_todos[0]["is_done"] is False

    # 完成点名
    rec = client.post(
        "/api/v1/academic/class-records",
        headers=admin,
        json={
            "class_id": cls["id"],
            "hours": 1,
            "schedule_id": schedule_id,
            "attendances": [{"student_id": student_id, "status": "present"}],
        },
    )
    assert rec.status_code == 201, rec.text
    record_id = rec.json()["data"]["id"]

    after = client.get("/api/v1/dashboard/today-todos", headers=admin)
    assert after.status_code == 200
    done_todos = [
        t
        for t in after.json()["data"]
        if t.get("source") == "schedule" and t.get("ref_id") == schedule_id
    ]
    assert len(done_todos) == 1
    assert done_todos[0]["is_done"] is True
    assert "已点名" in (done_todos[0].get("content") or "")
    assert done_todos[0]["path"] == f"/academic/class-records/{record_id}"

    cr_after = client.get("/api/v1/dashboard/today-todos", headers=cr)
    cr_done = [
        t
        for t in cr_after.json()["data"]
        if t.get("source") == "schedule" and t.get("ref_id") == schedule_id
    ]
    assert len(cr_done) == 1
    assert cr_done[0]["is_done"] is True

    # 撤销点名后恢复未完成
    voided = client.post(
        f"/api/v1/academic/class-records/{record_id}/void",
        headers=admin,
    )
    assert voided.status_code == 200, voided.text

    restored = client.get("/api/v1/dashboard/today-todos", headers=admin)
    restored_todos = [
        t
        for t in restored.json()["data"]
        if t.get("source") == "schedule" and t.get("ref_id") == schedule_id
    ]
    assert len(restored_todos) == 1
    assert restored_todos[0]["is_done"] is False
