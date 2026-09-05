from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.crosscheck.exact import run_exact_crosscheck
from sixbirds_event.crosscheck.models import (
    BlockingProxyResult,
    ExactCrosscheckResults,
    ExactCrosscheckRow,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


CONFIG = Path("experiments/configs/crosscheck/flagship-exact-crosscheck.json")


def test_exact_crosscheck_config_format_validates() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.EXACT_CROSSCHECK)
    assert result.ok
    assert result.kind == SchemaKind.EXACT_CROSSCHECK


def test_exact_crosscheck_result_format_validates() -> None:
    row = ExactCrosscheckRow(
        row_format_version="exact-crosscheck-row.v1",
        crosscheck_id="demo_crosscheck",
        target_id="demo_target",
        target_type="benchmark",
        package_path="experiments/instances/benchmarks/parity-context-witness/instance.json",
        evaluation_mode="hard_only",
        backend_label="scipy_milp_v1",
        crosscheck_status="solved",
        feasibility_status="infeasible",
        exact_respecting_tuple_count=0,
        exact_selected_tuple_count=None,
        model_artifact_path="results/results/demo/crosscheck-model.json",
        summary_artifact_path="results/results/demo/crosscheck-summary.json",
        note_artifact_path="results/results/demo/crosscheck-note.md",
        solution_artifact_path=None,
        blocking_proxy=BlockingProxyResult(
            status="solved",
            blocking_proposal_ids=["p_demo"],
            single_proposal_results=[],
            notes=["demo_proxy"],
        ),
        applicability_reason=None,
        notes=["demo_row"],
    )
    table = ExactCrosscheckResults(
        result_format_version="exact-crosscheck-result.v1",
        crosscheck_id="demo_crosscheck",
        row_count=1,
        rows=[row],
        metadata={"rule_version": "demo"},
    )
    assert table.row_count == 1


def test_committed_exact_crosscheck_runs_end_to_end(tmp_path: Path) -> None:
    artifacts = run_exact_crosscheck(
        config_path=CONFIG.as_posix(),
        category="results",
        label="exact-crosscheck",
        seed=0,
        timestamp="2026-03-26T08:00:00Z",
        root=tmp_path,
    )

    results = load_model(
        tmp_path / artifacts.results_path,
        kind=SchemaKind.EXACT_CROSSCHECK_RESULT,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(results, ExactCrosscheckResults)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert results.crosscheck_id == "flagship_exact_crosscheck"
    assert results.row_count == 2

    summary_payload = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    model_payload = json.loads(
        (tmp_path / artifacts.model_path).read_text(encoding="utf-8")
    )

    assert summary_payload["crosscheck_id"] == "flagship_exact_crosscheck"
    assert "semantic alignment" in note.lower()
    assert model_payload["evaluation_mode"] == "hard_only"
    assert model_payload["respecting_tuple_count"] == 0
    assert len(model_payload["enforced_proposal_ids"]) == 9

    rows = {row.target_id: row for row in results.rows}
    parity = rows["parity_context_witness_hard_only"]
    discovered = rows["discovered_strong_candidate_slot"]

    assert parity.crosscheck_status == "solved"
    assert parity.feasibility_status == "infeasible"
    assert parity.exact_respecting_tuple_count == 0
    assert parity.blocking_proxy.status == "solved"
    assert parity.blocking_proxy.blocking_proposal_ids
    assert len(parity.blocking_proxy.single_proposal_results) == 9
    assert all(
        item.feasibility_status == "feasible"
        for item in parity.blocking_proxy.single_proposal_results
    )
    assert parity.model_artifact_path is not None
    assert parity.summary_artifact_path is not None
    assert parity.note_artifact_path is not None
    assert (tmp_path / parity.model_artifact_path).exists()
    assert (tmp_path / parity.summary_artifact_path).exists()
    assert (tmp_path / parity.note_artifact_path).exists()

    assert discovered.crosscheck_status == "not_applicable"
    assert discovered.applicability_reason == "no_strong_discovered_candidate"
    assert discovered.feasibility_status is None

    assert artifacts.solution_path is None
    assert manifest.metadata["analysis_kind"] == "exact_crosscheck"
    assert set(manifest.output_artifacts) == {
        "results",
        "summary",
        "note",
        "result_note",
        "model",
    }


def test_cli_smoke_works_on_committed_exact_crosscheck(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "crosscheck",
            "run",
            CONFIG.as_posix(),
            "--category",
            "results",
            "--label",
            "exact-crosscheck",
            "--timestamp",
            "2026-03-26T08:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "target=parity_context_witness_hard_only" in result.stdout
    assert "status=solved" in result.stdout
    assert "target=discovered_strong_candidate_slot" in result.stdout
    assert "status=not_applicable" in result.stdout
