from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.discovery.context_discovery import discover_context_family
from sixbirds_event.reporting.context_discovery_report import (
    write_context_discovery_report,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.substrates.engine import load_substrate_run
from sixbirds_event.validation import load_model, validate_payload


RAW_RUN_DIR = Path("experiments/instances/smoke/substrate-runs")
DETERMINISTIC_RUN = RAW_RUN_DIR / "deterministic-cycle-seed0.json"
STOCHASTIC_RUN = RAW_RUN_DIR / "stochastic-two-state-seed123.json"


def test_discovered_context_family_format_validates() -> None:
    run = load_substrate_run(STOCHASTIC_RUN)
    discovery = discover_context_family(
        [run],
        source_run_artifacts=[STOCHASTIC_RUN.as_posix()],
        family_id="family_demo",
    )

    result = validate_payload(
        discovery.family.model_dump(mode="json"),
        kind=SchemaKind.DISCOVERED_CONTEXT_FAMILY,
    )
    assert result.ok
    assert result.kind == SchemaKind.DISCOVERED_CONTEXT_FAMILY


def test_extractor_finds_nontrivial_context_family_on_stochastic_sample() -> None:
    run = load_substrate_run(STOCHASTIC_RUN)
    discovery = discover_context_family(
        [run],
        source_run_artifacts=[STOCHASTIC_RUN.as_posix()],
        family_id="family_demo",
    )
    family = discovery.family

    assert family.diagnostics_summary.accepted_context_count >= 2
    assert family.diagnostics_summary.rejected_candidate_count == 0
    assert family.metadata["observable_only"] is True
    first_context = family.accepted_contexts[0]
    assert first_context.candidate_key.preparation_id == "prep0"
    assert first_context.candidate_key.protocol_id == "flip6"
    assert first_context.candidate_key.lens_id in {"bias", "occupancy"}
    assert first_context.candidate_key.step_index >= 0
    assert len(first_context.atomic_outcomes) == 2
    assert {outcome.observation_label for outcome in first_context.atomic_outcomes} in (
        {"cold", "hot"},
        {"zero", "one"},
    )
    assert first_context.diagnostics.trajectory_count == 20
    assert first_context.diagnostics.coverage_fraction == 1.0
    assert first_context.diagnostics.batch_tv_max <= 0.35


def test_rejected_candidates_record_explicit_rejection_reasons() -> None:
    run = load_substrate_run(DETERMINISTIC_RUN)
    discovery = discover_context_family(
        [run],
        source_run_artifacts=[DETERMINISTIC_RUN.as_posix()],
        family_id="family_demo",
    )
    family = discovery.family

    assert family.diagnostics_summary.accepted_context_count == 0
    assert family.diagnostics_summary.rejected_candidate_count > 0
    assert discovery.event_package_skeleton is None
    reasons = {
        reason
        for candidate in family.rejected_candidates
        for reason in candidate.rejection_reasons
    }
    assert "trivial_context" in reasons
    assert "insufficient_trajectory_count" in reasons
    assert family.diagnostics_summary.rejection_reason_counts


def test_emitted_event_package_skeleton_is_schema_valid() -> None:
    run = load_substrate_run(STOCHASTIC_RUN)
    discovery = discover_context_family(
        [run],
        source_run_artifacts=[STOCHASTIC_RUN.as_posix()],
        family_id="family_demo",
    )

    assert discovery.event_package_skeleton is not None
    result = validate_payload(
        discovery.event_package_skeleton.model_dump(mode="json"),
        kind=SchemaKind.EVENT_PACKAGE_INSTANCE,
    )
    assert result.ok
    assert isinstance(result.model, EventPackageInstance)
    assert not result.model.equality_proposals
    assert result.model.instance_id == "inst_family_demo_skeleton"


def test_reporting_helper_writes_artifacts_and_manifest(tmp_path: Path) -> None:
    artifacts = write_context_discovery_report(
        run_paths=[STOCHASTIC_RUN.as_posix()],
        category="search",
        label="discover-stochastic",
        seed=123,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
    )

    family = load_model(
        tmp_path / artifacts.family_path,
        kind=SchemaKind.DISCOVERED_CONTEXT_FAMILY,
    )
    assert isinstance(family, type(artifacts.family))
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    assert isinstance(result_note, ResultNote)
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )
    assert isinstance(manifest, RunManifest)
    assert set(manifest.output_artifacts) == {
        "discovered_context_family",
        "note",
        "result_note",
        "event_package_skeleton",
    }
    assert manifest.metadata["analysis_kind"] == "context_discovery"
    assert manifest.metadata["observable_only"] is True
    assert artifacts.skeleton_path is not None

    skeleton = load_model(
        tmp_path / artifacts.skeleton_path,
        kind=SchemaKind.EVENT_PACKAGE_INSTANCE,
    )
    assert isinstance(skeleton, EventPackageInstance)

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "Accepted context count" in note
    assert "hidden-state IDs were not used" not in note


def test_cli_smoke_works_on_committed_sample_raw_run(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "discover-contexts",
            STOCHASTIC_RUN.as_posix(),
            "--category",
            "search",
            "--label",
            "discover-stochastic",
            "--timestamp",
            "2026-03-25T00:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "family=" in result.stdout
    assert "result_note=" in result.stdout
    assert "manifest=" in result.stdout
    assert "event_package_skeleton=" in result.stdout
    assert "accepted_context_count=12" in result.stdout

    stdout_lines = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in result.stdout.strip().splitlines()
        if "=" in line
    }
    family_path = tmp_path / stdout_lines["family"]
    payload = json.loads(family_path.read_text(encoding="utf-8"))
    assert payload["diagnostics_summary"]["accepted_context_count"] == 12
