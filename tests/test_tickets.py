from fastapi.testclient import TestClient


def create_ticket(client: TestClient) -> dict:
    response = client.post(
        "/tickets",
        json={
            "title": "VPN无法连接",
            "description": "认证服务器不可用，已经重启客户端",
            "user_category": "软件/VPN",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_ticket_lifecycle(client: TestClient) -> None:
    ticket = create_ticket(client)
    assert ticket["status"] == "open"

    response = client.patch(
        f"/tickets/{ticket['id']}",
        json={"final_category": "网络/VPN", "final_priority": "P2", "status": "in_progress"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"

    response = client.post(
        f"/tickets/{ticket['id']}/close",
        json={
            "final_category": "网络/VPN",
            "final_priority": "P2",
            "resolution": "重新签发设备证书后恢复连接",
        },
    )
    assert response.status_code == 200
    closed = response.json()
    assert closed["status"] == "closed"
    assert closed["resolution"] == "重新签发设备证书后恢复连接"
    assert closed["resolved_at"] is not None


def test_list_and_filter_tickets(client: TestClient) -> None:
    ticket = create_ticket(client)

    response = client.get("/tickets?status=open")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == ticket["id"]

    response = client.get("/tickets?status=closed")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_missing_ticket_returns_404(client: TestClient) -> None:
    response = client.get("/tickets/999")
    assert response.status_code == 404


def test_closed_ticket_cannot_be_edited_or_closed_twice(client: TestClient) -> None:
    ticket = create_ticket(client)
    close_payload = {
        "final_category": "网络/VPN",
        "final_priority": "P3",
        "resolution": "刷新证书缓存后恢复",
    }
    assert client.post(f"/tickets/{ticket['id']}/close", json=close_payload).status_code == 200

    assert (
        client.patch(f"/tickets/{ticket['id']}", json={"final_priority": "P1"}).status_code == 409
    )
    assert client.post(f"/tickets/{ticket['id']}/close", json=close_payload).status_code == 409


def test_close_requires_engineer_decision(client: TestClient) -> None:
    ticket = create_ticket(client)
    response = client.post(f"/tickets/{ticket['id']}/close", json={})
    assert response.status_code == 422
