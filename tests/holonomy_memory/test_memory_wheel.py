from __future__ import annotations

import csv
from pathlib import Path

from holonomy_memory import run_benchmark
from holonomy_memory.analysis import (
    compute_current_loop_action,
    compute_exact_max_abs_future_gap,
    compute_predictive_loop_action,
    enumerate_memory_witnesses,
)
from holonomy_memory.benchmarks import load_benchmark_manifest_for_id, resolve_repo_relative_path
from holonomy_memory.core import load_route_transport_package
from holonomy_memory.schemas import BenchmarkResultManifest, ClassLabel
from holonomy_memory.validation import load_benchmark_result_manifest


def test_memory_wheel_regression(tmp_path: Path) -> None:
    artifacts = run_benchmark(
        benchmark_id="memory_wheel",
        seed=0,
        output_root=tmp_path,
    )
    manifest = load_benchmark_result_manifest(artifacts.json_artifact_path)
    benchmark_manifest = load_benchmark_manifest_for_id("memory_wheel")

    assert isinstance(manifest, BenchmarkResultManifest)
    assert [record.interface_id for record in manifest.records] == benchmark_manifest.interfaces_to_measure

    flagship_records = [
        record
        for record in manifest.records
        if record.witness_count > 0
        and record.discrepancy_metric_value > 0.0
        and record.class_label == ClassLabel.COHERENT_CANDIDATE
        and (
            record.current_quotient_size < record.predictive_quotient_size
            or record.max_fiber_size > 1
        )
        and record.loop_action_score_current_quotient == 0.0
        and record.loop_action_score_predictive_quotient > 0.0
        and record.flattening_status.value != "passed"
        and record.currentization_status.value != "passed"
    ]
    assert flagship_records
    flagship_interface_id = flagship_records[0].interface_id

    package = load_route_transport_package(
        resolve_repo_relative_path(benchmark_manifest.transport_package_ref)
    )
    designated_loop_witnesses = []
    for loop_id in benchmark_manifest.loops_to_test:
        current_action = compute_current_loop_action(package, loop_id)
        predictive_action = compute_predictive_loop_action(package, loop_id)
        if (
            current_action.interface_id == flagship_interface_id
            and current_action.is_trivial
            and not predictive_action.is_trivial
            and predictive_action.moved_class_ids
        ):
            designated_loop_witnesses.append((loop_id, current_action, predictive_action))
    assert designated_loop_witnesses

    witnesses = enumerate_memory_witnesses(package, flagship_interface_id)
    assert witnesses
    discrepancy = compute_exact_max_abs_future_gap(package, flagship_interface_id)
    assert discrepancy.history_pair == ("h_mid_0", "h_mid_1")

    assert artifacts.csv_artifact_path.is_file()
    assert artifacts.ops_note_path.is_file()

    with artifacts.csv_artifact_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert rows[0]["loop_action_score_current_quotient_exact"] == "0"
    assert rows[0]["loop_action_score_predictive_quotient_exact"] != "0"

    note = artifacts.ops_note_path.read_text(encoding="utf-8")
    assert "best_witness_pair: h_mid_0, h_mid_1" in note
    assert "predictive_moved_class_ids: C0, C1" in note
