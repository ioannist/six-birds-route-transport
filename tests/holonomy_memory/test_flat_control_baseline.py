from __future__ import annotations

import csv
from pathlib import Path

from holonomy_memory import run_benchmark
from holonomy_memory.benchmarks import load_benchmark_manifest_for_id
from holonomy_memory.schemas import BenchmarkResultManifest, ClassLabel
from holonomy_memory.validation import load_benchmark_result_manifest


def test_flat_control_baseline_regression(tmp_path: Path) -> None:
    artifacts = run_benchmark(
        benchmark_id="flat_control",
        seed=0,
        output_root=tmp_path,
    )

    manifest = load_benchmark_result_manifest(artifacts.json_artifact_path)
    benchmark_manifest = load_benchmark_manifest_for_id("flat_control")

    assert isinstance(manifest, BenchmarkResultManifest)
    assert [record.interface_id for record in manifest.records] == benchmark_manifest.interfaces_to_measure
    assert artifacts.csv_artifact_path.is_file()
    assert artifacts.ops_note_path.is_file()

    for record in manifest.records:
        assert record.current_quotient_size == record.predictive_quotient_size
        assert record.witness_count == 0
        assert record.discrepancy_metric_value == 0.0
        assert record.loop_action_score_current_quotient == 0.0
        assert record.loop_action_score_predictive_quotient == 0.0
        assert record.class_label == ClassLabel.FLAT

    with artifacts.csv_artifact_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(manifest.records)
    assert all(row["discrepancy_metric_value_exact"] == "0" for row in rows)

    note = artifacts.ops_note_path.read_text(encoding="utf-8")
    assert "flat-control baseline is satisfied" in note
