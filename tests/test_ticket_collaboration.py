import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import UserRole
from app.schemas.auth import UserCreate
from app.services.auth_service import create_user


def switch_user(client: TestClient, db: Session, role: UserRole, name: str) -> None:
    create_user(
        db, UserCreate(username=name, display_name=name, password="Other-Password-2026!", role=role)
    )
    assert (
        client.post(
            "/auth/login", json={"username": name, "password": "Other-Password-2026!"}
        ).status_code
        == 200
    )


def test_stale_update_is_rejected_without_audit(client: TestClient) -> None:
    ticket = client.post("/tickets", json={"title": "VPN", "description": "认证失败"}).json()
    version = ticket["version"]
    first = client.patch(
        f"/tickets/{ticket['id']}",
        json={"final_priority": "P1"},
        headers={"X-Ticket-Version": str(version)},
    )
    assert first.status_code == 200
    stale = client.patch(
        f"/tickets/{ticket['id']}",
        json={"final_priority": "P4"},
        headers={"X-Ticket-Version": str(version)},
    )
    assert stale.status_code == 409
    current = client.get(f"/tickets/{ticket['id']}").json()
    assert current["final_priority"] == "P1"
    assert current["version"] == version + 1
    events = client.get(f"/tickets/{ticket['id']}/events").json()
    assert [item["action"] for item in events] == ["updated"]
    assert events[0]["actor_name"] == "测试工程师"


def test_claim_and_release_are_versioned(client: TestClient) -> None:
    ticket = client.post("/tickets", json={"title": "VPN", "description": "认证失败"}).json()
    path = f"/tickets/{ticket['id']}"
    claimed = client.post(f"{path}/claim").json()
    assert claimed["assigned_engineer_id"] is not None
    assert claimed["status"] == "in_progress"
    assert claimed["version"] == ticket["version"] + 1
    assert client.post(f"{path}/claim").status_code == 409
    released = client.post(f"{path}/release").json()
    assert released["assigned_engineer_id"] is None
    assert released["status"] == "in_progress"
    assert [event["action"] for event in client.get(f"{path}/events").json()] == [
        "claimed",
        "released",
    ]


@pytest.mark.parametrize(
    "method,endpoint,payload",
    [
        ("post", "claim", None),
        ("post", "release", None),
        ("post", "analyze", None),
        ("post", "solutions/generate", None),
        ("post", "solutions/999/review", {"decision": "ADOPTED", "engineer_solution": "检查证书"}),
        ("post", "classification/confirm", {"category": "网络", "subcategory": "VPN"}),
        (
            "post",
            "close",
            {"final_category": "网络/VPN", "final_priority": "P3", "resolution": "完成"},
        ),
        ("patch", "", {"final_priority": "P1"}),
    ],
)
def test_non_assignee_cannot_mutate(
    client: TestClient, db_session: Session, method: str, endpoint: str, payload: dict | None
) -> None:
    ticket = client.post("/tickets", json={"title": "VPN", "description": "认证失败"}).json()
    path = f"/tickets/{ticket['id']}"
    assert client.post(f"{path}/claim").status_code == 200
    switch_user(client, db_session, UserRole.ENGINEER, "other-engineer")
    response = client.request(method, f"{path}/{endpoint}" if endpoint else path, json=payload)
    assert response.status_code == 403
    assert client.get(path).json()["version"] == 2
    assert len(client.get(f"{path}/events").json()) == 1


def test_admin_can_release_other_assignee_and_user_cannot_read_events(
    client: TestClient, db_session: Session
) -> None:
    ticket = client.post("/tickets", json={"title": "VPN", "description": "认证失败"}).json()
    path = f"/tickets/{ticket['id']}"
    assert client.post(f"{path}/claim").status_code == 200
    switch_user(client, db_session, UserRole.ADMIN, "other-admin")
    assert client.post(f"{path}/release").status_code == 200
    assert client.post(f"{path}/release").status_code == 409
    switch_user(client, db_session, UserRole.USER, "other-user")
    assert client.get(f"{path}/events").status_code == 403
    assert client.post(f"{path}/claim").status_code == 403


@pytest.mark.parametrize("version", ["0", "-1", "bad"])
def test_invalid_version_header(client: TestClient, version: str) -> None:
    assert client.post("/tickets/1/claim", headers={"X-Ticket-Version": version}).status_code == 422


def test_audit_all_mutations_and_stale_solution(client: TestClient) -> None:
    ticket = client.post("/tickets", json={"title": "VPN", "description": "认证失败"}).json()
    path = f"/tickets/{ticket['id']}"
    assert client.post(f"{path}/analyze").status_code == 200
    solution = client.post(f"{path}/solutions/generate").json()
    assert client.post(f"{path}/analyze").status_code == 200
    review = {"decision": "ADOPTED", "engineer_solution": "检查设备证书"}
    assert client.post(f"{path}/solutions/{solution['id']}/review", json=review).status_code == 409
    solution = client.post(f"{path}/solutions/generate").json()
    assert client.post(f"{path}/solutions/{solution['id']}/review", json=review).status_code == 200
    assert (
        client.post(
            f"{path}/classification/confirm", json={"category": "网络", "subcategory": "VPN"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"{path}/close",
            json={"final_category": "网络/VPN", "final_priority": "P3", "resolution": "证书恢复"},
        ).status_code
        == 200
    )
    for endpoint in ["claim", "release", "analyze", "solutions/generate"]:
        assert client.post(f"{path}/{endpoint}").status_code == 409
    events = client.get(f"{path}/events").json()
    assert [item["version"] for item in events] == list(range(2, 9))
    assert events[-1]["action"] == "closed"
    assert client.get(f"{path}/events?limit=1&offset=6").json() == [events[-1]]
    assert client.get("/tickets/999/events").status_code == 404
