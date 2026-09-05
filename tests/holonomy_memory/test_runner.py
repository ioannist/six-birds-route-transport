from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from holonomy_memory import BenchmarkRunArtifacts, run_benchmark
from holonomy_memory.schemas import BenchmarkResultManifest, ClassLabel
from holonomy_memory.validation import load_benchmark_result_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_benchmark_writes_stable_programmatic_artifacts(tmp_path: Path) -> None:
    artifacts = run_benchmark(
        benchmark_id="flat_control",
        seed=0,
        output_root=tmp_path,
    )

    assert isinstance(artifacts, BenchmarkRunArtifacts)
    assert artifacts.json_artifact_path == tmp_path / "artifacts" / "results" / "flat_control.result.json"
    assert artifacts.csv_artifact_path == tmp_path / "artifacts" / "tables" / "flat_control.csv"
    assert artifacts.ops_note_path == tmp_path / "docs" / "results" / "flat_control.md"
    assert artifacts.json_artifact_path.is_file()
    assert artifacts.csv_artifact_path.is_file()
    assert artifacts.ops_note_path.is_file()

    manifest = load_benchmark_result_manifest(artifacts.json_artifact_path)
    assert isinstance(manifest, BenchmarkResultManifest)
    assert [record.interface_id for record in manifest.records] == ["mid"]
    assert manifest.records[0].witness_count == 0
    assert manifest.records[0].discrepancy_metric_value == 0.0
    assert manifest.records[0].class_label == ClassLabel.FLAT

    with artifacts.csv_artifact_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["interface_id"] == "mid"
    assert rows[0]["witness_count"] == "0"
    assert rows[0]["discrepancy_metric_value"] == "0.0"
    assert rows[0]["discrepancy_metric_value_exact"] == "0"
    assert rows[0]["class_label"] == "flat"

    note = artifacts.ops_note_path.read_text(encoding="utf-8")
    assert "flat_control" in note
    assert "mid" in note
    assert "artifacts/results/flat_control.result.json" in note
    assert "artifacts/tables/flat_control.csv" in note
    assert "docs/results/flat_control.md" in note


def test_cli_run_benchmark_smoke_writes_expected_paths(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holonomy_memory",
            "run-benchmark",
            "--benchmark-id",
            "flat_control",
            "--seed",
            "0",
            "--output-root",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "artifacts" / "results" / "flat_control.result.json").is_file()
    assert (tmp_path / "artifacts" / "tables" / "flat_control.csv").is_file()
    assert (tmp_path / "docs" / "results" / "flat_control.md").is_file()


def test_run_benchmark_overwrites_same_paths_on_repeat(tmp_path: Path) -> None:
    first = run_benchmark(
        benchmark_id="flat_control",
        seed=0,
        output_root=tmp_path,
    )
    second = run_benchmark(
        benchmark_id="flat_control",
        seed=0,
        output_root=tmp_path,
    )

    assert first.json_artifact_path == second.json_artifact_path
    assert first.csv_artifact_path == second.csv_artifact_path
    assert first.ops_note_path == second.ops_note_path
    assert load_benchmark_result_manifest(second.json_artifact_path).records[0].class_label == ClassLabel.FLAT
