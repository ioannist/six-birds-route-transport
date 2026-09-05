from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sixbirds_event.hierarchy.models import (
    BestEvidenceByAxis,
    ClaimStrengthRegistry,
    ThreeAxisHierarchyConfig,
    ThreeAxisHierarchyResults,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_file


COMMITTED_CONFIG = Path("experiments/configs/hierarchy/three-axis-hierarchy.json")


def test_three_axis_hierarchy_config_validates() -> None:
    result = validate_file(
        COMMITTED_CONFIG, kind=SchemaKind.THREE_AXIS_HIERARCHY_CONFIG
    )
    assert result.ok
    assert isinstance(result.model, ThreeAxisHierarchyConfig)
    assert result.model.hierarchy_id == "three_axis_hierarchy_th6"


def test_three_axis_hierarchy_build_runs_end_to_end(tmp_path: Path) -> None:
    from sixbirds_event.hierarchy.atlas import build_three_axis_hierarchy

    artifacts = build_three_axis_hierarchy(
        config_path=COMMITTED_CONFIG,
        category="results",
        label="three-axis-hierarchy-test",
        timestamp="2026-03-30T22:00:00Z",
        root=tmp_path,
    )

    summary = load_model(
        tmp_path / artifacts.summary_path,
        kind=SchemaKind.THREE_AXIS_HIERARCHY_RESULTS,
    )
    assert isinstance(summary, ThreeAxisHierarchyResults)
    assert summary.row_count == 3
    assert summary.strongest_current_axis == "packaging"
    assert summary.accepted_obstruction_exists_on_mechanism is True
    assert summary.accepted_obstruction_exists_on_lens is True
    assert summary.accepted_obstruction_exists_on_packaging is True

    row_map = {row.axis: row for row in summary.rows}
    assert row_map["mechanism"].axis_campaign_outcome_kind == "design_inadequate"
    assert row_map["mechanism"].best_witness_status == "accepted_proposal_obstruction"
    assert (
        row_map["mechanism"].claim_level_supported
        == "nontrivial_multicontext_structure"
    )
    assert "campaign_design_inadequate" in row_map["mechanism"].caveat_flags

    assert row_map["lens"].axis_campaign_outcome_kind == "finalized_axis_closure"
    assert row_map["lens"].best_witness_status == "accepted_proposal_obstruction"
    assert row_map["lens"].accepted_proposal_obstruction_count == 1
    assert row_map["lens"].candidate_subset_quotient_witness_count == 1
    assert (
        row_map["lens"].claim_level_supported
        == "provenance_admissible_strong_obstruction"
    )

    assert row_map["packaging"].axis_campaign_outcome_kind == "best_candidate"
    assert row_map["packaging"].best_witness_status == "accepted_proposal_obstruction"
    assert row_map["packaging"].accepted_proposal_obstruction_count == 1
    assert row_map["packaging"].candidate_subset_quotient_witness_count == 2
    assert (
        row_map["packaging"].claim_level_supported
        == "provenance_admissible_packaging_obstruction"
    )
    assert "selector_branch_divergence" in row_map["packaging"].caveat_flags

    registry = load_model(
        tmp_path / artifacts.claim_strength_registry_path,
        kind=SchemaKind.CLAIM_STRENGTH_REGISTRY,
    )
    assert isinstance(registry, ClaimStrengthRegistry)
    assert {entry.axis for entry in registry.entries} == {
        "mechanism",
        "lens",
        "packaging",
    }

    best_evidence = load_model(
        tmp_path / artifacts.best_evidence_by_axis_path,
        kind=SchemaKind.BEST_EVIDENCE_BY_AXIS,
    )
    assert isinstance(best_evidence, BestEvidenceByAxis)
    assert {entry.axis for entry in best_evidence.entries} == {
        "mechanism",
        "lens",
        "packaging",
    }

    note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    assert isinstance(note, ResultNote)
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )
    assert isinstance(manifest, RunManifest)

    output_dir = tmp_path / artifacts.run_dir
    assert (output_dir / "three-axis-hierarchy-summary.json").exists()
    assert (output_dir / "three-axis-hierarchy.csv").exists()
    assert (output_dir / "claim-strength-registry.json").exists()
    assert (output_dir / "best-evidence-by-axis.json").exists()
    assert (output_dir / "figure-axis-comparison.csv").exists()
    assert (output_dir / "figure-quotient-status.csv").exists()
    assert (output_dir / "figure-claim-strength.csv").exists()
    assert (output_dir / "table-axis-summary.json").exists()
    assert (output_dir / "table-best-evidence.json").exists()
    assert (output_dir / "three-axis-hierarchy-note.md").exists()


def test_cli_smoke_build_three_axis_hierarchy(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "hierarchy",
            "build-three-axis",
            COMMITTED_CONFIG.as_posix(),
            "--category",
            "results",
            "--label",
            "three-axis-hierarchy-cli",
            "--timestamp",
            "2026-03-30T22:05:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "strongest_axis=packaging" in result.stdout
    assert (
        "mechanism_campaign_outcome=design_inadequate_campaign_with_committed_witness"
        in result.stdout
    )
    assert (
        "lens_campaign_outcome=closed_with_cross_resolution_accepted_obstruction"
        in result.stdout
    )
    assert (
        "packaging_campaign_outcome=best_candidate_with_packaging_caveat"
        in result.stdout
    )
    assert "mechanism_claim_level=nontrivial_multicontext_structure" in result.stdout
    assert "lens_claim_level=provenance_admissible_strong_obstruction" in result.stdout
    assert (
        "packaging_claim_level=provenance_admissible_packaging_obstruction"
        in result.stdout
    )
    assert "summary=" in result.stdout
    assert "claim_strength_registry=" in result.stdout
    assert "best_evidence_by_axis=" in result.stdout
