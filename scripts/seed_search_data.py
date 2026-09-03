import json
from pathlib import Path

from pydantic import TypeAdapter

from app.db.session import SessionLocal
from app.schemas.search import HistoricalTicketSeed, KnowledgeSeed
from app.services import knowledge_service
from app.services.embedding_service import get_embedding_service

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_knowledge() -> list[KnowledgeSeed]:
    content = json.loads((DATA_DIR / "sample_knowledge.json").read_text(encoding="utf-8"))
    return TypeAdapter(list[KnowledgeSeed]).validate_python(content)


def load_history() -> list[HistoricalTicketSeed]:
    content = json.loads((DATA_DIR / "sample_resolved_tickets.json").read_text(encoding="utf-8"))
    return TypeAdapter(list[HistoricalTicketSeed]).validate_python(content)


def main() -> None:
    knowledge = load_knowledge()
    history = load_history()
    with SessionLocal() as db:
        result = knowledge_service.seed_sample_catalog(
            db,
            knowledge_items=knowledge,
            historical_items=history,
            embedding_service=get_embedding_service(),
        )
    print(
        "Seed complete: "
        f"knowledge created={result.knowledge_created}, updated={result.knowledge_updated}; "
        f"history created={result.history_created}, skipped={result.history_skipped}"
    )


if __name__ == "__main__":
    main()
