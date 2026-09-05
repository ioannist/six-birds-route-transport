from __future__ import annotations

import csv
from pathlib import Path

from holonomy_memory import run_benchmark
from holonomy_memory.analysis import compute_predictive_transport_map
from holonomy_memory.benchmarks import load_benchmark_manifest_for_id, resolve_repo_relative_path
from holonomy_memory.core import load_route_transport_package
from holonomy_memory.schemas import BenchmarkResultManifest, ClassLabel
from holonomy_memory.validation import load_benchmark_result_manifest


def test_dissipative_memory_regression(tmp_path: Path) -> None:
    artifacts = run_benchmark(
        benchmark_id="dissipative_memory",
        seed=0,
        output_root=tmp_path,
    )
    manifest = load_benchmark_result_manifest(artifacts.json_artifact_path)
    benchmark_manifest = load_benchmark_manifest_for_id("dissipative_memory")

    assert isinstance(manifest, BenchmarkResultManifest)
    assert [record.interface_id for record in manifest.records] == benchmark_manifest.interfaces_to_measure
    assert len(manifest.records) >= 2

    earliest_record = manifest.records[0]
    later_records = manifest.records[1:]

    assert earliest_record.witness_count > 0
    assert earliest_record.discrepancy_metric_value > 0.0
    assert earliest_record.class_label == ClassLabel.DISSIPATIVE
    assert (
        earliest_record.current_quotient_size < earliest_record.predictive_quotient_size
        or earliest_record.max_fiber_size > 1
    )

    collapsed_later_records = [
        record
        for record in later_records
        if record.witness_count == 0
        and record.discrepancy_metric_value == 0.0
        and record.current_quotient_size == record.predictive_quotient_size
        and record.max_fiber_size == 1
        and record.class_label == ClassLabel.FLAT
    ]
    assert collapsed_later_records

    package = load_route_transport_package(
        resolve_repo_relative_path(benchmark_manifest.transport_package_ref)
    )
    designated_continuations = [
        continuation.continuation_id
        for continuation in package.continuations
        if continuation.source_interface_id == benchmark_manifest.interfaces_to_measure[0]
        and continuation.target_interface_id in benchmark_manifest.interfaces_to_measure[1:]
    ]
    assert designated_continuations

    collapse_witness_found = False
    for continuation_id in designated_continuations:
        transport_map = compute_predictive_transport_map(package, continuation_id)
        target_class_ids = {image.target_class_id for image in transport_map.class_images}
        if len(target_class_ids) < len(transport_map.class_images):
            collapse_witness_found = True
            break
    assert collapse_witness_found

    assert artifacts.csv_artifact_path.is_file()
    assert artifacts.ops_note_path.is_file()

    with artifacts.csv_artifact_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    later_interface_ids = {record.interface_id for record in later_records}
    later_zero_rows = [row for row in rows if row["interface_id"] in later_interface_ids]
    assert later_zero_rows
    assert all(row["discrepancy_metric_value_exact"] == "0" for row in later_zero_rows)
