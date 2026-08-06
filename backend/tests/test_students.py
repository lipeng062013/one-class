import pytest

from app.models.student import Student
from tests.conftest import auth_header, first_manager_id

# 建档须关联课程（与产品规则一致）
_SAMPLE_COURSES = [{"name": "测试关联课", "type": "一对多", "price_label": "单价(100元/课时)"}]


def _student_payload(**kwargs):
    body = {
        "name": "测试生",
        "grade": "一年级",
        "school": "测试小学",
        "phone": "13800000000",
        "courses": list(_SAMPLE_COURSES),
    }
    body.update(kwargs)
    return body


@pytest.mark.parametrize(
    "phone",
    [
        "1380000111",
        "23800001111",
        "1380000111a",
        13800001111,
    ],
)
def test_create_student_rejects_invalid_phone(client, phone):
    admin = auth_header(client, "admin", "admin123")
    res = client.post(
        "/api/v1/students",
        headers=admin,
        json=_student_payload(phone=phone),
    )
    assert res.status_code == 422


def test_update_student_rejects_invalid_phone(client):
    admin = auth_header(client, "admin", "admin123")
    created = client.post(
        "/api/v1/students",
        headers=admin,
        json=_student_payload(phone="13800001111"),
    )
    assert created.status_code == 201, created.text

    res = client.patch(
        f"/api/v1/students/{created.json()['data']['id']}",
        headers=admin,
        json={"phone": "03800001111"},
    )
    assert res.status_code == 422


def test_student_model_rejects_invalid_phone_assignment():
    with pytest.raises(ValueError, match="手机号必须为11位数字且以1开头"):
        Student(name="模型校验", phone="123")


def test_create_student_with_school_and_manager(client):
    admin = auth_header(client, "admin", "admin123")
    teacher = auth_header(client, "teacher1", "t123")

    managers = client.get("/api/v1/students/managers", headers=admin)
    assert managers.status_code == 200
    mgr_list = managers.json()["data"]
    assert any(m["username"] == "cr1" for m in mgr_list)
    assert all(m["username"] != "teacher1" for m in mgr_list)
    manager_id = first_manager_id(client, admin)

    res = client.post(
        "/api/v1/students",
        headers=admin,
        json=_student_payload(
            name="张小明",
            grade="三年级",
            school="实验小学",
            phone="13800001111",
            parent_name="张妈妈",
            academic_manager_id=manager_id,
            notes="数学提高",
        ),
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["name"] == "张小明"
    assert data["school"] == "实验小学"
    assert data["academic_manager_id"] == manager_id
    assert data["academic_manager_name"] == "学管甲"
    sid = data["id"]

    # filter by grade / name / phone / school（分页 envelope）
    listed = client.get(
        "/api/v1/students",
        headers=admin,
        params={"grade": "三年级", "page": 1, "page_size": 20},
    )
    body = listed.json()["data"]
    assert "items" in body and "total" in body
    assert any(s["id"] == sid for s in body["items"])

    by_name = client.get(
        "/api/v1/students",
        headers=admin,
        params={"name": "小明", "page": 1, "page_size": 20},
    )
    assert len(by_name.json()["data"]["items"]) >= 1

    by_phone = client.get(
        "/api/v1/students",
        headers=admin,
        params={"phone": "1380000", "page": 1, "page_size": 20},
    )
    assert len(by_phone.json()["data"]["items"]) >= 1

    # teacher can see students
    t_list = client.get("/api/v1/students", headers=teacher, params={"page": 1, "page_size": 50})
    assert t_list.status_code == 200
    assert any(s["id"] == sid for s in t_list.json()["data"]["items"])


def test_teacher_create_student_and_learning_with_image(client):
    h = auth_header(client, "teacher1", "t123")
    admin = auth_header(client, "admin", "admin123")
    manager_id = first_manager_id(client, admin)
    teacher_id = client.get("/api/v1/auth/me", headers=h).json()["data"]["id"]

    s = client.post(
        "/api/v1/students",
        headers=admin,
        json=_student_payload(
            name="李小红",
            grade="四年级",
            school="育才小学",
            phone="13900002222",
            academic_manager_id=manager_id,
        ),
    )
    assert s.status_code == 201
    sid = s.json()["data"]["id"]

    rec = client.post(
        "/api/v1/learning-records",
        headers=h,
        json={
            "student_id": sid,
            "class_status": "attended",
            "learning_summary": "今日掌握分数加减",
            "subject": "数学",
            "notes": "表现积极",
        },
    )
    assert rec.status_code == 201, rec.text
    rid = rec.json()["data"]["id"]
    assert rec.json()["data"]["student_name"] == "李小红"

    upload = client.post(
        f"/api/v1/learning-records/{rid}/files",
        headers=h,
        files={"file": ("note.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )
    assert upload.status_code == 201, upload.text

    detail = client.get(f"/api/v1/learning-records/{rid}", headers=h)
    assert len(detail.json()["data"]["files"]) == 1
    fid = detail.json()["data"]["files"][0]["id"]

    img = client.get(f"/api/v1/learning-records/files/{fid}/content", headers=h)
    assert img.status_code == 200

    def _items(res):
        data = res.json()["data"]
        return data["items"] if isinstance(data, dict) else data

    # timeline on student
    timeline = client.get("/api/v1/learning-records", headers=h, params={"student_id": sid})
    assert any(r["id"] == rid for r in _items(timeline))

    # 老师默认仅自己的学情；mine=false 可看全部
    mine_only = client.get("/api/v1/learning-records", headers=h)
    assert mine_only.status_code == 200
    assert all(r["teacher_id"] == teacher_id for r in _items(mine_only))

    all_rows = client.get("/api/v1/learning-records", headers=h, params={"mine": False})
    assert all_rows.status_code == 200
    assert any(r["id"] == rid for r in _items(all_rows))


def test_admin_learning_list_defaults_to_all(client):
    admin = auth_header(client, "admin", "admin123")
    teacher = auth_header(client, "teacher1", "t123")
    manager_id = first_manager_id(client, admin)
    sid = client.post(
        "/api/v1/students",
        headers=admin,
        json=_student_payload(
            name="学情全量生",
            grade="二年级",
            school="B",
            academic_manager_id=manager_id,
        ),
    ).json()["data"]["id"]
    rid = client.post(
        "/api/v1/learning-records",
        headers=teacher,
        json={"student_id": sid, "learning_summary": "负责人应能看见"},
    ).json()["data"]["id"]

    def _items(res):
        data = res.json()["data"]
        return data["items"] if isinstance(data, dict) else data

    listed = client.get("/api/v1/learning-records", headers=admin)
    assert listed.status_code == 200
    assert any(r["id"] == rid for r in _items(listed))

    mine = client.get("/api/v1/learning-records", headers=admin, params={"mine": True})
    assert all(r["id"] != rid for r in _items(mine))


def test_operator_cannot_access_students(client):
    admin = auth_header(client, "admin", "admin123")
    teacher = auth_header(client, "teacher1", "t123")
    ops = auth_header(client, "ops", "ops123")
    manager_id = first_manager_id(client, admin)

    s = client.post(
        "/api/v1/students",
        headers=admin,
        json=_student_payload(
            name="王同学",
            grade="五年级",
            school="中心小学",
            academic_manager_id=manager_id,
        ),
    )
    assert s.status_code == 201
    sid = s.json()["data"]["id"]

    assert client.get("/api/v1/students", headers=ops).status_code == 403
    assert client.post(
        "/api/v1/learning-records",
        headers=ops,
        json={"student_id": sid, "learning_summary": "不应成功"},
    ).status_code == 403

    client.post(
        "/api/v1/learning-records",
        headers=teacher,
        json={"student_id": sid, "learning_summary": "正常上课"},
    )
    from urllib.parse import unquote

    report = client.get(f"/api/v1/students/{sid}/growth-report", headers=teacher)
    assert report.status_code == 200
    assert report.headers.get("content-type", "").startswith("application/pdf")
    assert "成长档案" in unquote(report.headers.get("content-disposition") or "")

    # 带学情区间参数仍应返回 PDF（区间外可为空内容）
    ranged = client.get(
        f"/api/v1/students/{sid}/growth-report",
        headers=teacher,
        params={"date_from": "2099-01-01", "date_to": "2099-12-31"},
    )
    assert ranged.status_code == 200
    assert ranged.headers.get("content-type", "").startswith("application/pdf")

    # 指定学情 id
    lr = client.get(
        "/api/v1/learning-records",
        headers=teacher,
        params={"student_id": sid},
    )
    assert lr.status_code == 200
    _d = lr.json()["data"]
    items = _d["items"] if isinstance(_d, dict) else _d
    assert len(items) >= 1
    rid = items[0]["id"]
    by_id = client.get(
        f"/api/v1/students/{sid}/growth-report",
        headers=teacher,
        params={"record_ids": str(rid)},
    )
    assert by_id.status_code == 200
    assert by_id.headers.get("content-type", "").startswith("application/pdf")
    # 三种方式文件名统一为「XXX的成长档案.pdf」
    assert "成长档案.pdf" in unquote(by_id.headers.get("content-disposition") or "")

    bad = client.get(
        f"/api/v1/students/{sid}/growth-report",
        headers=teacher,
        params={"date_from": "not-a-date"},
    )
    assert bad.status_code == 400


def test_bulk_delete_students(client):
    admin = auth_header(client, "admin", "admin123")
    teacher = auth_header(client, "teacher1", "t123")
    manager_id = first_manager_id(client, admin)

    ids = []
    for name in ("批量删甲", "批量删乙"):
        res = client.post(
            "/api/v1/students",
            headers=admin,
            json=_student_payload(
                name=name,
                grade="一年级",
                school="实验小学",
                academic_manager_id=manager_id,
            ),
        )
        assert res.status_code == 201
        ids.append(res.json()["data"]["id"])

    # teacher cannot bulk delete
    assert (
        client.post(
            "/api/v1/students/bulk-delete",
            headers=teacher,
            json={"student_ids": ids},
        ).status_code
        == 403
    )

    res = client.post(
        "/api/v1/students/bulk-delete",
        headers=admin,
        json={"student_ids": ids},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["deleted_count"] == 2
    listed = client.get("/api/v1/students", headers=admin, params={"page": 1, "page_size": 100}).json()[
        "data"
    ]["items"]
    listed_ids = {s["id"] for s in listed}
    assert ids[0] not in listed_ids
    assert ids[1] not in listed_ids


def test_bulk_reassign_academic_manager(client):
    admin = auth_header(client, "admin", "admin123")
    # create second CR 学管师
    cr2 = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "cr2",
            "display_name": "学管乙",
            "role": "cr",
            "password": "cr22345",
        },
    )
    assert cr2.status_code == 201, cr2.text
    cr2_id = cr2.json()["data"]["id"]

    cr1_id = first_manager_id(client, admin, username="cr1")

    ids = []
    for name in ("转交甲", "转交乙"):
        res = client.post(
            "/api/v1/students",
            headers=admin,
            json=_student_payload(
                name=name,
                grade="二年级",
                school="希望小学",
                academic_manager_id=cr1_id,
            ),
        )
        assert res.status_code == 201, res.text
        ids.append(res.json()["data"]["id"])

    # deactivate cr1 (simulates 离职)
    client.patch(
        f"/api/v1/users/{cr1_id}",
        headers=admin,
        json={"is_active": False},
    )

    # reassign selected students to cr2
    result = client.post(
        "/api/v1/students/reassign",
        headers=admin,
        json={
            "student_ids": ids,
            "from_manager_id": cr1_id,
            "to_manager_id": cr2_id,
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["data"]["updated_count"] == 2

    for sid in ids:
        detail = client.get(f"/api/v1/students/{sid}", headers=admin)
        assert detail.json()["data"]["academic_manager_id"] == cr2_id
        assert detail.json()["data"]["academic_manager_name"] == "学管乙"

    # operator 不可见学生 / 不可转交
    ops = auth_header(client, "ops", "ops123")
    assert client.get("/api/v1/students", headers=ops).status_code == 403
    one = client.post(
        "/api/v1/students/reassign",
        headers=ops,
        json={"student_ids": [ids[0]], "to_manager_id": cr2_id},
    )
    assert one.status_code == 403


def test_teacher_forbidden_reassign(client):
    h = auth_header(client, "teacher1", "t123")
    admin = auth_header(client, "admin", "admin123")
    manager_id = first_manager_id(client, admin)
    s = client.post(
        "/api/v1/students",
        headers=admin,
        json=_student_payload(
            name="不可转交",
            grade="一年级",
            school="A",
            academic_manager_id=manager_id,
        ),
    )
    assert s.status_code == 201, s.text
    sid = s.json()["data"]["id"]
    res = client.post(
        "/api/v1/students/reassign",
        headers=h,
        json={"student_ids": [sid], "to_manager_id": manager_id},
    )
    assert res.status_code == 403


def test_only_admin_delete_student(client):
    admin = auth_header(client, "admin", "admin123")
    teacher = auth_header(client, "teacher1", "t123")
    s = client.post(
        "/api/v1/students",
        headers=admin,
        json=_student_payload(name="待删除", grade="六年级", school="B"),
    )
    assert s.status_code == 201, s.text
    sid = s.json()["data"]["id"]
    assert client.delete(f"/api/v1/students/{sid}", headers=teacher).status_code == 403
    assert client.delete(f"/api/v1/students/{sid}", headers=admin).status_code == 200
