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


def _create_student(client, headers, course=None, **kwargs):
    if course is None:
        course = _create_course(client, headers, name=f"建档课-{headers.get('Authorization', '')[-6:]}")
    body = {
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
    }
    body.update(kwargs)
    res = client.post(
        "/api/v1/students",
        headers=headers,
        json=body,
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


def test_enroll_renew_reject_zero_payment(client):
    """报名/续费有应收时，零实收不可提交。"""
    admin = auth_header(client, "admin", "admin123")
    course = _create_course(client, admin, name="零支付拦截课")
    student = _create_student(client, admin, course=course)

    for kind in ("enroll", "renew"):
        res = client.post(
            "/api/v1/enrollments",
            headers=admin,
            json={
                "student_id": student["id"],
                "kind": kind,
                "amount": 1000,
                "courses": [
                    {
                        "id": course["id"],
                        "name": course["name"],
                        "hours": 1,
                        "unit_price": 1000,
                    }
                ],
                "pay_methods": ["微信"],
                "payments": [{"method": "微信", "amount": 0}],
                "attributions": [{"user_id": 1, "amount": 1000}],
            },
        )
        assert res.status_code == 400, res.text
        assert "实收" in res.json()["error"]["message"] or "零支付" in res.json()["error"]["message"]


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


def test_enrollment_accepts_manual_subtotal_override(client):
    """学管/负责人可提交手动小计（可低于或高于目录总价）。"""
    admin = auth_header(client, "admin", "admin123")
    course = _create_course(client, admin, name="改价小计课")
    student = _create_student(client, admin, course=course)

    # 目录：10 课时 × 100 = 1000；手动小计 888
    low = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 888,
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "hours": 10,
                    "unit_price": 100,
                    "discount_type": "reduce",
                    "discount_value": 0,
                    "subtotal": 888,
                }
            ],
            "pay_methods": ["微信"],
            "payments": [{"method": "微信", "amount": 888}],
            "attributions": [{"user_id": 1, "amount": 888}],
        },
    )
    assert low.status_code == 201, low.text
    low_course = low.json()["data"]["courses"][0]
    assert low_course["subtotal"] == 888
    # 小计与直减独立：未传优惠时 discount 仍为 0，不因小计自动改写
    assert low_course["discount"] == 0

    student2 = _create_student(client, admin, course=course, name="涨价小计生", phone="13800009999")
    # 高于目录价：10×100=1000 → 小计 1200，单价反推 120；直减可单独保留
    high = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student2["id"],
            "kind": "renew",
            "amount": 1200,
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "hours": 10,
                    "unit_price": 100,
                    "discount_type": "reduce",
                    "discount_value": 50,
                    "discount": 50,
                    "subtotal": 1200,
                }
            ],
            "pay_methods": ["现金"],
            "payments": [{"method": "现金", "amount": 1200}],
            "attributions": [{"user_id": 1, "amount": 1200}],
        },
    )
    assert high.status_code == 201, high.text
    high_course = high.json()["data"]["courses"][0]
    assert high_course["subtotal"] == 1200
    assert high_course["discount"] == 50
    assert high_course["unit_price"] == 120


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


def test_transfer_course_between_packages(client):
    """转课：扣减转出课包，写入转入课包，差额建单。"""
    admin = auth_header(client, "admin", "admin123")
    out_course = _create_course(client, admin, name="转出化学课")
    # 覆盖单价
    client.patch(
        f"/api/v1/academic/courses/{out_course['id']}",
        headers=admin,
        json={"unit_price": 150},
    )
    in_course = client.post(
        "/api/v1/academic/courses",
        headers=admin,
        json={
            "name": "转入语文课",
            "course_type": "one_to_one",
            "unit_price": 200,
            "enabled": True,
        },
    ).json()["data"]
    student = _create_student(client, admin, course=out_course)

    # 先报名获得 10 课时 @150
    en = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "enroll",
            "amount": 1500,
            "courses": [
                {
                    "id": out_course["id"],
                    "name": out_course["name"],
                    "hours": 10,
                    "unit_price": 150,
                }
            ],
            "pay_methods": ["微信"],
            "payments": [{"method": "微信", "amount": 1500}],
            "attributions": [{"user_id": 1, "amount": 1500}],
        },
    )
    assert en.status_code == 201, en.text

    pkgs = client.get(
        f"/api/v1/students/{student['id']}/course-packages",
        headers=admin,
    ).json()["data"]
    out_pkg = pkgs["courses"][0]["packages"][0]
    package_id = out_pkg["package_id"]
    assert float(out_pkg["remain_hours"]) >= 10

    # 转出 3 课时(价值 450) → 转入 3 课时 @200 = 600，应收 150
    transfer = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": student["id"],
            "kind": "transfer",
            "amount": 150,
            "transfer_mode": "course",
            "transfer_out_course_id": out_course["id"],
            "transfer_out_items": [
                {
                    "package_id": package_id,
                    "transfer_hours": 3,
                    "transfer_gift_hours": 0,
                    "fee": 0,
                    "exit_order": False,
                    "transfer_amount": 450,
                }
            ],
            "courses": [
                {
                    "id": in_course["id"],
                    "name": in_course["name"],
                    "hours": 3,
                    "unit_price": 200,
                    "discount_type": "reduce",
                    "discount_value": 0,
                }
            ],
            "pay_methods": ["微信"],
            "payments": [{"method": "微信", "amount": 150}],
            "attributions": [{"user_id": 1, "amount": 150}],
        },
    )
    assert transfer.status_code == 201, transfer.text
    body = transfer.json()["data"]
    assert body["kind"] == "transfer"
    assert body["order_no"].startswith("TF")
    assert abs(float(body["amount"]) - 150) < 0.01
    assert body["order_id"]

    pkgs2 = client.get(
        f"/api/v1/students/{student['id']}/course-packages",
        headers=admin,
    ).json()["data"]
    by_name = {c["course_name"]: c for c in pkgs2["courses"]}
    assert "转出化学课" in by_name or out_course["name"] in by_name
    out_group = by_name.get("转出化学课") or by_name.get(out_course["name"])
    in_group = by_name.get("转入语文课") or by_name.get(in_course["name"])
    assert out_group is not None
    assert in_group is not None
    # 转出后剩余约 7
    assert abs(float(out_group["remain_hours"]) - 7) < 0.01
    # 转入 3 课时
    assert abs(float(in_group["remain_hours"]) - 3) < 0.01

    order = client.get(f"/api/v1/finance/orders/{body['order_id']}", headers=admin)
    assert order.status_code == 200
    assert order.json()["data"]["order_type"] == "transfer"


def test_transfer_course_to_another_student(client):
    """转课给其他学员：源学员扣课时，目标学员获得课包。"""
    admin = auth_header(client, "admin", "admin123")
    course = _create_course(client, admin, name="学员互转课")
    source = _create_student(client, admin, course=course)
    # 目标学员
    target = client.post(
        "/api/v1/students",
        headers=admin,
        json={
            "name": "转入目标生",
            "grade": "五年级",
            "school": "测试小学",
            "phone": "13800002222",
            "academic_manager_id": first_manager_id(client, admin),
            "status": "active",
            "courses": [],
        },
    )
    assert target.status_code == 201, target.text
    target = target.json()["data"]

    en = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": source["id"],
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
            "payments": [{"method": "微信", "amount": 2000}],
            "attributions": [{"user_id": 1, "amount": 2000}],
        },
    )
    assert en.status_code == 201, en.text

    pkgs = client.get(
        f"/api/v1/students/{source['id']}/course-packages",
        headers=admin,
    ).json()["data"]
    package_id = pkgs["courses"][0]["packages"][0]["package_id"]

    # 转 4 课时给目标学员，等值转移应收 0
    transfer = client.post(
        "/api/v1/enrollments",
        headers=admin,
        json={
            "student_id": source["id"],
            "kind": "transfer",
            "amount": 0,
            "transfer_mode": "student",
            "transfer_to_student_id": target["id"],
            "transfer_out_course_id": course["id"],
            "transfer_out_items": [
                {
                    "package_id": package_id,
                    "transfer_hours": 4,
                    "transfer_gift_hours": 0,
                    "fee": 0,
                    "exit_order": False,
                    "transfer_amount": 800,
                }
            ],
            "courses": [
                {
                    "id": course["id"],
                    "name": course["name"],
                    "hours": 4,
                    "unit_price": 200,
                    "discount_type": "reduce",
                    "discount_value": 0,
                }
            ],
            "pay_methods": [],
            "payments": [],
            "attributions": [{"user_id": 1, "amount": 0}],
        },
    )
    assert transfer.status_code == 201, transfer.text
    body = transfer.json()["data"]
    assert body["kind"] == "transfer"
    assert abs(float(body["amount"])) < 0.01

    src_pkgs = client.get(
        f"/api/v1/students/{source['id']}/course-packages",
        headers=admin,
    ).json()["data"]
    tgt_pkgs = client.get(
        f"/api/v1/students/{target['id']}/course-packages",
        headers=admin,
    ).json()["data"]
    src_remain = float(src_pkgs["summary"]["remain_hours"])
    tgt_remain = float(tgt_pkgs["summary"]["remain_hours"])
    assert abs(src_remain - 6) < 0.01
    assert abs(tgt_remain - 4) < 0.01

    # 目标学员有转入登记
    tgt_ens = client.get(
        "/api/v1/enrollments",
        headers=admin,
        params={"student_id": target["id"], "kind": "transfer"},
    )
    assert tgt_ens.status_code == 200
    assert tgt_ens.json()["data"]["total"] >= 1
