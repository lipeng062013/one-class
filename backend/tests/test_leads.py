import pytest

from app.models.lead import Lead
from tests.conftest import auth_header


@pytest.mark.parametrize(
    "phone",
    [
        "1380000111",
        "23800001111",
        "1380000111a",
        13800001111,
    ],
)
def test_create_lead_rejects_invalid_phone(client, phone):
    h = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/leads",
        headers=h,
        json={"student_or_parent_name": "手机号测试", "phone": phone},
    )
    assert res.status_code == 422


def test_update_lead_rejects_invalid_phone(client):
    h = auth_header(client, "ops", "ops123")
    created = client.post(
        "/api/v1/leads",
        headers=h,
        json={"student_or_parent_name": "手机号测试", "phone": "13800001111"},
    )
    assert created.status_code == 201, created.text

    res = client.patch(
        f"/api/v1/leads/{created.json()['data']['id']}",
        headers=h,
        json={"phone": "1380000111-"},
    )
    assert res.status_code == 422


def test_lead_model_rejects_invalid_phone_assignment():
    with pytest.raises(ValueError, match="手机号必须为11位数字且以1开头"):
        Lead(student_or_parent_name="模型校验", phone="1380000000x")


def test_create_and_update_lead(client):
    h = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/leads",
        headers=h,
        json={
            "student_or_parent_name": "张妈妈",
            "phone": "13800001001",
            "source": "referral",
            "referrer_name": "李同学",
            "need": "三年级数学",
        },
    )
    assert res.status_code in (200, 201)
    data = res.json()["data"]
    lid = data["id"]
    # 创建人默认成为主跟进人
    assert data.get("owner_id") is not None
    assert data.get("owner_name")

    # 建档动态
    acts = client.get(f"/api/v1/leads/{lid}/activities", headers=h)
    assert acts.status_code == 200
    items = acts.json()["data"]["items"]
    assert any(a["kind"] == "create" for a in items)

    patch = client.patch(
        f"/api/v1/leads/{lid}",
        headers=h,
        json={
            "status": "contacted",
            "notes": "已电话",
            "external_code": "EDIT-001",
            "school": "实验小学",
            "grade": "三年级",
            "age": 9,
            "campus": "中心校区",
            "imported_creator_name": "历史创建人",
        },
    )
    assert patch.status_code == 200
    updated = patch.json()["data"]
    assert updated["status"] == "contacted"
    assert updated["external_code"] == "EDIT-001"
    assert updated["school"] == "实验小学"
    assert updated["grade"] == "三年级"
    assert updated["age"] == 9
    assert updated["campus"] == "中心校区"
    assert updated["imported_creator_name"] == "历史创建人"

    acts2 = client.get(f"/api/v1/leads/{lid}/activities", headers=h)
    kinds = [a["kind"] for a in acts2.json()["data"]["items"]]
    assert "update" in kinds


def test_lead_detail_follow_and_collaborators(client):
    ops = auth_header(client, "ops", "ops123")
    admin = auth_header(client, "admin", "admin123")

    res = client.post(
        "/api/v1/leads",
        headers=ops,
        json={
            "student_or_parent_name": "协作家长",
            "phone": "13800001002",
            "source": "wechat",
            "need": "英语",
        },
    )
    lid = res.json()["data"]["id"]

    # 详情
    detail = client.get(f"/api/v1/leads/{lid}", headers=ops)
    assert detail.status_code == 200
    assert detail.json()["data"]["student_or_parent_name"] == "协作家长"

    # 写跟进
    follow = client.post(
        f"/api/v1/leads/{lid}/activities",
        headers=ops,
        json={
            "content": "电话沟通，家长意向较强，约周末到访",
            "contact_method": "phone",
            "status": "contacted",
        },
    )
    assert follow.status_code in (200, 201)
    body = follow.json()["data"]
    assert body["activity"]["kind"] == "follow"
    assert body["lead"]["status"] == "contacted"
    assert body["lead"]["last_contact_by_name"]

    # 负责人加入协作
    join = client.post(f"/api/v1/leads/{lid}/collaborators/me", headers=admin)
    assert join.status_code == 200
    followers = join.json()["data"]["followers"]
    assert len(followers) >= 2  # 主责 + 协作

    listed = client.get(
        "/api/v1/leads",
        headers=ops,
        params={"name": "协作家长"},
    )
    assert listed.status_code == 200, listed.text
    list_item = listed.json()["data"]["items"][0]
    assert list_item["owner_name"]
    assert list_item["last_contact_by_name"]
    assert list_item["collaborator_count"] >= 1

    # 可指派列表
    assignees = client.get("/api/v1/leads/assignees", headers=ops)
    assert assignees.status_code == 200
    assert len(assignees.json()["data"]) >= 1


def test_teacher_forbidden_leads(client):
    h = auth_header(client, "teacher1", "t123")
    assert client.get("/api/v1/leads", headers=h).status_code == 403


def test_dashboard_counts(client):
    h = auth_header(client, "admin", "admin123")
    res = client.get("/api/v1/dashboard/summary", headers=h)
    assert res.status_code == 200
    assert "materials_new" in res.json()["data"]
    assert "leads_follow_today" in res.json()["data"]
