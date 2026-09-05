from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from time import perf_counter

from .analysis import (
    compute_predictive_transport_map,
    InterfacePartition,
    compute_current_loop_action,
    compute_current_partition,
    compute_exact_max_abs_future_gap,
    compute_predictive_loop_action,
    compute_predictive_partition,
    enumerate_memory_witnesses,
    resolve_interface_history_ids,
)
from .benchmarks import (
    REPO_ROOT,
    benchmark_manifest_path_for_id,
    load_benchmark_manifest_for_id,
    resolve_repo_relative_path,
)
from .controls import (
    ClassificationEvidence,
    InterfaceEvidenceSummary,
    build_perturbation_sweep_plan,
    check_currentization,
    check_flattening,
    check_support_fixation,
    classify_regime,
    evaluate_perturbation_hook,
    resolve_perturbation_targets,
)
from .core import (
    RouteTransportPackage,
    load_route_transport_package_from_config,
)
from .schemas import (
    AuditStatus,
    BenchmarkManifest,
    BenchmarkResultManifest,
    CompletionManifest,
    CurrentizationManifest,
    DiscrepancyMetricName,
    InterfaceResultRecord,
    PerturbationSweep,
    RouteTransportPackageConfig,
)
from .validation import (
    load_benchmark_manifest,
    load_completion_manifest,
    load_currentization_manifest,
    load_perturbation_sweep,
)


@dataclass(frozen=True)
class BenchmarkRunArtifacts:
    benchmark_id: str
    seed: int
    manifest_path: Path
    package_config_path: Path | None
    json_artifact_path: Path
    csv_artifact_path: Path
    ops_note_path: Path
    result_manifest: BenchmarkResultManifest
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _InterfaceExecution:
    interface_id: str
    history_count: int
    current_partition: InterfacePartition
    predictive_partition: InterfacePartition
    witness_count: int
    max_fiber_size: int
    discrepancy_metric_name: DiscrepancyMetricName
    discrepancy_metric_value: Fraction
    loop_action_score_current: Fraction
    loop_action_score_predictive: Fraction
    current_loop_is_trivial: bool | None
    predictive_loop_is_nontrivial: bool | None
    runtime_seconds: float


@dataclass(frozen=True)
class _BenchmarkExecutionBundle:
    manifest: BenchmarkManifest
    manifest_path: Path
    package: RouteTransportPackage
    package_config: RouteTransportPackageConfig
    package_config_path: Path | None
    result_manifest: BenchmarkResultManifest
    executions: tuple[_InterfaceExecution, ...]
    warnings: tuple[str, ...]
    perturbation_sweep: PerturbationSweep | None
    perturbation_resolutions: tuple[object, ...]
    perturbation_plan: object | None
    perturbation_hook: object | None
    transport_collapse_lines: tuple[str, ...]
    memory_wheel_lines: tuple[str, ...]


def run_benchmark(
    *,
    benchmark_id: str | None = None,
    manifest_path: str | Path | None = None,
    seed: int = 0,
    output_root: str | Path | None = None,
) -> BenchmarkRunArtifacts:
    resolved_manifest_path, manifest = _resolve_benchmark_manifest(
        benchmark_id=benchmark_id,
        manifest_path=manifest_path,
    )
    bundle = _execute_benchmark_manifest(
        manifest,
        manifest_path=resolved_manifest_path,
        seed=seed,
    )

    return write_benchmark_artifacts(
        benchmark_id=bundle.manifest.benchmark_id,
        seed=seed,
        manifest_path=bundle.manifest_path,
        package_config_path=bundle.package_config_path,
        result_manifest=bundle.result_manifest,
        output_root=output_root,
        warnings=bundle.warnings,
        executions=bundle.executions,
        loops_to_test=tuple(bundle.manifest.loops_to_test),
        perturbation_sweep=bundle.perturbation_sweep,
        perturbation_resolutions=bundle.perturbation_resolutions,
        perturbation_plan=bundle.perturbation_plan,
        perturbation_hook=bundle.perturbation_hook,
        transport_collapse_lines=bundle.transport_collapse_lines,
        memory_wheel_lines=bundle.memory_wheel_lines,
    )


def _execute_benchmark_manifest(
    manifest: BenchmarkManifest,
    *,
    manifest_path: Path,
    seed: int,
    package_config: RouteTransportPackageConfig | None = None,
    package_config_path: Path | None = None,
) -> _BenchmarkExecutionBundle:
    if package_config is None:
        package, package_config, package_config_path = _load_runtime_package_for_manifest(
            manifest,
            manifest_path=manifest_path,
        )
    else:
        package = load_route_transport_package_from_config(package_config)

    executions = tuple(
        _compute_interface_execution(
            package,
            interface_id,
            manifest.loops_to_test,
        )
        for interface_id in manifest.interfaces_to_measure
    )
    execution_by_interface = {
        execution.interface_id: execution for execution in executions
    }
    summaries = {
        execution.interface_id: _summary_from_execution(
            manifest.benchmark_id,
            execution,
        )
        for execution in executions
    }

    warnings: list[str] = []
    support_status_by_interface = {
        interface_id: AuditStatus.SKIPPED for interface_id in manifest.interfaces_to_measure
    }
    flattening_status_by_interface = {
        interface_id: AuditStatus.SKIPPED for interface_id in manifest.interfaces_to_measure
    }
    currentization_status_by_interface = {
        interface_id: AuditStatus.SKIPPED for interface_id in manifest.interfaces_to_measure
    }
    artifact_trap_flag_by_interface = {
        interface_id: False for interface_id in manifest.interfaces_to_measure
    }
    dissipative_flag_by_interface = _compute_dissipative_flags(
        manifest.benchmark_id,
        executions,
    )

    if manifest.completion_manifest_ref is not None:
        completion_manifest = load_completion_manifest(
            resolve_repo_relative_path(manifest.completion_manifest_ref)
        )
        support_check, completion_statuses, completion_warnings = _evaluate_completion_controls(
            manifest,
            package,
            completion_manifest,
            summaries,
        )
        warnings.extend(completion_warnings)
        for interface_id, status in completion_statuses.items():
            flattening_status_by_interface[interface_id] = status
            if support_check is not None:
                support_status_by_interface[interface_id] = support_check.status

    if manifest.currentization_manifest_ref is not None:
        currentization_manifest = load_currentization_manifest(
            resolve_repo_relative_path(manifest.currentization_manifest_ref)
        )
        support_check, currentization_statuses, currentization_warnings = _evaluate_currentization_controls(
            manifest,
            package,
            currentization_manifest,
            summaries,
        )
        warnings.extend(currentization_warnings)
        for interface_id, status in currentization_statuses.items():
            currentization_status_by_interface[interface_id] = status
            if support_check is not None:
                support_status_by_interface[interface_id] = support_check.status

    if manifest.benchmark_id == "protocol_trap_naive":
        artifact_support_check, artifact_flags, artifact_warnings = _evaluate_protocol_trap_flags(
            manifest,
            package,
            summaries,
        )
        warnings.extend(artifact_warnings)
        if artifact_support_check is not None:
            for interface_id in manifest.interfaces_to_measure:
                support_status_by_interface[interface_id] = artifact_support_check.status
        artifact_trap_flag_by_interface.update(artifact_flags)

    perturbation_sweep = None
    perturbation_resolutions = ()
    perturbation_plan = None
    perturbation_hook = None
    transport_collapse_lines: tuple[str, ...] = ()
    memory_wheel_lines: tuple[str, ...] = ()
    if manifest.perturbation_sweep_ref is not None:
        perturbation_sweep = load_perturbation_sweep(
            resolve_repo_relative_path(manifest.perturbation_sweep_ref)
        )
        perturbation_resolutions = resolve_perturbation_targets(
            package_config,
            perturbation_sweep,
        )
        perturbation_plan = build_perturbation_sweep_plan(
            package_config,
            perturbation_sweep,
        )
        perturbation_hook = evaluate_perturbation_hook(
            package_config,
            perturbation_sweep,
        )
        if perturbation_hook.unresolved_target_count > 0:
            warnings.append("some perturbation targets did not resolve cleanly")

    if manifest.benchmark_id == "dissipative_memory":
        transport_collapse_lines = _build_transport_collapse_lines(
            package,
            manifest,
        )
    if manifest.benchmark_id == "memory_wheel":
        memory_wheel_lines = _build_memory_wheel_lines(
            package,
            manifest,
        )

    records: list[InterfaceResultRecord] = []
    for interface_id in manifest.interfaces_to_measure:
        execution = execution_by_interface[interface_id]
        classification = classify_regime(
            ClassificationEvidence(
                benchmark_id=manifest.benchmark_id,
                interface_id=interface_id,
                witness_count=execution.witness_count,
                discrepancy_metric_name=execution.discrepancy_metric_name,
                discrepancy_metric_value=execution.discrepancy_metric_value,
                support_fixation_status=support_status_by_interface[interface_id],
                currentization_status=currentization_status_by_interface[interface_id],
                flattening_status=flattening_status_by_interface[interface_id],
                artifact_trap_flag=artifact_trap_flag_by_interface[interface_id],
                dissipative_flag=dissipative_flag_by_interface[interface_id],
                current_loop_is_trivial=execution.current_loop_is_trivial,
                predictive_loop_is_nontrivial=execution.predictive_loop_is_nontrivial,
                # Real robustness sweeps land in HM-016; the single-run path stays explicit.
                robustness_fraction=Fraction(0, 1),
            )
        )
        records.append(
            InterfaceResultRecord(
                benchmark_id=manifest.benchmark_id,
                interface_id=interface_id,
                history_count=execution.history_count,
                current_quotient_size=execution.current_partition.class_count,
                predictive_quotient_size=execution.predictive_partition.class_count,
                witness_count=execution.witness_count,
                max_fiber_size=execution.max_fiber_size,
                discrepancy_metric_name=execution.discrepancy_metric_name,
                discrepancy_metric_value=float(execution.discrepancy_metric_value),
                loop_action_score_current_quotient=float(execution.loop_action_score_current),
                loop_action_score_predictive_quotient=float(
                    execution.loop_action_score_predictive
                ),
                support_fixation_status=support_status_by_interface[interface_id],
                currentization_status=currentization_status_by_interface[interface_id],
                flattening_status=flattening_status_by_interface[interface_id],
                robustness_fraction=0.0,
                class_label=classification.class_label,
                runtime=execution.runtime_seconds,
                seed=seed,
            )
        )

    result_manifest = BenchmarkResultManifest.model_validate(
        {
            "schema_version": "benchmark-result-manifest.v1",
            "manifest_id": f"{manifest.benchmark_id}.result",
            "benchmark_id": manifest.benchmark_id,
            "records": [record.model_dump(mode="json") for record in records],
            "tags": list(manifest.tags),
        }
    )
    return _BenchmarkExecutionBundle(
        manifest=manifest,
        manifest_path=manifest_path,
        package=package,
        package_config=package_config,
        package_config_path=package_config_path,
        result_manifest=result_manifest,
        executions=executions,
        warnings=tuple(warnings),
        perturbation_sweep=perturbation_sweep,
        perturbation_resolutions=perturbation_resolutions,
        perturbation_plan=perturbation_plan,
        perturbation_hook=perturbation_hook,
        transport_collapse_lines=transport_collapse_lines,
        memory_wheel_lines=memory_wheel_lines,
    )


def write_benchmark_artifacts(
    *,
    benchmark_id: str,
    seed: int,
    manifest_path: str | Path,
    package_config_path: str | Path | None,
    result_manifest: BenchmarkResultManifest,
    output_root: str | Path | None = None,
    warnings: tuple[str, ...] = (),
    executions: tuple[_InterfaceExecution, ...],
    loops_to_test: tuple[str, ...],
    perturbation_sweep: PerturbationSweep | None = None,
    perturbation_resolutions: tuple[object, ...] = (),
    perturbation_plan: object | None = None,
    perturbation_hook: object | None = None,
    transport_collapse_lines: tuple[str, ...] = (),
    memory_wheel_lines: tuple[str, ...] = (),
) -> BenchmarkRunArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    json_path = root / "artifacts" / "results" / f"{benchmark_id}.result.json"
    csv_path = root / "artifacts" / "tables" / f"{benchmark_id}.csv"
    ops_path = root / "docs" / "results" / f"{benchmark_id}.md"

    for path in (json_path, csv_path, ops_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(result_manifest.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(csv_path, result_manifest, executions)
    _write_ops_note(
        benchmark_id=benchmark_id,
        seed=seed,
        manifest_path=Path(manifest_path),
        package_config_path=Path(package_config_path) if package_config_path is not None else None,
        json_path=json_path,
        csv_path=csv_path,
        note_path=ops_path,
        result_manifest=result_manifest,
        executions=executions,
        loops_to_test=loops_to_test,
        perturbation_sweep=perturbation_sweep,
        perturbation_resolutions=perturbation_resolutions,
        perturbation_plan=perturbation_plan,
        perturbation_hook=perturbation_hook,
        transport_collapse_lines=transport_collapse_lines,
        memory_wheel_lines=memory_wheel_lines,
        warnings=warnings,
    )

    return BenchmarkRunArtifacts(
        benchmark_id=benchmark_id,
        seed=seed,
        manifest_path=Path(manifest_path),
        package_config_path=Path(package_config_path) if package_config_path is not None else None,
        json_artifact_path=json_path,
        csv_artifact_path=csv_path,
        ops_note_path=ops_path,
        result_manifest=result_manifest,
        warnings=warnings,
    )


def _resolve_benchmark_manifest(
    *,
    benchmark_id: str | None,
    manifest_path: str | Path | None,
) -> tuple[Path, BenchmarkManifest]:
    if (benchmark_id is None) == (manifest_path is None):
        raise ValueError("exactly one of benchmark_id or manifest_path must be provided")
    if benchmark_id is not None:
        resolved_path = benchmark_manifest_path_for_id(benchmark_id)
        return resolved_path, load_benchmark_manifest_for_id(benchmark_id)
    resolved_path = Path(manifest_path).resolve()
    return resolved_path, load_benchmark_manifest(resolved_path)


def _load_runtime_package_for_manifest(
    manifest: BenchmarkManifest,
    *,
    manifest_path: Path,
) -> tuple[RouteTransportPackage, RouteTransportPackageConfig, Path | None]:
    if manifest.transport_package is not None:
        config = manifest.transport_package
        package = load_route_transport_package_from_config(config)
        return package, config, None

    if manifest.transport_package_ref is None:
        raise ValueError(
            f"benchmark manifest {manifest_path} does not specify a transport package"
        )
    config_path = resolve_repo_relative_path(manifest.transport_package_ref)
    config = RouteTransportPackageConfig.model_validate(
        json.loads(config_path.read_text(encoding="utf-8"))
    )
    package = load_route_transport_package_from_config(config)
    return package, config, config_path


def _compute_interface_execution(
    package: RouteTransportPackage,
    interface_id: str,
    loop_ids_to_test: list[str] | tuple[str, ...],
) -> _InterfaceExecution:
    started = perf_counter()
    history_ids = resolve_interface_history_ids(package, interface_id)
    current_partition = compute_current_partition(package, interface_id, history_ids)
    predictive_partition = compute_predictive_partition(package, interface_id, history_ids)
    witnesses = enumerate_memory_witnesses(package, interface_id, history_ids)
    discrepancy = compute_exact_max_abs_future_gap(package, interface_id, history_ids)
    loop_scores = _compute_loop_scores(
        package,
        interface_id,
        history_ids,
        loop_ids_to_test,
    )
    runtime_seconds = perf_counter() - started
    return _InterfaceExecution(
        interface_id=interface_id,
        history_count=len(history_ids),
        current_partition=current_partition,
        predictive_partition=predictive_partition,
        witness_count=len(witnesses),
        max_fiber_size=_compute_max_fiber_size(current_partition, predictive_partition),
        discrepancy_metric_name=discrepancy.metric_name,
        discrepancy_metric_value=discrepancy.metric_value,
        loop_action_score_current=loop_scores[0],
        loop_action_score_predictive=loop_scores[1],
        current_loop_is_trivial=loop_scores[2],
        predictive_loop_is_nontrivial=loop_scores[3],
        runtime_seconds=runtime_seconds,
    )


def _compute_loop_scores(
    package: RouteTransportPackage,
    interface_id: str,
    history_ids: tuple[str, ...],
    loop_ids_to_test: list[str] | tuple[str, ...],
) -> tuple[Fraction, Fraction, bool | None, bool | None]:
    applicable_loop_ids = tuple(
        loop_id
        for loop_id in loop_ids_to_test
        if package.get_loop(loop_id).interface_id == interface_id
    )
    if not applicable_loop_ids:
        return Fraction(0, 1), Fraction(0, 1), None, None

    current_actions = tuple(
        compute_current_loop_action(package, loop_id, history_ids)
        for loop_id in applicable_loop_ids
    )
    predictive_actions = tuple(
        compute_predictive_loop_action(package, loop_id, history_ids)
        for loop_id in applicable_loop_ids
    )
    return (
        max(
            (action.moved_class_fraction for action in current_actions),
            default=Fraction(0, 1),
        ),
        max(
            (action.moved_class_fraction for action in predictive_actions),
            default=Fraction(0, 1),
        ),
        all(action.is_trivial for action in current_actions),
        any(not action.is_trivial for action in predictive_actions),
    )


def _compute_max_fiber_size(
    current_partition: InterfacePartition,
    predictive_partition: InterfacePartition,
) -> int:
    max_fiber_size = 0
    for current_class in current_partition.classes:
        predictive_class_ids = {
            predictive_partition.history_to_class_id[history_id]
            for history_id in current_class.member_history_ids
        }
        max_fiber_size = max(max_fiber_size, len(predictive_class_ids))
    return max_fiber_size


def _summary_from_execution(
    benchmark_id: str,
    execution: _InterfaceExecution,
) -> InterfaceEvidenceSummary:
    return InterfaceEvidenceSummary(
        benchmark_id=benchmark_id,
        interface_id=execution.interface_id,
        history_count=execution.history_count,
        current_class_count=execution.current_partition.class_count,
        predictive_class_count=execution.predictive_partition.class_count,
        witness_count=execution.witness_count,
        max_fiber_size=execution.max_fiber_size,
        discrepancy_metric_name=execution.discrepancy_metric_name,
        discrepancy_metric_value=execution.discrepancy_metric_value,
        current_loop_is_trivial=execution.current_loop_is_trivial,
        predictive_loop_is_nontrivial=execution.predictive_loop_is_nontrivial,
        robustness_fraction=Fraction(0, 1),
    )


def _evaluate_completion_controls(
    manifest: BenchmarkManifest,
    package: RouteTransportPackage,
    completion_manifest: CompletionManifest,
    base_summaries: dict[str, InterfaceEvidenceSummary],
) -> tuple[
    object | None,
    dict[str, AuditStatus],
    tuple[str, ...],
]:
    warnings: list[str] = []
    compared_manifest = load_benchmark_manifest_for_id(
        completion_manifest.completed_benchmark_id
    )
    compared_package, _, _ = _load_runtime_package_for_manifest(
        compared_manifest,
        manifest_path=benchmark_manifest_path_for_id(compared_manifest.benchmark_id),
    )
    support_check = check_support_fixation(
        package,
        compared_package,
        same_support_required=completion_manifest.same_support_required,
        base_id=completion_manifest.base_benchmark_id,
        compared_id=completion_manifest.completed_benchmark_id,
    )
    compared_summaries = _compute_interface_summaries(
        compared_manifest,
        compared_package,
    )
    statuses = {
        interface_id: AuditStatus.SKIPPED for interface_id in manifest.interfaces_to_measure
    }
    for interface_id in manifest.interfaces_to_measure:
        compared_summary = compared_summaries.get(interface_id)
        if compared_summary is None:
            warnings.append(
                f"completed benchmark {completion_manifest.completed_benchmark_id} "
                f"does not provide interface {interface_id}"
            )
            continue
        result = check_flattening(
            completion_manifest,
            base_summaries[interface_id],
            compared_summary,
            support_check=support_check,
        )
        statuses[interface_id] = result.status
    return support_check, statuses, tuple(warnings)


def _evaluate_currentization_controls(
    manifest: BenchmarkManifest,
    package: RouteTransportPackage,
    currentization_manifest: CurrentizationManifest,
    base_summaries: dict[str, InterfaceEvidenceSummary],
) -> tuple[
    object | None,
    dict[str, AuditStatus],
    tuple[str, ...],
]:
    warnings: list[str] = []
    compared_manifest = load_benchmark_manifest_for_id(
        currentization_manifest.refined_benchmark_id
    )
    compared_package, _, _ = _load_runtime_package_for_manifest(
        compared_manifest,
        manifest_path=benchmark_manifest_path_for_id(compared_manifest.benchmark_id),
    )
    support_check = check_support_fixation(
        package,
        compared_package,
        same_support_required=currentization_manifest.same_support_required,
        base_id=currentization_manifest.base_benchmark_id,
        compared_id=currentization_manifest.refined_benchmark_id,
    )
    compared_summaries = _compute_interface_summaries(
        compared_manifest,
        compared_package,
    )
    statuses = {
        interface_id: AuditStatus.SKIPPED for interface_id in manifest.interfaces_to_measure
    }
    for interface_id in manifest.interfaces_to_measure:
        compared_summary = compared_summaries.get(interface_id)
        if compared_summary is None:
            warnings.append(
                f"refined benchmark {currentization_manifest.refined_benchmark_id} "
                f"does not provide interface {interface_id}"
            )
            continue
        result = check_currentization(
            currentization_manifest,
            base_summaries[interface_id],
            compared_summary,
            support_check=support_check,
        )
        statuses[interface_id] = result.status
    return support_check, statuses, tuple(warnings)


def _evaluate_protocol_trap_flags(
    manifest: BenchmarkManifest,
    package: RouteTransportPackage,
    base_summaries: dict[str, InterfaceEvidenceSummary],
) -> tuple[object | None, dict[str, bool], tuple[str, ...]]:
    warnings: list[str] = []
    honest_manifest = load_benchmark_manifest_for_id("protocol_trap_honest")
    honest_package, _, _ = _load_runtime_package_for_manifest(
        honest_manifest,
        manifest_path=benchmark_manifest_path_for_id(honest_manifest.benchmark_id),
    )
    support_check = check_support_fixation(
        package,
        honest_package,
        same_support_required=True,
        base_id=manifest.benchmark_id,
        compared_id=honest_manifest.benchmark_id,
    )
    honest_summaries = _compute_interface_summaries(honest_manifest, honest_package)
    flags = {interface_id: False for interface_id in manifest.interfaces_to_measure}
    for interface_id in manifest.interfaces_to_measure:
        honest_summary = honest_summaries.get(interface_id)
        if honest_summary is None:
            warnings.append(
                f"protocol_trap_honest does not provide interface {interface_id}"
            )
            continue
        flags[interface_id] = (
            _has_residue(base_summaries[interface_id])
            and _is_flat(honest_summary)
            and support_check.status != AuditStatus.FAILED
        )
    return support_check, flags, tuple(warnings)


def _compute_dissipative_flags(
    benchmark_id: str,
    executions: tuple[_InterfaceExecution, ...],
) -> dict[str, bool]:
    flags = {execution.interface_id: False for execution in executions}
    if benchmark_id != "dissipative_memory":
        return flags

    summaries = tuple(_summary_from_execution(benchmark_id, execution) for execution in executions)
    for index, summary in enumerate(summaries):
        if not _has_residue(summary):
            continue
        later_summaries = summaries[index + 1 :]
        flags[summary.interface_id] = any(_is_flat(later) for later in later_summaries)
    return flags


def _compute_interface_summaries(
    manifest: BenchmarkManifest,
    package: RouteTransportPackage,
) -> dict[str, InterfaceEvidenceSummary]:
    summaries: dict[str, InterfaceEvidenceSummary] = {}
    for interface_id in manifest.interfaces_to_measure:
        execution = _compute_interface_execution(package, interface_id, manifest.loops_to_test)
        summaries[interface_id] = _summary_from_execution(manifest.benchmark_id, execution)
    return summaries


def _has_residue(summary: InterfaceEvidenceSummary) -> bool:
    return (
        summary.witness_count > 0
        or summary.discrepancy_metric_value > Fraction(0, 1)
    )


def _is_flat(summary: InterfaceEvidenceSummary) -> bool:
    return (
        summary.witness_count == 0
        and summary.discrepancy_metric_value == Fraction(0, 1)
    )


def _write_csv(
    csv_path: Path,
    result_manifest: BenchmarkResultManifest,
    executions: tuple[_InterfaceExecution, ...],
) -> None:
    execution_by_interface = {
        execution.interface_id: execution for execution in executions
    }
    fieldnames = [
        "benchmark_id",
        "interface_id",
        "history_count",
        "current_quotient_size",
        "predictive_quotient_size",
        "witness_count",
        "max_fiber_size",
        "discrepancy_metric_name",
        "discrepancy_metric_value",
        "discrepancy_metric_value_exact",
        "loop_action_score_current_quotient",
        "loop_action_score_current_quotient_exact",
        "loop_action_score_predictive_quotient",
        "loop_action_score_predictive_quotient_exact",
        "support_fixation_status",
        "currentization_status",
        "flattening_status",
        "robustness_fraction",
        "class_label",
        "runtime",
        "seed",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in result_manifest.records:
            execution = execution_by_interface[record.interface_id]
            writer.writerow(
                {
                    "benchmark_id": record.benchmark_id,
                    "interface_id": record.interface_id,
                    "history_count": record.history_count,
                    "current_quotient_size": record.current_quotient_size,
                    "predictive_quotient_size": record.predictive_quotient_size,
                    "witness_count": record.witness_count,
                    "max_fiber_size": record.max_fiber_size,
                    "discrepancy_metric_name": record.discrepancy_metric_name.value,
                    "discrepancy_metric_value": record.discrepancy_metric_value,
                    "discrepancy_metric_value_exact": _fraction_string(
                        execution.discrepancy_metric_value
                    ),
                    "loop_action_score_current_quotient": (
                        record.loop_action_score_current_quotient
                    ),
                    "loop_action_score_current_quotient_exact": _fraction_string(
                        execution.loop_action_score_current
                    ),
                    "loop_action_score_predictive_quotient": (
                        record.loop_action_score_predictive_quotient
                    ),
                    "loop_action_score_predictive_quotient_exact": _fraction_string(
                        execution.loop_action_score_predictive
                    ),
                    "support_fixation_status": record.support_fixation_status.value,
                    "currentization_status": record.currentization_status.value,
                    "flattening_status": record.flattening_status.value,
                    "robustness_fraction": record.robustness_fraction,
                    "class_label": record.class_label.value,
                    "runtime": record.runtime,
                    "seed": record.seed,
                }
            )


def _write_ops_note(
    *,
    benchmark_id: str,
    seed: int,
    manifest_path: Path,
    package_config_path: Path | None,
    json_path: Path,
    csv_path: Path,
    note_path: Path,
    result_manifest: BenchmarkResultManifest,
    executions: tuple[_InterfaceExecution, ...],
    loops_to_test: tuple[str, ...],
    perturbation_sweep: PerturbationSweep | None,
    perturbation_resolutions: tuple[object, ...],
    perturbation_plan: object | None,
    perturbation_hook: object | None,
    transport_collapse_lines: tuple[str, ...],
    memory_wheel_lines: tuple[str, ...],
    warnings: tuple[str, ...],
) -> None:
    execution_by_interface = {
        execution.interface_id: execution for execution in executions
    }
    lines = [
        f"# {benchmark_id}",
        "",
        f"- benchmark_id: {benchmark_id}",
        f"- manifest_path: {_display_path(manifest_path)}",
        "- transport_package: "
        + (
            _display_path(package_config_path)
            if package_config_path is not None
            else "inline benchmark manifest package"
        ),
        f"- seed: {seed}",
        f"- json_artifact: {_display_path(json_path)}",
        f"- csv_artifact: {_display_path(csv_path)}",
        f"- ops_note: {_display_path(note_path)}",
        f"- measured_interfaces: {', '.join(record.interface_id for record in result_manifest.records)}",
        f"- loops_tested: {', '.join(loops_to_test) if loops_to_test else '(none)'}",
        "",
        "## Interface Summaries",
        "",
    ]

    for record in result_manifest.records:
        execution = execution_by_interface[record.interface_id]
        lines.extend(
            [
                f"### {record.interface_id}",
                f"- history_count: {record.history_count}",
                f"- |Q|: {record.current_quotient_size}",
                f"- |M|: {record.predictive_quotient_size}",
                f"- max_fiber_size: {record.max_fiber_size}",
                f"- witness_count: {record.witness_count}",
                "- discrepancy: "
                f"{record.discrepancy_metric_name.value} = {_fraction_string(execution.discrepancy_metric_value)}",
                "- loop_score_current: "
                f"{_fraction_string(execution.loop_action_score_current)}",
                "- loop_score_predictive: "
                f"{_fraction_string(execution.loop_action_score_predictive)}",
                f"- support_fixation_status: {record.support_fixation_status.value}",
                f"- currentization_status: {record.currentization_status.value}",
                f"- flattening_status: {record.flattening_status.value}",
                f"- class_label: {record.class_label.value}",
                "",
            ]
        )

    lines.extend(["## Perturbation Preflight", ""])
    if perturbation_sweep is None:
        lines.append("- perturbation_hook: skipped")
    else:
        resolved_count = sum(
            1 for resolution in perturbation_resolutions if getattr(resolution, "resolved", False)
        )
        lines.extend(
            [
                f"- sweep_id: {perturbation_sweep.sweep_id}",
                f"- resolved_targets: {resolved_count}",
                "- hook_status: "
                + (
                    getattr(perturbation_hook, "status").value
                    if perturbation_hook is not None
                    else "skipped"
                ),
                f"- planned_trials: {getattr(perturbation_plan, 'trial_count', 0)}",
            ]
        )
    lines.append("")

    if transport_collapse_lines:
        lines.extend(transport_collapse_lines)
        lines.append("")
    if memory_wheel_lines:
        lines.extend(memory_wheel_lines)
        lines.append("")

    lines.extend(["## Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend(["## Conclusion", ""])
    if benchmark_id == "flat_control" and all(
        record.class_label.value == "flat" for record in result_manifest.records
    ):
        lines.append("- flat-control baseline is satisfied for all measured interfaces")
    elif benchmark_id == "flat_control":
        lines.append("- flat-control baseline is not satisfied for all measured interfaces")
    elif benchmark_id == "protocol_trap_naive":
        lines.append(
            "- apparent residue observed, but classified as protocol trap / artifact"
        )
    elif benchmark_id == "protocol_trap_honest":
        lines.append("- honest/internalized control is flat")
    elif benchmark_id == "flattenable_raw":
        lines.append(
            "- non-flat mismatch observed, but collapses under admissible completion"
        )
    elif benchmark_id == "flattenable_completed":
        lines.append("- completion counterpart is flat/collapsed")
    elif benchmark_id == "latent_memory_base":
        lines.append(
            "- latent predictive residue is present but dissolves under admissible same-object refinement"
        )
    elif benchmark_id == "latent_memory_refined":
        lines.append(
            "- refinement makes the relevant distinction current-visible and removes the witness"
        )
    elif benchmark_id == "dissipative_memory":
        lines.append(
            "- earlier interface has predictive residue, later transport collapses it, and the earlier interface is classified dissipative"
        )
    elif benchmark_id == "memory_wheel":
        lines.append(
            "- same-now/different-later residue exists, current loop action is trivial, predictive loop action is nontrivial, no benchmark-attached refinement/completion clears the effect, and the benchmark is classified coherent_candidate"
        )
    else:
        lines.append("- benchmark artifacts refreshed successfully")
    lines.append("")

    note_path.write_text("\n".join(lines), encoding="utf-8")


def _fraction_string(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _display_path(path: Path | None) -> str:
    if path is None:
        return "(none)"
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _build_transport_collapse_lines(
    package: RouteTransportPackage,
    manifest: BenchmarkManifest,
) -> tuple[str, ...]:
    if len(manifest.interfaces_to_measure) < 2:
        return ()

    source_interface_id = manifest.interfaces_to_measure[0]
    later_interface_ids = tuple(manifest.interfaces_to_measure[1:])
    designated_continuations = tuple(
        continuation.continuation_id
        for continuation in package.continuations
        if continuation.source_interface_id == source_interface_id
        and continuation.target_interface_id in later_interface_ids
    )
    if not designated_continuations:
        return (
            "## Transport Collapse",
            "",
            "- designated_continuation_family: (none)",
            f"- source_interface: {source_interface_id}",
            f"- target_interfaces: {', '.join(later_interface_ids)}",
            "- transport_collapse: unavailable",
        )

    lines = [
        "## Transport Collapse",
        "",
        f"- designated_continuation_family: {', '.join(designated_continuations)}",
        f"- source_interface: {source_interface_id}",
        f"- target_interfaces: {', '.join(later_interface_ids)}",
    ]
    for continuation_id in designated_continuations:
        transport_map = compute_predictive_transport_map(package, continuation_id)
        mapping = ", ".join(
            f"{class_image.source_class_id}->{class_image.target_class_id}"
            for class_image in transport_map.class_images
        )
        lines.extend(
            [
                f"- continuation {continuation_id}: "
                f"{transport_map.source_interface_id} -> {transport_map.target_interface_id}",
                f"- continuation {continuation_id} source_predictive_class_count: "
                f"{len(transport_map.source_classes)}",
                f"- continuation {continuation_id} target_predictive_class_count: "
                f"{len(transport_map.target_classes)}",
                f"- continuation {continuation_id} class_image_mapping: {mapping}",
            ]
        )
    return tuple(lines)


def _build_memory_wheel_lines(
    package: RouteTransportPackage,
    manifest: BenchmarkManifest,
) -> tuple[str, ...]:
    flagship_interface_id = _select_memory_wheel_flagship_interface(package, manifest)
    discrepancy = compute_exact_max_abs_future_gap(package, flagship_interface_id)
    witnesses = enumerate_memory_witnesses(package, flagship_interface_id)

    best_witness_pair = discrepancy.history_pair
    current_class_id = discrepancy.current_class_id
    witness_discrepancy = discrepancy.metric_value
    if best_witness_pair is None and witnesses:
        first_witness = witnesses[0]
        best_witness_pair = (first_witness.history_id_1, first_witness.history_id_2)
        current_class_id = first_witness.current_class_id

    designated_loop_id, current_action, predictive_action = _select_memory_wheel_loop_action(
        package,
        manifest,
        flagship_interface_id,
    )
    predictive_mapping = ", ".join(
        f"{class_image.source_class_id}->{class_image.target_class_id}"
        for class_image in predictive_action.class_images
    )
    current_moved = ", ".join(current_action.moved_class_ids) or "(none)"
    predictive_moved = ", ".join(predictive_action.moved_class_ids) or "(none)"
    witness_pair_text = (
        f"{best_witness_pair[0]}, {best_witness_pair[1]}"
        if best_witness_pair is not None
        else "(none)"
    )

    return (
        "## Flagship Witness",
        "",
        f"- flagship_interface: {flagship_interface_id}",
        f"- best_witness_pair: {witness_pair_text}",
        f"- current_class_id: {current_class_id or '(unknown)'}",
        f"- witness_discrepancy: {_fraction_string(witness_discrepancy)}",
        "",
        "## Loop Action",
        "",
        f"- designated_loop_id: {designated_loop_id}",
        f"- current_moved_class_ids: {current_moved}",
        f"- predictive_moved_class_ids: {predictive_moved}",
        f"- predictive_class_image_mapping: {predictive_mapping}",
        f"- predictive_moved_class_fraction: {_fraction_string(predictive_action.moved_class_fraction)}",
    )


def _select_memory_wheel_flagship_interface(
    package: RouteTransportPackage,
    manifest: BenchmarkManifest,
) -> str:
    for interface_id in manifest.interfaces_to_measure:
        history_ids = resolve_interface_history_ids(package, interface_id)
        current_partition = compute_current_partition(package, interface_id, history_ids)
        predictive_partition = compute_predictive_partition(package, interface_id, history_ids)
        discrepancy = compute_exact_max_abs_future_gap(package, interface_id, history_ids)
        loop_score_current, loop_score_predictive, _, _ = _compute_loop_scores(
            package,
            interface_id,
            history_ids,
            manifest.loops_to_test,
        )
        if (
            len(enumerate_memory_witnesses(package, interface_id, history_ids)) > 0
            and discrepancy.metric_value > Fraction(0, 1)
            and loop_score_current == Fraction(0, 1)
            and loop_score_predictive > Fraction(0, 1)
            and (
                current_partition.class_count < predictive_partition.class_count
                or _compute_max_fiber_size(current_partition, predictive_partition) > 1
            )
        ):
            return interface_id
    return manifest.interfaces_to_measure[0]


def _select_memory_wheel_loop_action(
    package: RouteTransportPackage,
    manifest: BenchmarkManifest,
    flagship_interface_id: str,
):
    applicable_loop_ids = tuple(
        loop_id
        for loop_id in manifest.loops_to_test
        if package.get_loop(loop_id).interface_id == flagship_interface_id
    )
    for loop_id in applicable_loop_ids:
        current_action = compute_current_loop_action(package, loop_id)
        predictive_action = compute_predictive_loop_action(package, loop_id)
        if current_action.is_trivial and not predictive_action.is_trivial:
            return loop_id, current_action, predictive_action

    first_loop_id = applicable_loop_ids[0]
    return (
        first_loop_id,
        compute_current_loop_action(package, first_loop_id),
        compute_predictive_loop_action(package, first_loop_id),
    )
