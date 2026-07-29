from tests.conftest import auth_header


def test_create_and_update_lead(client):
    h = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/leads",
        headers=h,
        json={
            "student_or_parent_name": "张妈妈",
            "source": "referral",
            "referrer_name": "李同学",
            "need": "三年级数学",
        },
    )
    assert res.status_code == 200
    lid = res.json()["data"]["id"]
    patch = client.patch(
        f"/api/v1/leads/{lid}",
        headers=h,
        json={"status": "contacted", "notes": "已电话"},
    )
    assert patch.json()["data"]["status"] == "contacted"


def test_teacher_forbidden_leads(client):
    h = auth_header(client, "teacher1", "t123")
    assert client.get("/api/v1/leads", headers=h).status_code == 403


def test_dashboard_counts(client):
    h = auth_header(client, "admin", "admin123")
    res = client.get("/api/v1/dashboard/summary", headers=h)
    assert res.status_code == 200
    assert "materials_new" in res.json()["data"]
    assert "leads_follow_today" in res.json()["data"]
