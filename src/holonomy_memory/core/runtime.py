from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Mapping

from ..schemas import RouteTransportPackageConfig
from .exact import (
    apply_row_vector_to_kernel,
    compose_row_stochastic_kernels,
    normalize_sparse_distribution,
    normalize_sparse_kernel,
    ordered_fraction_mapping,
    project_state_distribution_to_support,
)
from .exceptions import CompositionTypeError, RouteTransportLookupError


@dataclass(frozen=True)
class SupportRuntime:
    support_id: str
    visible_support_labels: tuple[str, ...]
    same_support_required: bool


@dataclass(frozen=True)
class StateSpaceRuntime:
    internal_state_ids: tuple[str, ...]
    support_projection: Mapping[str, str]


@dataclass(frozen=True)
class InterfaceRuntime:
    interface_id: str
    label: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class EventRuntime:
    event_id: str
    weights: tuple[Fraction, ...]


@dataclass(frozen=True)
class EventPackageRuntime:
    package_id: str
    interface_id: str
    events: tuple[EventRuntime, ...]


@dataclass(frozen=True)
class HistoryDistributionRuntime:
    history_id: str
    source_interface_id: str
    target_interface_id: str
    probabilities: tuple[Fraction, ...]


@dataclass(frozen=True)
class ContinuationKernelRuntime:
    """Row-stochastic continuation kernel for row-vector execution p' = pK."""

    continuation_id: str
    source_interface_id: str
    target_interface_id: str
    kernel: tuple[tuple[Fraction, ...], ...]


@dataclass(frozen=True)
class LoopRuntime:
    loop_id: str
    interface_id: str
    continuation_id: str


@dataclass(frozen=True)
class RouteTransportPackage:
    """Exact finite route-transport package with row-vector execution semantics."""

    package_id: str
    support: SupportRuntime
    state_space: StateSpaceRuntime
    interfaces: tuple[InterfaceRuntime, ...]
    event_packages: tuple[EventPackageRuntime, ...]
    histories: tuple[HistoryDistributionRuntime, ...]
    continuations: tuple[ContinuationKernelRuntime, ...]
    loops: tuple[LoopRuntime, ...]
    interface_by_id: Mapping[str, InterfaceRuntime]
    event_package_by_interface_id: Mapping[str, EventPackageRuntime]
    history_by_id: Mapping[str, HistoryDistributionRuntime]
    continuation_by_id: Mapping[str, ContinuationKernelRuntime]
    loop_by_id: Mapping[str, LoopRuntime]

    @classmethod
    def from_config(cls, config: RouteTransportPackageConfig) -> "RouteTransportPackage":
        support_labels = tuple(config.support.visible_support_labels)
        state_ids = tuple(config.state_space.internal_state_ids)
        support_projection = MappingProxyType(dict(config.state_space.support_projection))

        support = SupportRuntime(
            support_id=config.support.support_id,
            visible_support_labels=support_labels,
            same_support_required=config.support.same_support_required,
        )
        state_space = StateSpaceRuntime(
            internal_state_ids=state_ids,
            support_projection=support_projection,
        )

        interfaces = tuple(
            InterfaceRuntime(
                interface_id=interface.interface_id,
                label=interface.label,
                description=interface.description,
            )
            for interface in config.interfaces
        )
        interface_by_id = MappingProxyType(
            {interface.interface_id: interface for interface in interfaces}
        )

        event_packages = tuple(
            EventPackageRuntime(
                package_id=event_package.package_id,
                interface_id=event_package.interface_id,
                events=tuple(
                    EventRuntime(
                        event_id=event.event_id,
                        weights=normalize_sparse_distribution(
                            support_labels,
                            event.weights,
                            context=f"event {event.event_id} weights",
                        ),
                    )
                    for event in event_package.events
                ),
            )
            for event_package in config.event_packages
        )

        event_package_map: dict[str, EventPackageRuntime] = {}
        for event_package in event_packages:
            if event_package.interface_id in event_package_map:
                raise ValueError(
                    f"multiple event packages declared for interface {event_package.interface_id}"
                )
            event_package_map[event_package.interface_id] = event_package
        event_package_by_interface_id = MappingProxyType(event_package_map)

        histories = tuple(
            HistoryDistributionRuntime(
                history_id=history.history_id,
                source_interface_id=history.source_interface_id,
                target_interface_id=history.target_interface_id,
                probabilities=normalize_sparse_distribution(
                    state_ids,
                    history.probabilities,
                    context=f"history {history.history_id} probabilities",
                    require_total=Fraction(1, 1),
                ),
            )
            for history in config.histories
        )
        history_by_id = MappingProxyType({history.history_id: history for history in histories})

        continuations = tuple(
            ContinuationKernelRuntime(
                continuation_id=continuation.continuation_id,
                source_interface_id=continuation.source_interface_id,
                target_interface_id=continuation.target_interface_id,
                kernel=normalize_sparse_kernel(
                    state_ids,
                    state_ids,
                    continuation.kernel,
                    context=f"continuation {continuation.continuation_id} kernel",
                ),
            )
            for continuation in config.continuations
        )
        continuation_by_id = MappingProxyType(
            {
                continuation.continuation_id: continuation
                for continuation in continuations
            }
        )

        loops = tuple(
            LoopRuntime(
                loop_id=loop.loop_id,
                interface_id=loop.interface_id,
                continuation_id=loop.continuation_id,
            )
            for loop in config.loops
        )
        loop_by_id = MappingProxyType({loop.loop_id: loop for loop in loops})

        return cls(
            package_id=config.package_id,
            support=support,
            state_space=state_space,
            interfaces=interfaces,
            event_packages=event_packages,
            histories=histories,
            continuations=continuations,
            loops=loops,
            interface_by_id=interface_by_id,
            event_package_by_interface_id=event_package_by_interface_id,
            history_by_id=history_by_id,
            continuation_by_id=continuation_by_id,
            loop_by_id=loop_by_id,
        )

    def interface_ids(self) -> tuple[str, ...]:
        return tuple(interface.interface_id for interface in self.interfaces)

    def history_ids(self) -> tuple[str, ...]:
        return tuple(history.history_id for history in self.histories)

    def continuation_ids(self) -> tuple[str, ...]:
        return tuple(continuation.continuation_id for continuation in self.continuations)

    def loop_ids(self) -> tuple[str, ...]:
        return tuple(loop.loop_id for loop in self.loops)

    def get_event_package(self, interface_id: str) -> EventPackageRuntime:
        event_package = self.event_package_by_interface_id.get(interface_id)
        if event_package is None:
            raise RouteTransportLookupError(
                f"unknown event package interface {interface_id}"
            )
        return event_package

    def get_history(self, history_id: str) -> HistoryDistributionRuntime:
        history = self.history_by_id.get(history_id)
        if history is None:
            raise RouteTransportLookupError(f"unknown history {history_id}")
        return history

    def get_continuation(self, continuation_id: str) -> ContinuationKernelRuntime:
        continuation = self.continuation_by_id.get(continuation_id)
        if continuation is None:
            raise RouteTransportLookupError(f"unknown continuation {continuation_id}")
        return continuation

    def get_loop(self, loop_id: str) -> LoopRuntime:
        loop = self.loop_by_id.get(loop_id)
        if loop is None:
            raise RouteTransportLookupError(f"unknown loop {loop_id}")
        return loop

    def get_event(self, interface_id: str, event_id: str) -> EventRuntime:
        event_package = self.get_event_package(interface_id)
        for event in event_package.events:
            if event.event_id == event_id:
                return event
        raise RouteTransportLookupError(
            f"unknown event {event_id} for interface {interface_id}"
        )

    def get_history_distribution(
        self, history_id: str
    ) -> OrderedDict[str, Fraction]:
        history = self.get_history(history_id)
        return ordered_fraction_mapping(
            self.state_space.internal_state_ids,
            history.probabilities,
        )

    def project_history_to_support(
        self, history_id: str
    ) -> OrderedDict[str, Fraction]:
        history = self.get_history(history_id)
        projected = project_state_distribution_to_support(
            history.probabilities,
            state_ids=self.state_space.internal_state_ids,
            support_labels=self.support.visible_support_labels,
            support_projection=self.state_space.support_projection,
        )
        return ordered_fraction_mapping(self.support.visible_support_labels, projected)

    def evaluate_event_statistic(
        self,
        history_id: str,
        event_id: str,
        *,
        interface_id: str | None = None,
    ) -> Fraction:
        history = self.get_history(history_id)
        resolved_interface_id = self._resolve_history_interface(history, interface_id)
        event = self.get_event(resolved_interface_id, event_id)
        support_distribution = self.project_history_to_support(history_id)
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

    def evaluate_event_package(
        self,
        history_id: str,
        *,
        interface_id: str | None = None,
    ) -> OrderedDict[str, Fraction]:
        history = self.get_history(history_id)
        resolved_interface_id = self._resolve_history_interface(history, interface_id)
        event_package = self.get_event_package(resolved_interface_id)
        evaluations = OrderedDict()
        for event in event_package.events:
            evaluations[event.event_id] = self.evaluate_event_statistic(
                history_id,
                event.event_id,
                interface_id=resolved_interface_id,
            )
        return evaluations

    def compose_history_with_continuation(
        self,
        history_id: str,
        continuation_id: str,
        *,
        new_id: str | None = None,
    ) -> HistoryDistributionRuntime:
        history = self.get_history(history_id)
        continuation = self.get_continuation(continuation_id)
        return self.compose_history_with_continuation_runtime(
            history,
            continuation,
            new_id=new_id or f"{history_id}__then__{continuation_id}",
        )

    def compose_history_with_continuation_runtime(
        self,
        history: HistoryDistributionRuntime,
        continuation: ContinuationKernelRuntime,
        *,
        new_id: str | None = None,
    ) -> HistoryDistributionRuntime:
        # Histories act as row vectors p and continuations act as row-stochastic
        # kernels K, so typed execution is the exact product p' = pK.
        if history.target_interface_id != continuation.source_interface_id:
            raise CompositionTypeError(
                "cannot compose history "
                f"{history.history_id} targeting interface {history.target_interface_id} "
                f"with continuation {continuation.continuation_id} sourced at interface "
                f"{continuation.source_interface_id}"
            )

        probabilities = apply_row_vector_to_kernel(
            history.probabilities,
            continuation.kernel,
        )
        return HistoryDistributionRuntime(
            history_id=new_id or f"{history.history_id}__then__{continuation.continuation_id}",
            source_interface_id=history.source_interface_id,
            target_interface_id=continuation.target_interface_id,
            probabilities=probabilities,
        )

    def compose_continuations(
        self,
        first_continuation_id: str,
        second_continuation_id: str,
        *,
        new_id: str | None = None,
    ) -> ContinuationKernelRuntime:
        # Continuation composition follows the same row-vector convention:
        # first K1 : i -> j, second K2 : j -> k, composite K12 = K1K2.
        first = self.get_continuation(first_continuation_id)
        second = self.get_continuation(second_continuation_id)
        if first.target_interface_id != second.source_interface_id:
            raise CompositionTypeError(
                "cannot compose continuation "
                f"{first.continuation_id} targeting interface {first.target_interface_id} "
                f"with continuation {second.continuation_id} sourced at interface "
                f"{second.source_interface_id}"
            )

        kernel = compose_row_stochastic_kernels(first.kernel, second.kernel)
        return ContinuationKernelRuntime(
            continuation_id=new_id or f"{first_continuation_id}__then__{second_continuation_id}",
            source_interface_id=first.source_interface_id,
            target_interface_id=second.target_interface_id,
            kernel=kernel,
        )

    def _resolve_history_interface(
        self,
        history: HistoryDistributionRuntime,
        interface_id: str | None,
    ) -> str:
        resolved = interface_id or history.target_interface_id
        if resolved != history.target_interface_id:
            raise CompositionTypeError(
                "cannot evaluate history "
                f"{history.history_id} at interface {resolved}; expected "
                f"{history.target_interface_id}"
            )
        return resolved
