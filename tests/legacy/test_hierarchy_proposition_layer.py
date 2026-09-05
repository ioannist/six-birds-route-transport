from __future__ import annotations

from pathlib import Path

from sixbirds_event.hierarchy.models import HierarchyPropositionIndex
from sixbirds_event.schemas.common import SchemaKind, VERSION_FIELDS
from sixbirds_event.validation import load_model, validate_file


INDEX_PATH = Path("experiments/instances/hierarchy/hierarchy-proposition-index.json")


def test_hierarchy_proposition_index_format_validates() -> None:
    result = validate_file(INDEX_PATH, kind=SchemaKind.HIERARCHY_PROPOSITION_INDEX)
    assert result.ok
    assert isinstance(result.model, HierarchyPropositionIndex)
    assert len(result.model.entries) == 4


def test_committed_hierarchy_proposition_index_validates() -> None:
    index = load_model(INDEX_PATH, kind=SchemaKind.HIERARCHY_PROPOSITION_INDEX)
    assert isinstance(index, HierarchyPropositionIndex)
    assert index.theorem_object_label == "event_package"
    assert {entry.kind for entry in index.entries} == {
        "formal_consequence",
        "non_implication",
        "adjudicated_rule",
    }


def test_shared_validation_layer_exposes_schema_kind_cleanly() -> None:
    assert (
        VERSION_FIELDS[SchemaKind.HIERARCHY_PROPOSITION_INDEX][1]
        == "hierarchy-proposition-index.v1"
    )
