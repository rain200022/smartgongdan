import argparse
import getpass
import os

from app.db.session import SessionLocal
from app.models.user import UserRole
from app.schemas.auth import UserCreate
from app.services import auth_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Smart Gongdan user")
    parser.add_argument("username")
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", choices=[role.value for role in UserRole], default="USER")
    parser.add_argument(
        "--password-env",
        default="SMARTGONGDAN_USER_PASSWORD",
        help="Environment variable containing the password; prompts when unset",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    password = os.environ.get(args.password_env) or getpass.getpass("Password: ")
    payload = UserCreate(
        username=args.username,
        display_name=args.display_name,
        password=password,
        role=UserRole(args.role),
    )
    with SessionLocal() as db:
        user = auth_service.create_user(db, payload)
    print(f"Created user '{user.username}' with role {user.role.value}")


if __name__ == "__main__":
    main()
