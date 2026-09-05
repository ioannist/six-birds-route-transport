from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from ..core import (
    EventPackageRuntime,
    EventRuntime,
    HistoryDistributionRuntime,
    RouteTransportPackage,
)
from ..core.exact import ordered_fraction_mapping, project_state_distribution_to_support
from .exceptions import InvalidHistorySelectionError, MissingEventPackageError

CurrentSignatureKey = tuple[tuple[str, Fraction], ...]
FutureSignatureEntry = tuple[str, str, str, Fraction]
FutureSignatureKey = tuple[FutureSignatureEntry, ...]
SignatureKey = CurrentSignatureKey | FutureSignatureKey


@dataclass(frozen=True)
class CurrentSignature:
    interface_id: str
    history_id: str
    event_statistics: CurrentSignatureKey
    signature_key: CurrentSignatureKey


@dataclass(frozen=True)
class FutureSignature:
    source_interface_id: str
    history_id: str
    continuation_event_statistics: FutureSignatureKey
    signature_key: FutureSignatureKey


def compute_current_signature(
    package: RouteTransportPackage,
    history_id: str,
    interface_id: str | None = None,
) -> CurrentSignature:
    history = package.get_history(history_id)
    return compute_current_signature_for_history(
        package,
        interface_id or history.target_interface_id,
        history,
    )


def compute_future_signature(
    package: RouteTransportPackage,
    history_id: str,
    interface_id: str | None = None,
) -> FutureSignature:
    history = package.get_history(history_id)
    return compute_future_signature_for_history(
        package,
        interface_id or history.target_interface_id,
        history,
    )


def compute_current_signature_for_history(
    package: RouteTransportPackage,
    interface_id: str,
    history: HistoryDistributionRuntime,
) -> CurrentSignature:
    measured_interface_id = _resolve_history_interface(history, interface_id)
    event_package = _require_event_package(
        package,
        measured_interface_id,
        context=f"current signature for history {history.history_id}",
    )
    event_statistics = _evaluate_event_package_for_history(
        package,
        history,
        event_package,
    )
    key = tuple(event_statistics.items())
    return CurrentSignature(
        interface_id=measured_interface_id,
        history_id=history.history_id,
        event_statistics=key,
        signature_key=key,
    )


def compute_future_signature_for_history(
    package: RouteTransportPackage,
    interface_id: str,
    history: HistoryDistributionRuntime,
) -> FutureSignature:
    measured_interface_id = _resolve_history_interface(history, interface_id)
    flattened: list[FutureSignatureEntry] = []
    for continuation in package.continuations:
        if continuation.source_interface_id != measured_interface_id:
            continue
        target_event_package = _require_event_package(
            package,
            continuation.target_interface_id,
            context=(
                "future signature for history "
                f"{history.history_id} via continuation {continuation.continuation_id}"
            ),
        )
        composed_history = package.compose_history_with_continuation_runtime(
            history,
            continuation,
            new_id=f"{history.history_id}__future__{continuation.continuation_id}",
        )
        event_statistics = _evaluate_event_package_for_history(
            package,
            composed_history,
            target_event_package,
        )
        for event_id, value in event_statistics.items():
            flattened.append(
                (
                    continuation.continuation_id,
                    continuation.target_interface_id,
                    event_id,
                    value,
                )
            )

    key = tuple(flattened)
    return FutureSignature(
        source_interface_id=measured_interface_id,
        history_id=history.history_id,
        continuation_event_statistics=key,
        signature_key=key,
    )


def resolve_interface_history_ids(
    package: RouteTransportPackage,
    interface_id: str,
    history_ids: list[str] | tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    declared_history_ids = tuple(
        history.history_id
        for history in package.histories
        if history.target_interface_id == interface_id
    )
    if history_ids is None:
        return declared_history_ids

    requested = tuple(history_ids)
    if len(set(requested)) != len(requested):
        raise InvalidHistorySelectionError("history_ids must not contain duplicates")

    filtered = tuple(history_id for history_id in declared_history_ids if history_id in requested)
    missing = set(requested) - set(filtered)
    if missing:
        missing_names = ", ".join(sorted(missing))
        raise InvalidHistorySelectionError(
            f"history_ids are not declared for interface {interface_id}: {missing_names}"
        )
    return filtered


def _resolve_history_interface(
    history: HistoryDistributionRuntime,
    interface_id: str | None,
) -> str:
    measured_interface_id = interface_id or history.target_interface_id
    if measured_interface_id != history.target_interface_id:
        raise InvalidHistorySelectionError(
            f"history {history.history_id} does not end at interface {measured_interface_id}"
        )
    return measured_interface_id


def _require_event_package(
    package: RouteTransportPackage,
    interface_id: str,
    *,
    context: str,
) -> EventPackageRuntime:
    try:
        return package.get_event_package(interface_id)
    except Exception as exc:  # pragma: no cover - narrow runtime error wrapped below
        raise MissingEventPackageError(
            f"interface {interface_id} has no event package for {context}"
        ) from exc


def _evaluate_event_package_for_history(
    package: RouteTransportPackage,
    history: HistoryDistributionRuntime,
    event_package: EventPackageRuntime,
) -> OrderedDict[str, Fraction]:
    support_distribution = _project_history_to_support_distribution(package, history)
    evaluations: OrderedDict[str, Fraction] = OrderedDict()
    for event in event_package.events:
        evaluations[event.event_id] = _evaluate_event_on_support_distribution(
            support_distribution,
            package.support.visible_support_labels,
            event,
        )
    return evaluations


def _project_history_to_support_distribution(
    package: RouteTransportPackage,
    history: HistoryDistributionRuntime,
) -> OrderedDict[str, Fraction]:
    projected = project_state_distribution_to_support(
        history.probabilities,
        state_ids=package.state_space.internal_state_ids,
        support_labels=package.support.visible_support_labels,
        support_projection=package.state_space.support_projection,
    )
    return ordered_fraction_mapping(package.support.visible_support_labels, projected)


def _evaluate_event_on_support_distribution(
    support_distribution: Mapping[str, Fraction],
    support_labels: tuple[str, ...],
    event: EventRuntime,
) -> Fraction:
    return sum(
        (
            probability * weight
            for probability, weight in zip(
                support_distribution.values(),
                event.weights,
                strict=True,
            )
        ),
        start=Fraction(0, 1),
    )
