from __future__ import annotations

from fractions import Fraction

from ..schemas import AuditStatus, ClassLabel
from .models import ClassificationEvidence, ClassificationResult


def classify_regime(evidence: ClassificationEvidence) -> ClassificationResult:
    """Apply the deterministic first-pass rule order over normalized audit evidence."""

    reasons: list[str] = []
    discrepancy_is_zero = evidence.discrepancy_metric_value == Fraction(0, 1)
    has_residue = evidence.witness_count > 0 or evidence.discrepancy_metric_value > Fraction(0, 1)
    support_failed = evidence.support_fixation_status == AuditStatus.FAILED
    flattening_passed = evidence.flattening_status == AuditStatus.PASSED
    currentization_passed = evidence.currentization_status == AuditStatus.PASSED

    if evidence.artifact_trap_flag:
        reasons.append("artifact_trap_flag is set")
        label = ClassLabel.ARTIFACT_TRAP
    elif evidence.witness_count == 0 and discrepancy_is_zero:
        reasons.append("witness count is zero and discrepancy is exactly zero")
        label = ClassLabel.FLAT
    elif flattening_passed:
        reasons.append("flattening check passed")
        label = ClassLabel.FLATTENABLE
    elif currentization_passed:
        reasons.append("currentization check passed")
        label = ClassLabel.EXPLICIT_LATENT
    elif evidence.dissipative_flag:
        reasons.append("dissipative_flag is set")
        label = ClassLabel.DISSIPATIVE
    elif has_residue and not support_failed and not flattening_passed and not currentization_passed:
        reasons.append("nontrivial predictive residue remains under non-failing controls")
        label = ClassLabel.COHERENT_CANDIDATE
    else:
        if support_failed:
            reasons.append("support fixation failed; falling back conservatively")
        else:
            reasons.append("evidence is incomplete for a more specific label")
        label = ClassLabel.COHERENT_CANDIDATE if has_residue else ClassLabel.FLAT

    return ClassificationResult(
        benchmark_id=evidence.benchmark_id,
        interface_id=evidence.interface_id,
        class_label=label,
        reasons=tuple(reasons),
        evidence=evidence,
    )
