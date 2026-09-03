from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.evaluate_ai import (
    PilotClassificationManifest,
    build_pilot_cases,
    evaluate_cases,
    load_base_cases,
    load_manifest,
)

BASE_DATASET = Path("data/sample_tickets.json")
PILOT_MANIFEST = Path("data/pilot_classification_manifest.json")


def test_pilot_dataset_is_deterministic_and_preserves_labels() -> None:
    base_cases = load_base_cases(BASE_DATASET)
    manifest = load_manifest(PILOT_MANIFEST)

    first = build_pilot_cases(base_cases, manifest)
    second = build_pilot_cases(base_cases, manifest)

    assert len(base_cases) == 30
    assert len(manifest.variants) == 4
    assert len(first) == 120
    assert len({case.id for case in first}) == 120
    assert first == second
    for case in first:
        source = next(item for item in base_cases if item.id == case.source_id)
        assert case.expected == source.expected


def test_pilot_dataset_uses_placeholders_instead_of_direct_identifiers() -> None:
    cases = build_pilot_cases(load_base_cases(BASE_DATASET), load_manifest(PILOT_MANIFEST))
    redacted_cases = [case for case in cases if case.variant_id == "redacted-context"]

    assert len(redacted_cases) == 30
    assert all("[EMAIL]" in case.description for case in redacted_cases)
    assert all("[IP_ADDRESS]" in case.description for case in redacted_cases)
    assert all("example.com" not in case.description for case in redacted_cases)


def test_local_analyzer_handles_all_controlled_pilot_variants() -> None:
    cases = build_pilot_cases(load_base_cases(BASE_DATASET), load_manifest(PILOT_MANIFEST))

    result = evaluate_cases(cases)

    assert result.total == 120
    assert result.category_correct == 120
    assert result.exact_correct == 120
    assert result.failures == []
    assert sum(row.total for row in result.by_classification) == 120


def test_manifest_rejects_duplicate_variant_ids() -> None:
    with pytest.raises(ValidationError, match="variant id"):
        PilotClassificationManifest.model_validate(
            {
                "name": "duplicate-test",
                "version": "v1",
                "description": "test",
                "variants": [
                    {
                        "id": "same",
                        "title_template": "{title}",
                        "description_template": "{description}",
                    },
                    {
                        "id": "same",
                        "title_template": "{title}",
                        "description_template": "{description}",
                    },
                ],
            }
        )


def test_pilot_builder_rejects_unknown_template_placeholder() -> None:
    manifest = PilotClassificationManifest.model_validate(
        {
            "name": "bad-template-test",
            "version": "v1",
            "description": "test",
            "variants": [
                {
                    "id": "bad",
                    "title_template": "{unknown}",
                    "description_template": "{description}",
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="unknown placeholder"):
        build_pilot_cases(load_base_cases(BASE_DATASET), manifest)
