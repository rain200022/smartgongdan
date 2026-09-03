import argparse
import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from string import Formatter
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import ClassificationPair
from app.services.ai_service import LocalAIService

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "sample_tickets.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "pilot_classification_manifest.json"
ALLOWED_TEMPLATE_FIELDS = {"title", "description"}


class BenchmarkModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClassificationBenchmarkCase(BenchmarkModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=4_000)
    expected: ClassificationPair


class PilotClassificationCase(ClassificationBenchmarkCase):
    source_id: str = Field(min_length=1, max_length=100)
    variant_id: str = Field(min_length=1, max_length=50)


class PilotVariant(BenchmarkModel):
    id: str = Field(min_length=1, max_length=50)
    title_template: str = Field(min_length=1, max_length=1_000)
    description_template: str = Field(min_length=1, max_length=4_000)


class PilotClassificationManifest(BenchmarkModel):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=500)
    variants: list[PilotVariant] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_unique_variant_ids(self) -> Self:
        ids = [variant.id for variant in self.variants]
        if len(ids) != len(set(ids)):
            raise ValueError("variant ids must be unique")
        return self


class ClassificationFailure(BenchmarkModel):
    case_id: str
    expected_category: str
    expected_subcategory: str
    actual_category: str
    actual_subcategory: str


class ClassificationStratum(BenchmarkModel):
    category: str
    subcategory: str
    total: int
    category_correct: int
    exact_correct: int


class ClassificationEvaluationResult(BenchmarkModel):
    total: int
    category_correct: int
    exact_correct: int
    by_classification: list[ClassificationStratum]
    failures: list[ClassificationFailure]


def load_base_cases(dataset_path: Path) -> list[ClassificationBenchmarkCase]:
    payload: object = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("classification dataset must be a non-empty JSON array")
    return [ClassificationBenchmarkCase.model_validate(row) for row in payload]


def load_manifest(manifest_path: Path) -> PilotClassificationManifest:
    payload: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    return PilotClassificationManifest.model_validate(payload)


def _render_template(
    template: str,
    *,
    title: str,
    description: str,
    variant_id: str,
) -> str:
    for _, field_name, format_spec, conversion in Formatter().parse(template):
        if field_name is not None and field_name not in ALLOWED_TEMPLATE_FIELDS:
            raise ValueError(
                f"variant '{variant_id}' contains unknown placeholder '{{{field_name}}}'"
            )
        if format_spec or conversion:
            raise ValueError(f"variant '{variant_id}' cannot use format specifiers or conversions")
    return template.format(title=title, description=description)


def build_pilot_cases(
    base_cases: Sequence[ClassificationBenchmarkCase],
    manifest: PilotClassificationManifest,
) -> list[PilotClassificationCase]:
    cases: list[PilotClassificationCase] = []
    for source in base_cases:
        for variant in manifest.variants:
            cases.append(
                PilotClassificationCase(
                    id=f"{source.id}::{variant.id}",
                    source_id=source.id,
                    variant_id=variant.id,
                    title=_render_template(
                        variant.title_template,
                        title=source.title,
                        description=source.description,
                        variant_id=variant.id,
                    ),
                    description=_render_template(
                        variant.description_template,
                        title=source.title,
                        description=source.description,
                        variant_id=variant.id,
                    ),
                    expected=source.expected,
                )
            )
    return cases


def evaluate_cases(
    cases: Sequence[ClassificationBenchmarkCase],
) -> ClassificationEvaluationResult:
    if not cases:
        raise ValueError("classification evaluation requires at least one case")

    service = LocalAIService()
    category_correct = 0
    exact_correct = 0
    failures: list[ClassificationFailure] = []
    strata: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])

    for case in cases:
        actual = service.analyze_ticket(case)
        expected_category = case.expected.category.value
        actual_category = actual.category.value
        category_match = actual_category == expected_category
        exact_match = category_match and actual.subcategory == case.expected.subcategory
        category_correct += int(category_match)
        exact_correct += int(exact_match)

        key = (expected_category, case.expected.subcategory)
        stratum = strata[key]
        stratum[0] += 1
        stratum[1] += int(category_match)
        stratum[2] += int(exact_match)

        if not exact_match:
            failures.append(
                ClassificationFailure(
                    case_id=case.id,
                    expected_category=expected_category,
                    expected_subcategory=case.expected.subcategory,
                    actual_category=actual_category,
                    actual_subcategory=actual.subcategory,
                )
            )

    by_classification = [
        ClassificationStratum(
            category=category,
            subcategory=subcategory,
            total=counts[0],
            category_correct=counts[1],
            exact_correct=counts[2],
        )
        for (category, subcategory), counts in sorted(strata.items())
    ]
    return ClassificationEvaluationResult(
        total=len(cases),
        category_correct=category_correct,
        exact_correct=exact_correct,
        by_classification=by_classification,
        failures=failures,
    )


def evaluate(dataset_path: Path) -> tuple[int, int, int]:
    """Keep the original baseline API stable for tests and local tooling."""
    result = evaluate_cases(load_base_cases(dataset_path))
    return result.total, result.category_correct, result.exact_correct


def _print_human_result(
    result: ClassificationEvaluationResult,
    *,
    dataset_label: str,
) -> None:
    print(f"数据集: {dataset_label}")
    print(
        f"一级分类准确率: {result.category_correct}/{result.total} "
        f"({result.category_correct / result.total:.1%})"
    )
    print(
        f"精确分类准确率: {result.exact_correct}/{result.total} "
        f"({result.exact_correct / result.total:.1%})"
    )
    print("分类分层:")
    for row in result.by_classification:
        print(
            f"- {row.category}/{row.subcategory}: "
            f"一级 {row.category_correct}/{row.total}, 精确 {row.exact_correct}/{row.total}"
        )
    if result.failures:
        print("不一致样例:")
        for failure in result.failures:
            print(
                f"- {failure.case_id}: expected "
                f"{failure.expected_category}/{failure.expected_subcategory}, got "
                f"{failure.actual_category}/{failure.actual_subcategory}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the local M1 ticket analyzer")
    parser.add_argument("dataset", type=Path, nargs="?", default=DEFAULT_DATASET)
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="expand the base cases with the versioned robustness manifest",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    base_cases = load_base_cases(args.dataset)
    if args.pilot:
        manifest = load_manifest(args.manifest)
        cases: Sequence[ClassificationBenchmarkCase] = build_pilot_cases(base_cases, manifest)
        dataset_label = (
            f"{manifest.name} {manifest.version} — {len(base_cases)} 条基础样例 × "
            f"{len(manifest.variants)} 种受控表达 = {len(cases)} 条合成鲁棒性样例；"
            "不等同于独立真实工单"
        )
    else:
        cases = base_cases
        dataset_label = f"基础人工标注样例（{len(cases)} 条）"

    result = evaluate_cases(cases)
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        _print_human_result(result, dataset_label=dataset_label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
