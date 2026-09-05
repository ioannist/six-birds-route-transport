from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from ..core import RouteTransportPackage
from ..schemas import DiscrepancyMetricName
from .quotients import compute_current_partition
from .signatures import compute_future_signature, resolve_interface_history_ids


@dataclass(frozen=True)
class DiscrepancyMetricResult:
    metric_name: DiscrepancyMetricName
    interface_id: str
    metric_value: Fraction
    current_class_id: str | None = None
    history_pair: tuple[str, str] | None = None
    continuation_id: str | None = None
    event_id: str | None = None


def compute_exact_max_abs_future_gap(
    package: RouteTransportPackage,
    interface_id: str,
    history_ids: list[str] | tuple[str, ...] | None = None,
) -> DiscrepancyMetricResult:
    ordered_history_ids = resolve_interface_history_ids(package, interface_id, history_ids)
    current_partition = compute_current_partition(package, interface_id, ordered_history_ids)
    future_signatures = {
        history_id: compute_future_signature(package, history_id, interface_id=interface_id)
        for history_id in ordered_history_ids
    }

    max_gap = Fraction(0, 1)
    argmax_current_class_id: str | None = None
    argmax_history_pair: tuple[str, str] | None = None
    argmax_continuation_id: str | None = None
    argmax_event_id: str | None = None

    for current_class in current_partition.classes:
        members = current_class.member_history_ids
        for left_index, left_history_id in enumerate(members):
            for right_history_id in members[left_index + 1 :]:
                left_signature = future_signatures[left_history_id]
                right_signature = future_signatures[right_history_id]
                for left_entry, right_entry in zip(
                    left_signature.continuation_event_statistics,
                    right_signature.continuation_event_statistics,
                    strict=True,
                ):
                    continuation_id, _, event_id, left_value = left_entry
                    _, _, _, right_value = right_entry
                    gap = abs(left_value - right_value)
                    if gap > max_gap:
                        max_gap = gap
                        argmax_current_class_id = current_class.class_id
                        argmax_history_pair = (left_history_id, right_history_id)
                        argmax_continuation_id = continuation_id
                        argmax_event_id = event_id

    return DiscrepancyMetricResult(
        metric_name=DiscrepancyMetricName.EXACT_MAX_ABS_FUTURE_GAP,
        interface_id=interface_id,
        metric_value=max_gap,
        current_class_id=argmax_current_class_id,
        history_pair=argmax_history_pair,
        continuation_id=argmax_continuation_id,
        event_id=argmax_event_id,
    )
