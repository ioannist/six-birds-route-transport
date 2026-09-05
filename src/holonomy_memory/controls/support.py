from __future__ import annotations

from ..core import RouteTransportPackage
from ..schemas import AuditStatus
from .models import SupportFixationCheckResult


def check_support_fixation(
    base_package: RouteTransportPackage,
    compared_package: RouteTransportPackage,
    *,
    same_support_required: bool = True,
    base_id: str | None = None,
    compared_id: str | None = None,
) -> SupportFixationCheckResult:
    base_labels = tuple(base_package.support.visible_support_labels)
    compared_labels = tuple(compared_package.support.visible_support_labels)
    is_same_support = base_labels == compared_labels

    reasons: list[str] = []
    if not is_same_support:
        reasons.append(
            "visible support labels differ: "
            f"{list(base_labels)} != {list(compared_labels)}"
        )

    if is_same_support:
        status = AuditStatus.PASSED
        if base_package.support.support_id != compared_package.support.support_id:
            reasons.append(
                "support ids differ but visible support labels match"
            )
    elif same_support_required:
        status = AuditStatus.FAILED
    else:
        status = AuditStatus.INCONCLUSIVE

    return SupportFixationCheckResult(
        status=status,
        base_benchmark_id=base_id or base_package.package_id,
        compared_benchmark_id=compared_id or compared_package.package_id,
        same_support_required=same_support_required,
        base_support_id=base_package.support.support_id,
        compared_support_id=compared_package.support.support_id,
        is_same_support=is_same_support,
        mismatch_reasons=tuple(reasons),
        base_support_labels=base_labels,
        compared_support_labels=compared_labels,
        base_support_projection=tuple(base_package.state_space.support_projection.items()),
        compared_support_projection=tuple(compared_package.state_space.support_projection.items()),
    )
