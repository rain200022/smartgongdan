from app.db.session import SessionLocal
from app.schemas.evaluation import SearchEvaluationRunRead
from app.services import evaluation_service
from app.services.embedding_service import get_embedding_service


def main() -> None:
    with SessionLocal() as db:
        record = evaluation_service.run_search_evaluation(
            db,
            dataset=evaluation_service.load_search_benchmark(),
            embedding_service=get_embedding_service(),
        )
        result = SearchEvaluationRunRead.model_validate(record)
    print(
        f"Recall@5: {result.recall_at_5:.1%} "
        f"({result.query_count} cases, {result.dataset_version}, {result.embedding_model})"
    )


if __name__ == "__main__":
    main()
