from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.discovery.shared_event_inference import (
    build_event_package_from_candidates,
    infer_shared_event_candidates,
    load_discovered_context_family,
    load_discovered_event_package_skeleton,
    load_substrate_run_files,
)
from sixbirds_event.reporting.package_build_report import write_package_build_report
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.provenance.models import PackageProvenance
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


DISCOVERED_DIR = Path("experiments/instances/smoke/discovered-contexts")
RAW_RUN_DIR = Path("experiments/instances/smoke/substrate-runs")
FAMILY_PATH = DISCOVERED_DIR / "stochastic-two-state-contexts.json"
SKELETON_PATH = DISCOVERED_DIR / "stochastic-two-state-skeleton.json"
RAW_RUN_PATH = RAW_RUN_DIR / "stochastic-two-state-seed123.json"


def test_shared_event_candidates_format_validates() -> None:
    family = load_discovered_context_family(FAMILY_PATH)
    skeleton = load_discovered_event_package_skeleton(SKELETON_PATH)
    runs = load_substrate_run_files([RAW_RUN_PATH])
    candidates = infer_shared_event_candidates(
        family,
        runs,
        inference_id="infer_demo",
        source_discovered_context_family_artifact=FAMILY_PATH.as_posix(),
        source_run_artifacts=[RAW_RUN_PATH.as_posix()],
        skeleton=skeleton,
    )

    result = validate_payload(
        candidates.model_dump(mode="json"),
        kind=SchemaKind.SHARED_EVENT_CANDIDATES,
    )
    assert result.ok
    assert result.kind == SchemaKind.SHARED_EVENT_CANDIDATES


def test_discovered_context_family_builds_valid_event_package() -> None:
    family = load_discovered_context_family(FAMILY_PATH)
    skeleton = load_discovered_event_package_skeleton(SKELETON_PATH)
    runs = load_substrate_run_files([RAW_RUN_PATH])
    candidates = infer_shared_event_candidates(
        family,
        runs,
        inference_id="infer_demo",
        source_discovered_context_family_artifact=FAMILY_PATH.as_posix(),
        source_run_artifacts=[RAW_RUN_PATH.as_posix()],
        skeleton=skeleton,
    )
    event_package = build_event_package_from_candidates(
        family,
        candidates,
        skeleton=skeleton,
        created_at="2026-03-25T00:00:00Z",
    )

    assert candidates.diagnostics_summary.accepted_candidate_pair_count > 0
    assert candidates.diagnostics_summary.rejected_candidate_pair_count > 0
    accepted_rows = [row for row in candidates.candidate_rows if row.accepted]
    rejected_rows = [row for row in candidates.candidate_rows if not row.accepted]
    assert accepted_rows
    assert rejected_rows
    assert all(row.rejection_reasons for row in rejected_rows)

    result = validate_payload(
        event_package.model_dump(mode="json"),
        kind=SchemaKind.EVENT_PACKAGE_INSTANCE,
    )
    assert result.ok
    assert isinstance(result.model, EventPackageInstance)

    accepted_proposal_ids = [
        row.proposed_proposal_id for row in accepted_rows if row.proposed_proposal_id
    ]
    assert accepted_proposal_ids == [
        proposal.proposal_id for proposal in event_package.equality_proposals
    ]
    assert len(event_package.weights) == len(event_package.equality_proposals)


def test_reporting_helper_writes_artifacts_and_manifest(tmp_path: Path) -> None:
    artifacts = write_package_build_report(
        family_path=FAMILY_PATH,
        run_paths=[RAW_RUN_PATH],
        skeleton_path=SKELETON_PATH,
        category="search",
        label="build-package-stochastic",
        seed=123,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
    )

    discovered_event_family = load_model(
        tmp_path / artifacts.discovered_event_family_path,
        kind=SchemaKind.DISCOVERED_EVENT_FAMILY,
    )
    assert discovered_event_family is not None
    candidates = load_model(
        tmp_path / artifacts.candidates_path,
        kind=SchemaKind.SHARED_EVENT_CANDIDATES,
    )
    assert candidates is not None
    event_package = load_model(
        tmp_path / artifacts.event_package_path,
        kind=SchemaKind.EVENT_PACKAGE_INSTANCE,
    )
    assert isinstance(event_package, EventPackageInstance)
    provenance = load_model(
        tmp_path / artifacts.provenance_path,
        kind=SchemaKind.PACKAGE_PROVENANCE,
    )
    assert isinstance(provenance, PackageProvenance)
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
    assert manifest.metadata["analysis_kind"] == "package_build"
    assert manifest.metadata["observable_only"] is True

    summary = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    assert summary["inference_mode"] == "structural_primary"
    assert summary["structurally_valid_candidate_pair_count"] > 0
    assert summary["event_basis_mode"] == "singleton_only"
    assert summary["accepted_singleton_event_count"] == 24
    assert summary["accepted_coarse_event_count"] == 0
    assert summary["accepted_candidate_pair_count"] > 0
    assert (
        summary["discovered_event_family_artifact"]
        == artifacts.discovered_event_family_path
    )
    assert summary["built_event_package_artifact"] == artifacts.event_package_path
    assert summary["package_provenance_artifact"] == artifacts.provenance_path
    assert summary["weight_mapping_rule"] == "weight = max(0.1, 1 - approx_score)"

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "Event algebra mode" in note
    assert "Structural rule" in note
    assert "Threshold configuration" in note
    assert "Weight / proposal policy" in note
    assert "Built package validation" in note
    assert "Package provenance" in note


def test_cli_smoke_builds_package_from_committed_inputs(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "build-event-package",
            FAMILY_PATH.as_posix(),
            "--raw-run",
            RAW_RUN_PATH.as_posix(),
            "--skeleton",
            SKELETON_PATH.as_posix(),
            "--category",
            "search",
            "--label",
            "build-package-stochastic",
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
    assert "discovered_event_family=" in result.stdout
    assert "shared_event_candidates=" in result.stdout
    assert "event_package=" in result.stdout
    assert "package_provenance=" in result.stdout
    assert "event_algebra_coverage=" in result.stdout
    assert "probe_indistinguishability_signatures=" in result.stdout
    assert "summary=" in result.stdout
    assert "manifest=" in result.stdout
    assert "accepted_context_count=12" in result.stdout
    assert "total_generated_event_count=24" in result.stdout
    assert "generated_proper_coarse_event_count=0" in result.stdout
    assert "structurally_valid_candidate_count=" in result.stdout

    stdout_lines = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in result.stdout.strip().splitlines()
        if "=" in line
    }
    discovered_event_family_path = tmp_path / stdout_lines["discovered_event_family"]
    package_path = tmp_path / stdout_lines["event_package"]
    provenance_path = tmp_path / stdout_lines["package_provenance"]
    discovered_event_family_payload = json.loads(
        discovered_event_family_path.read_text(encoding="utf-8")
    )
    assert (
        discovered_event_family_payload["event_family_format_version"]
        == "discovered-event-family.v1"
    )
    payload = json.loads(package_path.read_text(encoding="utf-8"))
    assert payload["equality_proposals"]
    provenance_payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance_payload["provenance_format_version"] == "package-provenance.v1"
