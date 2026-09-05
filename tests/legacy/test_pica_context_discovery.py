from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sixbirds_event.discovery.pica_context_discovery import discover_pica_context_family
from sixbirds_event.pica_bridge.ingest import load_pica_export_bundle
from sixbirds_event.reporting.pica_context_discovery_report import (
    write_pica_context_discovery_report,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_file


CONFIG = Path("experiments/configs/pica/context-discovery-exp100-multiseed.json")
BUNDLE = Path(
    "experiments/contracts/pica/pilot/exp100_multiseed/pica-export-bundle.json"
)


def test_pica_context_discovery_config_validates() -> None:
    assert validate_file(CONFIG, kind=SchemaKind.PICA_CONTEXT_DISCOVERY).ok


def test_pica_context_extractor_runs_end_to_end_on_committed_bundle() -> None:
    resolved = load_pica_export_bundle(BUNDLE)
    config = load_model(CONFIG, kind=SchemaKind.PICA_CONTEXT_DISCOVERY)
    family_artifacts = discover_pica_context_family(
        resolved,
        config=config,
        family_id="family_test_pica_contexts",
        bundle_artifact=BUNDLE.as_posix(),
    )
    family = family_artifacts.family

    assert validate_file(BUNDLE, kind=SchemaKind.PICA_EXPORT_BUNDLE).ok
    assert validate_file(CONFIG, kind=SchemaKind.PICA_CONTEXT_DISCOVERY).ok

    assert family.diagnostics_summary.accepted_context_count >= 1
    assert any(
        context.diagnostics.retained_atom_count >= 2
        for context in family.accepted_contexts
    )
    distinct_resolutions = {
        context.candidate_key.resolution_id
        for context in family.accepted_contexts
        if context.candidate_key.resolution_id is not None
    }
    distinct_closures = {
        context.candidate_key.closure_id
        for context in family.accepted_contexts
        if context.candidate_key.closure_id is not None
    }
    assert len(distinct_resolutions) >= 2 or len(distinct_closures) >= 2
    assert all(
        context.source_metadata is not None for context in family.accepted_contexts
    )
    assert any(candidate.rejection_reasons for candidate in family.rejected_candidates)


def test_pica_context_discovery_report_writes_required_outputs(tmp_path: Path) -> None:
    report = write_pica_context_discovery_report(
        bundle_path=BUNDLE,
        category="search",
        label="pica-contexts",
        seed=0,
        timestamp="2026-03-27T02:00:00Z",
        root=tmp_path,
        config=load_model(CONFIG, kind=SchemaKind.PICA_CONTEXT_DISCOVERY),
    )

    family = load_model(
        tmp_path / report.family_path,
        kind=SchemaKind.DISCOVERED_CONTEXT_FAMILY,
    )
    assert family.source_mode == "pica_export_bundle"
    assert family.source_bundle_artifact == BUNDLE.as_posix()
    assert family.diagnostics_summary.accepted_context_count == 3
    assert family.diagnostics_summary.rejected_candidate_count == 2
    assert family.metadata["distinct_resolution_count"] >= 3
    assert family.metadata["distinct_closure_count"] >= 3

    note_path = tmp_path / report.note_path
    assert note_path.exists()
    note_text = note_path.read_text(encoding="utf-8")
    assert "Projection mode" in note_text
    assert "Accepted context count" in note_text

    if report.skeleton_path is not None:
        skeleton = load_model(
            tmp_path / report.skeleton_path,
            kind=SchemaKind.EVENT_PACKAGE_INSTANCE,
        )
        assert (
            len(skeleton.contexts) == family.diagnostics_summary.accepted_context_count
        )

    result_note = load_model(
        tmp_path / report.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    assert isinstance(result_note, ResultNote)
    manifest = load_model(
        tmp_path / report.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )
    assert isinstance(manifest, RunManifest)
    assert manifest.metadata["analysis_kind"] == "pica_context_discovery"
    assert "discovered_context_family" in manifest.output_artifacts


def test_cli_smoke_runs_pica_native_context_discovery(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pica",
            "discover-contexts",
            BUNDLE.as_posix(),
            "--category",
            "search",
            "--label",
            "pica-contexts-cli",
            "--timestamp",
            "2026-03-27T02:05:00Z",
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
    assert "accepted_context_count=3" in result.stdout
    assert "distinct_level_count=1" in result.stdout
    assert "distinct_resolution_count=3" in result.stdout
    assert "distinct_closure_count=3" in result.stdout
