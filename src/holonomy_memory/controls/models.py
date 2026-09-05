from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from ..schemas import AuditStatus, ClassLabel, DiscrepancyMetricName, PerturbationKind


@dataclass(frozen=True)
class InterfaceEvidenceSummary:
    benchmark_id: str
    interface_id: str
    history_count: int
    current_class_count: int
    predictive_class_count: int
    witness_count: int
    max_fiber_size: int
    discrepancy_metric_name: DiscrepancyMetricName
    discrepancy_metric_value: Fraction
    current_loop_is_trivial: bool | None = None
    predictive_loop_is_nontrivial: bool | None = None
    robustness_fraction: Fraction | None = None


@dataclass(frozen=True)
class SupportFixationCheckResult:
    status: AuditStatus
    base_benchmark_id: str
    compared_benchmark_id: str
    same_support_required: bool
    base_support_id: str
    compared_support_id: str
    is_same_support: bool
    mismatch_reasons: tuple[str, ...]
    base_support_labels: tuple[str, ...]
    compared_support_labels: tuple[str, ...]
    base_support_projection: tuple[tuple[str, str], ...]
    compared_support_projection: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CurrentizationCheckResult:
    status: AuditStatus
    manifest_id: str
    base_benchmark_id: str
    refined_benchmark_id: str
    interface_id: str
    same_support_required: bool
    base_witness_count: int
    refined_witness_count: int
    base_discrepancy_value: Fraction
    refined_discrepancy_value: Fraction
    dissolved: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FlatteningCheckResult:
    status: AuditStatus
    manifest_id: str
    base_benchmark_id: str
    completed_benchmark_id: str
    interface_id: str
    same_support_required: bool
    base_witness_count: int
    completed_witness_count: int
    base_discrepancy_value: Fraction
    completed_discrepancy_value: Fraction
    collapsed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PerturbationTargetResolution:
    target_path: str
    perturbation_kind: PerturbationKind
    resolved: bool
    resolved_location: str | None
    resolved_type: str | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PerturbationSweepPlan:
    sweep_id: str
    benchmark_id: str
    seed: int
    trial_count: int
    resolved_targets: tuple[PerturbationTargetResolution, ...]
    trial_ids: tuple[str, ...]
    trial_seeds: tuple[int, ...]


@dataclass(frozen=True)
class PerturbationHookResult:
    status: AuditStatus
    sweep_id: str
    benchmark_id: str
    resolved_target_count: int
    unresolved_target_count: int
    trial_count: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ClassificationEvidence:
    benchmark_id: str
    interface_id: str
    witness_count: int
    discrepancy_metric_name: DiscrepancyMetricName
    discrepancy_metric_value: Fraction
    support_fixation_status: AuditStatus
    currentization_status: AuditStatus
    flattening_status: AuditStatus
    artifact_trap_flag: bool
    dissipative_flag: bool
    current_loop_is_trivial: bool | None = None
    predictive_loop_is_nontrivial: bool | None = None
    robustness_fraction: Fraction | None = None


@dataclass(frozen=True)
class ClassificationResult:
    benchmark_id: str
    interface_id: str
    class_label: ClassLabel
    reasons: tuple[str, ...]
    evidence: ClassificationEvidence
