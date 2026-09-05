from __future__ import annotations

from pathlib import Path

from sixbirds_event.hierarchy.models import (
    AxisClaimLadder,
    SharedMetricSurface,
    ThreeAxisSearchConfig,
    ThreeAxisSearchRow,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.validation import load_json_file, validate_file, validate_payload


EXAMPLES_ROOT = Path("experiments/contracts/hierarchy/examples")


def test_three_axis_search_config_validates() -> None:
    result = validate_file(
        EXAMPLES_ROOT / "three-axis-search-config.json",
        kind=SchemaKind.THREE_AXIS_SEARCH_CONFIG,
    )
    assert result.ok
    assert result.kind == SchemaKind.THREE_AXIS_SEARCH_CONFIG
    assert isinstance(result.model, ThreeAxisSearchConfig)
    assert result.model.axis == "packaging"


def test_three_axis_search_row_validates() -> None:
    result = validate_file(
        EXAMPLES_ROOT / "three-axis-search-row.json",
        kind=SchemaKind.THREE_AXIS_SEARCH_ROW,
    )
    assert result.ok
    assert result.kind == SchemaKind.THREE_AXIS_SEARCH_ROW
    assert isinstance(result.model, ThreeAxisSearchRow)
    assert result.model.claim_level_support == "package_conflict_tension"


def test_axis_claim_ladder_validates() -> None:
    result = validate_file(
        EXAMPLES_ROOT / "axis-claim-ladder.json",
        kind=SchemaKind.AXIS_CLAIM_LADDER,
    )
    assert result.ok
    assert result.kind == SchemaKind.AXIS_CLAIM_LADDER
    assert isinstance(result.model, AxisClaimLadder)
    assert len(result.model.levels) == 6


def test_shared_metric_surface_validates() -> None:
    result = validate_file(
        EXAMPLES_ROOT / "shared-metric-surface.json",
        kind=SchemaKind.SHARED_METRIC_SURFACE,
    )
    assert result.ok
    assert result.kind == SchemaKind.SHARED_METRIC_SURFACE
    assert isinstance(result.model, SharedMetricSurface)
    assert result.model.rm.status == "not_applicable"
    assert result.model.sec.status == "solved"


def test_example_files_validate_with_shared_layer() -> None:
    examples = {
        "three-axis-search-config.json": SchemaKind.THREE_AXIS_SEARCH_CONFIG,
        "three-axis-search-row.json": SchemaKind.THREE_AXIS_SEARCH_ROW,
        "axis-claim-ladder.json": SchemaKind.AXIS_CLAIM_LADDER,
        "shared-metric-surface.json": SchemaKind.SHARED_METRIC_SURFACE,
    }
    for name, kind in examples.items():
        result = validate_file(EXAMPLES_ROOT / name, kind=kind)
        assert result.ok, name


def test_packaging_axis_requires_packaging_varying_metadata() -> None:
    payload = load_json_file(EXAMPLES_ROOT / "three-axis-search-config.json")
    payload["axis_admissibility"]["varied_fields"] = ["projection_id"]
    result = validate_payload(payload, kind=SchemaKind.THREE_AXIS_SEARCH_CONFIG)
    assert not result.ok
    assert any("packaging axis must vary" in issue.message for issue in result.issues)


def test_mechanism_axis_cannot_claim_strong_obstruction_by_default() -> None:
    payload = load_json_file(EXAMPLES_ROOT / "three-axis-search-row.json")
    payload["axis"] = "mechanism"
    payload["fixed_field_summary"] = {
        "lens_family_id": "observable_row_record_algebra_v1",
        "packaging_policy_id": "default_packaging",
    }
    payload["varying_field_summary"] = {"mechanism_family_id": "exp120_discovery_grade"}
    payload["claim_level_support"] = "provenance_admissible_strong_obstruction"
    result = validate_payload(payload, kind=SchemaKind.THREE_AXIS_SEARCH_ROW)
    assert not result.ok
    assert any("exceeds default ceiling" in issue.message for issue in result.issues)


def test_validation_layer_exposes_new_schema_kinds() -> None:
    assert SchemaKind.THREE_AXIS_SEARCH_CONFIG.value == "three-axis-search-config"
    assert SchemaKind.THREE_AXIS_SEARCH_ROW.value == "three-axis-search-row"
    assert SchemaKind.AXIS_CLAIM_LADDER.value == "axis-claim-ladder"
    assert SchemaKind.SHARED_METRIC_SURFACE.value == "shared-metric-surface"
