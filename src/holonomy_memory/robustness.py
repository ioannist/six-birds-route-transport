from __future__ import annotations

import csv
import hashlib
import json
import random
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from .analysis import (
    compute_current_loop_action,
    compute_predictive_loop_action,
    compute_predictive_transport_map,
    resolve_interface_history_ids,
)
from .benchmarks import REPO_ROOT
from .controls import resolve_perturbation_targets
from .runner import _execute_benchmark_manifest
from .schemas import (
    AuditStatus,
    BenchmarkManifest,
    ClassLabel,
    PerturbationKind,
    RouteTransportPackageConfig,
)
from .validation import load_perturbation_sweep
from .runner import _resolve_benchmark_manifest


CORE_ROBUSTNESS_BENCHMARK_IDS = (
    "flat_control",
    "protocol_trap_honest",
    "flattenable_completed",
    "latent_memory_base",
    "latent_memory_refined",
    "dissipative_memory",
    "memory_wheel",
)


@dataclass(frozen=True)
class RobustnessInterfaceMetrics:
    interface_id: str
    history_count: int
    current_quotient_size: int
    predictive_quotient_size: int
    witness_count: int
    max_fiber_size: int
    discrepancy_metric_value: Fraction
    current_loop_score: Fraction
    predictive_loop_score: Fraction
    support_fixation_status: AuditStatus
    currentization_status: AuditStatus
    flattening_status: AuditStatus
    class_label: ClassLabel


@dataclass(frozen=True)
class RobustnessTrialRecord:
    benchmark_id: str
    trial_id: str
    trial_seed: int
    validation_status: str
    run_status: str
    predicate_pass: bool
    failure_reasons: tuple[str, ...]
    interface_metrics: tuple[RobustnessInterfaceMetrics, ...]
    transport_collapse_persisted: bool | None = None
    transport_collapse_continuation_id: str | None = None
    transport_collapse_mapping: tuple[str, ...] = ()
    designated_loop_id: str | None = None
    predictive_moved_class_ids: tuple[str, ...] = ()
    predictive_moved_class_fraction: Fraction | None = None


@dataclass(frozen=True)
class RobustnessBenchmarkSummary:
    benchmark_id: str
    predicate_name: str
    trial_count: int
    successful_trial_count: int
    predicate_pass_count: int
    survival_fraction: Fraction
    required_threshold: Fraction
    meets_threshold: bool
    json_artifact_path: Path
    csv_artifact_path: Path
    ops_note_path: Path
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RobustnessSuiteSummary:
    suite_id: str
    seed: int
    benchmark_summaries: tuple[RobustnessBenchmarkSummary, ...]
    overall_pass: bool
    json_artifact_path: Path
    csv_artifact_path: Path
    ops_note_path: Path


@dataclass(frozen=True)
class RobustnessRunArtifacts:
    benchmark_id: str | None
    suite_id: str | None
    seed: int
    json_artifact_paths: tuple[Path, ...]
    csv_artifact_paths: tuple[Path, ...]
    ops_note_paths: tuple[Path, ...]
    benchmark_summary: RobustnessBenchmarkSummary | None = None
    suite_summary: RobustnessSuiteSummary | None = None


def run_robustness_sweep(
    *,
    benchmark_id: str | None = None,
    manifest_path: str | Path | None = None,
    seed: int = 0,
    output_root: str | Path | None = None,
) -> RobustnessRunArtifacts:
    resolved_manifest_path, manifest = _resolve_benchmark_manifest(
        benchmark_id=benchmark_id,
        manifest_path=manifest_path,
    )
    if manifest.perturbation_sweep_ref is None:
        raise ValueError(
            f"benchmark {manifest.benchmark_id} does not define perturbation_sweep_ref"
        )

    sweep_path = (REPO_ROOT / manifest.perturbation_sweep_ref).resolve()
    sweep = load_perturbation_sweep(sweep_path)
    bundle = _execute_benchmark_manifest(
        manifest,
        manifest_path=resolved_manifest_path,
        seed=seed,
    )
    resolutions = resolve_perturbation_targets(bundle.package_config, sweep)
    if any(not resolution.resolved for resolution in resolutions):
        unresolved = ", ".join(
            resolution.target_path for resolution in resolutions if not resolution.resolved
        )
        raise ValueError(
            f"perturbation targets did not resolve for {manifest.benchmark_id}: {unresolved}"
        )

    trial_records: list[RobustnessTrialRecord] = []
    warnings: list[str] = []
    for trial_index in range(sweep.trial_count):
        trial_id = f"{sweep.sweep_id}:trial:{trial_index}"
        trial_seed = _derive_trial_seed(
            benchmark_id=manifest.benchmark_id,
            sweep_id=sweep.sweep_id,
            base_seed=seed,
            trial_index=trial_index,
        )
        trial_records.append(
            _run_robustness_trial(
                manifest=manifest,
                manifest_path=resolved_manifest_path,
                base_package_config=bundle.package_config,
                base_package_config_path=bundle.package_config_path,
                sweep=sweep,
                trial_id=trial_id,
                trial_seed=trial_seed,
            )
        )

    pass_count = sum(1 for record in trial_records if record.predicate_pass)
    successful_trial_count = sum(
        1
        for record in trial_records
        if record.validation_status == "passed" and record.run_status == "passed"
    )
    threshold = _required_threshold_for_benchmark(manifest.benchmark_id)
    survival_fraction = Fraction(pass_count, sweep.trial_count)
    meets_threshold = survival_fraction >= threshold

    root = Path(output_root) if output_root is not None else REPO_ROOT
    json_path = root / "artifacts" / "results" / "robustness" / (
        f"{manifest.benchmark_id}.robustness.json"
    )
    csv_path = root / "artifacts" / "tables" / f"robustness_{manifest.benchmark_id}.csv"
    ops_path = root / "docs" / "results" / f"{manifest.benchmark_id}.robustness.md"
    for path in (json_path, csv_path, ops_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    summary = RobustnessBenchmarkSummary(
        benchmark_id=manifest.benchmark_id,
        predicate_name=_predicate_name_for_benchmark(manifest.benchmark_id),
        trial_count=sweep.trial_count,
        successful_trial_count=successful_trial_count,
        predicate_pass_count=pass_count,
        survival_fraction=survival_fraction,
        required_threshold=threshold,
        meets_threshold=meets_threshold,
        json_artifact_path=json_path,
        csv_artifact_path=csv_path,
        ops_note_path=ops_path,
        warnings=tuple(warnings),
    )

    _write_robustness_benchmark_json(
        json_path=json_path,
        summary=summary,
        trial_records=tuple(trial_records),
        perturbation_manifest_path=sweep_path,
        resolved_targets=resolutions,
        seed=seed,
    )
    _write_robustness_benchmark_csv(csv_path, tuple(trial_records))
    _write_robustness_benchmark_note(
        ops_path=ops_path,
        summary=summary,
        trial_records=tuple(trial_records),
        perturbation_manifest_path=sweep_path,
        resolved_targets=resolutions,
        base_seed=seed,
    )

    return RobustnessRunArtifacts(
        benchmark_id=manifest.benchmark_id,
        suite_id=None,
        seed=seed,
        json_artifact_paths=(json_path,),
        csv_artifact_paths=(csv_path,),
        ops_note_paths=(ops_path,),
        benchmark_summary=summary,
    )


def run_core_robustness_suite(
    *,
    seed: int = 0,
    output_root: str | Path | None = None,
    benchmark_ids: tuple[str, ...] = CORE_ROBUSTNESS_BENCHMARK_IDS,
) -> RobustnessRunArtifacts:
    benchmark_artifacts = tuple(
        run_robustness_sweep(
            benchmark_id=benchmark_id,
            seed=seed,
            output_root=output_root,
        )
        for benchmark_id in benchmark_ids
    )
    benchmark_summaries = tuple(
        artifact.benchmark_summary
        for artifact in benchmark_artifacts
        if artifact.benchmark_summary is not None
    )
    root = Path(output_root) if output_root is not None else REPO_ROOT
    json_path = root / "artifacts" / "results" / "robustness" / "core_suite.robustness.json"
    csv_path = root / "artifacts" / "tables" / "robustness_core_suite.csv"
    ops_path = root / "docs" / "results" / "robustness_core_suite.md"
    for path in (json_path, csv_path, ops_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    suite_summary = RobustnessSuiteSummary(
        suite_id="core_suite",
        seed=seed,
        benchmark_summaries=benchmark_summaries,
        overall_pass=all(summary.meets_threshold for summary in benchmark_summaries),
        json_artifact_path=json_path,
        csv_artifact_path=csv_path,
        ops_note_path=ops_path,
    )

    _write_robustness_suite_json(json_path, suite_summary)
    _write_robustness_suite_csv(csv_path, benchmark_summaries)
    _write_robustness_suite_note(ops_path, suite_summary, benchmark_ids)

    return RobustnessRunArtifacts(
        benchmark_id=None,
        suite_id="core_suite",
        seed=seed,
        json_artifact_paths=tuple(
            summary.json_artifact_path for summary in benchmark_summaries
        )
        + (json_path,),
        csv_artifact_paths=tuple(
            summary.csv_artifact_path for summary in benchmark_summaries
        )
        + (csv_path,),
        ops_note_paths=tuple(
            summary.ops_note_path for summary in benchmark_summaries
        )
        + (ops_path,),
        suite_summary=suite_summary,
    )


def _run_robustness_trial(
    *,
    manifest: BenchmarkManifest,
    manifest_path: Path,
    base_package_config: RouteTransportPackageConfig,
    base_package_config_path: Path | None,
    sweep: Any,
    trial_id: str,
    trial_seed: int,
) -> RobustnessTrialRecord:
    try:
        perturbed_config = _apply_perturbation_trial(
            base_package_config,
            sweep,
            trial_seed=trial_seed,
        )
    except Exception as exc:
        return RobustnessTrialRecord(
            benchmark_id=manifest.benchmark_id,
            trial_id=trial_id,
            trial_seed=trial_seed,
            validation_status="failed",
            run_status="skipped",
            predicate_pass=False,
            failure_reasons=(f"perturbation application failed: {exc}",),
            interface_metrics=(),
        )

    try:
        validated_config = RouteTransportPackageConfig.model_validate(perturbed_config)
    except Exception as exc:
        return RobustnessTrialRecord(
            benchmark_id=manifest.benchmark_id,
            trial_id=trial_id,
            trial_seed=trial_seed,
            validation_status="failed",
            run_status="skipped",
            predicate_pass=False,
            failure_reasons=(f"validation failed: {exc}",),
            interface_metrics=(),
        )

    try:
        bundle = _execute_benchmark_manifest(
            manifest,
            manifest_path=manifest_path,
            seed=trial_seed,
            package_config=validated_config,
            package_config_path=base_package_config_path,
        )
    except Exception as exc:
        return RobustnessTrialRecord(
            benchmark_id=manifest.benchmark_id,
            trial_id=trial_id,
            trial_seed=trial_seed,
            validation_status="passed",
            run_status="failed",
            predicate_pass=False,
            failure_reasons=(f"benchmark execution failed: {exc}",),
            interface_metrics=(),
        )

    interface_metrics = _extract_interface_metrics(bundle)
    predicate_pass, failure_reasons, extra_fields = _evaluate_survival_predicate(
        manifest=manifest,
        bundle=bundle,
        interface_metrics=interface_metrics,
    )
    return RobustnessTrialRecord(
        benchmark_id=manifest.benchmark_id,
        trial_id=trial_id,
        trial_seed=trial_seed,
        validation_status="passed",
        run_status="passed",
        predicate_pass=predicate_pass,
        failure_reasons=failure_reasons,
        interface_metrics=interface_metrics,
        transport_collapse_persisted=extra_fields["transport_collapse_persisted"],
        transport_collapse_continuation_id=extra_fields["transport_collapse_continuation_id"],
        transport_collapse_mapping=extra_fields["transport_collapse_mapping"],
        designated_loop_id=extra_fields["designated_loop_id"],
        predictive_moved_class_ids=extra_fields["predictive_moved_class_ids"],
        predictive_moved_class_fraction=extra_fields["predictive_moved_class_fraction"],
    )


def _extract_interface_metrics(bundle: Any) -> tuple[RobustnessInterfaceMetrics, ...]:
    return tuple(
        RobustnessInterfaceMetrics(
            interface_id=record.interface_id,
            history_count=record.history_count,
            current_quotient_size=record.current_quotient_size,
            predictive_quotient_size=record.predictive_quotient_size,
            witness_count=record.witness_count,
            max_fiber_size=record.max_fiber_size,
            discrepancy_metric_value=execution.discrepancy_metric_value,
            current_loop_score=execution.loop_action_score_current,
            predictive_loop_score=execution.loop_action_score_predictive,
            support_fixation_status=record.support_fixation_status,
            currentization_status=record.currentization_status,
            flattening_status=record.flattening_status,
            class_label=record.class_label,
        )
        for record, execution in zip(
            bundle.result_manifest.records,
            bundle.executions,
            strict=True,
        )
    )


def _evaluate_survival_predicate(
    *,
    manifest: BenchmarkManifest,
    bundle: Any,
    interface_metrics: tuple[RobustnessInterfaceMetrics, ...],
) -> tuple[bool, tuple[str, ...], dict[str, object]]:
    benchmark_id = manifest.benchmark_id
    extra_fields: dict[str, object] = {
        "transport_collapse_persisted": None,
        "transport_collapse_continuation_id": None,
        "transport_collapse_mapping": (),
        "designated_loop_id": None,
        "predictive_moved_class_ids": (),
        "predictive_moved_class_fraction": None,
    }
    if benchmark_id in {"flat_control", "protocol_trap_honest"}:
        for metric in interface_metrics:
            if not (
                metric.witness_count == 0
                and metric.discrepancy_metric_value == Fraction(0, 1)
                and metric.current_loop_score == Fraction(0, 1)
                and metric.predictive_loop_score == Fraction(0, 1)
                and metric.class_label == ClassLabel.FLAT
            ):
                return False, (
                    f"{metric.interface_id} did not stay fully flat",
                ), extra_fields
        return True, (), extra_fields

    if benchmark_id == "flattenable_completed":
        for metric in interface_metrics:
            if not (
                metric.witness_count == 0
                and metric.current_quotient_size == metric.predictive_quotient_size
                and metric.discrepancy_metric_value == Fraction(0, 1)
                and metric.current_loop_score == Fraction(0, 1)
                and metric.predictive_loop_score == Fraction(0, 1)
                and metric.class_label == ClassLabel.FLAT
            ):
                return False, (
                    f"{metric.interface_id} did not stay collapsed",
                ), extra_fields
        return True, (), extra_fields

    if benchmark_id == "latent_memory_base":
        for metric in interface_metrics:
            if (
                metric.witness_count > 0
                and metric.discrepancy_metric_value > Fraction(0, 1)
                and (
                    metric.current_quotient_size < metric.predictive_quotient_size
                    or metric.max_fiber_size > 1
                )
            ):
                return True, (), extra_fields
        return False, ("no measured interface retained the latent witness",), extra_fields

    if benchmark_id == "latent_memory_refined":
        for metric in interface_metrics:
            if not (
                metric.witness_count == 0
                and metric.current_quotient_size == metric.predictive_quotient_size
                and metric.max_fiber_size == 1
                and metric.discrepancy_metric_value == Fraction(0, 1)
                and metric.class_label == ClassLabel.FLAT
            ):
                return False, (
                    f"{metric.interface_id} did not stay refined-flat",
                ), extra_fields
        return True, (), extra_fields

    if benchmark_id == "dissipative_memory":
        if len(interface_metrics) < 2:
            return False, ("dissipative benchmark lost later interfaces",), extra_fields
        earliest = interface_metrics[0]
        later_metrics = interface_metrics[1:]
        collapsed_later = [
            metric
            for metric in later_metrics
            if (
                metric.witness_count == 0
                and metric.discrepancy_metric_value == Fraction(0, 1)
                and metric.current_quotient_size == metric.predictive_quotient_size
                and metric.max_fiber_size == 1
                and metric.class_label == ClassLabel.FLAT
            )
        ]
        if not (
            earliest.witness_count > 0
            and earliest.discrepancy_metric_value > Fraction(0, 1)
            and earliest.class_label == ClassLabel.DISSIPATIVE
            and (
                earliest.current_quotient_size < earliest.predictive_quotient_size
                or earliest.max_fiber_size > 1
            )
        ):
            return False, ("earliest interface did not retain dissipative residue",), extra_fields
        if not collapsed_later:
            return False, ("no later interface stayed collapsed",), extra_fields
        transport_ok, continuation_id, mapping = _dissipative_transport_collapse_evidence(
            bundle.package,
            manifest,
            tuple(metric.interface_id for metric in collapsed_later),
        )
        extra_fields["transport_collapse_persisted"] = transport_ok
        extra_fields["transport_collapse_continuation_id"] = continuation_id
        extra_fields["transport_collapse_mapping"] = mapping
        if not transport_ok:
            return False, ("transport-collapse evidence did not persist",), extra_fields
        return True, (), extra_fields

    if benchmark_id == "memory_wheel":
        for metric in interface_metrics:
            if not (
                metric.witness_count > 0
                and metric.discrepancy_metric_value > Fraction(0, 1)
                and metric.current_loop_score == Fraction(0, 1)
                and metric.predictive_loop_score > Fraction(0, 1)
                and metric.class_label == ClassLabel.COHERENT_CANDIDATE
                and (
                    metric.current_quotient_size < metric.predictive_quotient_size
                    or metric.max_fiber_size > 1
                )
                and metric.flattening_status != AuditStatus.PASSED
                and metric.currentization_status != AuditStatus.PASSED
            ):
                continue
            loop_id, moved_ids, moved_fraction = _memory_wheel_loop_evidence(
                bundle.package,
                manifest,
                metric.interface_id,
            )
            extra_fields["designated_loop_id"] = loop_id
            extra_fields["predictive_moved_class_ids"] = moved_ids
            extra_fields["predictive_moved_class_fraction"] = moved_fraction
            return True, (), extra_fields
        return False, ("no measured interface retained the memory-wheel asymmetry",), extra_fields

    raise ValueError(f"unsupported robustness benchmark: {benchmark_id}")


def _dissipative_transport_collapse_evidence(
    package: Any,
    manifest: BenchmarkManifest,
    collapsed_targets: tuple[str, ...],
) -> tuple[bool, str | None, tuple[str, ...]]:
    source_interface_id = manifest.interfaces_to_measure[0]
    candidate_continuations = tuple(
        continuation.continuation_id
        for continuation in package.continuations
        if continuation.source_interface_id == source_interface_id
        and continuation.target_interface_id in collapsed_targets
    )
    for continuation_id in candidate_continuations:
        transport_map = compute_predictive_transport_map(package, continuation_id)
        target_ids = tuple(
            class_image.target_class_id for class_image in transport_map.class_images
        )
        if len(set(target_ids)) < len(target_ids):
            mapping = tuple(
                f"{class_image.source_class_id}->{class_image.target_class_id}"
                for class_image in transport_map.class_images
            )
            return True, continuation_id, mapping
    return False, None, ()


def _memory_wheel_loop_evidence(
    package: Any,
    manifest: BenchmarkManifest,
    interface_id: str,
) -> tuple[str | None, tuple[str, ...], Fraction | None]:
    history_ids = resolve_interface_history_ids(package, interface_id)
    for loop_id in manifest.loops_to_test:
        if package.get_loop(loop_id).interface_id != interface_id:
            continue
        current_action = compute_current_loop_action(package, loop_id, history_ids)
        predictive_action = compute_predictive_loop_action(package, loop_id, history_ids)
        if current_action.is_trivial and not predictive_action.is_trivial:
            return (
                loop_id,
                predictive_action.moved_class_ids,
                predictive_action.moved_class_fraction,
            )
    return None, (), None


def _apply_perturbation_trial(
    base_package_config: RouteTransportPackageConfig,
    sweep: Any,
    *,
    trial_seed: int,
) -> dict[str, object]:
    root = deepcopy(base_package_config.model_dump(mode="python"))
    for target_index, target in enumerate(sweep.targets):
        _apply_target_perturbation(
            root,
            target_path=target.target_path,
            perturbation_kind=target.perturbation_kind,
            magnitude=target.magnitude,
            radius=target.radius,
            lower_bound=target.lower_bound,
            upper_bound=target.upper_bound,
            trial_seed=trial_seed,
            target_index=target_index,
        )
    return root


def _apply_target_perturbation(
    root: dict[str, object],
    *,
    target_path: str,
    perturbation_kind: PerturbationKind,
    magnitude: float,
    radius: float | None,
    lower_bound: float | None,
    upper_bound: float | None,
    trial_seed: int,
    target_index: int,
) -> None:
    tokens = _tokenize_target_path(target_path)
    container: Any = root
    for token in tokens[:-1]:
        container = container[token]
    leaf = tokens[-1]
    current_value = container[leaf]
    if not isinstance(current_value, (int, float)):
        raise TypeError(f"target {target_path} does not resolve to a numeric leaf")

    delta = _draw_lattice_delta(
        magnitude=magnitude,
        radius=radius,
        trial_seed=trial_seed,
        target_index=target_index,
    )
    current_decimal = Decimal(str(current_value))
    lower_decimal = Decimal(str(lower_bound)) if lower_bound is not None else None
    upper_decimal = Decimal(str(upper_bound)) if upper_bound is not None else None

    if perturbation_kind == PerturbationKind.WEIGHT_SHIFT:
        updated = current_decimal + delta
    elif perturbation_kind == PerturbationKind.ADDITIVE:
        updated = current_decimal + delta
    elif perturbation_kind == PerturbationKind.MULTIPLICATIVE:
        updated = current_decimal * (Decimal("1") + delta)
    else:
        raise ValueError(f"unsupported perturbation kind for executor: {perturbation_kind.value}")

    if lower_decimal is not None and updated < lower_decimal:
        updated = lower_decimal
    if upper_decimal is not None and updated > upper_decimal:
        updated = upper_decimal
    container[leaf] = float(updated)

    if ".probabilities." in target_path:
        _renormalize_nonnegative_mapping(container)
    if ".kernel." in target_path:
        _renormalize_nonnegative_mapping(container)


def _renormalize_nonnegative_mapping(mapping: dict[str, float]) -> None:
    total = Decimal("0")
    values: dict[str, Decimal] = {}
    for key, raw_value in mapping.items():
        decimal_value = max(Decimal("0"), Decimal(str(raw_value)))
        values[key] = decimal_value
        total += decimal_value
    if total == 0:
        raise ValueError("cannot renormalize an all-zero probability-bearing mapping")
    for key, decimal_value in values.items():
        mapping[key] = float(decimal_value / total)


def _draw_lattice_delta(
    *,
    magnitude: float,
    radius: float | None,
    trial_seed: int,
    target_index: int,
) -> Decimal:
    step = Decimal(str(magnitude))
    max_radius = Decimal(str(radius if radius is not None else magnitude))
    if step == 0:
        return Decimal("0")
    step_count = int(max_radius / step)
    lattice = [Decimal(index) * step for index in range(-step_count, step_count + 1)]
    if not lattice:
        lattice = [Decimal("0")]
    rng = random.Random(trial_seed + target_index)
    return lattice[rng.randrange(len(lattice))]


def _tokenize_target_path(path: str) -> tuple[str | int, ...]:
    tokens: list[str | int] = []
    buffer = ""
    index = 0
    while index < len(path):
        character = path[index]
        if character == ".":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            index += 1
            continue
        if character == "[":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            end_index = path.index("]", index)
            tokens.append(int(path[index + 1 : end_index]))
            index = end_index + 1
            continue
        buffer += character
        index += 1
    if buffer:
        tokens.append(buffer)
    return tuple(tokens)


def _derive_trial_seed(
    *,
    benchmark_id: str,
    sweep_id: str,
    base_seed: int,
    trial_index: int,
) -> int:
    digest = hashlib.sha256(
        f"{benchmark_id}|{sweep_id}|{base_seed}|{trial_index}".encode("utf-8")
    ).hexdigest()
    return int(digest[:16], 16)


def _predicate_name_for_benchmark(benchmark_id: str) -> str:
    return {
        "flat_control": "flat_cleared",
        "protocol_trap_honest": "honest_trap_cleared",
        "flattenable_completed": "completed_collapsed",
        "latent_memory_base": "explicit_latent_base_retains_witness",
        "latent_memory_refined": "explicit_latent_refined_dissolves",
        "dissipative_memory": "dissipative_persists",
        "memory_wheel": "memory_wheel_persists",
    }[benchmark_id]


def _required_threshold_for_benchmark(benchmark_id: str) -> Fraction:
    return {
        "flat_control": Fraction(95, 100),
        "protocol_trap_honest": Fraction(95, 100),
        "flattenable_completed": Fraction(80, 100),
        "latent_memory_base": Fraction(80, 100),
        "latent_memory_refined": Fraction(80, 100),
        "dissipative_memory": Fraction(80, 100),
        "memory_wheel": Fraction(80, 100),
    }[benchmark_id]


def _write_robustness_benchmark_json(
    *,
    json_path: Path,
    summary: RobustnessBenchmarkSummary,
    trial_records: tuple[RobustnessTrialRecord, ...],
    perturbation_manifest_path: Path,
    resolved_targets: tuple[object, ...],
    seed: int,
) -> None:
    payload = {
        "benchmark_id": summary.benchmark_id,
        "seed": seed,
        "perturbation_manifest_path": _display_path(perturbation_manifest_path),
        "predicate_name": summary.predicate_name,
        "trial_count": summary.trial_count,
        "successful_trial_count": summary.successful_trial_count,
        "pass_count": summary.predicate_pass_count,
        "survival_fraction": float(summary.survival_fraction),
        "survival_fraction_exact": _fraction_string(summary.survival_fraction),
        "threshold": float(summary.required_threshold),
        "threshold_exact": _fraction_string(summary.required_threshold),
        "meets_threshold": summary.meets_threshold,
        "resolved_targets": [
            getattr(resolution, "target_path", "(unknown)") for resolution in resolved_targets
        ],
        "trials": [_trial_record_payload(record) for record in trial_records],
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_robustness_benchmark_csv(
    csv_path: Path,
    trial_records: tuple[RobustnessTrialRecord, ...],
) -> None:
    fieldnames = [
        "benchmark_id",
        "trial_id",
        "trial_seed",
        "validation_status",
        "run_status",
        "predicate_pass",
        "failure_reason",
        "interface_metrics",
        "transport_collapse_persisted",
        "transport_collapse_continuation_id",
        "transport_collapse_mapping",
        "designated_loop_id",
        "predictive_moved_class_ids",
        "predictive_moved_class_fraction",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in trial_records:
            writer.writerow(
                {
                    "benchmark_id": record.benchmark_id,
                    "trial_id": record.trial_id,
                    "trial_seed": record.trial_seed,
                    "validation_status": record.validation_status,
                    "run_status": record.run_status,
                    "predicate_pass": str(record.predicate_pass).lower(),
                    "failure_reason": "; ".join(record.failure_reasons),
                    "interface_metrics": json.dumps(
                        [
                            _interface_metrics_payload(metric)
                            for metric in record.interface_metrics
                        ],
                        sort_keys=True,
                    ),
                    "transport_collapse_persisted": (
                        ""
                        if record.transport_collapse_persisted is None
                        else str(record.transport_collapse_persisted).lower()
                    ),
                    "transport_collapse_continuation_id": (
                        record.transport_collapse_continuation_id or ""
                    ),
                    "transport_collapse_mapping": ", ".join(record.transport_collapse_mapping),
                    "designated_loop_id": record.designated_loop_id or "",
                    "predictive_moved_class_ids": ", ".join(record.predictive_moved_class_ids),
                    "predictive_moved_class_fraction": (
                        ""
                        if record.predictive_moved_class_fraction is None
                        else _fraction_string(record.predictive_moved_class_fraction)
                    ),
                }
            )


def _write_robustness_benchmark_note(
    *,
    ops_path: Path,
    summary: RobustnessBenchmarkSummary,
    trial_records: tuple[RobustnessTrialRecord, ...],
    perturbation_manifest_path: Path,
    resolved_targets: tuple[object, ...],
    base_seed: int,
) -> None:
    lines = [
        f"# {summary.benchmark_id} robustness",
        "",
        f"- benchmark_id: {summary.benchmark_id}",
        f"- perturbation_manifest_path: {_display_path(perturbation_manifest_path)}",
        f"- base_seed: {base_seed}",
        f"- trial_count: {summary.trial_count}",
        "- resolved_targets: "
        + ", ".join(getattr(target, "target_path", "(unknown)") for target in resolved_targets),
        f"- predicate_name: {summary.predicate_name}",
        f"- threshold: {_fraction_string(summary.required_threshold)}",
        f"- pass_count: {summary.predicate_pass_count}/{summary.trial_count}",
        f"- survival_fraction: {_fraction_string(summary.survival_fraction)}",
        f"- meets_threshold: {str(summary.meets_threshold).lower()}",
        "",
        "## Evidence",
        "",
    ]

    if summary.benchmark_id in {
        "flat_control",
        "protocol_trap_honest",
        "flattenable_completed",
        "latent_memory_refined",
    }:
        lines.append(
            f"- cleared_or_collapsed_trials: {summary.predicate_pass_count}/{summary.trial_count}"
        )
        failure_reason = _most_common_failure_reason(trial_records)
        lines.append(f"- representative_failure_reason: {failure_reason}")
    elif summary.benchmark_id == "latent_memory_base":
        representative = _first_passing_trial(trial_records) or _first_nonempty_trial(trial_records)
        lines.append(
            f"- witness_retention_count: {summary.predicate_pass_count}/{summary.trial_count}"
        )
        if representative is not None and representative.interface_metrics:
            metric = representative.interface_metrics[0]
            lines.append(
                f"- representative_structure: |Q|={metric.current_quotient_size}, "
                f"|M|={metric.predictive_quotient_size}, max_fiber_size={metric.max_fiber_size}"
            )
    elif summary.benchmark_id == "dissipative_memory":
        earliest_survivals = sum(
            1
            for record in trial_records
            if record.predicate_pass and record.interface_metrics
        )
        later_survivals = sum(
            1
            for record in trial_records
            if record.predicate_pass and len(record.interface_metrics) > 1
        )
        lines.append(f"- earliest_interface_survivals: {earliest_survivals}/{summary.trial_count}")
        lines.append(f"- later_interface_survivals: {later_survivals}/{summary.trial_count}")
        representative = next(
            (
                record
                for record in trial_records
                if record.transport_collapse_persisted
            ),
            None,
        )
        if representative is not None:
            lines.append(
                "- representative_transport_collapse: "
                f"{representative.transport_collapse_continuation_id}: "
                f"{', '.join(representative.transport_collapse_mapping)}"
            )
    elif summary.benchmark_id == "memory_wheel":
        loop_retention_count = sum(
            1
            for record in trial_records
            if any(
                metric.predictive_loop_score > Fraction(0, 1)
                for metric in record.interface_metrics
            )
        )
        lines.append(
            f"- witness_retention_count: {summary.predicate_pass_count}/{summary.trial_count}"
        )
        lines.append(
            f"- predictive_loop_nontrivial_count: {loop_retention_count}/{summary.trial_count}"
        )
        representative = _first_passing_trial(trial_records)
        if representative is not None:
            lines.append(
                "- representative_predictive_motion: "
                f"{', '.join(representative.predictive_moved_class_ids) or '(none)'} "
                f"(fraction="
                f"{_fraction_string(representative.predictive_moved_class_fraction or Fraction(0, 1))})"
            )

    lines.extend(["", "## Conclusion", ""])
    if summary.meets_threshold:
        lines.append("- robustness threshold is met for this benchmark")
    else:
        lines.append("- robustness threshold is not met for this benchmark")
    lines.append("")
    ops_path.write_text("\n".join(lines), encoding="utf-8")


def _write_robustness_suite_json(
    json_path: Path,
    suite_summary: RobustnessSuiteSummary,
) -> None:
    payload = {
        "suite_id": suite_summary.suite_id,
        "seed": suite_summary.seed,
        "overall_pass": suite_summary.overall_pass,
        "benchmarks": [
            {
                "benchmark_id": summary.benchmark_id,
                "predicate_name": summary.predicate_name,
                "trial_count": summary.trial_count,
                "pass_count": summary.predicate_pass_count,
                "survival_fraction": float(summary.survival_fraction),
                "survival_fraction_exact": _fraction_string(summary.survival_fraction),
                "threshold": float(summary.required_threshold),
                "threshold_exact": _fraction_string(summary.required_threshold),
                "meets_threshold": summary.meets_threshold,
                "json_artifact_path": _display_path(summary.json_artifact_path),
                "csv_artifact_path": _display_path(summary.csv_artifact_path),
                "ops_note_path": _display_path(summary.ops_note_path),
            }
            for summary in suite_summary.benchmark_summaries
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_robustness_suite_csv(
    csv_path: Path,
    benchmark_summaries: tuple[RobustnessBenchmarkSummary, ...],
) -> None:
    fieldnames = [
        "benchmark_id",
        "predicate_name",
        "trial_count",
        "pass_count",
        "survival_fraction",
        "threshold",
        "meets_threshold",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for summary in benchmark_summaries:
            writer.writerow(
                {
                    "benchmark_id": summary.benchmark_id,
                    "predicate_name": summary.predicate_name,
                    "trial_count": summary.trial_count,
                    "pass_count": summary.predicate_pass_count,
                    "survival_fraction": float(summary.survival_fraction),
                    "threshold": float(summary.required_threshold),
                    "meets_threshold": str(summary.meets_threshold).lower(),
                }
            )


def _write_robustness_suite_note(
    ops_path: Path,
    suite_summary: RobustnessSuiteSummary,
    benchmark_ids: tuple[str, ...],
) -> None:
    lines = [
        "# core robustness suite",
        "",
        f"- seed: {suite_summary.seed}",
        f"- benchmark_list: {', '.join(benchmark_ids)}",
        f"- overall_pass: {str(suite_summary.overall_pass).lower()}",
        "",
        "## Summary",
        "",
    ]
    for summary in suite_summary.benchmark_summaries:
        lines.extend(
            [
                f"### {summary.benchmark_id}",
                f"- predicate_name: {summary.predicate_name}",
                f"- pass_count: {summary.predicate_pass_count}/{summary.trial_count}",
                f"- survival_fraction: {_fraction_string(summary.survival_fraction)}",
                f"- threshold: {_fraction_string(summary.required_threshold)}",
                f"- meets_threshold: {str(summary.meets_threshold).lower()}",
            ]
        )
    lines.extend(["", "## Conclusion", ""])
    if suite_summary.overall_pass:
        lines.append("- the core robustness suite is strong enough to proceed")
    else:
        lines.append("- the core robustness suite is not yet strong enough to proceed")
    lines.append("")
    ops_path.write_text("\n".join(lines), encoding="utf-8")


def _trial_record_payload(record: RobustnessTrialRecord) -> dict[str, object]:
    return {
        "benchmark_id": record.benchmark_id,
        "trial_id": record.trial_id,
        "trial_seed": record.trial_seed,
        "validation_status": record.validation_status,
        "run_status": record.run_status,
        "predicate_pass": record.predicate_pass,
        "failure_reasons": list(record.failure_reasons),
        "interface_metrics": [
            _interface_metrics_payload(metric) for metric in record.interface_metrics
        ],
        "transport_collapse_persisted": record.transport_collapse_persisted,
        "transport_collapse_continuation_id": record.transport_collapse_continuation_id,
        "transport_collapse_mapping": list(record.transport_collapse_mapping),
        "designated_loop_id": record.designated_loop_id,
        "predictive_moved_class_ids": list(record.predictive_moved_class_ids),
        "predictive_moved_class_fraction": (
            None
            if record.predictive_moved_class_fraction is None
            else float(record.predictive_moved_class_fraction)
        ),
        "predictive_moved_class_fraction_exact": (
            None
            if record.predictive_moved_class_fraction is None
            else _fraction_string(record.predictive_moved_class_fraction)
        ),
    }


def _interface_metrics_payload(metric: RobustnessInterfaceMetrics) -> dict[str, object]:
    return {
        "interface_id": metric.interface_id,
        "history_count": metric.history_count,
        "current_quotient_size": metric.current_quotient_size,
        "predictive_quotient_size": metric.predictive_quotient_size,
        "witness_count": metric.witness_count,
        "max_fiber_size": metric.max_fiber_size,
        "discrepancy_metric_value": float(metric.discrepancy_metric_value),
        "discrepancy_metric_value_exact": _fraction_string(metric.discrepancy_metric_value),
        "current_loop_score": float(metric.current_loop_score),
        "current_loop_score_exact": _fraction_string(metric.current_loop_score),
        "predictive_loop_score": float(metric.predictive_loop_score),
        "predictive_loop_score_exact": _fraction_string(metric.predictive_loop_score),
        "support_fixation_status": metric.support_fixation_status.value,
        "currentization_status": metric.currentization_status.value,
        "flattening_status": metric.flattening_status.value,
        "class_label": metric.class_label.value,
    }


def _most_common_failure_reason(trial_records: tuple[RobustnessTrialRecord, ...]) -> str:
    counts: dict[str, int] = {}
    for record in trial_records:
        for reason in record.failure_reasons:
            counts[reason] = counts.get(reason, 0) + 1
    if not counts:
        return "none"
    return min(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[0]


def _first_passing_trial(
    trial_records: tuple[RobustnessTrialRecord, ...],
) -> RobustnessTrialRecord | None:
    return next((record for record in trial_records if record.predicate_pass), None)


def _first_nonempty_trial(
    trial_records: tuple[RobustnessTrialRecord, ...],
) -> RobustnessTrialRecord | None:
    return next((record for record in trial_records if record.interface_metrics), None)


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
