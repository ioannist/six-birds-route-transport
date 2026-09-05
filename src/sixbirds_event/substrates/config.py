from __future__ import annotations

import math

from pydantic import Field, field_validator, model_validator

from ..schemas.common import MetadataValue, SixBirdsModel, ensure_metadata_shape

_PROBABILITY_TOLERANCE = 1e-9


class HiddenState(SixBirdsModel):
    state_id: str
    label: str | None = None


class PreparationSpec(SixBirdsModel):
    preparation_id: str
    distribution: dict[str, float]

    @field_validator("distribution")
    @classmethod
    def validate_distribution(cls, distribution: dict[str, float]) -> dict[str, float]:
        if not distribution:
            raise ValueError("distribution must not be empty")
        total = 0.0
        for state_id, probability in distribution.items():
            if not state_id:
                raise ValueError("distribution keys must be non-empty strings")
            if (
                isinstance(probability, bool)
                or not math.isfinite(probability)
                or probability < 0
                or probability > 1
            ):
                raise ValueError(
                    "distribution values must be finite probabilities in [0, 1]"
                )
            total += probability
        if abs(total - 1.0) > _PROBABILITY_TOLERANCE:
            raise ValueError("distribution probabilities must sum to 1")
        return distribution


class ActionSpec(SixBirdsModel):
    action_id: str
    transition_kernel: dict[str, dict[str, float]]

    @field_validator("transition_kernel")
    @classmethod
    def validate_transition_kernel(
        cls, transition_kernel: dict[str, dict[str, float]]
    ) -> dict[str, dict[str, float]]:
        if not transition_kernel:
            raise ValueError("transition_kernel must not be empty")
        for state_id, row in transition_kernel.items():
            if not state_id:
                raise ValueError("transition_kernel keys must be non-empty strings")
            if not row:
                raise ValueError(
                    "transition_kernel rows must not be empty distributions"
                )
            total = 0.0
            for next_state_id, probability in row.items():
                if not next_state_id:
                    raise ValueError(
                        "transition_kernel row keys must be non-empty strings"
                    )
                if (
                    isinstance(probability, bool)
                    or not math.isfinite(probability)
                    or probability < 0
                    or probability > 1
                ):
                    raise ValueError(
                        "transition probabilities must be finite values in [0, 1]"
                    )
                total += probability
            if abs(total - 1.0) > _PROBABILITY_TOLERANCE:
                raise ValueError("transition rows must sum to 1")
        return transition_kernel


class LensSpec(SixBirdsModel):
    lens_id: str
    readout_map: dict[str, str]

    @field_validator("readout_map")
    @classmethod
    def validate_readout_map(cls, readout_map: dict[str, str]) -> dict[str, str]:
        if not readout_map:
            raise ValueError("readout_map must not be empty")
        for state_id, observation_label in readout_map.items():
            if not state_id:
                raise ValueError("readout_map keys must be non-empty strings")
            if not observation_label:
                raise ValueError("readout_map values must be non-empty strings")
        return readout_map


class ProtocolSpec(SixBirdsModel):
    protocol_id: str
    action_ids: list[str]

    @field_validator("action_ids")
    @classmethod
    def validate_action_ids(cls, action_ids: list[str]) -> list[str]:
        if not action_ids:
            raise ValueError("action_ids must not be empty")
        if any(not action_id for action_id in action_ids):
            raise ValueError("action_ids must contain only non-empty strings")
        return action_ids


class SubstrateDefaults(SixBirdsModel):
    trajectory_count: int | None = None
    seed: int | None = None

    @model_validator(mode="after")
    def validate_defaults(self) -> "SubstrateDefaults":
        if self.trajectory_count is not None and (
            isinstance(self.trajectory_count, bool) or self.trajectory_count <= 0
        ):
            raise ValueError("trajectory_count must be a positive integer")
        if self.seed is not None and isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        return self


class SubstrateConfig(SixBirdsModel):
    config_format_version: str
    config_id: str
    states: list[HiddenState]
    preparations: list[PreparationSpec]
    actions: list[ActionSpec]
    lenses: list[LensSpec]
    protocols: list[ProtocolSpec]
    defaults: SubstrateDefaults | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_config(self) -> "SubstrateConfig":
        if self.config_format_version != "substrate-config.v1":
            raise ValueError("config_format_version must equal 'substrate-config.v1'")
        if not self.states:
            raise ValueError("states must not be empty")
        if not self.preparations:
            raise ValueError("preparations must not be empty")
        if not self.actions:
            raise ValueError("actions must not be empty")
        if not self.lenses:
            raise ValueError("lenses must not be empty")
        if not self.protocols:
            raise ValueError("protocols must not be empty")

        ensure_metadata_shape(self.metadata)

        state_ids = [state.state_id for state in self.states]
        if len(set(state_ids)) != len(state_ids):
            raise ValueError("state_id values must be unique")
        state_id_set = set(state_ids)

        preparation_ids = [
            preparation.preparation_id for preparation in self.preparations
        ]
        if len(set(preparation_ids)) != len(preparation_ids):
            raise ValueError("preparation_id values must be unique")
        for preparation in self.preparations:
            unknown = sorted(set(preparation.distribution) - state_id_set)
            if unknown:
                raise ValueError(
                    f"preparation '{preparation.preparation_id}' references unknown states: {', '.join(unknown)}"
                )

        action_ids = [action.action_id for action in self.actions]
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("action_id values must be unique")
        for action in self.actions:
            kernel_state_ids = set(action.transition_kernel)
            if kernel_state_ids != state_id_set:
                missing = sorted(state_id_set - kernel_state_ids)
                extra = sorted(kernel_state_ids - state_id_set)
                fragments: list[str] = []
                if missing:
                    fragments.append(f"missing rows for states: {', '.join(missing)}")
                if extra:
                    fragments.append(f"unknown rows for states: {', '.join(extra)}")
                raise ValueError(
                    f"action '{action.action_id}' transition_kernel must define exactly one row for each state ({'; '.join(fragments)})"
                )
            for from_state_id, row in action.transition_kernel.items():
                unknown = sorted(set(row) - state_id_set)
                if unknown:
                    raise ValueError(
                        f"action '{action.action_id}' row '{from_state_id}' references unknown next states: {', '.join(unknown)}"
                    )

        lens_ids = [lens.lens_id for lens in self.lenses]
        if len(set(lens_ids)) != len(lens_ids):
            raise ValueError("lens_id values must be unique")
        for lens in self.lenses:
            mapped_state_ids = set(lens.readout_map)
            if mapped_state_ids != state_id_set:
                missing = sorted(state_id_set - mapped_state_ids)
                extra = sorted(mapped_state_ids - state_id_set)
                fragments = []
                if missing:
                    fragments.append(f"missing states: {', '.join(missing)}")
                if extra:
                    fragments.append(f"unknown states: {', '.join(extra)}")
                raise ValueError(
                    f"lens '{lens.lens_id}' readout_map must define exactly one observation for each state ({'; '.join(fragments)})"
                )

        action_id_set = set(action_ids)
        protocol_ids = [protocol.protocol_id for protocol in self.protocols]
        if len(set(protocol_ids)) != len(protocol_ids):
            raise ValueError("protocol_id values must be unique")
        for protocol in self.protocols:
            unknown = sorted(set(protocol.action_ids) - action_id_set)
            if unknown:
                raise ValueError(
                    f"protocol '{protocol.protocol_id}' references unknown actions: {', '.join(unknown)}"
                )

        return self
