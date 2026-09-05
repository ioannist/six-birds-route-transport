from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from ..core import HistoryDistributionRuntime, RouteTransportPackage
from .exceptions import TransportMapNotWellDefinedError, TransportMapUndefinedError
from .quotients import (
    EquivalenceClass,
    InterfacePartition,
    PartitionKind,
    compute_current_partition,
    compute_predictive_partition,
)
from .signatures import (
    SignatureKey,
    compute_current_signature_for_history,
    compute_future_signature_for_history,
    resolve_interface_history_ids,
)


@dataclass(frozen=True)
class ClassTransportImage:
    source_class_id: str
    target_class_id: str
    representative_source_history_id: str
    image_signature_key: SignatureKey


@dataclass(frozen=True)
class ClassTransportMap:
    partition_kind: PartitionKind
    source_interface_id: str
    target_interface_id: str
    continuation_id: str
    source_classes: tuple[EquivalenceClass, ...]
    target_classes: tuple[EquivalenceClass, ...]
    class_images: tuple[ClassTransportImage, ...]
    class_image_by_source_id: Mapping[str, str]
    is_identity: bool


def compute_predictive_transport_map(
    package: RouteTransportPackage,
    continuation_id: str,
    source_history_ids: list[str] | tuple[str, ...] | None = None,
    target_history_ids: list[str] | tuple[str, ...] | None = None,
) -> ClassTransportMap:
    return _compute_class_transport_map(
        package,
        continuation_id,
        partition_kind="predictive",
        source_history_ids=source_history_ids,
        target_history_ids=target_history_ids,
    )


def compute_current_transport_map(
    package: RouteTransportPackage,
    continuation_id: str,
    source_history_ids: list[str] | tuple[str, ...] | None = None,
    target_history_ids: list[str] | tuple[str, ...] | None = None,
) -> ClassTransportMap:
    return _compute_class_transport_map(
        package,
        continuation_id,
        partition_kind="current",
        source_history_ids=source_history_ids,
        target_history_ids=target_history_ids,
    )


def _compute_class_transport_map(
    package: RouteTransportPackage,
    continuation_id: str,
    *,
    partition_kind: PartitionKind,
    source_history_ids: list[str] | tuple[str, ...] | None,
    target_history_ids: list[str] | tuple[str, ...] | None,
) -> ClassTransportMap:
    continuation = package.get_continuation(continuation_id)
    source_interface_id = continuation.source_interface_id
    target_interface_id = continuation.target_interface_id

    source_ordered_history_ids = resolve_interface_history_ids(
        package,
        source_interface_id,
        source_history_ids,
    )
    target_ordered_history_ids = resolve_interface_history_ids(
        package,
        target_interface_id,
        target_history_ids,
    )
    source_partition = _compute_partition(
        package,
        source_interface_id,
        partition_kind,
        source_ordered_history_ids,
    )
    target_partition = _compute_partition(
        package,
        target_interface_id,
        partition_kind,
        target_ordered_history_ids,
    )
    target_class_by_signature = {
        target_class.signature_key: target_class for target_class in target_partition.classes
    }

    class_images: list[ClassTransportImage] = []
    class_image_by_source_id: dict[str, str] = {}
    for source_class in source_partition.classes:
        target_class_ids_for_members: list[str] = []
        representative_signature_key: SignatureKey | None = None
        for history_id in source_class.member_history_ids:
            composed_history = package.compose_history_with_continuation_runtime(
                package.get_history(history_id),
                continuation,
                new_id=f"{history_id}__transport__{continuation_id}",
            )
            signature_key = _compute_signature_key_for_history(
                package,
                partition_kind,
                target_interface_id,
                composed_history,
            )
            target_class = target_class_by_signature.get(signature_key)
            if target_class is None:
                raise TransportMapUndefinedError(
                    f"continuation {continuation_id} image of history {history_id} "
                    f"does not match any {partition_kind} class at interface {target_interface_id}"
                )
            if representative_signature_key is None:
                representative_signature_key = signature_key
            target_class_ids_for_members.append(target_class.class_id)

        first_target_class_id = target_class_ids_for_members[0]
        if any(target_class_id != first_target_class_id for target_class_id in target_class_ids_for_members):
            raise TransportMapNotWellDefinedError(
                f"continuation {continuation_id} is not well-defined on "
                f"{partition_kind} class {source_class.class_id}"
            )
        class_image_by_source_id[source_class.class_id] = first_target_class_id
        class_images.append(
            ClassTransportImage(
                source_class_id=source_class.class_id,
                target_class_id=first_target_class_id,
                representative_source_history_id=source_class.representative_history_id,
                image_signature_key=representative_signature_key,
            )
        )

    return ClassTransportMap(
        partition_kind=partition_kind,
        source_interface_id=source_interface_id,
        target_interface_id=target_interface_id,
        continuation_id=continuation_id,
        source_classes=source_partition.classes,
        target_classes=target_partition.classes,
        class_images=tuple(class_images),
        class_image_by_source_id=MappingProxyType(class_image_by_source_id),
        is_identity=_is_identity_transport_map(
            source_partition,
            target_partition,
            class_images,
        ),
    )


def _compute_partition(
    package: RouteTransportPackage,
    interface_id: str,
    partition_kind: PartitionKind,
    history_ids: tuple[str, ...],
) -> InterfacePartition:
    if partition_kind == "current":
        return compute_current_partition(package, interface_id, history_ids)
    return compute_predictive_partition(package, interface_id, history_ids)


def _compute_signature_key_for_history(
    package: RouteTransportPackage,
    partition_kind: PartitionKind,
    interface_id: str,
    history: HistoryDistributionRuntime,
) -> SignatureKey:
    if partition_kind == "current":
        return compute_current_signature_for_history(package, interface_id, history).signature_key
    return compute_future_signature_for_history(package, interface_id, history).signature_key


def _is_identity_transport_map(
    source_partition: InterfacePartition,
    target_partition: InterfacePartition,
    class_images: list[ClassTransportImage],
) -> bool:
    if source_partition.interface_id != target_partition.interface_id:
        return False
    if len(source_partition.classes) != len(target_partition.classes):
        return False
    return all(
        class_image.source_class_id == class_image.target_class_id
        for class_image in class_images
    )
