from __future__ import annotations

import json
from pathlib import Path

from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import (
    DownstreamProbe,
    Observation,
    ObservationTrace,
    RepeatedReadSequence,
    RouteObservation,
    RouteTrace,
)
from ..validation import load_model, validate_observation_trace


def make_observation(
    *,
    context_id: str,
    atom_ids: list[str],
    status: str | None = None,
    count: int | None = None,
    probability: float | None = None,
) -> Observation:
    return Observation(
        context_id=context_id,
        atom_ids=atom_ids,
        status=status,
        count=count,
        probability=probability,
    )


def make_repeated_read_sequence(
    *,
    context_id: str,
    reads: list[list[str]],
) -> RepeatedReadSequence:
    return RepeatedReadSequence(context_id=context_id, reads=reads)


def make_downstream_probe(
    *,
    probe_id: str,
    signature: str,
    event_id: str | None = None,
    context_id: str | None = None,
    outcome_counts: dict[str, int] | None = None,
    outcome_probabilities: dict[str, float] | None = None,
    payload: dict[str, object] | None = None,
) -> DownstreamProbe:
    return DownstreamProbe(
        probe_id=probe_id,
        event_id=event_id,
        context_id=context_id,
        signature=signature,
        outcome_counts=outcome_counts,
        outcome_probabilities=outcome_probabilities,
        payload=payload,
    )


def make_route_trace(
    *,
    route_id: str | None = None,
    steps: list[str] | None = None,
    notes: str | None = None,
) -> RouteTrace:
    return RouteTrace(route_id=route_id, steps=steps, notes=notes)


def make_route_observation(
    *,
    route_id: str,
    endpoint_id: str,
    preparation_id: str | None = None,
    macrostate_id: str | None = None,
    context_id: str | None = None,
    outcome_counts: dict[str, int] | None = None,
    outcome_probabilities: dict[str, float] | None = None,
) -> RouteObservation:
    return RouteObservation(
        preparation_id=preparation_id,
        macrostate_id=macrostate_id,
        route_id=route_id,
        endpoint_id=endpoint_id,
        context_id=context_id,
        outcome_counts=outcome_counts,
        outcome_probabilities=outcome_probabilities,
    )


def build_observation_trace(
    *,
    trace_id: str,
    observations: list[Observation],
    instance_id: str | None = None,
    instance_artifact: str | None = None,
    repeated_read_sequences: list[RepeatedReadSequence] | None = None,
    downstream_probes: list[DownstreamProbe] | None = None,
    route_observations: list[RouteObservation] | None = None,
    route_trace: RouteTrace | None = None,
    metadata: dict[str, str | int | float | bool | None | list[str]] | None = None,
) -> ObservationTrace:
    return ObservationTrace(
        trace_format_version="observation-trace.v1",
        trace_id=trace_id,
        instance_id=instance_id,
        instance_artifact=instance_artifact,
        observations=observations,
        repeated_read_sequences=repeated_read_sequences or [],
        downstream_probes=downstream_probes or [],
        route_observations=route_observations or [],
        route_trace=route_trace,
        metadata=metadata or {},
    )


def write_observation_trace(trace: ObservationTrace, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(trace.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def load_observation_trace(
    path: str | Path,
    *,
    linked_instance: EventPackageInstance | None = None,
) -> ObservationTrace:
    model = load_model(path, kind="observation-trace")
    assert isinstance(model, ObservationTrace)
    if linked_instance is not None:
        result = validate_observation_trace(
            model.model_dump(mode="json"),
            linked_instance=linked_instance,
        )
        if not result.ok or not isinstance(result.model, ObservationTrace):
            raise ValueError("linked instance validation failed for observation trace")
        return result.model
    return model
