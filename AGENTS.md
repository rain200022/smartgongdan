# Repository instructions

## Scope and architecture

- Preserve the current M1.5 HTTP paths and Alembic migration history unless the task explicitly changes them.
- Keep dependency direction: `api -> services -> models/db`; schemas and core utilities must not import API modules.
- API modules validate transport data and serialize responses. Business rules belong in services.
- AI providers implement the `AIService` protocol. Ticket business logic must not depend on a provider SDK.
- Alembic is the only production schema-management mechanism. Never create tables during application startup.

## Python conventions

- Support Python 3.11 or later and use modern annotations (`X | None`, built-in generics).
- Add type annotations to production functions. `uv run mypy` must pass.
- Format and lint with Ruff; do not hand-format around the configured rules.
- Use Pydantic schemas at HTTP boundaries and SQLAlchemy models inside persistence services.
- Raise domain exceptions from `app.core.exceptions`; translate them to HTTP responses centrally.
- Public service functions own one complete use case and commit once. Helpers prefixed with `stage_` may flush but must not commit.
- Store all timestamps as timezone-aware UTC values.
- Do not log credentials, raw API keys, or unnecessary ticket contents.

## Data and behavior invariants

- AI and engineer judgments are append-only audit records.
- Reanalysis and reconfirmation must not overwrite prior records.
- Classification pairs must come from `CLASSIFICATION_TREE`.
- Only exact category and subcategory agreement sets `agreement=true`.
- Closed tickets are immutable.
- AI provider failures must not persist partial analysis or judgment rows.
- Authentication tokens are opaque, stored only as hashes, and transported in HttpOnly cookies.
- Disabling an account or administratively resetting its password revokes all of its sessions.
- Administrators must not deactivate or administratively reset the password of their current account.
- Frontend route guards improve navigation only; every ownership and role decision must be enforced by FastAPI.
- Public self-registration is disabled. Only administrators or the local user-management script create accounts.

## Required checks

Run before handoff:

```powershell
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest --cov=app --cov-fail-under=90
uv pip check
uv run alembic check
cd frontend
npm run quality
```

## Frontend conventions

- Use Vue 3 Composition API with strict TypeScript and Ant Design Vue as the only component library.
- Keep HTTP access in `frontend/src/api`; views must not duplicate fetch and error parsing logic.
- Reuse the tokens in `frontend/src/styles/tokens.css`. Do not add gradients, decorative shadows, or one-off brand colors.
- User-facing flows use `PortalLayout`; engineer and administrator flows use `ConsoleLayout`.
- Preserve keyboard focus visibility, semantic status labels, and responsive behavior when changing UI.
