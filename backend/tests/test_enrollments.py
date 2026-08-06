from tests.conftest import auth_header, first_manager_id


def _create_course(client, headers, name="初一物理一对一"):
    res = client.post(
        "/api/v1/academic/courses",
        headers=headers,
        json={
            "name": name,
            "course_type": "one_to_one",
            "unit_price": 1000,
            "enabled": True,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]


def _create_student(client, headers, course=None):
    if course is None:
        course = _create_course(client, headers, name=f"建档课-{headers.get('Authorization','')[-6:]}")
    res = client.post(
        "/api/v1/students",
        headers=headers,
        json={
            "name": "续费测试生",
            "grade": "四年级",
            "school": "测试小学",
            "phone": "13800001111",
            "academic_manager_id": first_manager_id(client, headers),
            "status": "active",
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "type": course.get("type_label") or "一对一",
                    "price_label": course.get("price_label") or "",
                }
            ],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]


def test_enrollment_admin_only(client):
    ops = auth_header(client, "ops", "ops123")
    res = client.get("/api/v1/enrollments", headers=ops)
    assert res.status_code == 403


def test_create_enrollment_and_list(client):
    admin = auth_header(client, "admin", "admin123")
    course = _create_course(client, admin, name="初一物理一对一")
    student = _create_student(client, admin, course=course)

    res = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "renew",
            "handled_at": "2026-08-01T12:00:00",
            "amount": 0,
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "type": "一对一",
                    "price_label": course["price_label"],
                    "hours": 10,
                    "unit_price": 1000,
                }
            ],
            "pay_methods": ["微信", "支付宝"],
            "attributions": [{"user_id": 1, "amount": 1200}, {"user_id": 3, "amount": 300}],
            "internal_notes": "内部备注",
            "external_notes": "家长可见",
            "internal_images": [],
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["kind"] == "renew"
    assert data["student_name"] == "续费测试生"
    assert data["amount"] == 1500
    assert len(data["attributions"]) == 2
    assert len(data["courses"]) == 1
    assert data["courses"][0]["name"] == "初一物理一对一"
    assert data["order_no"]
    assert data["order_id"]
    assert "微信" in (data.get("pay_methods") or [])

    listed = client.get("/api/v1/enrollments", headers=admin)
    assert listed.status_code == 200
    body = listed.json()["data"]
    assert body["total"] >= 1
    listed_record = next(x for x in body["items"] if x["id"] == data["id"])
    assert listed_record["order_id"] == data["order_id"]

    # 财务订单已同步
    orders = client.get("/api/v1/finance/orders", headers=admin)
    assert orders.status_code == 200
    order = next(o for o in orders.json()["data"]["items"] if o["order_no"] == data["order_no"])
    assert order["id"] == data["order_id"]


def test_enrollment_requires_course(client):
    admin = auth_header(client, "admin", "admin123")
    student = _create_student(client, admin)
    res = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 100,
            "courses": [],
            "pay_methods": ["微信"],
        },
    )
    assert res.status_code in (400, 422)


def test_enrollment_requires_pay_method(client):
    admin = auth_header(client, "admin", "admin123")
    course = _create_course(client, admin, name="支付测试课")
    student = _create_student(client, admin, course=course)
    res = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 100,
            "courses": [{"id": course["id"], "name": course["name"], "hours": 5}],
            "pay_methods": [],
        },
    )
    assert res.status_code in (400, 422)


def test_enrollment_purchase_details_and_split_payments(client):
    admin = auth_header(client, "admin", "admin123")
    course = _create_course(client, admin, name="分笔支付测试课")
    student = _create_student(client, admin, course=course)

    res = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 800,
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "hours": 1,
                    "gift_hours": 2,
                    "unit_price": 1000,
                    "price_standard": "单价(1000元/课时)",
                    "discount": 200,
                }
            ],
            "pay_methods": ["微信", "现金"],
            "payments": [
                {"method": "微信", "amount": 300},
                {"method": "现金", "amount": 200},
            ],
            "attributions": [
                {"user_id": 1, "amount": 500},
                {"user_id": 3, "amount": 300},
            ],
        },
    )
    assert res.status_code == 201, res.text
    enrollment = res.json()["data"]
    assert enrollment["courses"][0]["gift_hours"] == 2
    assert enrollment["courses"][0]["price_standard"] == "单价(1000元/课时)"
    assert enrollment["courses"][0]["discount"] == 200
    assert enrollment["courses"][0]["subtotal"] == 800

    orders = client.get("/api/v1/finance/orders", headers=admin).json()["data"]["items"]
    order = next(x for x in orders if x["order_no"] == enrollment["order_no"])
    assert order["receivable"] == 800
    assert order["received"] == 500
    assert order["arrears"] == 300
    assert order["status"] == "partial"

    detail_res = client.get(f"/api/v1/finance/orders/{order['id']}", headers=admin)
    assert detail_res.status_code == 200, detail_res.text
    detail = detail_res.json()["data"]
    assert sorted((p["pay_method"], p["amount"]) for p in detail["payments"]) == [
        ("微信", 300),
        ("现金", 200),
    ]
    assert detail["line_items"][0]["gift_qty"] == "2课时"
    assert detail["line_items"][0]["valid_until"] == "-"

    packages = client.get(
        f"/api/v1/students/{student['id']}/course-packages",
        headers=admin,
    ).json()["data"]
    assert packages["summary"]["total_hours"] == 3


def test_enrollment_rejects_unbalanced_attributions(client):
    admin = auth_header(client, "admin", "admin123")
    course = _create_course(client, admin, name="业绩合计测试课")
    student = _create_student(client, admin, course=course)

    res = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 1000,
            "courses": [{"id": course["id"], "name": course["name"], "hours": 1}],
            "pay_methods": ["微信"],
            "payments": [{"method": "微信", "amount": 1000}],
            "attributions": [
                {"user_id": 1, "amount": 500},
                {"user_id": 3, "amount": 300},
            ],
        },
    )
    assert res.status_code == 400
    assert "销售业绩合计必须等于应收金额" in res.text
