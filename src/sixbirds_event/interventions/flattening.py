from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..discovery.models import DiscoveredContextFamily
from ..schemas.observation_trace import Observation, ObservationTrace, RouteObservation
from ..substrates.config import ProtocolSpec, SubstrateConfig
from ..substrates.run_trace import SubstrateRun
from ..validation import load_model
from .models import FlatteningIntervention


def load_flattening_intervention(path: str | Path) -> FlatteningIntervention:
    model = load_model(path, kind="flattening-intervention")
    assert isinstance(model, FlatteningIntervention)
    return model


def load_substrate_run(path: str | Path) -> SubstrateRun:
    model = load_model(path, kind="substrate-run")
    assert isinstance(model, SubstrateRun)
    return model


def build_completed_config(
    config: SubstrateConfig,
    spec: FlatteningIntervention,
    *,
    derived_config_artifact: str,
) -> tuple[SubstrateConfig, str]:
    before_protocol = next(
        (
            protocol
            for protocol in config.protocols
            if protocol.protocol_id == spec.before_protocol_id
        ),
        None,
    )
    if before_protocol is None:
        raise ValueError(
            f"unknown before_protocol_id '{spec.before_protocol_id}' in source config"
        )
    action_ids = [action.action_id for action in config.actions]
    if spec.completion_policy.append_action_id not in action_ids:
        raise ValueError(
            f"unknown append_action_id '{spec.completion_policy.append_action_id}' in source config"
        )
    after_protocol_id = spec.completion_policy.after_protocol_id or (
        f"{spec.before_protocol_id}__completed_"
        f"{spec.completion_policy.append_action_id}_x{spec.completion_policy.append_repetitions}"
    )
    appended_actions = [
        spec.completion_policy.append_action_id
    ] * spec.completion_policy.append_repetitions
    after_protocol = ProtocolSpec(
        protocol_id=after_protocol_id,
        action_ids=[*before_protocol.action_ids, *appended_actions],
    )
    derived = config.model_copy(
        update={
            "config_id": f"{config.config_id}__flattened",
            "protocols": [*config.protocols, after_protocol],
            "metadata": {
                **config.metadata,
                "source_config_artifact": config.metadata.get(
                    "source_config_artifact", config.config_id
                ),
                "derived_config_artifact": derived_config_artifact,
                "flattening_append_action_id": spec.completion_policy.append_action_id,
                "flattening_append_repetitions": spec.completion_policy.append_repetitions,
            },
        }
    )
    return derived, after_protocol_id


def derive_route_trace_from_run(
    raw_run: SubstrateRun,
    spec: FlatteningIntervention,
    *,
    trace_id: str,
    endpoint_step_index: int,
) -> ObservationTrace:
    route_counts: dict[str, Counter[str]] = {}
    aggregate_counts: Counter[str] = Counter()
    for trajectory in raw_run.trajectories:
        route_step = next(
            (
                step
                for step in trajectory.steps
                if step.step_index == spec.route_extraction.route_step_index
            ),
            None,
        )
        endpoint_step = next(
            (
                step
                for step in trajectory.steps
                if step.step_index == endpoint_step_index
            ),
            None,
        )
        if route_step is None or endpoint_step is None:
            continue
        route_label = route_step.observations.get(spec.route_extraction.route_lens_id)
        endpoint_label = endpoint_step.observations.get(
            spec.route_extraction.endpoint_lens_id
        )
        if route_label is None or endpoint_label is None:
            continue
        route_counts.setdefault(route_label, Counter())[endpoint_label] += 1
        aggregate_counts[endpoint_label] += 1
    observations = [
        Observation(
            context_id=spec.route_extraction.endpoint_id,
            atom_ids=[outcome],
            count=count,
            status="observed",
        )
        for outcome, count in sorted(aggregate_counts.items())
    ]
    route_observations = [
        RouteObservation(
            preparation_id=raw_run.preparation_id,
            route_id=route_id,
            endpoint_id=spec.route_extraction.endpoint_id,
            outcome_counts=dict(sorted(counts.items())),
        )
        for route_id, counts in sorted(route_counts.items())
    ]
    if not observations or not route_observations:
        raise ValueError(
            "route extraction yielded no observable route/endpoint data for the configured lens and step settings"
        )
    return ObservationTrace(
        trace_format_version="observation-trace.v1",
        trace_id=trace_id,
        observations=observations,
        route_observations=route_observations,
        metadata={
            "derived_from_substrate_run": raw_run.run_id,
            "route_lens_id": spec.route_extraction.route_lens_id,
            "route_step_index": spec.route_extraction.route_step_index,
            "endpoint_lens_id": spec.route_extraction.endpoint_lens_id,
            "endpoint_step_index": endpoint_step_index,
            "observable_route_only": True,
        },
    )


def derive_stat_trace_from_family(
    raw_run: SubstrateRun,
    family: DiscoveredContextFamily,
    *,
    instance_id: str,
    instance_artifact: str,
    trace_id: str,
) -> ObservationTrace:
    observations: list[Observation] = []
    for context in family.accepted_contexts:
        label_to_outcome = {
            outcome.observation_label: outcome.outcome_id
            for outcome in context.atomic_outcomes
        }
        counts: Counter[str] = Counter()
        for trajectory in raw_run.trajectories:
            if (
                trajectory.preparation_id != context.candidate_key.preparation_id
                or trajectory.protocol_id != context.candidate_key.protocol_id
            ):
                continue
            step = next(
                (
                    step
                    for step in trajectory.steps
                    if step.step_index == context.candidate_key.step_index
                ),
                None,
            )
            if step is None:
                continue
            label = step.observations.get(context.candidate_key.lens_id)
            if label is None:
                continue
            outcome_id = label_to_outcome.get(label)
            if outcome_id is None:
                continue
            counts[outcome_id] += 1
        for outcome in context.atomic_outcomes:
            observations.append(
                Observation(
                    context_id=context.context_id,
                    atom_ids=[outcome.outcome_id],
                    count=counts.get(outcome.outcome_id, 0),
                    status="observed",
                )
            )
    if not observations:
        raise ValueError("derived statistical trace would be empty")
    return ObservationTrace(
        trace_format_version="observation-trace.v1",
        trace_id=trace_id,
        instance_id=instance_id,
        instance_artifact=instance_artifact,
        observations=observations,
        metadata={
            "derived_from_substrate_run": raw_run.run_id,
            "derivation_kind": "flattening_stat_trace",
        },
    )
