from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.user import AuthSession, User, UserRole
from app.schemas.auth import UserCreate
from app.services import auth_service


def create_user(
    db: Session,
    *,
    username: str,
    role: UserRole = UserRole.USER,
    password: str = "Test-User-Password-2026!",
) -> User:
    return auth_service.create_user(
        db,
        UserCreate(
            username=username,
            display_name=username,
            password=password,
            role=role,
        ),
    )


def login(client: TestClient, username: str, password: str = "Test-User-Password-2026!") -> None:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def test_protected_routes_require_login(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/tickets").status_code == 401
    assert anonymous_client.get("/classification-tree").status_code == 401
    assert anonymous_client.get("/auth/me").status_code == 401


def test_login_me_and_logout(anonymous_client: TestClient, db_session: Session) -> None:
    create_user(db_session, username="requester")

    login(anonymous_client, "requester")
    me = anonymous_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "USER"

    logout = anonymous_client.post("/auth/logout")
    assert logout.status_code == 204
    assert anonymous_client.get("/auth/me").status_code == 401


def test_invalid_credentials_are_rejected(
    anonymous_client: TestClient, db_session: Session
) -> None:
    create_user(db_session, username="requester")
    response = anonymous_client.post(
        "/auth/login", json={"username": "requester", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码错误"


def test_only_admin_can_manage_users(client: TestClient, db_session: Session) -> None:
    payload = {
        "username": "new-user",
        "display_name": "新用户",
        "password": "New-User-Password-2026!",
        "role": "USER",
    }
    assert client.post("/users", json=payload).status_code == 403

    create_user(
        db_session,
        username="test-admin",
        role=UserRole.ADMIN,
        password="Test-Admin-Password-2026!",
    )
    assert client.post("/auth/logout").status_code == 204
    login(client, "test-admin", "Test-Admin-Password-2026!")
    created = client.post("/users", json=payload)
    assert created.status_code == 201
    assert created.json()["username"] == "new-user"
    assert len(client.get("/users").json()) == 3


def test_users_can_only_see_their_own_tickets(
    anonymous_client: TestClient, db_session: Session
) -> None:
    create_user(db_session, username="owner")
    create_user(db_session, username="other")
    login(anonymous_client, "owner")
    created = anonymous_client.post(
        "/tickets",
        json={"title": "我的工单", "description": "只能由创建者查看"},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]
    assert created.json()["requester_id"] is not None

    assert anonymous_client.post("/auth/logout").status_code == 204
    login(anonymous_client, "other")
    assert anonymous_client.get(f"/tickets/{ticket_id}").status_code == 403
    assert anonymous_client.get("/tickets").json()["total"] == 0
    assert (
        anonymous_client.patch(f"/tickets/{ticket_id}", json={"status": "in_progress"}).status_code
        == 403
    )


def test_expired_session_is_rejected(anonymous_client: TestClient, db_session: Session) -> None:
    create_user(db_session, username="expired")
    login(anonymous_client, "expired")
    session = db_session.query(AuthSession).one()
    session.expires_at = utc_now() - timedelta(minutes=1)
    db_session.commit()
    assert anonymous_client.get("/auth/me").status_code == 401


def test_duplicate_username_returns_conflict(client: TestClient, db_session: Session) -> None:
    create_user(
        db_session,
        username="test-admin",
        role=UserRole.ADMIN,
        password="Test-Admin-Password-2026!",
    )
    assert client.post("/auth/logout").status_code == 204
    login(client, "test-admin", "Test-Admin-Password-2026!")
    payload = {
        "username": "test-admin",
        "display_name": "重复管理员",
        "password": "Another-Admin-Password-2026!",
        "role": "ADMIN",
    }
    assert client.post("/users", json=payload).status_code == 409


def login_as_admin(client: TestClient, db_session: Session) -> User:
    admin = create_user(
        db_session,
        username="account-admin",
        role=UserRole.ADMIN,
        password="Account-Admin-Password-2026!",
    )
    assert client.post("/auth/logout").status_code == 204
    login(client, "account-admin", "Account-Admin-Password-2026!")
    return admin


def test_admin_can_disable_and_reenable_user(client: TestClient, db_session: Session) -> None:
    admin = login_as_admin(client, db_session)
    target = create_user(db_session, username="status-target")
    auth_service.create_session(db_session, target)

    disabled = client.patch(f"/users/{target.id}/status", json={"is_active": False})
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False
    assert (
        db_session.scalar(
            select(func.count(AuthSession.id)).where(AuthSession.user_id == target.id)
        )
        == 0
    )
    assert client.post("/auth/logout").status_code == 204
    assert (
        client.post(
            "/auth/login",
            json={"username": "status-target", "password": "Test-User-Password-2026!"},
        ).status_code
        == 401
    )

    login(client, admin.username, "Account-Admin-Password-2026!")
    enabled = client.patch(f"/users/{target.id}/status", json={"is_active": True})
    assert enabled.status_code == 200
    assert enabled.json()["is_active"] is True


def test_admin_cannot_disable_or_reset_current_account(
    client: TestClient, db_session: Session
) -> None:
    admin = login_as_admin(client, db_session)
    disable = client.patch(f"/users/{admin.id}/status", json={"is_active": False})
    assert disable.status_code == 409
    assert disable.json()["detail"] == "不能停用当前登录账号"

    reset = client.post(
        f"/users/{admin.id}/password/reset",
        json={"new_password": "Replacement-Password-2026!"},
    )
    assert reset.status_code == 409


def test_admin_can_reset_password_and_revoke_sessions(
    client: TestClient, db_session: Session
) -> None:
    login_as_admin(client, db_session)
    target = create_user(db_session, username="password-target")
    auth_service.create_session(db_session, target)

    reset = client.post(
        f"/users/{target.id}/password/reset",
        json={"new_password": "Replacement-Password-2026!"},
    )
    assert reset.status_code == 200
    assert (
        db_session.scalar(
            select(func.count(AuthSession.id)).where(AuthSession.user_id == target.id)
        )
        == 0
    )

    assert client.post("/auth/logout").status_code == 204
    old_password = client.post(
        "/auth/login",
        json={"username": "password-target", "password": "Test-User-Password-2026!"},
    )
    assert old_password.status_code == 401
    login(client, "password-target", "Replacement-Password-2026!")


def test_account_management_handles_missing_user_and_weak_password(
    client: TestClient, db_session: Session
) -> None:
    login_as_admin(client, db_session)
    assert client.patch("/users/999/status", json={"is_active": False}).status_code == 404
    assert (
        client.post(
            "/users/999/password/reset",
            json={"new_password": "Replacement-Password-2026!"},
        ).status_code
        == 404
    )
    target = create_user(db_session, username="weak-password-target")
    assert (
        client.post(
            f"/users/{target.id}/password/reset",
            json={"new_password": "too-short"},
        ).status_code
        == 422
    )
