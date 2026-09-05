from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sixbirds_event.falsification.flagship_bundle import run_flagship_control_bundle
from sixbirds_event.falsification.models import (
    FlagshipControlBundle,
    FlagshipControlResult,
)
from sixbirds_event.schemas.common import SchemaKind, VERSION_FIELDS
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_file


BUNDLE_CONFIG = Path("experiments/configs/falsification/flagship-control-bundle.json")


def test_flagship_control_bundle_format_validates() -> None:
    result = validate_file(BUNDLE_CONFIG, kind=SchemaKind.FLAGSHIP_CONTROL_BUNDLE)
    assert result.ok
    assert isinstance(result.model, FlagshipControlBundle)


def test_flagship_control_result_format_validates() -> None:
    result = FlagshipControlResult(
        result_format_version="flagship-control-result.v1",
        bundle_id="demo_bundle",
        cases=[
            {
                "case_id": "demo_packaging_case",
                "case_type": "packaging_flagship",
                "source_refs": {
                    "discovered_context_family_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/discovered-context-family.json",
                    "event_package_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/event-package.json",
                    "package_provenance_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/package-provenance.json",
                    "shared_event_candidates_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/shared-event-candidates.json",
                    "quotient_feasibility_summary_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/quotient-feasibility-summary.json",
                    "source_pica_bundle_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/pica-export-bundle.json",
                },
                "hidden_record": {
                    "applicability_status": "not_applicable",
                    "verdict": "not_applicable",
                    "reason": "demo",
                    "pre_control": {
                        "witness_classification": "accepted_proposal_obstruction",
                        "exact_feasible": False,
                        "survivor_count": 1,
                        "failure_reason": "coverage_failure",
                        "quotient_class_count": 2,
                        "uncovered_atom_count": 1,
                        "gpd_str": {
                            "status": "solved",
                            "value": 1.0,
                            "reason": None,
                        },
                        "gpd_stat": {
                            "status": "solved",
                            "value": 0.5,
                            "reason": None,
                        },
                    },
                    "artifact_refs": {},
                    "first_crossings": {},
                    "notes": [],
                },
                "flattening": {
                    "applicability_status": "not_applicable",
                    "verdict": "not_applicable",
                    "reason": "demo",
                    "pre_control": {
                        "witness_classification": "accepted_proposal_obstruction",
                        "exact_feasible": False,
                        "survivor_count": 1,
                        "failure_reason": "coverage_failure",
                        "quotient_class_count": 2,
                        "uncovered_atom_count": 1,
                        "gpd_str": {
                            "status": "solved",
                            "value": 1.0,
                            "reason": None,
                        },
                        "gpd_stat": {
                            "status": "solved",
                            "value": 0.5,
                            "reason": None,
                        },
                    },
                    "artifact_refs": {},
                    "first_crossings": {},
                    "notes": [],
                },
                "robustness": {
                    "applicability_status": "completed",
                    "verdict": "survived",
                    "reason": None,
                    "pre_control": {
                        "witness_classification": "accepted_proposal_obstruction",
                        "exact_feasible": False,
                        "survivor_count": 1,
                        "failure_reason": "coverage_failure",
                        "quotient_class_count": 2,
                        "uncovered_atom_count": 1,
                        "gpd_str": {
                            "status": "solved",
                            "value": 1.0,
                            "reason": None,
                        },
                        "gpd_stat": {
                            "status": "solved",
                            "value": 0.5,
                            "reason": None,
                        },
                    },
                    "post_control": {
                        "witness_classification": "accepted_proposal_obstruction",
                        "exact_feasible": False,
                        "survivor_count": 1,
                        "failure_reason": "coverage_failure",
                        "quotient_class_count": 2,
                        "uncovered_atom_count": 1,
                        "gpd_str": {
                            "status": "solved",
                            "value": 1.0,
                            "reason": None,
                        },
                        "gpd_stat": {
                            "status": "solved",
                            "value": 0.8,
                            "reason": None,
                        },
                    },
                    "run_id": "run_results_demo_flagship_bundle",
                    "artifact_refs": {
                        "summary": "results/results/demo/robustness-summary.json",
                        "manifest": "results/results/demo/run-manifest.json",
                    },
                    "first_crossings": {
                        "gpd_stat": {"first_crossing_noise_level": 0.05}
                    },
                    "notes": ["demo"],
                },
                "final_verdict": "survived",
                "artifact_refs": {
                    "quotient_feasibility_summary": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/quotient-feasibility-summary.json"
                },
                "notes": ["demo"],
            }
        ],
        overall_bundle_verdict="all_applicable_flagships_survived",
        artifact_refs={
            "summary": "results/results/demo/flagship-control-summary.json",
            "note": "results/results/demo/flagship-control-note.md",
            "table_json": "results/results/demo/flagship-control-table.json",
            "table_csv": "results/results/demo/flagship-control-table.csv",
            "result_note": "results/results/demo/result-note.json",
            "manifest": "results/results/demo/run-manifest.json",
        },
        notes=["demo"],
    )
    assert result.overall_bundle_verdict == "all_applicable_flagships_survived"


def test_committed_flagship_control_bundle_runs_end_to_end(tmp_path: Path) -> None:
    artifacts = run_flagship_control_bundle(
        bundle_path=BUNDLE_CONFIG.as_posix(),
        category="results",
        label="flagship-control-bundle",
        seed=0,
        timestamp="2026-03-31T03:00:00Z",
        root=tmp_path,
    )

    summary = load_model(
        tmp_path / artifacts.summary_path,
        kind=SchemaKind.FLAGSHIP_CONTROL_RESULT,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(summary, FlagshipControlResult)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert summary.bundle_id == "flagship_control_bundle_t50"
    assert summary.overall_bundle_verdict == "all_applicable_flagships_survived"

    cases = {case.case_id: case for case in summary.cases}
    assert (
        cases["mechanism_exp104_p6_row_all_n64_seed0"].final_verdict == "not_applicable"
    )
    assert (
        cases["lens_exp104_p6_row_all_n64_cross_res_k4_k20"].final_verdict == "survived"
    )
    assert cases["packaging_cross_res_k4_k20"].final_verdict == "survived"
    assert (
        cases["lens_exp104_p6_row_all_n64_cross_res_k4_k20"].robustness.post_control
        is not None
    )
    assert (
        cases[
            "lens_exp104_p6_row_all_n64_cross_res_k4_k20"
        ].robustness.post_control.witness_classification
        == "accepted_proposal_obstruction"
    )
    assert cases["packaging_cross_res_k4_k20"].robustness.post_control is not None
    assert (
        cases[
            "packaging_cross_res_k4_k20"
        ].robustness.post_control.witness_classification
        == "accepted_proposal_obstruction"
    )

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "Post-control decisive evaluation remains quotient-backed." in note
    assert "not_applicable" in note
    assert "all_applicable_flagships_survived" in note

    assert (tmp_path / artifacts.table_json_path).exists()
    assert (tmp_path / artifacts.table_csv_path).exists()
    assert manifest.metadata["analysis_kind"] == "flagship_control_bundle"


def test_cli_smoke_works_on_committed_bundle(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "falsification",
            "run-flagship-bundle",
            BUNDLE_CONFIG.as_posix(),
            "--category",
            "results",
            "--label",
            "flagship-control-bundle",
            "--timestamp",
            "2026-03-31T03:01:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert (
        "mechanism_exp104_p6_row_all_n64_seed0_final_verdict=not_applicable"
        in result.stdout
    )
    assert (
        "lens_exp104_p6_row_all_n64_cross_res_k4_k20_final_verdict=survived"
        in result.stdout
    )
    assert "packaging_cross_res_k4_k20_final_verdict=survived" in result.stdout
    assert "overall_bundle_verdict=all_applicable_flagships_survived" in result.stdout
    assert "summary=" in result.stdout
    assert "table_json=" in result.stdout
    assert "table_csv=" in result.stdout
    assert "result_note=" in result.stdout
    assert "manifest=" in result.stdout


def test_shared_validation_layer_exposes_schema_kinds_cleanly() -> None:
    assert (
        VERSION_FIELDS[SchemaKind.FLAGSHIP_CONTROL_BUNDLE][1]
        == "flagship-control-bundle.v1"
    )
    assert (
        VERSION_FIELDS[SchemaKind.FLAGSHIP_CONTROL_RESULT][1]
        == "flagship-control-result.v1"
    )
