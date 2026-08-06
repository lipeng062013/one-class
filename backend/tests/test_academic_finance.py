from tests.conftest import auth_header


def _admin(client):
    return auth_header(client, "admin", "admin123")


def _teacher(client):
    return auth_header(client, "teacher1", "t123")


def _create_course(
    client,
    headers,
    name="初一物理一对一",
    course_type="one_to_one",
    price=1000,
    grade="初一",
):
    res = client.post(
        "/api/v1/academic/courses",
        headers=headers,
        json={
            "name": name,
            "course_type": course_type,
            "grade": grade,
            "subject": "物理",
            "unit_price": price,
            "enabled": True,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]


def _create_student(client, headers, name="测学员", course=None):
    from tests.conftest import first_manager_id

    if course is None:
        course = _create_course(client, headers, name=f"建档-{name}", course_type="group", price=200)
    res = client.post(
        "/api/v1/students",
        headers=headers,
        json={
            "name": name,
            "grade": "初一",
            "school": "测试中学",
            "phone": "13900001111",
            "academic_manager_id": first_manager_id(client, headers),
            "status": "active",
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "type": course.get("type_label") or "",
                    "price_label": course.get("price_label") or "",
                }
            ],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]


def test_course_crud_and_list(client):
    admin = _admin(client)
    teacher = _teacher(client)

    c = _create_course(client, admin, name="测试数学班课", course_type="group", price=300)
    assert c["name"] == "测试数学班课"
    assert c["type_label"] == "一对多"

    listed = client.get("/api/v1/academic/courses", headers=teacher)
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] >= 1

    patched = client.patch(
        f"/api/v1/academic/courses/{c['id']}",
        headers=admin,
        json={"enabled": False},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["enabled"] is False


def test_class_member_actions_ignore_legacy_invalid_members(client):
    admin = _admin(client)
    course = _create_course(client, admin, name="成员操作课程", course_type="group", price=300)
    other_course = _create_course(client, admin, name="其他课程", course_type="group", price=200)
    legacy = _create_student(client, admin, name="历史异常学员", course=course)
    removable = _create_student(client, admin, name="待移出学员", course=course)
    added = _create_student(client, admin, name="待添加学员", course=course)
    unrelated = _create_student(client, admin, name="未关联学员", course=other_course)

    created = client.post(
        "/api/v1/academic/classes",
        headers=admin,
        json={
            "name": "成员操作测试班",
            "mode": "group",
            "course_id": course["id"],
            "capacity": 5,
            "over_capacity": False,
        },
    )
    assert created.status_code == 201, created.text
    class_id = created.json()["data"]["id"]
    seeded = client.post(
        f"/api/v1/academic/classes/{class_id}/students",
        headers=admin,
        json={"student_ids": [legacy["id"], removable["id"]]},
    )
    assert seeded.status_code == 200, seeded.text

    # 模拟历史脏数据：学员仍在班内，但已不再关联本班课程。
    changed = client.patch(
        f"/api/v1/students/{legacy['id']}",
        headers=admin,
        json={
            "courses": [
                {
                    "id": other_course["id"],
                    "name": other_course["name"],
                }
            ]
        },
    )
    assert changed.status_code == 200, changed.text

    blocked = client.patch(
        f"/api/v1/academic/classes/{class_id}",
        headers=admin,
        json={"student_ids": [legacy["id"], removable["id"], added["id"]]},
    )
    assert blocked.status_code == 400
    assert "历史异常学员" in blocked.text

    added_result = client.post(
        f"/api/v1/academic/classes/{class_id}/students",
        headers=admin,
        json={"student_ids": [added["id"]]},
    )
    assert added_result.status_code == 200, added_result.text
    assert set(added_result.json()["data"]["student_ids"]) == {
        legacy["id"],
        removable["id"],
        added["id"],
    }

    duplicate_add = client.post(
        f"/api/v1/academic/classes/{class_id}/students",
        headers=admin,
        json={"student_ids": [added["id"]]},
    )
    assert duplicate_add.status_code == 400
    assert "已经在班，不用重复添加" in duplicate_add.text

    invalid_add = client.post(
        f"/api/v1/academic/classes/{class_id}/students",
        headers=admin,
        json={"student_ids": [unrelated["id"]]},
    )
    assert invalid_add.status_code == 400
    assert "未关联课程" in invalid_add.text

    removed_result = client.delete(
        f"/api/v1/academic/classes/{class_id}/students/{removable['id']}",
        headers=admin,
    )
    assert removed_result.status_code == 200, removed_result.text
    assert set(removed_result.json()["data"]["student_ids"]) == {
        legacy["id"],
        added["id"],
    }


def test_class_schedule_roll_and_finance_flow(client):
    admin = _admin(client)
    course = _create_course(client, admin, name="流程一对一", course_type="one_to_one", price=500)
    student = _create_student(client, admin, name="流程学员", course=course)

    # 报名 → 课包 + 订单 + 待确认收入
    en = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 5000,
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "hours": 10,
                    "unit_price": 500,
                }
            ],
            "pay_methods": ["微信"],
            "attributions": [{"user_id": 1, "amount": 5000}],
        },
    )
    assert en.status_code == 201, en.text
    assert en.json()["data"]["order_no"]

    orders = client.get("/api/v1/finance/orders", headers=admin)
    assert orders.status_code == 200
    assert orders.json()["data"]["total"] >= 1

    txs = client.get("/api/v1/finance/transactions", headers=admin)
    assert txs.status_code == 200
    body = txs.json()["data"]
    assert body["summary"]["pending_income"] >= 5000

    # 班级（一对一报名应自动建班；再查列表）
    classes = client.get(
        "/api/v1/academic/classes",
        headers=admin,
        params={"mode": "one_to_one", "q": "流程"},
    )
    assert classes.status_code == 200
    items = classes.json()["data"]["items"]
    assert len(items) >= 1
    class_id = items[0]["id"]

    # 排课
    sch = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": class_id,
            "start_at": "2026-08-02T10:00:00",
            "end_at": "2026-08-02T11:30:00",
            "room": "301",
            "teacher_ids": [3],
        },
    )
    assert sch.status_code == 201, sch.text

    # 点名
    rec = client.post(
        "/api/v1/academic/class-records",
        headers=admin,
        json={
            "class_id": class_id,
            "hours": 1,
            "schedule_id": sch.json()["data"]["id"],
            "attendances": [{"student_id": student["id"], "status": "present"}],
        },
    )
    assert rec.status_code == 201, rec.text
    assert rec.json()["data"]["amount"] >= 0

    # 学员详情只返回该学员的已上课记录，并支持到课状态筛选。
    student_records = client.get(
        f"/api/v1/students/{student['id']}/class-records",
        headers=admin,
        params={"view": "completed"},
    )
    assert student_records.status_code == 200, student_records.text
    record_data = student_records.json()["data"]
    assert record_data["total"] == 1
    assert record_data["items"][0]["id"] == rec.json()["data"]["id"]
    assert record_data["items"][0]["attendance_status"] == "present"
    assert record_data["summary"]["present"] == 1

    absent_records = client.get(
        f"/api/v1/students/{student['id']}/class-records",
        headers=admin,
        params={"view": "completed", "attendance_status": "absent"},
    )
    assert absent_records.status_code == 200
    assert absent_records.json()["data"]["total"] == 0

    pending = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": class_id,
            "start_at": "2026-08-03T10:00:00",
            "end_at": "2026-08-03T11:30:00",
            "room": "302",
            "teacher_ids": [3],
        },
    )
    assert pending.status_code == 201, pending.text
    pending_records = client.get(
        f"/api/v1/students/{student['id']}/class-records",
        headers=admin,
        params={"view": "pending"},
    )
    assert pending_records.status_code == 200, pending_records.text
    pending_data = pending_records.json()["data"]
    assert pending_data["total"] == 1
    assert pending_data["items"][0]["schedule_id"] == pending.json()["data"]["id"]
    assert pending_data["items"][0]["attendance_status"] == "pending"

    cons = client.get("/api/v1/finance/consumptions", headers=admin)
    assert cons.status_code == 200
    assert cons.json()["data"]["total"] >= 1

    # 确认收入
    tx_id = body["items"][0]["id"]
    conf = client.post(
        "/api/v1/finance/transactions/confirm",
        headers=admin,
        json={"ids": [tx_id]},
    )
    assert conf.status_code == 200
    assert conf.json()["data"]["confirmed"] >= 1

    report = client.get("/api/v1/finance/income-report", headers=admin)
    assert report.status_code == 200
    assert report.json()["data"]["confirmed_income"] >= 0

    pending_report = client.get("/api/v1/finance/pending-hours-report", headers=admin)
    assert pending_report.status_code == 200, pending_report.text
    pending_data = pending_report.json()["data"]
    assert pending_data["summary"]["total_hours"] == 10
    assert pending_data["summary"]["consumed_hours"] == 1
    assert pending_data["summary"]["pending_hours"] == 9
    assert pending_data["summary"]["consumption_rate"] == 10
    assert pending_data["summary"]["pending_student_count"] == 1
    assert pending_data["by_course"][0]["course_id"] == course["id"]
    assert pending_data["by_course"][0]["pending_hours"] == 9
    assert pending_data["items"][0]["student_id"] == student["id"]
    assert pending_data["items"][0]["course_id"] == course["id"]


def test_recharge(client):
    admin = _admin(client)
    course = _create_course(client, admin, name="充值建档课", course_type="group", price=100)
    student = _create_student(client, admin, name="充值学员", course=course)
    res = client.post(
        "/api/v1/finance/recharges",
        headers=admin,
        json={"student_id": student["id"], "amount": 1000, "pay_method": "支付宝"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["data"]["balance"] == 1000

    listed = client.get("/api/v1/finance/recharges", headers=admin)
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] >= 1


def test_manual_order_and_void_recharge(client):
    admin = _admin(client)
    course = _create_course(client, admin, name="手工单建档", course_type="group", price=50)
    student = _create_student(client, admin, name="手工单学员", course=course)

    # 手工转课单
    mo = client.post(
        "/api/v1/finance/orders",
        headers=admin,
        json={
            "student_id": student["id"],
            "order_type": "transfer",
            "item_summary": "转至班课A",
            "receivable": 500,
            "received": 500,
            "pay_method": "微信",
        },
    )
    assert mo.status_code == 201, mo.text
    assert mo.json()["data"]["order_type"] == "transfer"

    # 充值后作废应回退余额
    re = client.post(
        "/api/v1/finance/recharges",
        headers=admin,
        json={"student_id": student["id"], "amount": 800, "pay_method": "微信"},
    )
    assert re.status_code == 201, re.text
    assert re.json()["data"]["balance"] == 800
    order_id = re.json()["data"].get("order_id")
    # recharge response may not include order_id; find from orders
    orders = client.get(
        "/api/v1/finance/orders",
        headers=admin,
        params={"order_type": "recharge", "student_q": "手工单学员"},
    )
    assert orders.status_code == 200
    items = orders.json()["data"]["items"]
    assert items
    oid = items[0]["id"] if not order_id else order_id

    voided = client.post(f"/api/v1/finance/orders/{oid}/void", headers=admin)
    assert voided.status_code == 200, voided.text
    assert voided.json()["data"]["status"] == "void"

    # 再充 100 看余额从 0 起（作废后应为 0）
    re2 = client.post(
        "/api/v1/finance/recharges",
        headers=admin,
        json={"student_id": student["id"], "amount": 100, "pay_method": "现金"},
    )
    assert re2.status_code == 201, re2.text
    assert re2.json()["data"]["balance"] == 100


def test_order_detail_and_void(client):
    admin = _admin(client)
    course = _create_course(client, admin, name="详情课", course_type="one_to_one", price=800)
    student = _create_student(client, admin, name="详情学员", course=course)
    en = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 8000,
            "courses": [{"id": course["id"], "name": course["name"], "hours": 10, "unit_price": 800}],
            "pay_methods": ["微信"],
            "internal_notes": "内部备注A",
            "external_notes": "家长可见B",
        },
    )
    assert en.status_code == 201, en.text
    orders = client.get("/api/v1/finance/orders", headers=admin).json()["data"]["items"]
    assert orders
    oid = orders[0]["id"]

    detail = client.get(f"/api/v1/finance/orders/{oid}", headers=admin, params={"log_view": True})
    assert detail.status_code == 200, detail.text
    body = detail.json()["data"]
    assert body["order_no"]
    assert body["student"] == "详情学员"
    assert len(body["line_items"]) >= 1
    assert body["internal_notes"] == "内部备注A"
    assert body["external_notes"] == "家长可见B"
    assert isinstance(body["payments"], list)

    # 收据 PDF
    receipt = client.get(f"/api/v1/finance/orders/{oid}/receipt", headers=admin)
    assert receipt.status_code == 200, receipt.text
    assert receipt.headers.get("content-type", "").startswith("application/pdf")
    assert receipt.content[:4] == b"%PDF"

    logs = client.get(f"/api/v1/finance/orders/{oid}/logs", headers=admin)
    assert logs.status_code == 200
    log_items = logs.json()["data"]["items"]
    actions = {x["action"] for x in log_items}
    assert "create" in actions or "view" in actions or "print_receipt" in actions
    assert "print_receipt" in actions

    # 作废前课包应仍有剩余
    pkgs_before = client.get(
        f"/api/v1/students/{student['id']}/course-packages",
        headers=admin,
    )
    assert pkgs_before.status_code == 200, pkgs_before.text
    assert float(pkgs_before.json()["data"]["summary"]["remain_hours"]) >= 10

    voided = client.post(f"/api/v1/finance/orders/{oid}/void", headers=admin)
    assert voided.status_code == 200, voided.text
    assert voided.json()["data"]["status"] == "void"

    logs2 = client.get(f"/api/v1/finance/orders/{oid}/logs", headers=admin).json()["data"]["items"]
    assert any(x["action"] == "void" for x in logs2)

    # 作废后课包应收回
    pkgs_after = client.get(
        f"/api/v1/students/{student['id']}/course-packages",
        headers=admin,
    )
    assert pkgs_after.status_code == 200
    remain_after = float(pkgs_after.json()["data"]["summary"].get("remain_hours") or 0)
    assert remain_after < 0.01


def test_teacher_can_read_academic(client):
    teacher = _teacher(client)
    res = client.get("/api/v1/academic/courses", headers=teacher)
    assert res.status_code == 200
    # 老师不能建课
    bad = client.post(
        "/api/v1/academic/courses",
        headers=teacher,
        json={"name": "非法", "course_type": "group"},
    )
    assert bad.status_code == 403


def test_student_detail_tabs_apis(client):
    admin = _admin(client)
    course = _create_course(client, admin, name="详情Tab课", course_type="one_to_one", price=600)
    student = _create_student(client, admin, name="Tab学员", course=course)
    en = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 6000,
            "courses": [{"id": course["id"], "name": course["name"], "hours": 10, "unit_price": 600}],
            "pay_methods": ["微信"],
        },
    )
    assert en.status_code == 201, en.text

    pkgs = client.get(f"/api/v1/students/{student['id']}/course-packages", headers=admin)
    assert pkgs.status_code == 200, pkgs.text
    body = pkgs.json()["data"]
    assert "summary" in body
    assert body["summary"]["remain_hours"] >= 0
    assert len(body["courses"]) >= 1

    orders = client.get(f"/api/v1/students/{student['id']}/orders", headers=admin)
    assert orders.status_code == 200
    assert orders.json()["data"]["total"] >= 1

    act = client.get(f"/api/v1/students/{student['id']}/activity", headers=admin)
    assert act.status_code == 200
    assert act.json()["data"]["total"] >= 1

    # 老师也可读
    teacher = _teacher(client)
    assert client.get(f"/api/v1/students/{student['id']}/course-packages", headers=teacher).status_code == 200


def test_void_class_record_restores_package(client):
    admin = _admin(client)
    course = _create_course(client, admin, name="回滚课包课", course_type="one_to_one", price=200)
    student = _create_student(client, admin, name="回滚学员", course=course)

    en = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 2000,
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "hours": 10,
                    "unit_price": 200,
                }
            ],
            "pay_methods": ["微信"],
        },
    )
    assert en.status_code == 201, en.text

    classes = client.get(
        "/api/v1/academic/classes",
        headers=admin,
        params={"mode": "one_to_one", "q": "回滚"},
    )
    assert classes.status_code == 200
    items = classes.json()["data"]["items"]
    assert items
    class_id = items[0]["id"]
    remain_before = float(items[0].get("remain_hours") or 0)
    assert remain_before >= 10

    rec = client.post(
        "/api/v1/academic/class-records",
        headers=admin,
        json={
            "class_id": class_id,
            "hours": 1,
            "attendances": [{"student_id": student["id"], "status": "present"}],
        },
    )
    assert rec.status_code == 201, rec.text
    record_id = rec.json()["data"]["id"]

    classes_mid = client.get(
        f"/api/v1/academic/classes/{class_id}",
        headers=admin,
    )
    assert classes_mid.status_code == 200
    mid = classes_mid.json()["data"]
    assert float(mid.get("remain_hours") or 0) <= remain_before - 0.9

    voided = client.post(
        f"/api/v1/academic/class-records/{record_id}/void",
        headers=admin,
    )
    assert voided.status_code == 200, voided.text

    classes_after = client.get(
        f"/api/v1/academic/classes/{class_id}",
        headers=admin,
    )
    assert classes_after.status_code == 200
    after = classes_after.json()["data"]
    assert abs(float(after.get("remain_hours") or 0) - remain_before) < 0.01


def test_strict_enrollment_to_lesson_hours_closed_loop(client):
    """主流程须保留课包明细、限制入班、阻止重复点名并精确回滚。"""
    admin = _admin(client)
    course = _create_course(client, admin, name="闭环班课", course_type="group", price=100)
    student = _create_student(client, admin, name="闭环学员", course=course)

    first = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 100,
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "hours": 1,
                    "gift_hours": 1,
                    "unit_price": 100,
                }
            ],
            "pay_methods": ["微信"],
        },
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "renew",
            "amount": 200,
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "hours": 2,
                    "unit_price": 100,
                }
            ],
            "pay_methods": ["现金"],
        },
    )
    assert second.status_code == 201, second.text

    packages = client.get(
        f"/api/v1/students/{student['id']}/course-packages", headers=admin
    ).json()["data"]
    package_rows = packages["courses"][0]["packages"]
    assert packages["summary"]["total_hours"] == 4
    assert any(p["purchase_hours"] == 1 and p["gift_hours"] == 1 for p in package_rows)

    eligible = client.get(
        f"/api/v1/academic/courses/{course['id']}/eligible-students",
        headers=admin,
        params={"q": "闭环学员"},
    )
    assert eligible.status_code == 200, eligible.text
    assert eligible.json()["data"]["items"][0]["remain_hours"] == 4

    cls = client.post(
        "/api/v1/academic/classes",
        headers=admin,
        json={
            "name": "闭环测试班",
            "mode": "group",
            "course_id": course["id"],
            "capacity": 1,
            "over_capacity": False,
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

    other_course = _create_course(client, admin, name="无关课程", course_type="group", price=100)
    unrelated = _create_student(client, admin, name="无关学员", course=other_course)
    bad_member = client.patch(
        f"/api/v1/academic/classes/{class_id}",
        headers=admin,
        json={"student_ids": [student["id"], unrelated["id"]]},
    )
    assert bad_member.status_code == 400
    assert "未关联课程" in bad_member.text or "容量" in bad_member.text

    from app.core.timeutil import today as business_today
    from datetime import datetime, time

    day = business_today()
    schedule = client.post(
        "/api/v1/academic/schedules",
        headers=admin,
        json={
            "class_id": class_id,
            "start_at": datetime.combine(day, time(9, 0)).strftime("%Y-%m-%dT%H:%M:%S"),
            "end_at": datetime.combine(day, time(10, 30)).strftime("%Y-%m-%dT%H:%M:%S"),
            "room": "闭环教室",
            "teacher_ids": [3],
        },
    )
    assert schedule.status_code == 201, schedule.text
    schedule_id = schedule.json()["data"]["id"]

    roll_payload = {
        "class_id": class_id,
        "schedule_id": schedule_id,
        "hours": 5,
        "content": "闭环测试课",
        "attendances": [{"student_id": student["id"], "status": "present"}],
    }
    record = client.post(
        "/api/v1/academic/class-records", headers=admin, json=roll_payload
    )
    assert record.status_code == 201, record.text
    record_id = record.json()["data"]["id"]

    duplicate = client.post(
        "/api/v1/academic/class-records", headers=admin, json=roll_payload
    )
    assert duplicate.status_code == 400
    assert "已经点名" in duplicate.text

    detail = client.get(
        f"/api/v1/academic/class-records/{record_id}", headers=admin
    )
    assert detail.status_code == 200, detail.text
    detail_data = detail.json()["data"]
    assert detail_data["room"] == "闭环教室"
    assert detail_data["attendances"][0]["status"] == "present"
    assert detail_data["attendances"][0]["hours_consumed"] == 5
    assert detail_data["attendances"][0]["uncovered_hours"] == 1

    schedule_detail = client.get(
        f"/api/v1/academic/schedules/{schedule_id}", headers=admin
    )
    assert schedule_detail.status_code == 200, schedule_detail.text
    schedule_member = schedule_detail.json()["data"]["members"][0]
    assert schedule_member["deducted_hours"] == 5

    after_roll = client.get(
        f"/api/v1/students/{student['id']}/course-packages", headers=admin
    ).json()["data"]
    assert after_roll["summary"]["remain_hours"] == 0
    assert after_roll["summary"]["overtime_hours"] == 1

    voided = client.post(
        f"/api/v1/academic/class-records/{record_id}/void", headers=admin
    )
    assert voided.status_code == 200, voided.text
    restored = client.get(
        f"/api/v1/students/{student['id']}/course-packages", headers=admin
    ).json()["data"]
    assert restored["summary"]["remain_hours"] == 4
    assert restored["summary"]["overtime_hours"] == 0
    assert sorted(p["remain_hours"] for p in restored["courses"][0]["packages"]) == [2, 2]
