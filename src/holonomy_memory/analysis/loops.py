from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from ..core import RouteTransportPackage
from .exceptions import LoopActionUndefinedError, RouteTransportAnalysisError
from .quotients import PartitionKind
from .transport import (
    ClassTransportImage,
    ClassTransportMap,
    compute_current_transport_map,
    compute_predictive_transport_map,
)


@dataclass(frozen=True)
class LoopActionResult:
    partition_kind: PartitionKind
    interface_id: str
    loop_id: str
    class_images: tuple[ClassTransportImage, ...]
    fixed_class_ids: tuple[str, ...]
    moved_class_ids: tuple[str, ...]
    moved_class_count: int
    moved_class_fraction: Fraction
    is_trivial: bool


@dataclass(frozen=True)
class LoopMetricResult:
    metric_name: str
    interface_id: str
    loop_id: str
    partition_kind: PartitionKind
    metric_value: Fraction


def compute_current_loop_action(
    package: RouteTransportPackage,
    loop_id: str,
    history_ids: list[str] | tuple[str, ...] | None = None,
) -> LoopActionResult:
    return _compute_loop_action(
        package,
        loop_id,
        partition_kind="current",
        history_ids=history_ids,
    )


def compute_predictive_loop_action(
    package: RouteTransportPackage,
    loop_id: str,
    history_ids: list[str] | tuple[str, ...] | None = None,
) -> LoopActionResult:
    return _compute_loop_action(
        package,
        loop_id,
        partition_kind="predictive",
        history_ids=history_ids,
    )


def compute_loop_action_metrics(
    loop_action: LoopActionResult,
) -> tuple[LoopMetricResult, ...]:
    return (
        LoopMetricResult(
            metric_name="loop_moved_class_fraction",
            interface_id=loop_action.interface_id,
            loop_id=loop_action.loop_id,
            partition_kind=loop_action.partition_kind,
            metric_value=loop_action.moved_class_fraction,
        ),
        LoopMetricResult(
            metric_name="loop_moved_class_count",
            interface_id=loop_action.interface_id,
            loop_id=loop_action.loop_id,
            partition_kind=loop_action.partition_kind,
            metric_value=Fraction(loop_action.moved_class_count, 1),
        ),
    )


def _compute_loop_action(
    package: RouteTransportPackage,
    loop_id: str,
    *,
    partition_kind: PartitionKind,
    history_ids: list[str] | tuple[str, ...] | None,
) -> LoopActionResult:
    loop = package.get_loop(loop_id)
    try:
        if partition_kind == "current":
            transport_map = compute_current_transport_map(
                package,
                loop.continuation_id,
                source_history_ids=history_ids,
                target_history_ids=history_ids,
            )
        else:
            transport_map = compute_predictive_transport_map(
                package,
                loop.continuation_id,
                source_history_ids=history_ids,
                target_history_ids=history_ids,
            )
    except RouteTransportAnalysisError as exc:
        raise LoopActionUndefinedError(
            f"loop action {loop_id} is undefined on {partition_kind} partition"
        ) from exc

    return _loop_action_from_transport_map(loop_id, transport_map)


def _loop_action_from_transport_map(
    loop_id: str,
    transport_map: ClassTransportMap,
) -> LoopActionResult:
    fixed_class_ids = tuple(
        class_image.source_class_id
        for class_image in transport_map.class_images
        if class_image.source_class_id == class_image.target_class_id
    )
    moved_class_ids = tuple(
        class_image.source_class_id
        for class_image in transport_map.class_images
        if class_image.source_class_id != class_image.target_class_id
    )
    moved_class_count = len(moved_class_ids)
    total_class_count = len(transport_map.source_classes)
    moved_class_fraction = (
        Fraction(moved_class_count, total_class_count)
        if total_class_count
        else Fraction(0, 1)
    )
    return LoopActionResult(
        partition_kind=transport_map.partition_kind,
        interface_id=transport_map.source_interface_id,
        loop_id=loop_id,
        class_images=transport_map.class_images,
        fixed_class_ids=fixed_class_ids,
        moved_class_ids=moved_class_ids,
        moved_class_count=moved_class_count,
        moved_class_fraction=moved_class_fraction,
        is_trivial=moved_class_count == 0,
    )
