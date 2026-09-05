from __future__ import annotations

import csv
from pathlib import Path

from holonomy_memory import run_benchmark
from holonomy_memory.benchmarks import load_benchmark_manifest_for_id
from holonomy_memory.schemas import BenchmarkResultManifest, ClassLabel
from holonomy_memory.validation import load_benchmark_result_manifest


def test_protocol_trap_pair_regression(tmp_path: Path) -> None:
    naive_artifacts = run_benchmark(
        benchmark_id="protocol_trap_naive",
        seed=0,
        output_root=tmp_path,
    )
    honest_artifacts = run_benchmark(
        benchmark_id="protocol_trap_honest",
        seed=0,
        output_root=tmp_path,
    )

    naive_manifest = load_benchmark_result_manifest(naive_artifacts.json_artifact_path)
    honest_manifest = load_benchmark_result_manifest(honest_artifacts.json_artifact_path)
    naive_benchmark_manifest = load_benchmark_manifest_for_id("protocol_trap_naive")
    honest_benchmark_manifest = load_benchmark_manifest_for_id("protocol_trap_honest")

    assert isinstance(naive_manifest, BenchmarkResultManifest)
    assert isinstance(honest_manifest, BenchmarkResultManifest)
    assert [record.interface_id for record in naive_manifest.records] == naive_benchmark_manifest.interfaces_to_measure
    assert [record.interface_id for record in honest_manifest.records] == honest_benchmark_manifest.interfaces_to_measure

    naive_nonflat_artifact_records = [
        record
        for record in naive_manifest.records
        if (
            record.witness_count > 0
            or record.discrepancy_metric_value > 0.0
            or record.loop_action_score_predictive_quotient > 0.0
        )
        and record.class_label == ClassLabel.ARTIFACT_TRAP
        and record.support_fixation_status.value != "failed"
    ]
    assert naive_nonflat_artifact_records

    for record in honest_manifest.records:
        assert record.witness_count == 0
        assert record.discrepancy_metric_value == 0.0
        assert record.loop_action_score_current_quotient == 0.0
        assert record.loop_action_score_predictive_quotient == 0.0
        assert record.class_label == ClassLabel.FLAT

    assert naive_artifacts.csv_artifact_path.is_file()
    assert honest_artifacts.csv_artifact_path.is_file()
    assert naive_artifacts.ops_note_path.is_file()
    assert honest_artifacts.ops_note_path.is_file()

    with honest_artifacts.csv_artifact_path.open(newline="", encoding="utf-8") as handle:
        honest_rows = list(csv.DictReader(handle))
    assert honest_rows
    assert all(row["discrepancy_metric_value_exact"] == "0" for row in honest_rows)
