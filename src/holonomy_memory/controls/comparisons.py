from __future__ import annotations

from fractions import Fraction

from ..schemas import AuditStatus, CompletionManifest, CurrentizationManifest
from .exceptions import ControlInputMismatchError
from .models import (
    CurrentizationCheckResult,
    FlatteningCheckResult,
    InterfaceEvidenceSummary,
    SupportFixationCheckResult,
)


def check_currentization(
    manifest: CurrentizationManifest,
    base_summary: InterfaceEvidenceSummary,
    refined_summary: InterfaceEvidenceSummary,
    support_check: SupportFixationCheckResult | None = None,
) -> CurrentizationCheckResult:
    reasons: list[str] = []

    try:
        _validate_summary_pair(
            manifest.base_benchmark_id,
            manifest.refined_benchmark_id,
            base_summary,
            refined_summary,
        )
    except ControlInputMismatchError as exc:
        reasons.append(str(exc))
        return CurrentizationCheckResult(
            status=AuditStatus.FAILED,
            manifest_id=manifest.manifest_id,
            base_benchmark_id=manifest.base_benchmark_id,
            refined_benchmark_id=manifest.refined_benchmark_id,
            interface_id=base_summary.interface_id,
            same_support_required=manifest.same_support_required,
            base_witness_count=base_summary.witness_count,
            refined_witness_count=refined_summary.witness_count,
            base_discrepancy_value=base_summary.discrepancy_metric_value,
            refined_discrepancy_value=refined_summary.discrepancy_metric_value,
            dissolved=False,
            reasons=tuple(reasons),
        )

    if (
        manifest.same_support_required
        and support_check is not None
        and support_check.status == AuditStatus.FAILED
    ):
        reasons.append("support fixation precondition failed")
        return CurrentizationCheckResult(
            status=AuditStatus.FAILED,
            manifest_id=manifest.manifest_id,
            base_benchmark_id=manifest.base_benchmark_id,
            refined_benchmark_id=manifest.refined_benchmark_id,
            interface_id=base_summary.interface_id,
            same_support_required=manifest.same_support_required,
            base_witness_count=base_summary.witness_count,
            refined_witness_count=refined_summary.witness_count,
            base_discrepancy_value=base_summary.discrepancy_metric_value,
            refined_discrepancy_value=refined_summary.discrepancy_metric_value,
            dissolved=False,
            reasons=tuple(reasons),
        )

    base_has_residue = _has_predictive_residue(base_summary)
    refined_is_dissolved = _is_flat_summary(refined_summary)
    if not base_has_residue:
        reasons.append("base evidence has no predictive residue to dissolve")
        status = AuditStatus.INCONCLUSIVE
        dissolved = False
    elif refined_is_dissolved:
        reasons.append("refined evidence dissolved predictive residue")
        status = AuditStatus.PASSED
        dissolved = True
    else:
        reasons.append("refined evidence still has predictive residue")
        status = AuditStatus.FAILED
        dissolved = False

    return CurrentizationCheckResult(
        status=status,
        manifest_id=manifest.manifest_id,
        base_benchmark_id=manifest.base_benchmark_id,
        refined_benchmark_id=manifest.refined_benchmark_id,
        interface_id=base_summary.interface_id,
        same_support_required=manifest.same_support_required,
        base_witness_count=base_summary.witness_count,
        refined_witness_count=refined_summary.witness_count,
        base_discrepancy_value=base_summary.discrepancy_metric_value,
        refined_discrepancy_value=refined_summary.discrepancy_metric_value,
        dissolved=dissolved,
        reasons=tuple(reasons),
    )


def check_flattening(
    manifest: CompletionManifest,
    base_summary: InterfaceEvidenceSummary,
    completed_summary: InterfaceEvidenceSummary,
    support_check: SupportFixationCheckResult | None = None,
) -> FlatteningCheckResult:
    reasons: list[str] = []

    try:
        _validate_summary_pair(
            manifest.base_benchmark_id,
            manifest.completed_benchmark_id,
            base_summary,
            completed_summary,
        )
    except ControlInputMismatchError as exc:
        reasons.append(str(exc))
        return FlatteningCheckResult(
            status=AuditStatus.FAILED,
            manifest_id=manifest.manifest_id,
            base_benchmark_id=manifest.base_benchmark_id,
            completed_benchmark_id=manifest.completed_benchmark_id,
            interface_id=base_summary.interface_id,
            same_support_required=manifest.same_support_required,
            base_witness_count=base_summary.witness_count,
            completed_witness_count=completed_summary.witness_count,
            base_discrepancy_value=base_summary.discrepancy_metric_value,
            completed_discrepancy_value=completed_summary.discrepancy_metric_value,
            collapsed=False,
            reasons=tuple(reasons),
        )

    if (
        manifest.same_support_required
        and support_check is not None
        and support_check.status == AuditStatus.FAILED
    ):
        reasons.append("support fixation precondition failed")
        return FlatteningCheckResult(
            status=AuditStatus.FAILED,
            manifest_id=manifest.manifest_id,
            base_benchmark_id=manifest.base_benchmark_id,
            completed_benchmark_id=manifest.completed_benchmark_id,
            interface_id=base_summary.interface_id,
            same_support_required=manifest.same_support_required,
            base_witness_count=base_summary.witness_count,
            completed_witness_count=completed_summary.witness_count,
            base_discrepancy_value=base_summary.discrepancy_metric_value,
            completed_discrepancy_value=completed_summary.discrepancy_metric_value,
            collapsed=False,
            reasons=tuple(reasons),
        )

    base_has_residue = _has_predictive_residue(base_summary)
    completed_is_collapsed = _is_flat_summary(completed_summary)
    if not base_has_residue:
        reasons.append("base evidence has no predictive residue to collapse")
        status = AuditStatus.INCONCLUSIVE
        collapsed = False
    elif completed_is_collapsed:
        reasons.append("completed evidence collapsed predictive residue")
        status = AuditStatus.PASSED
        collapsed = True
    else:
        reasons.append("completed evidence still has predictive residue")
        status = AuditStatus.FAILED
        collapsed = False

    return FlatteningCheckResult(
        status=status,
        manifest_id=manifest.manifest_id,
        base_benchmark_id=manifest.base_benchmark_id,
        completed_benchmark_id=manifest.completed_benchmark_id,
        interface_id=base_summary.interface_id,
        same_support_required=manifest.same_support_required,
        base_witness_count=base_summary.witness_count,
        completed_witness_count=completed_summary.witness_count,
        base_discrepancy_value=base_summary.discrepancy_metric_value,
        completed_discrepancy_value=completed_summary.discrepancy_metric_value,
        collapsed=collapsed,
        reasons=tuple(reasons),
    )


def _validate_summary_pair(
    expected_base_benchmark_id: str,
    expected_compared_benchmark_id: str,
    base_summary: InterfaceEvidenceSummary,
    compared_summary: InterfaceEvidenceSummary,
) -> None:
    if base_summary.benchmark_id != expected_base_benchmark_id:
        raise ControlInputMismatchError(
            f"base summary benchmark_id {base_summary.benchmark_id} does not match "
            f"{expected_base_benchmark_id}"
        )
    if compared_summary.benchmark_id != expected_compared_benchmark_id:
        raise ControlInputMismatchError(
            f"compared summary benchmark_id {compared_summary.benchmark_id} does not match "
            f"{expected_compared_benchmark_id}"
        )
    if base_summary.interface_id != compared_summary.interface_id:
        raise ControlInputMismatchError("interface summaries must share the same interface_id")


def _has_predictive_residue(summary: InterfaceEvidenceSummary) -> bool:
    return summary.witness_count > 0 or summary.discrepancy_metric_value > Fraction(0, 1)


def _is_flat_summary(summary: InterfaceEvidenceSummary) -> bool:
    return (
        summary.witness_count == 0
        and summary.discrepancy_metric_value == Fraction(0, 1)
    )
