from __future__ import annotations

from pathlib import Path

from sixbirds_event.hierarchy.models import (
    PackageConflictObject,
    PackageConflictRelation,
)
from sixbirds_event.schemas.common import SchemaKind, VERSION_FIELDS
from sixbirds_event.validation import load_model, validate_file


OBJECT_EXAMPLE = Path(
    "experiments/contracts/theory/examples/package-conflict-object.json"
)
RELATION_EXAMPLE = Path(
    "experiments/contracts/theory/examples/package-conflict-relation.json"
)
ADJUDICATION_PATH = Path(
    "experiments/instances/packaging-axis/th5_campaign/package-conflict-adjudication.json"
)


def test_package_conflict_object_format_validates() -> None:
    result = validate_file(OBJECT_EXAMPLE, kind=SchemaKind.PACKAGE_CONFLICT_OBJECT)
    assert result.ok
    assert isinstance(result.model, PackageConflictObject)


def test_package_conflict_relation_format_and_examples_validate() -> None:
    relation = load_model(RELATION_EXAMPLE, kind=SchemaKind.PACKAGE_CONFLICT_RELATION)
    assert isinstance(relation, PackageConflictRelation)
    assert relation.relation_level == "package_conflict_proper"
    assert relation.classification == "strict_extension_package_conflict"
    assert relation.obstruction_status == "none"


def test_packaging_axis_adjudication_validates() -> None:
    relation = load_model(ADJUDICATION_PATH, kind=SchemaKind.PACKAGE_CONFLICT_RELATION)
    assert isinstance(relation, PackageConflictRelation)
    assert relation.relation_level == "packaging_obstruction"
    assert relation.classification == "selector_branch_package_divergence"
    assert relation.obstruction_status == "accepted_proposal_obstruction"
    assert "selector_branch_divergence" in relation.caveat_flags


def test_shared_validation_layer_exposes_schema_kinds_cleanly() -> None:
    assert (
        VERSION_FIELDS[SchemaKind.PACKAGE_CONFLICT_OBJECT][1]
        == "package-conflict-object.v1"
    )
    assert (
        VERSION_FIELDS[SchemaKind.PACKAGE_CONFLICT_RELATION][1]
        == "package-conflict-relation.v1"
    )
