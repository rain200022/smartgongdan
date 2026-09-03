from pathlib import Path

from scripts.evaluate_ai import evaluate


def test_local_analyzer_baseline_on_labeled_dataset() -> None:
    total, category_correct, subcategory_correct = evaluate(Path("data/sample_tickets.json"))

    assert total == 30
    assert category_correct / total >= 0.9
    assert subcategory_correct / total >= 0.85
