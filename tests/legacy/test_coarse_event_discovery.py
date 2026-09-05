from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.discovery.models import DiscoveredEventGenerationThresholds
from sixbirds_event.reporting.package_build_report import write_package_build_report
from sixbirds_event.provenance.models import PackageProvenance
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


DISCOVERED_DIR = Path("experiments/instances/smoke/discovered-contexts")
RAW_RUN_DIR = Path("experiments/instances/smoke/substrate-runs")
TRIADIC_FAMILY_PATH = DISCOVERED_DIR / "triadic-branch-contexts.json"
TRIADIC_SKELETON_PATH = DISCOVERED_DIR / "triadic-branch-skeleton.json"
TRIADIC_RAW_RUN_PATH = RAW_RUN_DIR / "triadic-branch-seed123.json"


def test_discovered_event_family_format_validates(tmp_path: Path) -> None:
    artifacts = write_package_build_report(
        family_path=TRIADIC_FAMILY_PATH,
        run_paths=[TRIADIC_RAW_RUN_PATH],
        skeleton_path=TRIADIC_SKELETON_PATH,
        category="search",
        label="build-package-triadic",
        seed=123,
        timestamp="2026-03-26T03:10:00Z",
        root=tmp_path,
        event_thresholds=DiscoveredEventGenerationThresholds(
            event_basis_mode="singleton_plus_small_unions",
            max_union_size=2,
            min_event_support_count=3,
            min_event_support_fraction=0.1,
        ),
    )
    payload = json.loads(
        (tmp_path / artifacts.discovered_event_family_path).read_text(encoding="utf-8")
    )
    result = validate_payload(payload, kind=SchemaKind.DISCOVERED_EVENT_FAMILY)
    assert result.ok
    assert result.kind == SchemaKind.DISCOVERED_EVENT_FAMILY


def test_triadic_build_contains_proper_coarse_events_and_candidates(
    tmp_path: Path,
) -> None:
    artifacts = write_package_build_report(
        family_path=TRIADIC_FAMILY_PATH,
        run_paths=[TRIADIC_RAW_RUN_PATH],
        skeleton_path=TRIADIC_SKELETON_PATH,
        category="search",
        label="build-package-triadic",
        seed=123,
        timestamp="2026-03-26T03:20:00Z",
        root=tmp_path,
        event_thresholds=DiscoveredEventGenerationThresholds(
            event_basis_mode="singleton_plus_small_unions",
            max_union_size=2,
            min_event_support_count=3,
            min_event_support_fraction=0.1,
        ),
    )

    discovered_event_family = load_model(
        tmp_path / artifacts.discovered_event_family_path,
        kind=SchemaKind.DISCOVERED_EVENT_FAMILY,
    )
    event_package = load_model(
        tmp_path / artifacts.event_package_path,
        kind=SchemaKind.EVENT_PACKAGE_INSTANCE,
    )
    candidates = load_model(
        tmp_path / artifacts.candidates_path,
        kind=SchemaKind.SHARED_EVENT_CANDIDATES,
    )
    provenance = load_model(
        tmp_path / artifacts.provenance_path,
        kind=SchemaKind.PACKAGE_PROVENANCE,
    )
    coverage = load_model(
        tmp_path / artifacts.event_algebra_coverage_path,
        kind=SchemaKind.EVENT_ALGEBRA_COVERAGE,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert event_package is not None
    assert isinstance(event_package, EventPackageInstance)
    assert candidates is not None
    assert isinstance(provenance, PackageProvenance)
    assert coverage is not None
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert discovered_event_family is not None

    assert discovered_event_family.diagnostics_summary.accepted_coarse_event_count > 0
    accepted_coarse_events = [
        event
        for context in discovered_event_family.contexts
        for event in context.events
        if event.accepted and event.event_kind == "proper_coarse"
    ]
    assert accepted_coarse_events
    assert all(len(event.retained_atom_ids) > 1 for event in accepted_coarse_events)

    package_coarse_events = [
        event for event in event_package.events if len(event.atom_ids) > 1
    ]
    assert package_coarse_events

    accepted_rows = [row for row in candidates.candidate_rows if row.accepted]
    accepted_coarse_rows = [
        row
        for row in accepted_rows
        if row.left_is_proper_coarse or row.right_is_proper_coarse
    ]
    assert accepted_coarse_rows
    assert all(
        row.left_event_kind in {"singleton", "proper_coarse"} for row in accepted_rows
    )
    assert all(
        row.right_event_kind in {"singleton", "proper_coarse"} for row in accepted_rows
    )
    assert all(
        row.left_event_size == len(row.left_event_atom_ids) for row in accepted_rows
    )
    assert all(
        row.right_event_size == len(row.right_event_atom_ids) for row in accepted_rows
    )

    accepted_proposal_ids = {
        row.proposed_proposal_id for row in accepted_rows if row.proposed_proposal_id
    }
    assert accepted_proposal_ids == {
        proposal.proposal_id for proposal in event_package.equality_proposals
    }

    coarse_provenance_entries = [
        entry for entry in provenance.event_entries if len(entry.source_atom_ids) > 1
    ]
    assert coarse_provenance_entries
    assert all(entry.source_context_id for entry in coarse_provenance_entries)
    assert all(entry.source_atom_ids for entry in coarse_provenance_entries)
    assert any(
        "coarse_event_union_of_retained_atoms" in entry.notes
        for entry in coarse_provenance_entries
    )

    summary = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    assert summary["event_basis_mode"] == "singleton_plus_small_unions"
    assert (
        summary["event_algebra_coverage_artifact"]
        == artifacts.event_algebra_coverage_path
    )
    assert summary["accepted_coarse_event_count"] > 0
    assert summary["accepted_coarse_proposal_count"] > 0
    assert summary["package_provenance_artifact"] == artifacts.provenance_path

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "Event algebra mode" in note
    assert "Generated proper coarse events" in note
    assert "Accepted coarse proposals" in note
    assert "Package provenance validated" in note

    assert set(manifest.output_artifacts) == {
        "discovered_event_family",
        "event_algebra_coverage",
        "probe_indistinguishability_signatures",
        "shared_event_candidates",
        "event_package",
        "package_provenance",
        "package_build_summary",
        "note",
        "result_note",
    }


def test_cli_smoke_builds_coarse_event_package_from_committed_triadic_inputs(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "build-event-package",
            TRIADIC_FAMILY_PATH.as_posix(),
            "--raw-run",
            TRIADIC_RAW_RUN_PATH.as_posix(),
            "--skeleton",
            TRIADIC_SKELETON_PATH.as_posix(),
            "--category",
            "search",
            "--label",
            "build-package-triadic",
            "--event-basis",
            "singleton_plus_small_unions",
            "--max-union-size",
            "2",
            "--timestamp",
            "2026-03-26T03:30:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "discovered_event_family=" in result.stdout
    assert "shared_event_candidates=" in result.stdout
    assert "event_package=" in result.stdout
    assert "package_provenance=" in result.stdout
    assert "event_algebra_coverage=" in result.stdout
    assert "accepted_context_count=6" in result.stdout
    assert "total_generated_event_count=36" in result.stdout
    assert "generated_proper_coarse_event_count=18" in result.stdout
    assert "accepted_shared_event_proposal_count=90" in result.stdout
