from __future__ import annotations

import csv
from pathlib import Path

from holonomy_memory import run_benchmark
from holonomy_memory.benchmarks import load_benchmark_manifest_for_id
from holonomy_memory.schemas import BenchmarkResultManifest, ClassLabel
from holonomy_memory.validation import load_benchmark_result_manifest


def test_flattenable_pair_regression(tmp_path: Path) -> None:
    raw_artifacts = run_benchmark(
        benchmark_id="flattenable_raw",
        seed=0,
        output_root=tmp_path,
    )
    completed_artifacts = run_benchmark(
        benchmark_id="flattenable_completed",
        seed=0,
        output_root=tmp_path,
    )

    raw_manifest = load_benchmark_result_manifest(raw_artifacts.json_artifact_path)
    completed_manifest = load_benchmark_result_manifest(
        completed_artifacts.json_artifact_path
    )
    raw_benchmark_manifest = load_benchmark_manifest_for_id("flattenable_raw")
    completed_benchmark_manifest = load_benchmark_manifest_for_id(
        "flattenable_completed"
    )

    assert isinstance(raw_manifest, BenchmarkResultManifest)
    assert isinstance(completed_manifest, BenchmarkResultManifest)
    assert [record.interface_id for record in raw_manifest.records] == raw_benchmark_manifest.interfaces_to_measure
    assert [record.interface_id for record in completed_manifest.records] == completed_benchmark_manifest.interfaces_to_measure

    raw_flattenable_records = [
        record
        for record in raw_manifest.records
        if (
            record.witness_count > 0
            or record.discrepancy_metric_value > 0.0
            or record.loop_action_score_predictive_quotient > 0.0
        )
        and record.class_label == ClassLabel.FLATTENABLE
        and record.flattening_status.value == "passed"
        and record.support_fixation_status.value != "failed"
    ]
    assert raw_flattenable_records

    for record in completed_manifest.records:
        assert record.witness_count == 0
        assert record.current_quotient_size == record.predictive_quotient_size
        assert record.discrepancy_metric_value == 0.0
        assert record.loop_action_score_current_quotient == 0.0
        assert record.loop_action_score_predictive_quotient == 0.0
        assert record.class_label == ClassLabel.FLAT

    assert raw_artifacts.csv_artifact_path.is_file()
    assert completed_artifacts.csv_artifact_path.is_file()
    assert raw_artifacts.ops_note_path.is_file()
    assert completed_artifacts.ops_note_path.is_file()

    with completed_artifacts.csv_artifact_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        completed_rows = list(csv.DictReader(handle))
    assert completed_rows
    assert all(row["discrepancy_metric_value_exact"] == "0" for row in completed_rows)
