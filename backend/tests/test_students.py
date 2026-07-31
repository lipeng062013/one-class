from tests.conftest import auth_header


def test_create_student_with_school_and_manager(client):
    admin = auth_header(client, "admin", "admin123")
    teacher = auth_header(client, "teacher1", "t123")

    managers = client.get("/api/v1/students/managers", headers=admin)
    assert managers.status_code == 200
    mgr_list = managers.json()["data"]
    assert any(m["username"] == "teacher1" for m in mgr_list)
    teacher_id = next(m["id"] for m in mgr_list if m["username"] == "teacher1")

    res = client.post(
        "/api/v1/students",
        headers=admin,
        json={
            "name": "张小明",
            "grade": "三年级",
            "school": "实验小学",
            "phone": "13800001111",
            "parent_name": "张妈妈",
            "academic_manager_id": teacher_id,
            "notes": "数学提高",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["name"] == "张小明"
    assert data["school"] == "实验小学"
    assert data["academic_manager_id"] == teacher_id
    assert data["academic_manager_name"] == "老师甲"
    sid = data["id"]

    # filter by grade / name / phone / school
    listed = client.get("/api/v1/students", headers=admin, params={"grade": "三年级"})
    assert any(s["id"] == sid for s in listed.json()["data"])

    by_name = client.get("/api/v1/students", headers=admin, params={"name": "小明"})
    assert len(by_name.json()["data"]) >= 1

    by_phone = client.get("/api/v1/students", headers=admin, params={"phone": "1380000"})
    assert len(by_phone.json()["data"]) >= 1

    # teacher can see students
    t_list = client.get("/api/v1/students", headers=teacher)
    assert t_list.status_code == 200
    assert any(s["id"] == sid for s in t_list.json()["data"])


def test_teacher_create_student_and_learning_with_image(client):
    h = auth_header(client, "teacher1", "t123")
    managers = client.get("/api/v1/students/managers", headers=h).json()["data"]
    teacher_id = next(m["id"] for m in managers if m["username"] == "teacher1")

    s = client.post(
        "/api/v1/students",
        headers=h,
        json={
            "name": "李小红",
            "grade": "四年级",
            "school": "育才小学",
            "phone": "13900002222",
            "academic_manager_id": teacher_id,
        },
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

    # timeline on student
    timeline = client.get("/api/v1/learning-records", headers=h, params={"student_id": sid})
    assert any(r["id"] == rid for r in timeline.json()["data"])


def test_operator_cannot_access_students(client):
    teacher = auth_header(client, "teacher1", "t123")
    ops = auth_header(client, "ops", "ops123")
    managers = client.get("/api/v1/students/managers", headers=teacher).json()["data"]
    teacher_id = next(m["id"] for m in managers if m["username"] == "teacher1")

    s = client.post(
        "/api/v1/students",
        headers=teacher,
        json={
            "name": "王同学",
            "grade": "五年级",
            "school": "中心小学",
            "academic_manager_id": teacher_id,
        },
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
    items = lr.json()["data"]
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
    managers = client.get("/api/v1/students/managers", headers=admin).json()["data"]
    teacher_id = next(m["id"] for m in managers if m["username"] == "teacher1")

    ids = []
    for name in ("批量删甲", "批量删乙"):
        res = client.post(
            "/api/v1/students",
            headers=admin,
            json={
                "name": name,
                "grade": "一年级",
                "school": "实验小学",
                "academic_manager_id": teacher_id,
            },
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
    listed = client.get("/api/v1/students", headers=admin).json()["data"]
    listed_ids = {s["id"] for s in listed}
    assert ids[0] not in listed_ids
    assert ids[1] not in listed_ids


def test_bulk_reassign_academic_manager(client):
    admin = auth_header(client, "admin", "admin123")
    # create second teacher
    t2 = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "teacher2",
            "display_name": "老师乙",
            "role": "teacher",
            "password": "t22345",
        },
    )
    assert t2.status_code == 201, t2.text
    teacher2_id = t2.json()["data"]["id"]

    managers = client.get("/api/v1/students/managers", headers=admin).json()["data"]
    teacher1_id = next(m["id"] for m in managers if m["username"] == "teacher1")

    ids = []
    for name in ("转交甲", "转交乙"):
        res = client.post(
            "/api/v1/students",
            headers=admin,
            json={
                "name": name,
                "grade": "二年级",
                "school": "希望小学",
                "academic_manager_id": teacher1_id,
            },
        )
        ids.append(res.json()["data"]["id"])

    # deactivate teacher1 (simulates 离职)
    client.patch(
        f"/api/v1/users/{teacher1_id}",
        headers=admin,
        json={"is_active": False},
    )

    # reassign selected students to teacher2
    result = client.post(
        "/api/v1/students/reassign",
        headers=admin,
        json={
            "student_ids": ids,
            "from_manager_id": teacher1_id,
            "to_manager_id": teacher2_id,
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["data"]["updated_count"] == 2

    for sid in ids:
        detail = client.get(f"/api/v1/students/{sid}", headers=admin)
        assert detail.json()["data"]["academic_manager_id"] == teacher2_id
        assert detail.json()["data"]["academic_manager_name"] == "老师乙"

    # operator 不可见学生 / 不可转交
    ops = auth_header(client, "ops", "ops123")
    assert client.get("/api/v1/students", headers=ops).status_code == 403
    one = client.post(
        "/api/v1/students/reassign",
        headers=ops,
        json={"student_ids": [ids[0]], "to_manager_id": teacher2_id},
    )
    assert one.status_code == 403


def test_teacher_forbidden_reassign(client):
    h = auth_header(client, "teacher1", "t123")
    managers = client.get("/api/v1/students/managers", headers=h).json()["data"]
    teacher_id = next(m["id"] for m in managers if m["username"] == "teacher1")
    s = client.post(
        "/api/v1/students",
        headers=h,
        json={"name": "不可转交", "grade": "一年级", "school": "A", "academic_manager_id": teacher_id},
    )
    sid = s.json()["data"]["id"]
    res = client.post(
        "/api/v1/students/reassign",
        headers=h,
        json={"student_ids": [sid], "to_manager_id": teacher_id},
    )
    assert res.status_code == 403


def test_only_admin_delete_student(client):
    admin = auth_header(client, "admin", "admin123")
    teacher = auth_header(client, "teacher1", "t123")
    s = client.post(
        "/api/v1/students",
        headers=teacher,
        json={"name": "待删除", "grade": "六年级", "school": "B"},
    )
    sid = s.json()["data"]["id"]
    assert client.delete(f"/api/v1/students/{sid}", headers=teacher).status_code == 403
    assert client.delete(f"/api/v1/students/{sid}", headers=admin).status_code == 200
