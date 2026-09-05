from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.falsification.discovered_case import (
    run_discovered_case_falsification,
)
from sixbirds_event.falsification.models import (
    DiscoveredCaseFalsificationResult,
    FalsificationInterventionResult,
    RobustnessSubrunResult,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


FALSIFICATION = Path(
    "experiments/instances/discovered/triadic-branch-flagship/falsification.json"
)
CASE_ROOT = Path("experiments/instances/discovered/triadic-branch-flagship")


def test_falsification_input_format_validates() -> None:
    payload = json.loads(FALSIFICATION.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.DISCOVERED_CASE_FALSIFICATION)
    assert result.ok
    assert result.kind == SchemaKind.DISCOVERED_CASE_FALSIFICATION


def test_falsification_result_format_validates() -> None:
    result = DiscoveredCaseFalsificationResult(
        result_format_version="discovered-case-falsification-result.v1",
        falsification_id="demo_falsification",
        selected_case_id="demo_case",
        selected_source_refs={
            "event_package": "experiments/instances/discovered/triadic-branch-flagship/event-package.json",
            "package_provenance": "experiments/instances/discovered/triadic-branch-flagship/package-provenance.json",
            "raw_run": "experiments/instances/discovered/triadic-branch-flagship/raw-run.json",
            "discovered_context_family": "experiments/instances/discovered/triadic-branch-flagship/discovered-context-family.json",
            "shared_event_candidates": "experiments/instances/discovered/triadic-branch-flagship/shared-event-candidates.json",
            "source_config": "experiments/configs/substrates/triadic-branch.json",
            "selection": "experiments/instances/discovered/triadic-branch-flagship/selection.json",
        },
        provenance_classification="admissible",
        baseline_hard_only={
            "exact_structural_status": "feasible",
            "exact_feasible": True,
            "exact_respecting_tuple_count": 1,
            "gpd_str_status": "solved",
            "gpd_str": 0.0,
            "gpd_str_reason": None,
            "gpd_stat_status": "solved",
            "gpd_stat": 0.0,
            "gpd_stat_reason": None,
        },
        baseline_all_accepted_proposals={
            "exact_structural_status": "feasible",
            "exact_feasible": True,
            "exact_respecting_tuple_count": 1,
            "gpd_str_status": "solved",
            "gpd_str": 0.0,
            "gpd_str_reason": None,
            "gpd_stat_status": "solved",
            "gpd_stat": 0.0,
            "gpd_stat_reason": None,
        },
        sec_status="scored",
        sec_mean=0.0,
        ccd_status="not_applicable",
        ccd_overall=None,
        rm_status="not_applicable",
        rm_overall=None,
        hidden_record=FalsificationInterventionResult(
            applicability_status="not_applicable",
            outcome=None,
            reason="not_configured",
        ),
        flattening=FalsificationInterventionResult(
            applicability_status="not_applicable",
            outcome=None,
            reason="not_configured",
        ),
        robustness=RobustnessSubrunResult(
            applicability_status="completed",
            run_id="run_results_demo",
            summary_artifact="results/results/demo/robustness-summary.json",
            note_artifact="results/results/demo/robustness-note.md",
            threshold_crossings_artifact="results/results/demo/threshold-crossings.json",
            result_note_artifact="results/results/demo/result-note.json",
            manifest_artifact="results/results/demo/run-manifest.json",
            first_crossings={"gpd_stat": None, "sec": None, "ccd": None, "rm": None},
            notes=["demo"],
        ),
        final_verdict="no_baseline_obstruction",
        artifact_refs={
            "summary": "results/results/demo/falsification-summary.json",
            "note": "results/results/demo/falsification-note.md",
            "result_note": "results/results/demo/result-note.json",
            "manifest": "results/results/demo/run-manifest.json",
        },
        notes=["demo"],
    )
    assert result.final_verdict == "no_baseline_obstruction"


def test_selected_discovered_case_assets_exist() -> None:
    expected = [
        "event-package.json",
        "package-provenance.json",
        "shared-event-candidates.json",
        "discovered-context-family.json",
        "raw-run.json",
        "selection.json",
        "falsification.json",
    ]
    for name in expected:
        assert (CASE_ROOT / name).exists()


def test_committed_falsification_bundle_runs_end_to_end(tmp_path: Path) -> None:
    artifacts = run_discovered_case_falsification(
        falsification_path=FALSIFICATION.as_posix(),
        category="results",
        label="triadic-branch-falsification",
        seed=0,
        timestamp="2026-03-26T06:40:00Z",
        root=tmp_path,
    )

    summary = load_model(
        tmp_path / artifacts.summary_path,
        kind=SchemaKind.DISCOVERED_CASE_FALSIFICATION_RESULT,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(summary, DiscoveredCaseFalsificationResult)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert summary.selected_case_id == "triadic_branch_multilens_seed123"
    assert summary.provenance_classification == "admissible"
    assert summary.baseline_hard_only.exact_feasible is True
    assert summary.baseline_hard_only.gpd_str == 0.0
    assert summary.baseline_all_accepted_proposals.exact_feasible is True
    assert summary.baseline_all_accepted_proposals.gpd_str == 0.0
    assert summary.sec_status == "scored"
    assert summary.sec_mean == 0.0
    assert summary.hidden_record.applicability_status == "not_applicable"
    assert summary.flattening.applicability_status == "not_applicable"
    assert summary.robustness.applicability_status == "completed"
    assert summary.final_verdict == "no_baseline_obstruction"

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "Baseline evaluation modes" in note
    assert "no_baseline_obstruction" in note
    assert "RM is diagnostic-only" in note
    assert "not_applicable / unsolved / insufficient_data" in note

    assert (tmp_path / summary.artifact_refs["provenance_audit_summary"]).exists()
    assert (tmp_path / summary.artifact_refs["baseline_statistical_summary"]).exists()
    assert (tmp_path / summary.artifact_refs["candidate_statistical_summary"]).exists()
    assert (tmp_path / summary.artifact_refs["robustness_summary"]).exists()
    assert (tmp_path / summary.artifact_refs["robustness_threshold_crossings"]).exists()

    assert manifest.metadata["analysis_kind"] == "discovered_case_falsification"
    assert manifest.output_artifacts == {
        "note": "results/results/20260326T064000Z--triadic_branch_falsification/falsification-note.md",
        "result_note": "results/results/20260326T064000Z--triadic_branch_falsification/result-note.json",
        "summary": "results/results/20260326T064000Z--triadic_branch_falsification/falsification-summary.json",
    }


def test_cli_smoke_works_on_committed_falsification_input(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "falsification",
            "run-discovered-case",
            FALSIFICATION.as_posix(),
            "--category",
            "results",
            "--label",
            "triadic-branch-falsification",
            "--timestamp",
            "2026-03-26T06:41:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "summary=" in result.stdout
    assert "note=" in result.stdout
    assert "result_note=" in result.stdout
    assert "manifest=" in result.stdout
    assert "selected_case_id=triadic_branch_multilens_seed123" in result.stdout
    assert "baseline_candidate_exact_feasible=True" in result.stdout
    assert "baseline_candidate_gpd_str=0.0" in result.stdout
    assert "final_verdict=no_baseline_obstruction" in result.stdout
