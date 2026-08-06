"""学管师：课程/学员删除权限 + 财务仅名下学员 + 无确认收入报表。"""

from tests.conftest import auth_header, first_manager_id
from tests.test_academic_finance import _admin, _create_course, _create_student


def test_cr_role_defaults_exclude_courses_admin_and_student_delete(client):
    cr = auth_header(client, "cr1", "cr11234")
    me = client.get("/api/v1/auth/me", headers=cr)
    assert me.status_code == 200
    perms = set(me.json()["data"]["permissions"])
    assert "academic.courses_admin" not in perms
    assert "students.delete" not in perms
    assert "finance.read" in perms
    assert "finance.income_report" not in perms

    # 课程增删改默认不可访问（需负责人授权）
    created = client.post(
        "/api/v1/academic/courses",
        headers=cr,
        json={
            "name": "学管新建课",
            "course_type": "group",
            "grade": "初一",
            "subject": "数学",
            "unit_price": 100,
            "enabled": True,
        },
    )
    assert created.status_code == 403


def test_cr_student_search_only_own_managed(client):
    """报名页搜索学员：学管师只能搜到自己名下。"""
    admin = _admin(client)
    cr_id = first_manager_id(client, admin, username="cr1")
    cr = auth_header(client, "cr1", "cr11234")

    other = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "cr_search_other",
            "display_name": "学管搜索乙",
            "role": "cr",
            "password": "crsearch12",
        },
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["data"]["id"]

    course = _create_course(client, admin, name="搜索范围课", course_type="group", price=100)
    mine = _create_student(client, admin, name="搜索我的学员甲", course=course)
    theirs = _create_student(client, admin, name="搜索他人学员乙", course=course)
    assert (
        client.patch(
            f"/api/v1/students/{mine['id']}",
            headers=admin,
            json={"academic_manager_id": cr_id},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/students/{theirs['id']}",
            headers=admin,
            json={"academic_manager_id": other_id},
        ).status_code
        == 200
    )

    res = client.get(
        "/api/v1/students",
        headers=cr,
        params={"q": "搜索", "page": 1, "page_size": 50},
    )
    assert res.status_code == 200, res.text
    names = {s["name"] for s in res.json()["data"]["items"]}
    assert "搜索我的学员甲" in names
    assert "搜索他人学员乙" not in names

    # 直接拉他人详情也应 404
    assert client.get(f"/api/v1/students/{theirs['id']}", headers=cr).status_code == 404


def test_cr_cannot_access_income_report(client):
    cr = auth_header(client, "cr1", "cr11234")
    assert client.get("/api/v1/finance/income-report", headers=cr).status_code == 403
    assert client.get("/api/v1/finance/pending-hours-report", headers=cr).status_code == 403

    admin = _admin(client)
    assert client.get("/api/v1/finance/income-report", headers=admin).status_code == 200


def test_cr_finance_only_sees_managed_students(client):
    admin = _admin(client)
    cr_id = first_manager_id(client, admin, username="cr1")
    cr = auth_header(client, "cr1", "cr11234")

    # 另一名学管
    other = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "cr_scope_other",
            "display_name": "学管范围乙",
            "role": "cr",
            "password": "crscope12",
        },
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["data"]["id"]

    course = _create_course(client, admin, name="学管财务范围课", course_type="group", price=200)
    mine = _create_student(client, admin, name="我的财务学员", course=course)
    other_stu = _create_student(client, admin, name="他人财务学员", course=course)

    assert (
        client.patch(
            f"/api/v1/students/{mine['id']}",
            headers=admin,
            json={"academic_manager_id": cr_id},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/students/{other_stu['id']}",
            headers=admin,
            json={"academic_manager_id": other_id},
        ).status_code
        == 200
    )

    # 为两名学员各建订单（报名）
    for sid, amount in ((mine["id"], 800), (other_stu["id"], 900)):
        en = client.post(
            "/api/v1/enrollments",
            headers=admin,
            json={
                "student_id": sid,
                "kind": "enroll",
                "amount": amount,
                "courses": [
                    {
                        "id": course["id"],
                        "name": course["name"],
                        "hours": 4,
                        "unit_price": amount / 4,
                    }
                ],
                "pay_methods": ["微信"],
                "attributions": [{"user_id": 1, "amount": amount}],
            },
        )
        assert en.status_code == 201, en.text

    # 学管只看到自己学员订单
    orders = client.get("/api/v1/finance/orders", headers=cr, params={"page_size": 100})
    assert orders.status_code == 200, orders.text
    items = orders.json()["data"]["items"]
    student_names = {i.get("student") for i in items}
    assert "我的财务学员" in student_names
    assert "他人财务学员" not in student_names

    # 他人订单详情 404
    all_orders = client.get("/api/v1/finance/orders", headers=admin, params={"page_size": 100})
    other_order = next(
        o for o in all_orders.json()["data"]["items"] if o.get("student") == "他人财务学员"
    )
    denied = client.get(f"/api/v1/finance/orders/{other_order['id']}", headers=cr)
    assert denied.status_code == 404

    mine_order = next(o for o in items if o.get("student") == "我的财务学员")
    ok_detail = client.get(f"/api/v1/finance/orders/{mine_order['id']}", headers=cr)
    assert ok_detail.status_code == 200

    # 收支同理
    txs = client.get("/api/v1/finance/transactions", headers=cr, params={"page_size": 100})
    assert txs.status_code == 200
    tx_students = {t.get("student") for t in txs.json()["data"]["items"]}
    assert "他人财务学员" not in tx_students

    # 不可为他人学员报名
    bad_en = client.post(
        "/api/v1/enrollments",
        headers=cr,
        json={
            "student_id": other_stu["id"],
            "kind": "enroll",
            "amount": 100,
            "courses": [{"id": course["id"], "name": course["name"], "hours": 1, "unit_price": 100}],
            "pay_methods": ["微信"],
            "attributions": [{"user_id": cr_id, "amount": 100}],
        },
    )
    assert bad_en.status_code == 400
    assert "绑定" in bad_en.json()["error"]["message"]
