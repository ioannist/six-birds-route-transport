from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.robustness.noise_runner import run_noise_robustness_sweep
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


SWEEP = Path("experiments/configs/robustness/small-noise-sweep.json")


def test_noise_robustness_sweep_format_validates() -> None:
    payload = json.loads(SWEEP.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.NOISE_ROBUSTNESS_SWEEP)
    assert result.ok
    assert result.kind == SchemaKind.NOISE_ROBUSTNESS_SWEEP


def test_noise_robustness_runner_writes_tables_and_thresholds(tmp_path: Path) -> None:
    artifacts = run_noise_robustness_sweep(
        sweep_path=SWEEP.as_posix(),
        category="search",
        label="small-noise-sweep",
        seed=0,
        timestamp="2026-03-26T00:00:00Z",
        root=tmp_path,
    )

    table = load_model(
        tmp_path / artifacts.json_path,
        kind=SchemaKind.NOISE_ROBUSTNESS_TABLE,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert table.sweep_id == "small_noise_sweep"
    assert table.row_count == 10

    classical_rows = [
        row for row in table.rows if row.target_id == "classical_master_test"
    ]
    epistemic_rows = [
        row for row in table.rows if row.target_id == "epistemic_six_state"
    ]

    assert [row.noise_level for row in classical_rows] == [0.0, 0.05, 0.1, 0.2, 0.3]
    assert [row.noise_level for row in epistemic_rows] == [0.0, 0.05, 0.1, 0.2, 0.3]
    assert all(row.gpd_stat_status == "solved" for row in classical_rows)
    assert all(row.ccd_status == "scored" for row in classical_rows)
    assert all(row.sec_status == "scored" for row in classical_rows)
    assert all(row.rm_status == "scored" for row in classical_rows)
    assert all(row.rm_status == "not_applicable" for row in epistemic_rows)
    assert all(row.rm_overall is None for row in epistemic_rows)

    summary_payload = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    threshold_payload = json.loads(
        (tmp_path / artifacts.threshold_crossings_path).read_text(encoding="utf-8")
    )

    assert summary_payload["target_count"] == 2
    assert summary_payload["row_count"] == 10
    assert summary_payload["committed_target_types"] == ["benchmark"]
    assert summary_payload["availability_counts"]["rm_applicable_rows"] == 5
    assert summary_payload["status_counts"]["rm_status:not_applicable"] == 5

    assert (
        threshold_payload["targets"]["classical_master_test"]["gpd_stat"][
            "first_crossing_noise_level"
        ]
        == 0.1
    )
    assert (
        threshold_payload["targets"]["epistemic_six_state"]["rm"][
            "first_crossing_noise_level"
        ]
        is None
    )
    assert threshold_payload["targets"]["epistemic_six_state"]["rm"][
        "observed_statuses"
    ] == ["not_applicable"]

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "RM is diagnostic-only" in note
    assert "not_applicable" in note

    assert manifest.metadata["analysis_kind"] == "noise_robustness"
    assert manifest.output_artifacts == {
        "note": "results/search/20260326T000000Z--small_noise_sweep/robustness-note.md",
        "result_note": "results/search/20260326T000000Z--small_noise_sweep/result-note.json",
        "robustness_csv": "results/search/20260326T000000Z--small_noise_sweep/robustness.csv",
        "robustness_json": "results/search/20260326T000000Z--small_noise_sweep/robustness.json",
        "summary": "results/search/20260326T000000Z--small_noise_sweep/robustness-summary.json",
        "threshold_crossings": "results/search/20260326T000000Z--small_noise_sweep/threshold-crossings.json",
    }


def test_cli_smoke_works_on_committed_noise_sweep(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "robustness",
            "run-sweep",
            SWEEP.as_posix(),
            "--category",
            "search",
            "--label",
            "small-noise-sweep",
            "--timestamp",
            "2026-03-26T00:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "robustness_csv=" in result.stdout
    assert "robustness_json=" in result.stdout
    assert "threshold_crossings=" in result.stdout
    assert "summary=" in result.stdout
    assert "note=" in result.stdout
    assert "result_note=" in result.stdout
    assert "manifest=" in result.stdout
    assert "classical_master_test" in result.stdout
    assert "epistemic_six_state" in result.stdout
