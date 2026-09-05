from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.validation import (
    load_model,
    validate_file,
    validate_observation_trace,
)


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("kind", "fixture_name", "expected_attr"),
    [
        (
            SchemaKind.EVENT_PACKAGE_INSTANCE,
            "event-package-instance.json",
            "instance_id",
        ),
        (SchemaKind.OBSERVATION_TRACE, "observation-trace.json", "trace_id"),
        (SchemaKind.RUN_MANIFEST, "run-manifest.json", "run_id"),
        (SchemaKind.RESULT_NOTE, "result-note.json", "note_id"),
    ],
)
def test_valid_fixtures_validate(
    kind: SchemaKind, fixture_name: str, expected_attr: str
) -> None:
    path = FIXTURES / "valid" / fixture_name
    result = validate_file(path, kind=kind)
    assert result.ok
    assert result.kind == kind
    assert result.model is not None
    assert getattr(result.model, expected_attr)


@pytest.mark.parametrize(
    ("kind", "fixture_name", "expected_fragment"),
    [
        (
            SchemaKind.EVENT_PACKAGE_INSTANCE,
            "event-package-instance.json",
            "unknown context_id",
        ),
        (
            SchemaKind.OBSERVATION_TRACE,
            "observation-trace.json",
            "observations must not be empty",
        ),
        (
            SchemaKind.RUN_MANIFEST,
            "run-manifest.json",
            "must be a normalized repo-relative path",
        ),
        (SchemaKind.RESULT_NOTE, "result-note.json", "instance_ids must be unique"),
    ],
)
def test_invalid_fixtures_fail(
    kind: SchemaKind, fixture_name: str, expected_fragment: str
) -> None:
    path = FIXTURES / "invalid" / fixture_name
    result = validate_file(path, kind=kind)
    assert not result.ok
    messages = " | ".join(f"{issue.path}: {issue.message}" for issue in result.issues)
    assert expected_fragment in messages


def test_trace_linkage_against_instance() -> None:
    instance = load_model(
        FIXTURES / "valid" / "event-package-instance.json",
        kind=SchemaKind.EVENT_PACKAGE_INSTANCE,
    )
    trace = load_model(
        FIXTURES / "valid" / "observation-trace.json", kind=SchemaKind.OBSERVATION_TRACE
    )
    result = validate_observation_trace(trace.model_dump(), linked_instance=instance)
    assert result.ok


def test_cli_validate_success() -> None:
    path = FIXTURES / "valid" / "event-package-instance.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "validate",
            str(path),
            "--kind",
            "auto",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "valid event-package-instance" in result.stdout


def test_cli_validate_failure() -> None:
    path = FIXTURES / "invalid" / "run-manifest.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "validate",
            str(path),
            "--kind",
            "run-manifest",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "invalid run-manifest" in result.stderr
    assert "normalized repo-relative path" in result.stderr
