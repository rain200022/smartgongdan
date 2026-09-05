from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.user import UserRole
from app.schemas.auth import UserCreate
from app.services import auth_service


def test_old_pending_tickets_remain_reachable_beyond_first_hundred(
    client: TestClient, db_session: Session
) -> None:
    oldest = Ticket(
        title="待跟进的旧工单",
        description="未解决",
        status=TicketStatus.OPEN,
        created_at=utc_now() - timedelta(days=30),
    )
    db_session.add(oldest)
    db_session.add(Ticket(title="正在处理", description="处理中", status=TicketStatus.IN_PROGRESS))
    db_session.add_all(
        Ticket(title=f"新工单 {index}", description="已解决", status=TicketStatus.CLOSED)
        for index in range(101)
    )
    db_session.commit()

    first = client.get("/tickets", params={"limit": 100}).json()
    assert first["total"] == 103
    assert len(first["items"]) == 100
    assert oldest.id not in {item["id"] for item in first["items"]}
    expected_counts = {"all": 103, "open": 1, "in_progress": 1, "closed": 101}
    assert first["status_counts"] == expected_counts

    last = client.get("/tickets", params={"limit": 100, "offset": 100}).json()
    assert last["total"] == 103
    assert len(last["items"]) == 3
    assert last["items"][-1]["id"] == oldest.id
    assert last["status_counts"] == expected_counts

    pending = client.get("/tickets", params={"status": "open", "limit": 20}).json()
    assert [item["id"] for item in pending["items"]] == [oldest.id]
    assert pending["total"] == 1
    assert pending["status_counts"] == expected_counts

    beyond = client.get("/tickets", params={"offset": 200}).json()
    assert beyond["items"] == []
    assert beyond["total"] == 103
    assert beyond["status_counts"] == expected_counts


def test_counts_and_results_respect_ownership_and_exclude_imports(
    client: TestClient, db_session: Session
) -> None:
    owner = auth_service.create_user(
        db_session,
        UserCreate(
            username="listing-owner",
            display_name="工单发起人",
            password="Listing-Owner-Password-2026!",
            role=UserRole.USER,
        ),
    )
    own = Ticket(title="VPN 自己的工单", description="未解决", requester_id=owner.id)
    db_session.add_all(
        [
            own,
            Ticket(title="VPN 别人的工单", description="未解决", requester_id=1),
            Ticket(
                title="VPN 导入案例",
                description="历史知识",
                requester_id=owner.id,
                external_reference="INC-IMPORTED-1",
                status=TicketStatus.CLOSED,
            ),
        ]
    )
    db_session.commit()
    staff_page = client.get("/tickets", params={"q": "VPN"}).json()
    assert staff_page["total"] == 2
    assert staff_page["status_counts"] == {"all": 2, "open": 2, "in_progress": 0, "closed": 0}

    assert client.post("/auth/logout").status_code == 204
    assert (
        client.post(
            "/auth/login",
            json={"username": owner.username, "password": "Listing-Owner-Password-2026!"},
        ).status_code
        == 200
    )
    own_page = client.get("/tickets", params={"q": "VPN"}).json()
    assert [item["id"] for item in own_page["items"]] == [own.id]
    assert own_page["total"] == 1
    assert own_page["status_counts"] == {"all": 1, "open": 1, "in_progress": 0, "closed": 0}
    assert client.get("/tickets", params={"q": "别人的"}).json()["total"] == 0


def test_priority_and_search_counts_are_scoped_before_status(
    client: TestClient, db_session: Session
) -> None:
    fallback = Ticket(
        title="VPN AI 优先级",
        description="待处理",
        ai_priority=TicketPriority.P2,
    )
    final = Ticket(
        title="VPN 人工优先级",
        description="已完成",
        ai_priority=TicketPriority.P1,
        final_priority=TicketPriority.P2,
        status=TicketStatus.CLOSED,
    )
    db_session.add_all(
        [
            fallback,
            final,
            Ticket(
                title="VPN 已调整优先级",
                description="人工优先",
                ai_priority=TicketPriority.P2,
                final_priority=TicketPriority.P3,
            ),
            Ticket(title="VPN 未评估", description="无优先级"),
            Ticket(title="打印机离线", description="另一类问题", ai_priority=TicketPriority.P2),
        ]
    )
    db_session.commit()

    page = client.get("/tickets", params={"q": "vpn", "priority": "P2", "status": "open"}).json()
    assert [item["id"] for item in page["items"]] == [fallback.id]
    assert page["total"] == 1
    assert page["status_counts"] == {"all": 2, "open": 1, "in_progress": 0, "closed": 1}
    closed = client.get(
        "/tickets", params={"q": "VPN", "priority": "P2", "status": "closed"}
    ).json()
    assert [item["id"] for item in closed["items"]] == [final.id]
    assert closed["status_counts"] == page["status_counts"]


@pytest.mark.parametrize(
    ("query", "matching", "other"),
    [
        ("%", "进度 100%", "进度 1000"),
        ("_", "vpn_log", "vpnXlog"),
        ("\\", "路径 C:\\logs", "路径 C:logs"),
        ("  VPN  ", "企业 VPN", "普通网络"),
    ],
)
def test_search_treats_wildcards_literally_and_trims_whitespace(
    client: TestClient, db_session: Session, query: str, matching: str, other: str
) -> None:
    target = Ticket(title=matching, description="原始问题")
    db_session.add_all([target, Ticket(title=other, description="原始问题")])
    db_session.commit()
    response = client.get("/tickets", params={"q": query})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [target.id]
    assert response.json()["status_counts"]["all"] == 1


def test_ticket_number_search_and_large_number_input(
    client: TestClient, db_session: Session
) -> None:
    target = Ticket(title="通过编号查找", description="原始问题")
    db_session.add(target)
    db_session.commit()
    for query in [str(target.id), f"INC-{target.id:04d}", f"inc-{target.id}"]:
        response = client.get("/tickets", params={"q": query})
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == [target.id]

    response = client.get("/tickets", params={"q": "INC-" + "9" * 196})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["status_counts"] == {"all": 0, "open": 0, "in_progress": 0, "closed": 0}


@pytest.mark.parametrize(
    "params",
    [
        {"q": ""},
        {"q": "   "},
        {"q": "a" * 201},
        {"priority": "P5"},
        {"limit": 101},
        {"offset": -1},
    ],
)
def test_listing_rejects_invalid_query_parameters(client: TestClient, params: dict) -> None:
    assert client.get("/tickets", params=params).status_code == 422
