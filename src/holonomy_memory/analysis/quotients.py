from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from types import MappingProxyType
from typing import Literal, Mapping

from ..core import RouteTransportPackage
from .signatures import (
    CurrentSignatureKey,
    FutureSignatureKey,
    compute_current_signature,
    compute_future_signature,
    resolve_interface_history_ids,
)

PartitionKind = Literal["current", "predictive"]
SignatureKey = CurrentSignatureKey | FutureSignatureKey


@dataclass(frozen=True)
class EquivalenceClass:
    class_id: str
    member_history_ids: tuple[str, ...]
    representative_history_id: str
    signature_key: SignatureKey


@dataclass(frozen=True)
class InterfacePartition:
    interface_id: str
    partition_kind: PartitionKind
    classes: tuple[EquivalenceClass, ...]
    history_to_class_id: Mapping[str, str]

    @property
    def class_count(self) -> int:
        return len(self.classes)


@dataclass(frozen=True)
class MemoryWitness:
    interface_id: str
    history_id_1: str
    history_id_2: str
    current_class_id: str
    predictive_class_id_1: str
    predictive_class_id_2: str


def compute_current_partition(
    package: RouteTransportPackage,
    interface_id: str,
    history_ids: list[str] | tuple[str, ...] | None = None,
) -> InterfacePartition:
    ordered_history_ids = resolve_interface_history_ids(package, interface_id, history_ids)
    signatures = {
        history_id: compute_current_signature(package, history_id, interface_id=interface_id)
        for history_id in ordered_history_ids
    }
    return _build_partition(
        interface_id,
        "current",
        ordered_history_ids,
        {history_id: signature.signature_key for history_id, signature in signatures.items()},
    )


def compute_predictive_partition(
    package: RouteTransportPackage,
    interface_id: str,
    history_ids: list[str] | tuple[str, ...] | None = None,
) -> InterfacePartition:
    ordered_history_ids = resolve_interface_history_ids(package, interface_id, history_ids)
    signatures = {
        history_id: compute_future_signature(package, history_id, interface_id=interface_id)
        for history_id in ordered_history_ids
    }
    return _build_partition(
        interface_id,
        "predictive",
        ordered_history_ids,
        {history_id: signature.signature_key for history_id, signature in signatures.items()},
    )


def predictive_refines_current(
    current_partition: InterfacePartition,
    predictive_partition: InterfacePartition,
) -> bool:
    if current_partition.interface_id != predictive_partition.interface_id:
        return False

    current_classes_by_id = {
        equivalence_class.class_id: set(equivalence_class.member_history_ids)
        for equivalence_class in current_partition.classes
    }
    for predictive_class in predictive_partition.classes:
        if not predictive_class.member_history_ids:
            continue
        representative = predictive_class.member_history_ids[0]
        current_class_id = current_partition.history_to_class_id[representative]
        current_members = current_classes_by_id[current_class_id]
        if not set(predictive_class.member_history_ids).issubset(current_members):
            return False
    return True


def enumerate_memory_witnesses(
    package: RouteTransportPackage,
    interface_id: str,
    history_ids: list[str] | tuple[str, ...] | None = None,
) -> tuple[MemoryWitness, ...]:
    current_partition = compute_current_partition(package, interface_id, history_ids)
    predictive_partition = compute_predictive_partition(package, interface_id, history_ids)

    witnesses: list[MemoryWitness] = []
    for current_class in current_partition.classes:
        for history_id_1, history_id_2 in combinations(current_class.member_history_ids, 2):
            predictive_class_id_1 = predictive_partition.history_to_class_id[history_id_1]
            predictive_class_id_2 = predictive_partition.history_to_class_id[history_id_2]
            if predictive_class_id_1 == predictive_class_id_2:
                continue
            witnesses.append(
                MemoryWitness(
                    interface_id=interface_id,
                    history_id_1=history_id_1,
                    history_id_2=history_id_2,
                    current_class_id=current_class.class_id,
                    predictive_class_id_1=predictive_class_id_1,
                    predictive_class_id_2=predictive_class_id_2,
                )
            )
    return tuple(witnesses)


def _build_partition(
    interface_id: str,
    partition_kind: PartitionKind,
    ordered_history_ids: tuple[str, ...],
    signature_keys: Mapping[str, SignatureKey],
) -> InterfacePartition:
    members_by_key: dict[SignatureKey, list[str]] = {}
    ordered_keys: list[SignatureKey] = []
    for history_id in ordered_history_ids:
        signature_key = signature_keys[history_id]
        if signature_key not in members_by_key:
            members_by_key[signature_key] = []
            ordered_keys.append(signature_key)
        members_by_key[signature_key].append(history_id)

    classes: list[EquivalenceClass] = []
    history_to_class_id: dict[str, str] = {}
    for index, signature_key in enumerate(ordered_keys):
        class_id = f"C{index}"
        member_history_ids = tuple(members_by_key[signature_key])
        for history_id in member_history_ids:
            history_to_class_id[history_id] = class_id
        classes.append(
            EquivalenceClass(
                class_id=class_id,
                member_history_ids=member_history_ids,
                representative_history_id=member_history_ids[0],
                signature_key=signature_key,
            )
        )

    return InterfacePartition(
        interface_id=interface_id,
        partition_kind=partition_kind,
        classes=tuple(classes),
        history_to_class_id=MappingProxyType(history_to_class_id),
    )
