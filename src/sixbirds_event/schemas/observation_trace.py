from __future__ import annotations

import math

from pydantic import Field, field_validator, model_validator

from .common import (
    MetadataValue,
    SixBirdsModel,
    collect_list_duplicates,
    ensure_metadata_shape,
    is_repo_relative_path,
)


class Observation(SixBirdsModel):
    context_id: str
    atom_ids: list[str]
    status: str | None = None
    count: int | None = None
    probability: float | None = None

    @field_validator("atom_ids")
    @classmethod
    def validate_atom_ids(cls, atom_ids: list[str]) -> list[str]:
        if not atom_ids:
            raise ValueError("atom_ids must not be empty")
        duplicates = collect_list_duplicates(atom_ids)
        if duplicates:
            raise ValueError(
                f"duplicate atom_ids in observation: {', '.join(duplicates)}"
            )
        return atom_ids

    @model_validator(mode="after")
    def validate_measurements(self) -> "Observation":
        if self.count is not None and (isinstance(self.count, bool) or self.count < 0):
            raise ValueError("count must be a non-negative integer")
        if self.probability is not None and (
            isinstance(self.probability, bool)
            or not math.isfinite(self.probability)
            or self.probability < 0
            or self.probability > 1
        ):
            raise ValueError("probability must be a finite value in [0, 1]")
        return self


class RepeatedReadSequence(SixBirdsModel):
    context_id: str
    reads: list[list[str]]

    @field_validator("reads")
    @classmethod
    def validate_reads(cls, reads: list[list[str]]) -> list[list[str]]:
        if not reads:
            raise ValueError("reads must not be empty")
        for index, read in enumerate(reads):
            if any(not isinstance(atom_id, str) for atom_id in read):
                raise ValueError(f"reads[{index}] must contain only strings")
            duplicates = collect_list_duplicates(read)
            if duplicates:
                raise ValueError(
                    f"reads[{index}] contains duplicate atom_ids: {', '.join(duplicates)}"
                )
        return reads


class DownstreamProbe(SixBirdsModel):
    probe_id: str
    event_id: str | None = None
    context_id: str | None = None
    signature: str
    outcome_counts: dict[str, int] | None = None
    outcome_probabilities: dict[str, float] | None = None
    payload: dict[str, object] | None = None

    @model_validator(mode="after")
    def validate_probe(self) -> "DownstreamProbe":
        if self.outcome_counts is not None and self.outcome_probabilities is not None:
            raise ValueError(
                "downstream probe must not carry both outcome_counts and outcome_probabilities"
            )
        if self.outcome_counts is not None:
            if not self.outcome_counts:
                raise ValueError("outcome_counts must not be empty")
            for outcome, count in self.outcome_counts.items():
                if not outcome:
                    raise ValueError("outcome_counts keys must be non-empty strings")
                if isinstance(count, bool) or count < 0:
                    raise ValueError(
                        "outcome_counts values must be non-negative integers"
                    )
        if self.outcome_probabilities is not None:
            if not self.outcome_probabilities:
                raise ValueError("outcome_probabilities must not be empty")
            for outcome, probability in self.outcome_probabilities.items():
                if not outcome:
                    raise ValueError(
                        "outcome_probabilities keys must be non-empty strings"
                    )
                if (
                    isinstance(probability, bool)
                    or not math.isfinite(probability)
                    or probability < 0
                    or probability > 1
                ):
                    raise ValueError(
                        "outcome_probabilities values must be finite values in [0, 1]"
                    )
        return self


class RouteObservation(SixBirdsModel):
    preparation_id: str | None = None
    macrostate_id: str | None = None
    route_id: str
    endpoint_id: str
    context_id: str | None = None
    outcome_counts: dict[str, int] | None = None
    outcome_probabilities: dict[str, float] | None = None

    @model_validator(mode="after")
    def validate_route_observation(self) -> "RouteObservation":
        has_preparation = self.preparation_id is not None
        has_macrostate = self.macrostate_id is not None
        if has_preparation == has_macrostate:
            raise ValueError(
                "route observation must carry exactly one of preparation_id or macrostate_id"
            )
        if self.outcome_counts is not None and self.outcome_probabilities is not None:
            raise ValueError(
                "route observation must not carry both outcome_counts and outcome_probabilities"
            )
        if self.outcome_counts is None and self.outcome_probabilities is None:
            raise ValueError(
                "route observation must carry outcome_counts or outcome_probabilities"
            )
        if self.outcome_counts is not None:
            if not self.outcome_counts:
                raise ValueError("route observation outcome_counts must not be empty")
            for outcome, count in self.outcome_counts.items():
                if not outcome:
                    raise ValueError(
                        "route observation outcome_counts keys must be non-empty strings"
                    )
                if isinstance(count, bool) or count < 0:
                    raise ValueError(
                        "route observation outcome_counts values must be non-negative integers"
                    )
        if self.outcome_probabilities is not None:
            if not self.outcome_probabilities:
                raise ValueError(
                    "route observation outcome_probabilities must not be empty"
                )
            for outcome, probability in self.outcome_probabilities.items():
                if not outcome:
                    raise ValueError(
                        "route observation outcome_probabilities keys must be non-empty strings"
                    )
                if (
                    isinstance(probability, bool)
                    or not math.isfinite(probability)
                    or probability < 0
                    or probability > 1
                ):
                    raise ValueError(
                        "route observation outcome_probabilities values must be finite values in [0, 1]"
                    )
        return self


class RouteTrace(SixBirdsModel):
    route_id: str | None = None
    steps: list[str] | None = None
    notes: str | None = None


class ObservationTrace(SixBirdsModel):
    trace_format_version: str
    trace_id: str
    instance_id: str | None = None
    instance_artifact: str | None = None
    observations: list[Observation]
    repeated_read_sequences: list[RepeatedReadSequence] = Field(default_factory=list)
    downstream_probes: list[DownstreamProbe] = Field(default_factory=list)
    route_observations: list[RouteObservation] = Field(default_factory=list)
    route_trace: RouteTrace | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_trace(self) -> "ObservationTrace":
        if self.trace_format_version != "observation-trace.v1":
            raise ValueError("trace_format_version must equal 'observation-trace.v1'")
        if not self.observations:
            raise ValueError("observations must not be empty")

        ensure_metadata_shape(self.metadata)
        if self.instance_artifact is not None and not is_repo_relative_path(
            self.instance_artifact
        ):
            raise ValueError(
                "instance_artifact must be a normalized repo-relative path"
            )

        probe_keys = [
            f"{probe.event_id or '<unlinked>'}:{probe.probe_id}"
            for probe in self.downstream_probes
        ]
        duplicates = collect_list_duplicates(probe_keys)
        if duplicates:
            raise ValueError(
                f"(event_id, probe_id) pairs must be unique: {', '.join(duplicates)}"
            )

        return self
