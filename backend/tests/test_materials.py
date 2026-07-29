from io import BytesIO

from tests.conftest import auth_header


def test_teacher_creates_material_and_uploads(client):
    h = auth_header(client, "teacher1", "t123")
    res = client.post(
        "/api/v1/materials",
        headers=h,
        json={
            "title": "课堂进步",
            "grade": "四年级",
            "subject": "数学",
            "pain_point": "应用题慢",
            "teacher_action": "拆步骤示范",
            "next_step": "预约试听",
            "auth_status": "authorized",
        },
    )
    assert res.status_code == 201, res.text
    mid = res.json()["data"]["id"]
    files = {"file": ("a.png", BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")}
    up = client.post(f"/api/v1/materials/{mid}/files", headers=h, files=files)
    assert up.status_code == 201, up.text
    assert up.json()["data"]["file_type"].startswith("image/")

    detail = client.get(f"/api/v1/materials/{mid}", headers=h)
    assert detail.status_code == 200
    assert len(detail.json()["data"]["files"]) == 1


def test_teacher_only_sees_own_materials(client):
    h_t = auth_header(client, "teacher1", "t123")
    client.post(
        "/api/v1/materials",
        headers=h_t,
        json={"title": "only-mine", "auth_status": "pending"},
    )
    h_ops = auth_header(client, "ops", "ops123")
    client.post(
        "/api/v1/materials",
        headers=h_ops,
        json={"title": "ops-mat", "auth_status": "pending"},
    )
    listed = client.get("/api/v1/materials", headers=h_t)
    assert listed.status_code == 200
    titles = [m["title"] for m in listed.json()["data"]]
    assert "only-mine" in titles
    assert "ops-mat" not in titles


def test_ops_sees_all_and_can_patch_status(client):
    h_t = auth_header(client, "teacher1", "t123")
    mid = client.post(
        "/api/v1/materials",
        headers=h_t,
        json={"title": "x", "auth_status": "pending"},
    ).json()["data"]["id"]
    h_ops = auth_header(client, "ops", "ops123")
    listed = client.get("/api/v1/materials", headers=h_ops)
    titles = [m["title"] for m in listed.json()["data"]]
    assert "x" in titles

    res = client.patch(
        f"/api/v1/materials/{mid}",
        headers=h_ops,
        json={"status": "usable", "auth_status": "authorized"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "usable"
    assert res.json()["data"]["auth_status"] == "authorized"


def test_teacher_cannot_patch_status(client):
    h_t = auth_header(client, "teacher1", "t123")
    mid = client.post(
        "/api/v1/materials",
        headers=h_t,
        json={"title": "y", "auth_status": "pending"},
    ).json()["data"]["id"]
    res = client.patch(
        f"/api/v1/materials/{mid}",
        headers=h_t,
        json={"status": "usable"},
    )
    assert res.status_code == 403


def test_teacher_cannot_view_others_material(client):
    h_ops = auth_header(client, "ops", "ops123")
    mid = client.post(
        "/api/v1/materials",
        headers=h_ops,
        json={"title": "secret", "auth_status": "pending"},
    ).json()["data"]["id"]
    h_t = auth_header(client, "teacher1", "t123")
    res = client.get(f"/api/v1/materials/{mid}", headers=h_t)
    assert res.status_code == 403
