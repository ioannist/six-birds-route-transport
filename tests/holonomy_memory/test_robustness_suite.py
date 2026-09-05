from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from holonomy_memory import CORE_ROBUSTNESS_BENCHMARK_IDS, run_core_robustness_suite


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_core_robustness_suite_meets_required_thresholds(tmp_path: Path) -> None:
    artifacts = run_core_robustness_suite(seed=0, output_root=tmp_path)
    summary = artifacts.suite_summary

    assert summary is not None
    assert summary.overall_pass is True
    assert summary.json_artifact_path.is_file()
    assert summary.csv_artifact_path.is_file()
    assert summary.ops_note_path.is_file()
    assert tuple(item.benchmark_id for item in summary.benchmark_summaries) == (
        CORE_ROBUSTNESS_BENCHMARK_IDS
    )

    thresholds = {
        "flat_control": 0.95,
        "protocol_trap_honest": 0.95,
        "flattenable_completed": 0.80,
        "latent_memory_base": 0.80,
        "latent_memory_refined": 0.80,
        "dissipative_memory": 0.80,
        "memory_wheel": 0.80,
    }

    for benchmark_summary in summary.benchmark_summaries:
        assert benchmark_summary.json_artifact_path.is_file()
        assert benchmark_summary.csv_artifact_path.is_file()
        assert benchmark_summary.ops_note_path.is_file()
        assert float(benchmark_summary.survival_fraction) >= thresholds[
            benchmark_summary.benchmark_id
        ]
        assert benchmark_summary.meets_threshold is True

    suite_payload = json.loads(summary.json_artifact_path.read_text(encoding="utf-8"))
    assert suite_payload["overall_pass"] is True
    assert [row["benchmark_id"] for row in suite_payload["benchmarks"]] == list(
        CORE_ROBUSTNESS_BENCHMARK_IDS
    )

    benchmark_payloads = {
        benchmark_id: json.loads(
            (
                tmp_path
                / "artifacts"
                / "results"
                / "robustness"
                / f"{benchmark_id}.robustness.json"
            ).read_text(encoding="utf-8")
        )
        for benchmark_id in CORE_ROBUSTNESS_BENCHMARK_IDS
    }

    memory_wheel_loop_retention = sum(
        1
        for trial in benchmark_payloads["memory_wheel"]["trials"]
        if any(
            interface["predictive_loop_score"] > 0.0
            for interface in trial["interface_metrics"]
        )
    )
    assert memory_wheel_loop_retention > 0

    dissipative_collapse_trials = sum(
        1
        for trial in benchmark_payloads["dissipative_memory"]["trials"]
        if trial["transport_collapse_persisted"] is True
    )
    assert dissipative_collapse_trials > 0

    flat_control_witness_failures = sum(
        1
        for trial in benchmark_payloads["flat_control"]["trials"]
        if any(interface["witness_count"] > 0 for interface in trial["interface_metrics"])
    )
    assert flat_control_witness_failures <= 1


def test_cli_run_robustness_smoke_writes_expected_paths(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holonomy_memory",
            "run-robustness",
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
    assert (
        tmp_path / "artifacts" / "results" / "robustness" / "flat_control.robustness.json"
    ).is_file()
    assert (tmp_path / "artifacts" / "tables" / "robustness_flat_control.csv").is_file()
    assert (tmp_path / "docs" / "results" / "flat_control.robustness.md").is_file()
