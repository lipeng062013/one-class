from tests.conftest import auth_header


def _create_group_course(client, headers):
    response = client.post(
        "/api/v1/academic/courses",
        headers=headers,
        json={
            "name": "Class ordering course",
            "course_type": "group",
            "enabled": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_class(client, headers, course_id, name):
    response = client.post(
        "/api/v1/academic/classes",
        headers=headers,
        json={
            "name": name,
            "mode": "group",
            "course_id": course_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_graduated_classes_are_listed_after_active_classes_across_pages(client):
    admin = auth_header(client, "admin", "admin123")
    course = _create_group_course(client, admin)

    active_old = _create_class(client, admin, course["id"], "Active old")
    graduated_old = _create_class(client, admin, course["id"], "Graduated old")
    active_new = _create_class(client, admin, course["id"], "Active new")
    graduated_new = _create_class(client, admin, course["id"], "Graduated new")

    for class_id in (graduated_old["id"], graduated_new["id"]):
        response = client.patch(
            f"/api/v1/academic/classes/{class_id}",
            headers=admin,
            json={"status": "graduated"},
        )
        assert response.status_code == 200, response.text

    first_page = client.get(
        "/api/v1/academic/classes",
        headers=admin,
        params={"mode": "group", "page": 1, "page_size": 2},
    )
    second_page = client.get(
        "/api/v1/academic/classes",
        headers=admin,
        params={"mode": "group", "page": 2, "page_size": 2},
    )

    assert first_page.status_code == 200, first_page.text
    assert second_page.status_code == 200, second_page.text
    assert [item["id"] for item in first_page.json()["data"]["items"]] == [
        active_new["id"],
        active_old["id"],
    ]
    assert [item["id"] for item in second_page.json()["data"]["items"]] == [
        graduated_new["id"],
        graduated_old["id"],
    ]
