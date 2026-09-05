from __future__ import annotations

from fractions import Fraction

from holonomy_memory.analysis import (
    compute_current_loop_action,
    compute_current_partition,
    compute_exact_max_abs_future_gap,
    compute_predictive_loop_action,
    compute_predictive_partition,
    enumerate_memory_witnesses,
)
from holonomy_memory.benchmarks import (
    BENCHMARK_IDS,
    benchmark_manifest_paths,
    pair_manifest_paths,
    perturbation_manifest_paths,
    resolve_repo_relative_path,
)
from holonomy_memory.controls import (
    InterfaceEvidenceSummary,
    build_perturbation_sweep_plan,
    check_currentization,
    check_flattening,
    check_support_fixation,
    evaluate_perturbation_hook,
    resolve_perturbation_targets,
)
from holonomy_memory.core import load_route_transport_package
from holonomy_memory.schemas import (
    AuditStatus,
    BenchmarkManifest,
    CompletionManifest,
    CurrentizationManifest,
    DiscrepancyMetricName,
    PerturbationSweep,
)
from holonomy_memory.validation import (
    load_benchmark_manifest,
    load_completion_manifest,
    load_currentization_manifest,
    load_json_file,
    load_perturbation_sweep,
)


BENCHMARK_PURPOSES = {
    "flat_control": "sanity baseline with no predictive residue",
    "protocol_trap_naive": "naive protocol-trap variant with apparent residue",
    "protocol_trap_honest": "honest protocol control expected to clear the residue",
    "flattenable_raw": "raw mismatch expected to collapse under admissible completion",
    "flattenable_completed": "completion counterpart expected to collapse the residue",
    "latent_memory_base": "base predictive-memory case before currentization",
    "latent_memory_refined": "same-support refinement expected to dissolve the witness",
    "dissipative_memory": "earlier residue with a later flat/collapsed interface",
    "memory_wheel": "coherent memory loop benchmark with nontrivial predictive holonomy",
}


def test_benchmark_inventory_helper_is_deterministic() -> None:
    manifest_paths = benchmark_manifest_paths()

    assert tuple(BENCHMARK_PURPOSES) == BENCHMARK_IDS
    assert tuple(path.name for path in manifest_paths) == tuple(
        f"{benchmark_id}.benchmark.json" for benchmark_id in BENCHMARK_IDS
    )
    assert tuple(path.name for path in pair_manifest_paths()) == (
        "flattenable_pair.completion.json",
        "latent_memory_pair.currentization.json",
    )
    assert tuple(path.name for path in perturbation_manifest_paths()) == tuple(
        f"{benchmark_id}.perturbation.json" for benchmark_id in BENCHMARK_IDS
    )


def test_benchmark_manifests_validate_and_preflight_runtime_analysis() -> None:
    manifests = {path.name: load_benchmark_manifest(path) for path in benchmark_manifest_paths()}

    assert all(isinstance(manifest, BenchmarkManifest) for manifest in manifests.values())

    for manifest in manifests.values():
        package = load_route_transport_package(resolve_repo_relative_path(manifest.transport_package_ref))
        interface_ids = set(package.interface_ids())
        loop_ids = set(package.loop_ids())

        for interface_id in manifest.interfaces_to_measure:
            assert interface_id in interface_ids
            package.get_event_package(interface_id)
            compute_current_partition(package, interface_id)
            compute_predictive_partition(package, interface_id)
            enumerate_memory_witnesses(package, interface_id)
            compute_exact_max_abs_future_gap(package, interface_id)

        for loop_id in manifest.loops_to_test:
            assert loop_id in loop_ids
            compute_current_loop_action(package, loop_id)
            compute_predictive_loop_action(package, loop_id)


def test_targeted_semantic_smoke_assertions_hold_for_core_suite() -> None:
    manifests = {manifest.benchmark_id: manifest for manifest in _load_benchmark_manifests()}

    flat_package = _load_package_for_manifest(manifests["flat_control"])
    flat_witnesses = enumerate_memory_witnesses(flat_package, "mid")
    flat_metric = compute_exact_max_abs_future_gap(flat_package, "mid")
    assert flat_witnesses == ()
    assert flat_metric.metric_value == Fraction(0, 1)

    protocol_naive_package = _load_package_for_manifest(manifests["protocol_trap_naive"])
    protocol_naive_witnesses = enumerate_memory_witnesses(protocol_naive_package, "mid")
    protocol_naive_metric = compute_exact_max_abs_future_gap(protocol_naive_package, "mid")
    assert protocol_naive_witnesses or protocol_naive_metric.metric_value > Fraction(0, 1)

    protocol_honest_package = _load_package_for_manifest(manifests["protocol_trap_honest"])
    assert enumerate_memory_witnesses(protocol_honest_package, "mid") == ()
    assert compute_exact_max_abs_future_gap(protocol_honest_package, "mid").metric_value == Fraction(0, 1)

    flattenable_raw_package = _load_package_for_manifest(manifests["flattenable_raw"])
    flattenable_raw_witnesses = enumerate_memory_witnesses(flattenable_raw_package, "mid")
    flattenable_raw_metric = compute_exact_max_abs_future_gap(flattenable_raw_package, "mid")
    assert flattenable_raw_witnesses or flattenable_raw_metric.metric_value > Fraction(0, 1)

    flattenable_completed_package = _load_package_for_manifest(manifests["flattenable_completed"])
    assert enumerate_memory_witnesses(flattenable_completed_package, "mid") == ()
    assert (
        compute_exact_max_abs_future_gap(flattenable_completed_package, "mid").metric_value
        == Fraction(0, 1)
    )

    latent_base_package = _load_package_for_manifest(manifests["latent_memory_base"])
    assert len(enumerate_memory_witnesses(latent_base_package, "mid")) > 0

    latent_refined_package = _load_package_for_manifest(manifests["latent_memory_refined"])
    assert enumerate_memory_witnesses(latent_refined_package, "mid") == ()
    assert compute_exact_max_abs_future_gap(latent_refined_package, "mid").metric_value == Fraction(0, 1)

    dissipative_package = _load_package_for_manifest(manifests["dissipative_memory"])
    assert len(enumerate_memory_witnesses(dissipative_package, "mid")) > 0
    assert enumerate_memory_witnesses(dissipative_package, "end") == ()
    assert compute_exact_max_abs_future_gap(dissipative_package, "end").metric_value == Fraction(0, 1)

    memory_wheel_package = _load_package_for_manifest(manifests["memory_wheel"])
    current_loop = compute_current_loop_action(memory_wheel_package, "swap_mid")
    predictive_loop = compute_predictive_loop_action(memory_wheel_package, "swap_mid")
    assert current_loop.is_trivial
    assert predictive_loop.is_trivial is False


def test_pair_manifests_validate_and_link_to_benchmark_inventory() -> None:
    manifests_by_id = {manifest.benchmark_id: manifest for manifest in _load_benchmark_manifests()}

    completion_manifest = load_completion_manifest(pair_manifest_paths()[0])
    currentization_manifest = load_currentization_manifest(pair_manifest_paths()[1])

    assert isinstance(completion_manifest, CompletionManifest)
    assert isinstance(currentization_manifest, CurrentizationManifest)
    assert completion_manifest.base_benchmark_id in manifests_by_id
    assert completion_manifest.completed_benchmark_id in manifests_by_id
    assert currentization_manifest.base_benchmark_id in manifests_by_id
    assert currentization_manifest.refined_benchmark_id in manifests_by_id

    flattenable_support = check_support_fixation(
        _load_package_for_manifest(manifests_by_id["flattenable_raw"]),
        _load_package_for_manifest(manifests_by_id["flattenable_completed"]),
        same_support_required=True,
        base_id="flattenable_raw",
        compared_id="flattenable_completed",
    )
    latent_support = check_support_fixation(
        _load_package_for_manifest(manifests_by_id["latent_memory_base"]),
        _load_package_for_manifest(manifests_by_id["latent_memory_refined"]),
        same_support_required=True,
        base_id="latent_memory_base",
        compared_id="latent_memory_refined",
    )

    assert flattenable_support.status != AuditStatus.FAILED
    assert latent_support.status != AuditStatus.FAILED

    flattening_result = check_flattening(
        completion_manifest,
        _summary("flattenable_raw", "mid", 1, Fraction(1, 2)),
        _summary("flattenable_completed", "mid", 0, Fraction(0, 1)),
        support_check=flattenable_support,
    )
    currentization_result = check_currentization(
        currentization_manifest,
        _summary("latent_memory_base", "mid", 1, Fraction(1, 2)),
        _summary("latent_memory_refined", "mid", 0, Fraction(0, 1)),
        support_check=latent_support,
    )

    assert flattening_result.status == AuditStatus.PASSED
    assert currentization_result.status == AuditStatus.PASSED


def test_perturbation_manifests_validate_and_resolve_targets() -> None:
    manifests_by_id = {manifest.benchmark_id: manifest for manifest in _load_benchmark_manifests()}

    for path in perturbation_manifest_paths():
        perturbation = load_perturbation_sweep(path)
        assert isinstance(perturbation, PerturbationSweep)
        assert perturbation.benchmark_id in manifests_by_id

        package_config = load_json_file(
            resolve_repo_relative_path(manifests_by_id[perturbation.benchmark_id].transport_package_ref)
        )
        resolutions = resolve_perturbation_targets(package_config, perturbation)
        plan = build_perturbation_sweep_plan(package_config, perturbation)
        hook = evaluate_perturbation_hook(package_config, perturbation)

        assert any(resolution.resolved for resolution in resolutions)
        assert all(resolution.resolved for resolution in plan.resolved_targets)
        assert hook.resolved_target_count >= 1


def _load_benchmark_manifests() -> tuple[BenchmarkManifest, ...]:
    return tuple(load_benchmark_manifest(path) for path in benchmark_manifest_paths())


def _load_package_for_manifest(manifest: BenchmarkManifest):
    return load_route_transport_package(resolve_repo_relative_path(manifest.transport_package_ref))


def _summary(
    benchmark_id: str,
    interface_id: str,
    witness_count: int,
    discrepancy_value: Fraction,
) -> InterfaceEvidenceSummary:
    return InterfaceEvidenceSummary(
        benchmark_id=benchmark_id,
        interface_id=interface_id,
        history_count=2,
        current_class_count=1,
        predictive_class_count=2 if witness_count else 1,
        witness_count=witness_count,
        max_fiber_size=2,
        discrepancy_metric_name=DiscrepancyMetricName.EXACT_MAX_ABS_FUTURE_GAP,
        discrepancy_metric_value=discrepancy_value,
        current_loop_is_trivial=True,
        predictive_loop_is_nontrivial=bool(witness_count),
    )
