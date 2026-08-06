from tests.conftest import auth_header, first_manager_id
from tests.test_academic_finance import _create_course


def _create_cr(client):
    """Use demo cr1 from conftest (学管师), avoid username collision."""
    admin = auth_header(client, "admin", "admin123")
    cr_id = first_manager_id(client, admin, username="cr1")
    users = client.get("/api/v1/users", headers=admin, params={"page_size": 100}).json()["data"]["items"]
    cr = next(u for u in users if u["id"] == cr_id)
    return admin, cr, auth_header(client, "cr1", "cr11234")


def test_cr_can_manage_students_and_load_role_todos(client):
    admin, cr, cr_headers = _create_cr(client)
    course = _create_course(client, admin, name="CR流程课", course_type="group", price=200)

    student = client.post(
        "/api/v1/students",
        headers=cr_headers,
        json={
            "name": "CR学员",
            "grade": "初一",
            "school": "测试中学",
            "phone": "13800008888",
            "academic_manager_id": cr["id"],
            "courses": [{"id": course["id"], "name": course["name"]}],
        },
    )
    assert student.status_code == 201, student.text
    assert student.json()["data"]["academic_manager_id"] == cr["id"]

    todos = client.get("/api/v1/dashboard/today-todos", headers=cr_headers)
    assert todos.status_code == 200, todos.text
    assert isinstance(todos.json()["data"], list)


def test_teacher_student_phone_is_masked_and_cannot_create_student(client):
    admin, cr, _ = _create_cr(client)
    course = _create_course(client, admin, name="手机号脱敏课", course_type="group", price=200)
    created = client.post(
        "/api/v1/students",
        headers=admin,
        json={
            "name": "脱敏学员",
            "grade": "初一",
            "school": "测试中学",
            "phone": "13900009999",
            "academic_manager_id": cr["id"],
            "courses": [{"id": course["id"], "name": course["name"]}],
        },
    )
    assert created.status_code == 201, created.text

    teacher = auth_header(client, "teacher1", "t123")
    student_id = created.json()["data"]["id"]
    detail = client.get(f"/api/v1/students/{student_id}", headers=teacher)
    assert detail.status_code == 200
    assert detail.json()["data"]["phone"] is None

    forbidden = client.post(
        "/api/v1/students",
        headers=teacher,
        json={
            "name": "老师不可建档",
            "grade": "初一",
            "phone": "13700007777",
            "courses": [{"id": course["id"], "name": course["name"]}],
        },
    )
    assert forbidden.status_code == 403


def test_create_phone_fields_are_required(client):
    admin = auth_header(client, "admin", "admin123")
    lead = client.post(
        "/api/v1/leads",
        headers=admin,
        json={"student_or_parent_name": "缺手机号线索"},
    )
    assert lead.status_code == 422
