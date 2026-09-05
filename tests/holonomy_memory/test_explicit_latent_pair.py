from __future__ import annotations

import csv
from pathlib import Path

from holonomy_memory import run_benchmark
from holonomy_memory.benchmarks import load_benchmark_manifest_for_id
from holonomy_memory.schemas import BenchmarkResultManifest, ClassLabel
from holonomy_memory.validation import load_benchmark_result_manifest


def test_explicit_latent_pair_regression(tmp_path: Path) -> None:
    base_artifacts = run_benchmark(
        benchmark_id="latent_memory_base",
        seed=0,
        output_root=tmp_path,
    )
    refined_artifacts = run_benchmark(
        benchmark_id="latent_memory_refined",
        seed=0,
        output_root=tmp_path,
    )

    base_manifest = load_benchmark_result_manifest(base_artifacts.json_artifact_path)
    refined_manifest = load_benchmark_result_manifest(refined_artifacts.json_artifact_path)
    base_benchmark_manifest = load_benchmark_manifest_for_id("latent_memory_base")
    refined_benchmark_manifest = load_benchmark_manifest_for_id("latent_memory_refined")

    assert isinstance(base_manifest, BenchmarkResultManifest)
    assert isinstance(refined_manifest, BenchmarkResultManifest)
    assert [record.interface_id for record in base_manifest.records] == base_benchmark_manifest.interfaces_to_measure
    assert [record.interface_id for record in refined_manifest.records] == refined_benchmark_manifest.interfaces_to_measure

    explicit_latent_records = [
        record
        for record in base_manifest.records
        if record.witness_count > 0
        and record.discrepancy_metric_value > 0.0
        and record.class_label == ClassLabel.EXPLICIT_LATENT
        and record.currentization_status.value == "passed"
        and record.support_fixation_status.value != "failed"
        and (
            record.current_quotient_size < record.predictive_quotient_size
            or record.max_fiber_size > 1
        )
    ]
    assert explicit_latent_records

    for record in refined_manifest.records:
        assert record.witness_count == 0
        assert record.current_quotient_size == record.predictive_quotient_size
        assert record.discrepancy_metric_value == 0.0
        assert record.max_fiber_size == 1
        assert record.class_label == ClassLabel.FLAT

    assert base_artifacts.csv_artifact_path.is_file()
    assert refined_artifacts.csv_artifact_path.is_file()
    assert base_artifacts.ops_note_path.is_file()
    assert refined_artifacts.ops_note_path.is_file()

    with refined_artifacts.csv_artifact_path.open(newline="", encoding="utf-8") as handle:
        refined_rows = list(csv.DictReader(handle))
    assert refined_rows
    assert all(row["discrepancy_metric_value_exact"] == "0" for row in refined_rows)
