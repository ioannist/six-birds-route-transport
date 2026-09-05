from __future__ import annotations

from pydantic import Field, model_validator

from .common import (
    HolonomyMemoryModel,
    ensure_finite_nonnegative_number,
    ensure_nonempty_string,
    ensure_probability_distribution,
    ensure_repo_relative_path,
    ensure_unique_strings,
)
from .enums import RouteTransportSchemaVersion


class SupportSpec(HolonomyMemoryModel):
    support_id: str
    visible_support_labels: list[str] = Field(min_length=1)
    same_support_required: bool

    @model_validator(mode="after")
    def validate_support(self) -> "SupportSpec":
        ensure_nonempty_string(self.support_id, "support_id")
        ensure_unique_strings(self.visible_support_labels, "visible_support_labels")
        for label in self.visible_support_labels:
            ensure_nonempty_string(label, "visible_support_labels")
        return self


class StateSpaceSpec(HolonomyMemoryModel):
    internal_state_ids: list[str] = Field(min_length=1)
    support_projection: dict[str, str]

    @model_validator(mode="after")
    def validate_state_space(self) -> "StateSpaceSpec":
        ensure_unique_strings(self.internal_state_ids, "internal_state_ids")
        state_ids = set(self.internal_state_ids)
        if set(self.support_projection) != state_ids:
            raise ValueError(
                "support_projection must define exactly one visible label for each internal state id"
            )
        for state_id, support_label in self.support_projection.items():
            ensure_nonempty_string(state_id, "support_projection keys")
            ensure_nonempty_string(support_label, f"support_projection[{state_id}]")
        return self


class InterfaceSpec(HolonomyMemoryModel):
    interface_id: str
    label: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def validate_interface(self) -> "InterfaceSpec":
        ensure_nonempty_string(self.interface_id, "interface_id")
        if self.label is not None:
            ensure_nonempty_string(self.label, "label")
        if self.description is not None:
            ensure_nonempty_string(self.description, "description")
        return self


class EventSpec(HolonomyMemoryModel):
    event_id: str
    weights: dict[str, float]

    @model_validator(mode="after")
    def validate_event(self) -> "EventSpec":
        ensure_nonempty_string(self.event_id, "event_id")
        if not self.weights:
            raise ValueError("weights must not be empty")
        total = 0.0
        for label, value in self.weights.items():
            ensure_nonempty_string(label, "weights keys")
            total += ensure_finite_nonnegative_number(value, f"weights[{label}]")
        if total <= 0:
            raise ValueError("weights must have positive total mass")
        return self


class EventPackageSpec(HolonomyMemoryModel):
    package_id: str
    interface_id: str
    events: list[EventSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_event_package(self) -> "EventPackageSpec":
        ensure_nonempty_string(self.package_id, "package_id")
        ensure_nonempty_string(self.interface_id, "interface_id")
        ensure_unique_strings([event.event_id for event in self.events], "event_ids")
        return self


class HistoryDistributionSpec(HolonomyMemoryModel):
    history_id: str
    source_interface_id: str
    target_interface_id: str
    probabilities: dict[str, float]

    @model_validator(mode="after")
    def validate_history_distribution(self) -> "HistoryDistributionSpec":
        ensure_nonempty_string(self.history_id, "history_id")
        ensure_nonempty_string(self.source_interface_id, "source_interface_id")
        ensure_nonempty_string(self.target_interface_id, "target_interface_id")
        ensure_probability_distribution(self.probabilities, "probabilities")
        return self


class ContinuationKernelSpec(HolonomyMemoryModel):
    continuation_id: str
    source_interface_id: str
    target_interface_id: str
    kernel: dict[str, dict[str, float]]

    @model_validator(mode="after")
    def validate_kernel(self) -> "ContinuationKernelSpec":
        ensure_nonempty_string(self.continuation_id, "continuation_id")
        ensure_nonempty_string(self.source_interface_id, "source_interface_id")
        ensure_nonempty_string(self.target_interface_id, "target_interface_id")
        if not self.kernel:
            raise ValueError("kernel must not be empty")
        for row_key, row in self.kernel.items():
            ensure_nonempty_string(row_key, "kernel row keys")
            ensure_probability_distribution(row, f"kernel[{row_key}]")
        return self


class LoopSpec(HolonomyMemoryModel):
    loop_id: str
    interface_id: str
    continuation_id: str

    @model_validator(mode="after")
    def validate_loop(self) -> "LoopSpec":
        ensure_nonempty_string(self.loop_id, "loop_id")
        ensure_nonempty_string(self.interface_id, "interface_id")
        ensure_nonempty_string(self.continuation_id, "continuation_id")
        return self


class RouteTransportPackageConfig(HolonomyMemoryModel):
    schema_version: RouteTransportSchemaVersion = RouteTransportSchemaVersion.V1
    package_id: str
    support: SupportSpec
    state_space: StateSpaceSpec
    interfaces: list[InterfaceSpec] = Field(min_length=1)
    event_packages: list[EventPackageSpec] = Field(min_length=1)
    histories: list[HistoryDistributionSpec] = Field(min_length=1)
    continuations: list[ContinuationKernelSpec] = Field(min_length=1)
    loops: list[LoopSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_package(self) -> "RouteTransportPackageConfig":
        ensure_nonempty_string(self.package_id, "package_id")
        ensure_unique_strings([item.interface_id for item in self.interfaces], "interface_ids")
        ensure_unique_strings([item.package_id for item in self.event_packages], "package_ids")
        ensure_unique_strings([item.history_id for item in self.histories], "history_ids")
        ensure_unique_strings(
            [item.continuation_id for item in self.continuations], "continuation_ids"
        )
        ensure_unique_strings([item.loop_id for item in self.loops], "loop_ids")

        interface_ids = {item.interface_id for item in self.interfaces}
        support_labels = set(self.support.visible_support_labels)
        state_ids = set(self.state_space.internal_state_ids)
        if set(self.state_space.support_projection) != state_ids:
            raise ValueError(
                "support_projection must define exactly one visible label for each internal state id"
            )
        unknown_support_labels = {
            label
            for label in self.state_space.support_projection.values()
            if label not in support_labels
        }
        if unknown_support_labels:
            raise ValueError(
                f"support_projection references undeclared support labels: {', '.join(sorted(unknown_support_labels))}"
            )

        for event_package in self.event_packages:
            if event_package.interface_id not in interface_ids:
                raise ValueError(
                    f"event package {event_package.package_id} references unknown interface {event_package.interface_id}"
                )
            for event in event_package.events:
                unknown_labels = set(event.weights) - support_labels
                if unknown_labels:
                    raise ValueError(
                        f"event {event.event_id} references undeclared support labels: {', '.join(sorted(unknown_labels))}"
                    )

        for history in self.histories:
            if history.source_interface_id not in interface_ids:
                raise ValueError(
                    f"history {history.history_id} references unknown source interface {history.source_interface_id}"
                )
            if history.target_interface_id not in interface_ids:
                raise ValueError(
                    f"history {history.history_id} references unknown target interface {history.target_interface_id}"
                )
            unknown_states = set(history.probabilities) - state_ids
            if unknown_states:
                raise ValueError(
                    f"history {history.history_id} references undeclared internal states: {', '.join(sorted(unknown_states))}"
                )

        continuation_by_id = {item.continuation_id: item for item in self.continuations}
        for continuation in self.continuations:
            if continuation.source_interface_id not in interface_ids:
                raise ValueError(
                    f"continuation {continuation.continuation_id} references unknown source interface {continuation.source_interface_id}"
                )
            if continuation.target_interface_id not in interface_ids:
                raise ValueError(
                    f"continuation {continuation.continuation_id} references unknown target interface {continuation.target_interface_id}"
                )
            for row in continuation.kernel.values():
                unknown_states = set(row) - state_ids
                if unknown_states:
                    raise ValueError(
                        f"continuation {continuation.continuation_id} references undeclared internal states: {', '.join(sorted(unknown_states))}"
                    )

        for loop in self.loops:
            continuation = continuation_by_id.get(loop.continuation_id)
            if continuation is None:
                raise ValueError(
                    f"loop {loop.loop_id} references unknown continuation {loop.continuation_id}"
                )
            if (
                continuation.source_interface_id != loop.interface_id
                or continuation.target_interface_id != loop.interface_id
            ):
                raise ValueError(
                    "loop must reference a continuation that starts and ends at the same interface"
                )
        return self
