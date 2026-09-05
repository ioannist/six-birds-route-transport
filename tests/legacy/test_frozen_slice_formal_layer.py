from __future__ import annotations

from pathlib import Path

from sixbirds_event.hierarchy.models import (
    FrozenSliceComparisonRegime,
    FrozenSliceSupportObject,
)
from sixbirds_event.schemas.common import SchemaKind, VERSION_FIELDS
from sixbirds_event.validation import load_model, validate_file


SUPPORT_EXAMPLE = Path(
    "experiments/contracts/theory/examples/frozen-slice-support-object.json"
)
REGIME_EXAMPLE = Path(
    "experiments/contracts/theory/examples/frozen-slice-comparison-regime.json"
)


def test_frozen_slice_support_object_validates() -> None:
    result = validate_file(SUPPORT_EXAMPLE, kind=SchemaKind.FROZEN_SLICE_SUPPORT_OBJECT)
    assert result.ok
    assert isinstance(result.model, FrozenSliceSupportObject)
    assert (
        result.model.support_object_id == "exp104_p6_row_all_n64_seed0_shared_support"
    )


def test_frozen_slice_comparison_regime_validates() -> None:
    result = validate_file(
        REGIME_EXAMPLE, kind=SchemaKind.FROZEN_SLICE_COMPARISON_REGIME
    )
    assert result.ok
    assert isinstance(result.model, FrozenSliceComparisonRegime)
    assert result.model.theorem_object == "event_package"
    assert "lens" in result.model.supported_axes
    assert "packaging" in result.model.supported_axes


def test_example_files_and_schema_kinds_are_wired() -> None:
    support = load_model(
        SUPPORT_EXAMPLE,
        kind=SchemaKind.FROZEN_SLICE_SUPPORT_OBJECT,
    )
    regime = load_model(
        REGIME_EXAMPLE,
        kind=SchemaKind.FROZEN_SLICE_COMPARISON_REGIME,
    )

    assert isinstance(support, FrozenSliceSupportObject)
    assert isinstance(regime, FrozenSliceComparisonRegime)
    assert (
        VERSION_FIELDS[SchemaKind.FROZEN_SLICE_SUPPORT_OBJECT][1]
        == "frozen-slice-support-object.v1"
    )
    assert (
        VERSION_FIELDS[SchemaKind.FROZEN_SLICE_COMPARISON_REGIME][1]
        == "frozen-slice-comparison-regime.v1"
    )
