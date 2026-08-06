"""排课：规则批量、冲突检测、多视图数据联动。"""

from datetime import date, datetime, time, timedelta

from app.core.timeutil import today as business_today
from tests.conftest import auth_header
from tests.test_academic_finance import _admin, _create_course, _create_student


def _dt(day: date, hour: int, minute: int = 0) -> str:
    return datetime.combine(day, time(hour, minute)).strftime("%Y-%m-%dT%H:%M:%S")


def _ensure_class(client, admin, name="排课测试班"):
    course = _create_course(client, admin, name=f"课-{name}", course_type="group", price=200)
    student = _create_student(client, admin, name=f"生-{name}", course=course)
    # 建班（学员改在详情页添加）
    res = client.post(
        "/api/v1/academic/classes",
        headers=admin,
        json={
            "name": name,
            "mode": "group",
            "course_id": course["id"],
            "capacity": 10,
            "teacher_ids": [3],
        },
    )
    assert res.status_code == 201, res.text
    added = client.post(
        f"/api/v1/academic/classes/{res.json()['data']['id']}/students",
        headers=admin,
        json={"student_ids": [student["id"]]},
    )
    assert added.status_code == 200, added.text
    return added.json()["data"], course


def test_schedule_batch_and_list_filter(client):
    admin = _admin(client)
    cls, course = _ensure_class(client, admin, name="批量排课班")

    batch = client.post(
        "/api/v1/academic/schedules/batch",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_date": "2026-09-01",
            "start_time": "09:00",
            "end_time": "10:30",
            "repeat_mode": "weekly",
            "end_mode": "by_count",
            "session_count": 4,
            "room": "小学部10教",
            "teacher_ids": [3],
            "remark": "第一章",
            "on_conflict": "skip",
        },
    )
    assert batch.status_code == 201, batch.text
    body = batch.json()["data"]
    assert body["created_count"] == 4
    assert body["skipped_count"] == 0
    assert len(body["items"]) == 4
    assert body["items"][0]["room"] == "小学部10教"
    assert body["items"][0]["course_color"]

    # 周范围列表
    listed = client.get(
        "/api/v1/academic/schedules",
        headers=admin,
        params={
            "start": "2026-09-01T00:00:00",
            "end": "2026-09-30T23:59:59",
            "class_id": cls["id"],
            "page_size": 50,
        },
    )
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] >= 4

    # 按老师过滤（排课 teacher_ids）
    by_teacher = client.get(
        "/api/v1/academic/schedules",
        headers=admin,
        params={
            "start": "2026-09-01T00:00:00",
            "end": "2026-09-30T23:59:59",
            "teacher_id": 3,
            "page_size": 50,
        },
    )
    assert by_teacher.status_code == 200
    assert by_teacher.json()["data"]["total"] >= 4

    # 按教室过滤
    by_room = client.get(
        "/api/v1/academic/schedules",
        headers=admin,
        params={
            "start": "2026-09-01T00:00:00",
            "end": "2026-09-30T23:59:59",
            "room": "小学部10教",
            "page_size": 50,
        },
    )
    assert by_room.status_code == 200
    assert by_room.json()["data"]["total"] >= 4

    # 课程过滤
    by_course = client.get(
        "/api/v1/academic/schedules",
        headers=admin,
        params={
            "start": "2026-09-01T00:00:00",
            "end": "2026-09-30T23:59:59",
            "course_id": course["id"],
            "page_size": 50,
        },
    )
    assert by_course.status_code == 200
    assert by_course.json()["data"]["total"] >= 4


def test_schedule_batch_with_selected_weekdays(client):
    admin = _admin(client)
    cls, _ = _ensure_class(client, admin, name="指定星期排课班")

    batch = client.post(
        "/api/v1/academic/schedules/batch",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_date": "2026-09-01",
            "start_time": "16:00",
            "end_time": "17:30",
            "repeat_mode": "weekly",
            "weekdays": [1, 3],
            "end_mode": "by_count",
            "session_count": 4,
            "room": "指定星期教室",
            "teacher_ids": [3],
            "on_conflict": "skip",
        },
    )

    assert batch.status_code == 201, batch.text
    items = batch.json()["data"]["items"]
    assert [item["start_at"][:10] for item in items] == [
        "2026-09-02",
        "2026-09-07",
        "2026-09-09",
        "2026-09-14",
    ]


def test_schedule_conflict_and_availability(client):
    admin = _admin(client)
    cls, _ = _ensure_class(client, admin, name="冲突检测班")

    # 先建一节
    first = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_at": "2026-10-10T14:00:00",
            "end_at": "2026-10-10T15:30:00",
            "room": "小学部6教",
            "teacher_ids": [3],
        },
    )
    assert first.status_code == 201, first.text

    # 冲突检测
    conf = client.post(
        "/api/v1/academic/schedules/conflicts",
        headers=admin,
        json={
            "start_at": "2026-10-10T14:30:00",
            "end_at": "2026-10-10T16:00:00",
            "teacher_ids": [3],
            "room": "小学部6教",
        },
    )
    assert conf.status_code == 200
    data = conf.json()["data"]
    assert data["has_conflict"] is True
    assert data["teachers"][0]["busy"] is True
    assert data["rooms"][0]["busy"] is True

    # 空闲时段
    free = client.post(
        "/api/v1/academic/schedules/conflicts",
        headers=admin,
        json={
            "start_at": "2026-10-10T16:00:00",
            "end_at": "2026-10-10T17:00:00",
            "teacher_ids": [3],
            "room": "小学部6教",
        },
    )
    assert free.status_code == 200
    assert free.json()["data"]["has_conflict"] is False

    # 创建冲突课次应失败
    dup = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_at": "2026-10-10T14:00:00",
            "end_at": "2026-10-10T15:00:00",
            "room": "小学部6教",
            "teacher_ids": [3],
        },
    )
    assert dup.status_code == 400

    # 强制创建
    forced = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_at": "2026-10-10T14:00:00",
            "end_at": "2026-10-10T15:00:00",
            "room": "小学部6教",
            "teacher_ids": [3],
            "force": True,
        },
    )
    assert forced.status_code == 201, forced.text

    # availability 接口
    avail = client.post(
        "/api/v1/academic/schedules/availability",
        headers=admin,
        json={
            "start_at": "2026-10-10T14:00:00",
            "end_at": "2026-10-10T15:00:00",
        },
    )
    assert avail.status_code == 200
    av = avail.json()["data"]
    assert any(t["id"] == 3 and t["busy"] for t in av["teachers"])
    assert any(r["name"] == "小学部6教" and r["busy"] for r in av["rooms"])


def test_rooms_list(client):
    admin = _admin(client)
    res = client.get("/api/v1/academic/rooms", headers=admin)
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert isinstance(items, list)
    assert len(items) >= 1
    assert any(i["name"] for i in items)


def test_roll_call_options_only_include_current_managers_today_schedules(client):
    admin = _admin(client)
    # 点名过滤依据是学员学管归属（CR），不是授课老师
    second_cr = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "cr_other",
            "display_name": "学管乙",
            "role": "cr",
            "password": "cr23456",
        },
    )
    assert second_cr.status_code == 201, second_cr.text
    second_cr_id = second_cr.json()["data"]["id"]

    cr_login_user = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "cr_mine",
            "display_name": "学管甲点名",
            "role": "cr",
            "password": "crmine12",
        },
    )
    assert cr_login_user.status_code == 201, cr_login_user.text
    cr_mine_id = cr_login_user.json()["data"]["id"]
    cr_headers = auth_header(client, "cr_mine", "crmine12")

    mine, _ = _ensure_class(client, admin, name="今日我的点名班")
    other, _ = _ensure_class(client, admin, name="今日其他老师班")
    tomorrow, _ = _ensure_class(client, admin, name="明日我的点名班")
    mine_detail = client.get(f"/api/v1/academic/classes/{mine['id']}", headers=admin).json()["data"]
    other_detail = client.get(
        f"/api/v1/academic/classes/{other['id']}", headers=admin
    ).json()["data"]
    tomorrow_detail = client.get(
        f"/api/v1/academic/classes/{tomorrow['id']}", headers=admin
    ).json()["data"]
    for sid in mine_detail["student_ids"] + tomorrow_detail["student_ids"]:
        assert (
            client.patch(
                f"/api/v1/students/{sid}",
                headers=admin,
                json={"academic_manager_id": cr_mine_id},
            ).status_code
            == 200
        )
    reassigned = client.patch(
        f"/api/v1/students/{other_detail['student_ids'][0]}",
        headers=admin,
        json={"academic_manager_id": second_cr_id},
    )
    assert reassigned.status_code == 200, reassigned.text

    today = date.today()
    starts = [
        # 学管师与授课老师故意不同，验证过滤依据是学员学管归属。
        (mine["id"], 1, today, "今日我的教室"),
        (other["id"], 3, today, "今日其他教室"),
        (tomorrow["id"], 1, today + timedelta(days=1), "明日我的教室"),
    ]
    schedule_ids = []
    for class_id, teacher_id, lesson_date, room in starts:
        start_at = datetime.combine(lesson_date, time(9, 0))
        created = client.post(
            "/api/v1/academic/schedules",
            headers=admin,
            json={
                "class_id": class_id,
                "start_at": start_at.isoformat(),
                "end_at": (start_at + timedelta(hours=1)).isoformat(),
                "room": room,
                "teacher_ids": [teacher_id],
            },
        )
        assert created.status_code == 201, created.text
        schedule_ids.append(created.json()["data"]["id"])

    result = client.get(
        "/api/v1/academic/class-records/roll-options",
        headers=cr_headers,
    )
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["date"] == today.isoformat()
    assert data["start"] == today.isoformat()
    assert data["end"] == today.isoformat()
    assert {item["id"] for item in data["classes"]} == {mine["id"]}
    assert {item["id"] for item in data["schedules"]} == {schedule_ids[0]}

    # 周范围：应包含今日 + 明日「我的」课次，仍不含其他学管班级
    week_end = today + timedelta(days=1)
    week_result = client.get(
        "/api/v1/academic/class-records/roll-options",
        headers=cr_headers,
        params={"start": today.isoformat(), "end": week_end.isoformat(), "date": today.isoformat()},
    )
    assert week_result.status_code == 200, week_result.text
    week_data = week_result.json()["data"]
    assert week_data["start"] == today.isoformat()
    assert week_data["end"] == week_end.isoformat()
    assert {item["id"] for item in week_data["schedules"]} == {schedule_ids[0], schedule_ids[2]}
    assert {item["id"] for item in week_data["classes"]} == {mine["id"], tomorrow["id"]}


def test_class_record_supplement_lists(client):
    admin = _admin(client)
    cls, _ = _ensure_class(client, admin, name="上课记录补充班")

    timeout_schedule = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_at": "2026-07-01T09:00:00",
            "end_at": "2026-07-01T10:00:00",
            "room": "补充测试教室",
            "teacher_ids": [3],
        },
    )
    assert timeout_schedule.status_code == 201, timeout_schedule.text

    timeout_list = client.get(
        "/api/v1/academic/class-records/timeout",
        headers=admin,
        params={
            "class_id": cls["id"],
            "start": "2026-07-01T00:00:00",
            "end": "2026-07-01T23:59:59",
        },
    )
    assert timeout_list.status_code == 200, timeout_list.text
    assert timeout_list.json()["data"]["total"] >= 1

    cls_detail = client.get(f"/api/v1/academic/classes/{cls['id']}", headers=admin)
    student_id = cls_detail.json()["data"]["student_ids"][0]
    record = client.post(
        "/api/v1/academic/class-records",
        headers=admin,
        json={
            "class_id": cls["id"],
            "class_start": "2026-07-02T09:00:00",
            "class_end": "2026-07-02T10:00:00",
            "hours": 1,
            "attendances": [{"student_id": student_id, "status": "absent"}],
        },
    )
    assert record.status_code == 201, record.text

    records = client.get(
        "/api/v1/academic/class-records",
        headers=admin,
        params={
            "class_id": cls["id"],
            "class_start": "2026-07-02T00:00:00",
            "class_end": "2026-07-02T23:59:59",
        },
    )
    assert records.status_code == 200, records.text
    assert records.json()["data"]["total"] >= 1

    makeup = client.get(
        "/api/v1/academic/class-records/makeup",
        headers=admin,
        params={
            "class_id": cls["id"],
            "start": "2026-07-02T00:00:00",
            "end": "2026-07-02T23:59:59",
        },
    )
    assert makeup.status_code == 200, makeup.text
    item = makeup.json()["data"]["items"][0]
    assert item["record_id"] == record.json()["data"]["id"]
    assert item["makeup_status_label"] == "待补课"


def test_class_record_detail_edit_attendance_and_logs(client):
    admin = _admin(client)
    course = _create_course(
        client,
        admin,
        name="详情编辑课程",
        course_type="group",
        price=100,
    )
    student_a = _create_student(client, admin, name="详情学员甲", course=course)
    student_b = _create_student(client, admin, name="详情学员乙", course=course)
    cls = client.post(
        "/api/v1/academic/classes",
        headers=admin,
        json={
            "name": "详情编辑班",
            "mode": "group",
            "course_id": course["id"],
            "capacity": 10,
            "teacher_ids": [3],
        },
    )
    assert cls.status_code == 201, cls.text
    class_id = cls.json()["data"]["id"]
    members = client.post(
        f"/api/v1/academic/classes/{class_id}/students",
        headers=admin,
        json={"student_ids": [student_a["id"], student_b["id"]]},
    )
    assert members.status_code == 200, members.text
    lesson_day = business_today()
    schedule = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": class_id,
            "start_at": _dt(lesson_day, 18, 0),
            "end_at": _dt(lesson_day, 19, 0),
            "room": "原教室",
            "teacher_ids": [3],
        },
    )
    assert schedule.status_code == 201, schedule.text
    assert schedule.json()["data"]["can_roll_call"] is True
    record = client.post(
        "/api/v1/academic/class-records",
        headers=admin,
        json={
            "class_id": class_id,
            "schedule_id": schedule.json()["data"]["id"],
            "hours": 1,
            "content": "初始内容",
            "attendances": [
                {"student_id": student_a["id"], "status": "present"},
                {"student_id": student_b["id"], "status": "absent"},
            ],
        },
    )
    assert record.status_code == 201, record.text
    record_id = record.json()["data"]["id"]
    assert record.json()["data"]["hours"] == 1
    assert record.json()["data"]["salary_hours"] == 1

    edited = client.patch(
        f"/api/v1/academic/class-records/{record_id}",
        headers=admin,
        json={
            "class_start": _dt(lesson_day, 18, 30),
            "class_end": _dt(lesson_day, 20, 0),
            "salary_hours": 0.75,
            "room": "新教室",
            "teacher_ids": [3],
            "content": "更新后的内容",
        },
    )
    assert edited.status_code == 200, edited.text
    edited_data = edited.json()["data"]
    assert edited_data["hours"] == 1
    assert edited_data["salary_hours"] == 0.75
    assert edited_data["room"] == "新教室"
    # 出勤扣 1 课时；缺勤不扣
    assert edited_data["amount"] == 100
    by_student = {item["student_id"]: item for item in edited_data["attendances"]}
    assert by_student[student_a["id"]]["hours_consumed"] == 1
    assert by_student[student_b["id"]]["hours_consumed"] == 0

    attendance = client.patch(
        f"/api/v1/academic/class-records/{record_id}/attendances/{student_b['id']}",
        headers=admin,
        json={"status": "leave"},
    )
    assert attendance.status_code == 200, attendance.text
    attendance_data = attendance.json()["data"]
    assert attendance_data["amount"] == 100
    assert attendance_data["salary_hours"] == 0.75
    assert next(
        item for item in attendance_data["attendances"] if item["student_id"] == student_b["id"]
    )["hours_consumed"] == 0

    # 请假改为出勤后应扣课
    to_present = client.patch(
        f"/api/v1/academic/class-records/{record_id}/attendances/{student_b['id']}",
        headers=admin,
        json={"status": "present"},
    )
    assert to_present.status_code == 200, to_present.text
    present_data = to_present.json()["data"]
    assert present_data["amount"] == 200
    assert next(
        item for item in present_data["attendances"] if item["student_id"] == student_b["id"]
    )["hours_consumed"] == 1

    # 再改回缺勤，退回扣课
    to_absent = client.patch(
        f"/api/v1/academic/class-records/{record_id}/attendances/{student_b['id']}",
        headers=admin,
        json={"status": "absent"},
    )
    assert to_absent.status_code == 200, to_absent.text
    absent_data = to_absent.json()["data"]
    assert absent_data["amount"] == 100
    assert next(
        item for item in absent_data["attendances"] if item["student_id"] == student_b["id"]
    )["hours_consumed"] == 0

    removed = client.delete(
        f"/api/v1/academic/class-records/{record_id}/attendances/{student_b['id']}",
        headers=admin,
    )
    assert removed.status_code == 200, removed.text
    removed_data = removed.json()["data"]
    assert removed_data["total_count"] == 1
    assert removed_data["present_count"] == 1
    assert removed_data["amount"] == 100

    logs = client.get(
        f"/api/v1/academic/class-records/{record_id}/logs",
        headers=admin,
    )
    assert logs.status_code == 200, logs.text
    actions = {item["action"] for item in logs.json()["data"]["items"]}
    assert {"create", "update", "attendance_update", "attendance_remove"} <= actions


def test_class_record_salary_hours_default_to_one_for_all_courses(client):
    admin = _admin(client)
    cases = [("三年级", "基础计薪课程A"), ("预初", "基础计薪课程B")]

    for grade, name in cases:
        course = _create_course(
            client,
            admin,
            name=name,
            course_type="group",
            price=100,
            grade=grade,
        )
        student = _create_student(client, admin, name=f"{grade}学员", course=course)
        cls = client.post(
            "/api/v1/academic/classes",
            headers=admin,
            json={
                "name": f"{grade}测试班",
                "mode": "group",
                "course_id": course["id"],
                "capacity": 10,
                "teacher_ids": [3],
            },
        )
        assert cls.status_code == 201, cls.text
        class_id = cls.json()["data"]["id"]
        members = client.post(
            f"/api/v1/academic/classes/{class_id}/students",
            headers=admin,
            json={"student_ids": [student["id"]]},
        )
        assert members.status_code == 200, members.text

        day = business_today()
        record = client.post(
            "/api/v1/academic/class-records",
            headers=admin,
            json={
                "class_id": class_id,
                "class_start": _dt(day, 18, 0),
                "class_end": _dt(day, 19, 30),
                "hours": 1,
                "attendances": [{"student_id": student["id"], "status": "present"}],
            },
        )
        assert record.status_code == 201, record.text
        data = record.json()["data"]
        assert data["hours"] == 1
        assert data["salary_hours"] == 1
        detail = client.get(
            f"/api/v1/academic/class-records/{data['id']}",
            headers=admin,
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["data"]["attendances"][0]["hours_consumed"] == 1


def test_cannot_roll_call_future_schedule(client):
    """未来课次不可点名；当天/过去可点。"""
    admin = _admin(client)
    course = _create_course(client, admin, name="未来点名课程", course_type="group", price=100)
    student = _create_student(client, admin, name="未来点名学员", course=course)
    created = client.post(
        "/api/v1/academic/classes",
        headers=admin,
        json={
            "name": "未来点名班",
            "mode": "group",
            "course_id": course["id"],
            "capacity": 10,
            "teacher_ids": [3],
        },
    )
    assert created.status_code == 201, created.text
    class_id = created.json()["data"]["id"]
    members = client.post(
        f"/api/v1/academic/classes/{class_id}/students",
        headers=admin,
        json={"student_ids": [student["id"]]},
    )
    assert members.status_code == 200, members.text

    future_day = business_today() + timedelta(days=3)
    future = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": class_id,
            "start_at": _dt(future_day, 9, 0),
            "end_at": _dt(future_day, 10, 0),
            "room": "未来教室",
            "teacher_ids": [3],
        },
    )
    assert future.status_code == 201, future.text
    assert future.json()["data"]["can_roll_call"] is False

    blocked = client.post(
        "/api/v1/academic/class-records",
        headers=admin,
        json={
            "class_id": class_id,
            "schedule_id": future.json()["data"]["id"],
            "hours": 1,
            "attendances": [{"student_id": student["id"], "status": "present"}],
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "未来" in blocked.text

    # 未排课直接点名且显式传未来上课时间，同样拒绝
    blocked_free = client.post(
        "/api/v1/academic/class-records",
        headers=admin,
        json={
            "class_id": class_id,
            "class_start": _dt(future_day, 14, 0),
            "class_end": _dt(future_day, 15, 0),
            "hours": 1,
            "attendances": [{"student_id": student["id"], "status": "present"}],
        },
    )
    assert blocked_free.status_code == 400, blocked_free.text
    assert "未来" in blocked_free.text

    today = business_today()
    ok_roll = client.post(
        "/api/v1/academic/class-records",
        headers=admin,
        json={
            "class_id": class_id,
            "class_start": _dt(today, 9, 0),
            "class_end": _dt(today, 10, 0),
            "hours": 1,
            "attendances": [{"student_id": student["id"], "status": "present"}],
        },
    )
    assert ok_roll.status_code == 201, ok_roll.text


def test_two_clock_hours_schedule_defaults_to_one_teaching_hour(client):
    """机构 2 小时墙钟 = 1 授课课时；计薪课时保持独立默认 1。"""
    admin = _admin(client)
    course = _create_course(client, admin, name="两小时一课次", course_type="group", price=200)
    student = _create_student(client, admin, name="两小时学员", course=course)
    created = client.post(
        "/api/v1/academic/classes",
        headers=admin,
        json={
            "name": "两小时一课次班",
            "mode": "group",
            "course_id": course["id"],
            "capacity": 10,
            "hours_per_session": 1,
            "teacher_ids": [3],
        },
    )
    assert created.status_code == 201, created.text
    class_id = created.json()["data"]["id"]
    members = client.post(
        f"/api/v1/academic/classes/{class_id}/students",
        headers=admin,
        json={"student_ids": [student["id"]]},
    )
    assert members.status_code == 200, members.text

    # 08:00-10:00 墙钟 2 小时（使用当天，避免未来课次不可点名）
    day = business_today()
    schedule = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": class_id,
            "start_at": _dt(day, 8, 0),
            "end_at": _dt(day, 10, 0),
            "room": "302",
            "teacher_ids": [3],
        },
    )
    assert schedule.status_code == 201, schedule.text
    schedule_id = schedule.json()["data"]["id"]
    assert schedule.json()["data"]["hours"] == 1
    assert schedule.json()["data"]["hours_per_session"] == 1

    detail = client.get(f"/api/v1/academic/schedules/{schedule_id}", headers=admin)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["hours"] == 1
    assert detail.json()["data"]["hours_per_session"] == 1

    # 不传 hours 时，默认按班级单次课次 1，而非 2 小时墙钟
    record = client.post(
        "/api/v1/academic/class-records",
        headers=admin,
        json={
            "class_id": class_id,
            "schedule_id": schedule_id,
            "attendances": [{"student_id": student["id"], "status": "present"}],
        },
    )
    assert record.status_code == 201, record.text
    body = record.json()["data"]
    assert body["hours"] == 1
    assert body["salary_hours"] == 1

    detail = client.get(f"/api/v1/academic/class-records/{body['id']}", headers=admin)
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()["data"]
    assert detail_body["hours"] == 1
    assert detail_body["salary_hours"] == 1
    assert detail_body["attendances"][0]["hours_consumed"] == 1


def test_batch_skip_conflict(client):
    admin = _admin(client)
    cls, _ = _ensure_class(client, admin, name="跳过冲突班")

    # 先占住 9/7 的时段
    client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_at": "2026-09-07T09:00:00",
            "end_at": "2026-09-07T10:30:00",
            "room": "新城203教室",
            "teacher_ids": [3],
        },
    )

    # 从 9/7 起每周 2 节，第一节冲突应 skip
    batch = client.post(
        "/api/v1/academic/schedules/batch",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_date": "2026-09-07",
            "start_time": "09:00",
            "end_time": "10:30",
            "repeat_mode": "weekly",
            "end_mode": "by_count",
            "session_count": 2,
            "room": "新城203教室",
            "teacher_ids": [3],
            "on_conflict": "skip",
        },
    )
    assert batch.status_code == 201, batch.text
    body = batch.json()["data"]
    assert body["created_count"] == 1
    assert body["skipped_count"] == 1


def test_schedule_batch_update_and_delete(client):
    """多选批量换老师/教室后，列表与课表同源数据同步。"""
    admin = _admin(client)
    cls, _ = _ensure_class(client, admin, name="批量改排课班")

    batch = client.post(
        "/api/v1/academic/schedules/batch",
        headers=admin,
        json={
            "class_id": cls["id"],
            "start_date": "2026-11-02",
            "start_time": "10:00",
            "end_time": "12:00",
            "repeat_mode": "weekly",
            "weekdays": [1, 3],
            "end_mode": "by_count",
            "session_count": 4,
            "room": "原教室A",
            "teacher_ids": [3],
            "on_conflict": "skip",
        },
    )
    assert batch.status_code == 201, batch.text
    items = batch.json()["data"]["items"]
    assert len(items) == 4
    ids = [it["id"] for it in items]

    # 批量换老师（学管 cr1 id=4）+ 改教室
    updated = client.post(
        "/api/v1/academic/schedules/batch-update",
        headers=admin,
        json={
            "ids": ids[:3],
            "update_teachers": True,
            "update_room": True,
            "teacher_ids": [4],
            "room": "临时教室B",
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()["data"]
    assert body["updated_count"] == 3
    assert body["failed_count"] == 0
    for it in body["items"]:
        assert it["room"] == "临时教室B"
        assert it["teacher_ids"] == [4]

    # 列表应反映修改（课表同源）
    listed = client.get(
        "/api/v1/academic/schedules",
        headers=admin,
        params={"class_id": cls["id"], "page_size": 50},
    )
    assert listed.status_code == 200
    by_id = {r["id"]: r for r in listed.json()["data"]["items"]}
    assert by_id[ids[0]]["room"] == "临时教室B"
    assert by_id[ids[0]]["teacher_ids"] == [4]
    assert by_id[ids[3]]["room"] == "原教室A"
    assert by_id[ids[3]]["teacher_ids"] == [3]

    # 批量改时间（仅时刻）
    timed = client.post(
        "/api/v1/academic/schedules/batch-update",
        headers=admin,
        json={
            "ids": [ids[0]],
            "update_time": True,
            "start_time": "14:00",
            "end_time": "16:00",
        },
    )
    assert timed.status_code == 200, timed.text
    assert timed.json()["data"]["items"][0]["start_at"][11:16] == "14:00"
    assert timed.json()["data"]["items"][0]["end_at"][11:16] == "16:00"

    # 批量删除
    deleted = client.post(
        "/api/v1/academic/schedules/batch-delete",
        headers=admin,
        json={"ids": ids[1:3]},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["deleted_count"] == 2

    listed2 = client.get(
        "/api/v1/academic/schedules",
        headers=admin,
        params={"class_id": cls["id"], "page_size": 50},
    )
    remain_ids = {r["id"] for r in listed2.json()["data"]["items"]}
    assert ids[1] not in remain_ids
    assert ids[2] not in remain_ids
    assert ids[0] in remain_ids
    assert ids[3] in remain_ids
