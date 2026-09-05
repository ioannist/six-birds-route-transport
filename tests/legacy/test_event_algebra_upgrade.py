from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.discovery.event_algebra import (
    build_event_algebra_coverage,
    generate_context_event_context,
)
from sixbirds_event.discovery.models import (
    AcceptedContext,
    CandidateKey,
    ContextDiagnostics,
    DiscoveredAtomicOutcome,
    DiscoveredEventGenerationThresholds,
)
from sixbirds_event.provenance.models import PackageProvenance
from sixbirds_event.reporting.package_build_report import write_package_build_report
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


PICA_BUNDLE_PATH = Path(
    "experiments/contracts/pica/pilot/exp100_multiseed/pica-export-bundle.json"
)
DISCOVERED_FAMILY_PATH = Path(
    "experiments/instances/discovered/pica-exp100-multiseed-contexts/discovered-context-family.json"
)
SKELETON_PATH = Path(
    "experiments/instances/discovered/pica-exp100-multiseed-contexts/event-package-skeleton.json"
)


def _build_full_powerset(tmp_path: Path):
    return write_package_build_report(
        family_path=DISCOVERED_FAMILY_PATH,
        pica_bundle_path=PICA_BUNDLE_PATH,
        skeleton_path=SKELETON_PATH,
        category="search",
        label="build-package-pica-full",
        seed=0,
        timestamp="2026-03-27T03:00:00Z",
        root=tmp_path,
        event_thresholds=DiscoveredEventGenerationThresholds(
            event_basis_mode="singleton_plus_small_unions",
            event_algebra_mode="full_powerset",
            max_full_powerset_atom_count=6,
            max_union_size=2,
            min_event_support_count=1,
            min_event_support_fraction=0.0,
        ),
    )


def test_event_algebra_coverage_format_validates(tmp_path: Path) -> None:
    artifacts = _build_full_powerset(tmp_path)
    payload = json.loads(
        (tmp_path / artifacts.event_algebra_coverage_path).read_text(encoding="utf-8")
    )
    result = validate_payload(payload, kind=SchemaKind.EVENT_ALGEBRA_COVERAGE)
    assert result.ok


def test_full_powerset_build_on_committed_pica_contexts(tmp_path: Path) -> None:
    artifacts = _build_full_powerset(tmp_path)

    discovered_event_family = load_model(
        tmp_path / artifacts.discovered_event_family_path,
        kind=SchemaKind.DISCOVERED_EVENT_FAMILY,
    )
    coverage = load_model(
        tmp_path / artifacts.event_algebra_coverage_path,
        kind=SchemaKind.EVENT_ALGEBRA_COVERAGE,
    )
    candidates = load_model(
        tmp_path / artifacts.candidates_path,
        kind=SchemaKind.SHARED_EVENT_CANDIDATES,
    )
    event_package = load_model(
        tmp_path / artifacts.event_package_path,
        kind=SchemaKind.EVENT_PACKAGE_INSTANCE,
    )
    provenance = load_model(
        tmp_path / artifacts.provenance_path,
        kind=SchemaKind.PACKAGE_PROVENANCE,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert discovered_event_family is not None
    assert coverage is not None
    assert isinstance(event_package, EventPackageInstance)
    assert isinstance(provenance, PackageProvenance)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)

    expected_counts = {3: 8, 2: 4}
    assert all(context.event_algebra_complete for context in coverage.contexts)
    assert {
        context.atom_count: context.expected_full_event_count
        for context in coverage.contexts
    } == expected_counts
    assert {
        context.atom_count: context.generated_event_count
        for context in coverage.contexts
    } == expected_counts
    assert all(context.coverage_fraction == 1.0 for context in coverage.contexts)

    assert discovered_event_family.diagnostics_summary.total_event_count == 20
    assert discovered_event_family.diagnostics_summary.generated_empty_event_count == 3
    assert (
        discovered_event_family.diagnostics_summary.generated_singleton_event_count == 8
    )
    assert (
        discovered_event_family.diagnostics_summary.generated_proper_coarse_event_count
        == 6
    )
    assert discovered_event_family.diagnostics_summary.generated_full_event_count == 3
    assert discovered_event_family.diagnostics_summary.match_eligible_event_count == 14
    assert discovered_event_family.diagnostics_summary.accepted_coarse_event_count == 6

    proper_coarse_events = [
        event
        for context in discovered_event_family.contexts
        for event in context.events
        if event.accepted and event.event_kind == "proper_coarse"
    ]
    assert proper_coarse_events
    assert all(event.match_eligible for event in proper_coarse_events)

    empty_events = [
        event
        for context in discovered_event_family.contexts
        for event in context.events
        if event.event_kind == "empty"
    ]
    full_events = [
        event
        for context in discovered_event_family.contexts
        for event in context.events
        if event.event_kind == "full"
    ]
    assert len(empty_events) == 3
    assert len(full_events) == 3
    assert all(not event.match_eligible for event in empty_events + full_events)

    candidate_kinds = {row.left_event_kind for row in candidates.candidate_rows} | {
        row.right_event_kind for row in candidates.candidate_rows
    }
    assert "proper_coarse" in candidate_kinds
    assert "empty" not in {
        row.left_event_kind for row in candidates.candidate_rows if row.accepted
    }

    assert any(event.atom_ids == [] for event in event_package.events)
    assert any(
        len(event.atom_ids)
        == len(
            next(
                context.atoms
                for context in event_package.contexts
                if context.context_id == event.context_id
            )
        )
        for event in event_package.events
        if event.label == "full"
    )

    event_notes = {entry.event_id: entry.notes for entry in provenance.event_entries}
    assert any(
        "empty_event_from_retained_atom_set" in notes for notes in event_notes.values()
    )
    assert any(
        "full_event_from_retained_atom_set" in notes for notes in event_notes.values()
    )
    assert any(
        "coarse_event_union_of_retained_atoms" in notes
        for notes in event_notes.values()
    )

    summary = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    assert summary["event_algebra_mode"] == "full_powerset"
    assert summary["per_context_generated_event_counts"]
    assert summary["per_context_completeness_flags"]
    assert summary["generated_empty_full_event_count"] == 6
    assert summary["total_match_eligible_event_count"] == 14
    assert (
        summary["event_algebra_coverage_artifact"]
        == artifacts.event_algebra_coverage_path
    )

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "Event algebra mode" in note
    assert "Full-vs-truncated policy" in note
    assert "Completeness / coverage diagnostics" in note
    assert "Generated empty/full events" in note

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


def test_auto_mode_truncation_reports_incompleteness_honestly() -> None:
    context = AcceptedContext(
        context_id="ctx_large",
        candidate_key=CandidateKey(
            preparation_id="prep",
            protocol_id="protocol",
            lens_id="lens",
            step_index=0,
        ),
        atomic_outcomes=[
            DiscoveredAtomicOutcome(
                outcome_id=f"atom_{index}",
                observation_label=f"label_{index}",
                support_count=1,
                support_fraction=1 / 7,
            )
            for index in range(7)
        ],
        diagnostics=ContextDiagnostics(
            trajectory_count=7,
            retained_atom_count=7,
            coverage_fraction=1.0,
            empirical_entropy=1.0,
            batch_tv_max=0.0,
            row_count=7,
            support_by_retained_atom={f"atom_{index}": 1 for index in range(7)},
        ),
    )
    thresholds = DiscoveredEventGenerationThresholds(
        event_basis_mode="singleton_plus_small_unions",
        event_algebra_mode="auto",
        max_full_powerset_atom_count=6,
        max_union_size=2,
        min_event_support_count=1,
        min_event_support_fraction=0.0,
    )
    event_context = generate_context_event_context(
        context=context,
        thresholds=thresholds,
    )
    coverage = build_event_algebra_coverage(
        source_discovered_context_family_artifact=DISCOVERED_FAMILY_PATH.as_posix(),
        thresholds=thresholds,
        contexts=[event_context],
    )

    assert event_context.event_algebra_complete is False
    assert event_context.generation_mode_used == "conservative_truncation"
    assert event_context.expected_full_event_count == 128
    assert event_context.generated_event_count == 30
    assert (
        event_context.truncation_reason
        == "atom_count_exceeds_max_full_powerset_atom_count"
    )
    assert coverage.contexts[0].coverage_fraction == 30 / 128
    assert "incomplete_event_algebra" in coverage.contexts[0].flags


def test_cli_smoke_builds_full_powerset_package_from_committed_pica_inputs(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "build-event-package",
            DISCOVERED_FAMILY_PATH.as_posix(),
            "--pica-bundle",
            PICA_BUNDLE_PATH.as_posix(),
            "--skeleton",
            SKELETON_PATH.as_posix(),
            "--category",
            "search",
            "--label",
            "build-package-pica-full",
            "--event-algebra-mode",
            "full_powerset",
            "--timestamp",
            "2026-03-27T03:10:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "event_algebra_coverage=" in result.stdout
    assert "accepted_context_count=3" in result.stdout
    assert "total_generated_event_count=20" in result.stdout
    assert "generated_proper_coarse_event_count=6" in result.stdout
    assert "event_algebra_complete=True" in result.stdout
