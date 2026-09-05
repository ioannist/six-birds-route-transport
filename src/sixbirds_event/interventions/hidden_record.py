from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..schemas.event_package import (
    Atom,
    AuditMetadata,
    Context,
    EqualityProposal,
    Event,
    EventPackageInstance,
)
from ..schemas.observation_trace import Observation, ObservationTrace, RouteObservation
from ..validation import load_model
from .models import HiddenRecordIntervention


@dataclass(slots=True)
class InterventionBuildArtifacts:
    augmented_instance: EventPackageInstance
    before_stat_trace: ObservationTrace
    after_stat_trace: ObservationTrace
    after_route_trace: ObservationTrace


def load_hidden_record_intervention(path: str | Path) -> HiddenRecordIntervention:
    model = load_model(path, kind="hidden-record-intervention")
    assert isinstance(model, HiddenRecordIntervention)
    return model


def load_route_source_trace(path: str | Path) -> ObservationTrace:
    model = load_model(path, kind="observation-trace")
    assert isinstance(model, ObservationTrace)
    return model


def _suffix_id(base: str, residue_field_name: str, residue_value: str) -> str:
    return f"{base}__{residue_field_name}_{residue_value}"


def _route_key(route_observation: RouteObservation) -> str:
    return route_observation.route_id


def _context_map(instance: EventPackageInstance) -> dict[str, Context]:
    return {context.context_id: context for context in instance.contexts}


def _event_map(instance: EventPackageInstance) -> dict[str, Event]:
    return {event.event_id: event for event in instance.events}


def _proposal_map(instance: EventPackageInstance) -> dict[str, EqualityProposal]:
    return {proposal.proposal_id: proposal for proposal in instance.equality_proposals}


def _selected_context_set(spec: HiddenRecordIntervention) -> set[str]:
    return set(spec.selected_context_ids)


def build_augmented_instance(
    spec: HiddenRecordIntervention,
    before_instance: EventPackageInstance,
    *,
    created_at: str,
    augmented_instance_artifact: str,
) -> EventPackageInstance:
    selected_contexts = _selected_context_set(spec)
    context_by_id = _context_map(before_instance)
    event_by_id = _event_map(before_instance)
    proposal_by_id = _proposal_map(before_instance)

    missing_contexts = selected_contexts - set(context_by_id)
    if missing_contexts:
        raise ValueError(
            f"selected_context_ids reference unknown contexts: {', '.join(sorted(missing_contexts))}"
        )
    missing_proposals = set(
        assignment.proposal_id for assignment in spec.proposal_residue_assignments
    ) - set(proposal_by_id)
    if missing_proposals:
        raise ValueError(
            f"proposal_residue_assignments reference unknown proposals: {', '.join(sorted(missing_proposals))}"
        )

    augmented_contexts: list[Context] = []
    atom_id_map: dict[tuple[str, str | None], dict[str, str]] = {}
    for context in before_instance.contexts:
        if context.context_id in selected_contexts:
            for residue_value in spec.residue_values:
                new_context_id = _suffix_id(
                    context.context_id,
                    spec.residue_field_name,
                    residue_value,
                )
                atoms = [
                    Atom(
                        atom_id=_suffix_id(
                            atom.atom_id, spec.residue_field_name, residue_value
                        ),
                        label=atom.label,
                    )
                    for atom in context.atoms
                ]
                atom_id_map[(context.context_id, residue_value)] = {
                    atom.atom_id: split.atom_id
                    for atom, split in zip(context.atoms, atoms, strict=True)
                }
                augmented_contexts.append(
                    Context(
                        context_id=new_context_id,
                        label=context.label,
                        atoms=atoms,
                    )
                )
        else:
            atom_id_map[(context.context_id, None)] = {
                atom.atom_id: atom.atom_id for atom in context.atoms
            }
            augmented_contexts.append(context.model_copy(deep=True))

    augmented_events: list[Event] = []
    event_id_map: dict[tuple[str, str | None], str] = {}
    for event in before_instance.events:
        if event.context_id in selected_contexts:
            for residue_value in spec.residue_values:
                new_event_id = _suffix_id(
                    event.event_id,
                    spec.residue_field_name,
                    residue_value,
                )
                new_context_id = _suffix_id(
                    event.context_id,
                    spec.residue_field_name,
                    residue_value,
                )
                new_atom_ids = [
                    atom_id_map[(event.context_id, residue_value)][atom_id]
                    for atom_id in event.atom_ids
                ]
                event_id_map[(event.event_id, residue_value)] = new_event_id
                augmented_events.append(
                    Event(
                        event_id=new_event_id,
                        context_id=new_context_id,
                        atom_ids=new_atom_ids,
                        label=event.label,
                    )
                )
        else:
            event_id_map[(event.event_id, None)] = event.event_id
            augmented_events.append(event.model_copy(deep=True))

    assignment_by_proposal = {
        assignment.proposal_id: assignment
        for assignment in spec.proposal_residue_assignments
    }
    augmented_proposals: list[EqualityProposal] = []
    augmented_weights = dict(before_instance.weights)
    for proposal in before_instance.equality_proposals:
        assignment = assignment_by_proposal.get(proposal.proposal_id)
        if assignment is None:
            continue
        left_event = event_by_id[proposal.left_event_id]
        right_event = event_by_id[proposal.right_event_id]
        for residue_value in assignment.residue_values:
            left_suffix = (
                residue_value if left_event.context_id in selected_contexts else None
            )
            right_suffix = (
                residue_value if right_event.context_id in selected_contexts else None
            )
            new_left_event_id = event_id_map[(proposal.left_event_id, left_suffix)]
            new_right_event_id = event_id_map[(proposal.right_event_id, right_suffix)]
            constraint_kind = (
                assignment.copied_constraint_kind or proposal.constraint_kind
            )
            new_weight_key = None
            if constraint_kind == "soft":
                if proposal.weight_key is None:
                    new_weight_key = _suffix_id(
                        f"w_{proposal.proposal_id}",
                        spec.residue_field_name,
                        residue_value,
                    )
                    augmented_weights[new_weight_key] = 1.0
                else:
                    new_weight_key = _suffix_id(
                        proposal.weight_key, spec.residue_field_name, residue_value
                    )
                    augmented_weights[new_weight_key] = before_instance.weights[
                        proposal.weight_key
                    ]
            augmented_proposals.append(
                EqualityProposal(
                    proposal_id=_suffix_id(
                        proposal.proposal_id,
                        spec.residue_field_name,
                        residue_value,
                    ),
                    left_event_id=new_left_event_id,
                    right_event_id=new_right_event_id,
                    constraint_kind=constraint_kind,
                    weight_key=new_weight_key,
                    notes=proposal.notes,
                )
            )

    return EventPackageInstance(
        instance_format_version="event-package-instance.v1",
        instance_id=f"{before_instance.instance_id}__{spec.residue_field_name}_explicit",
        contexts=augmented_contexts,
        events=augmented_events,
        equality_proposals=augmented_proposals,
        weights=augmented_weights,
        notes=before_instance.notes,
        metadata={
            **before_instance.metadata,
            "intervention_id": spec.intervention_id,
            "augmentation_policy": spec.augmentation_policy,
            "source_before_instance_artifact": spec.before_instance_artifact,
            "augmented_from_hidden_record": spec.residue_field_name,
            "augmented_instance_artifact": augmented_instance_artifact,
        },
        audit=AuditMetadata(
            created_at=created_at,
            created_by="hidden_record_intervention",
            source=spec.before_instance_artifact,
        ),
    )


def _normalize_probability_mapping(
    values: dict[str, float],
    *,
    tolerance: float = 1e-9,
) -> dict[str, float]:
    total = sum(values.values())
    if abs(total - 1.0) > tolerance:
        raise ValueError(
            f"probability contributions must sum to 1 within tolerance; observed total {total}"
        )
    return {
        outcome: value / total if total else 0.0
        for outcome, value in sorted(values.items())
    }


def _group_route_observations(
    route_source: ObservationTrace,
    *,
    selected_context_ids: set[str],
) -> dict[tuple[str, str], list[RouteObservation]]:
    grouped: dict[tuple[str, str], list[RouteObservation]] = defaultdict(list)
    for route_observation in route_source.route_observations:
        context_id = route_observation.context_id or route_observation.endpoint_id
        if context_id not in selected_context_ids:
            continue
        grouped[(context_id, _route_key(route_observation))].append(route_observation)
    return dict(grouped)


def _aggregate_group_observations(
    observations: list[RouteObservation],
) -> tuple[str, dict[str, int] | dict[str, float]]:
    modes = {
        "count" if observation.outcome_counts is not None else "probability"
        for observation in observations
    }
    if len(modes) != 1:
        raise ValueError("route observation group mixes count and probability inputs")
    mode = next(iter(modes))
    if mode == "count":
        counts: dict[str, int] = defaultdict(int)
        for observation in observations:
            assert observation.outcome_counts is not None
            for outcome, value in observation.outcome_counts.items():
                counts[outcome] += value
        return mode, dict(sorted(counts.items()))
    distributions = [
        _normalize_probability_mapping(observation.outcome_probabilities or {})
        for observation in observations
    ]
    outcomes = sorted({outcome for item in distributions for outcome in item})
    averaged = {
        outcome: sum(item.get(outcome, 0.0) for item in distributions)
        / len(distributions)
        for outcome in outcomes
    }
    return mode, averaged


def _suffix_outcome_values(
    values: dict[str, int] | dict[str, float],
    *,
    residue_field_name: str,
    residue_value: str,
) -> dict[str, int] | dict[str, float]:
    return {
        _suffix_id(outcome_id, residue_field_name, residue_value): value
        for outcome_id, value in sorted(values.items())
    }


def _observations_from_grouped(
    *,
    trace_id: str,
    instance_id: str,
    instance_artifact: str,
    grouped_values: dict[str, tuple[str, dict[str, int] | dict[str, float]]],
    metadata: dict[str, str | int | float | bool | None],
) -> ObservationTrace:
    observations: list[Observation] = []
    for context_id, (mode, values) in sorted(grouped_values.items()):
        for atom_id, value in sorted(values.items()):
            if mode == "count":
                observations.append(
                    Observation(
                        context_id=context_id,
                        atom_ids=[atom_id],
                        count=int(value),
                        status="observed",
                    )
                )
            else:
                observations.append(
                    Observation(
                        context_id=context_id,
                        atom_ids=[atom_id],
                        probability=float(value),
                        status="observed",
                    )
                )
    if not observations:
        raise ValueError("derived observation trace would be empty")
    return ObservationTrace(
        trace_format_version="observation-trace.v1",
        trace_id=trace_id,
        instance_id=instance_id,
        instance_artifact=instance_artifact,
        observations=observations,
        metadata=metadata,
    )


def derive_before_stat_trace(
    spec: HiddenRecordIntervention,
    before_instance: EventPackageInstance,
    route_source: ObservationTrace,
) -> ObservationTrace:
    grouped = _group_route_observations(
        route_source,
        selected_context_ids=_selected_context_set(spec),
    )
    by_context: dict[str, tuple[str, dict[str, int] | dict[str, float]]] = {}
    context_groups: dict[str, list[RouteObservation]] = defaultdict(list)
    for (context_id, _route_id), observations in grouped.items():
        context_groups[context_id].extend(observations)
    for context_id, observations in sorted(context_groups.items()):
        by_context[context_id] = _aggregate_group_observations(observations)
    return _observations_from_grouped(
        trace_id=f"{spec.intervention_id}__before_stat",
        instance_id=before_instance.instance_id,
        instance_artifact=spec.before_instance_artifact,
        grouped_values=by_context,
        metadata={
            "derived_from_route_source": True,
            "residue_field_name": spec.residue_field_name,
            "derivation_mode": "marginalized_over_residue",
        },
    )


def derive_after_stat_trace(
    spec: HiddenRecordIntervention,
    augmented_instance: EventPackageInstance,
    route_source: ObservationTrace,
    *,
    augmented_instance_artifact: str,
) -> ObservationTrace:
    grouped = _group_route_observations(
        route_source,
        selected_context_ids=_selected_context_set(spec),
    )
    by_context: dict[str, tuple[str, dict[str, int] | dict[str, float]]] = {}
    for (context_id, route_id), observations in sorted(grouped.items()):
        split_context_id = _suffix_id(context_id, spec.residue_field_name, route_id)
        mode, values = _aggregate_group_observations(observations)
        by_context[split_context_id] = (
            mode,
            _suffix_outcome_values(
                values,
                residue_field_name=spec.residue_field_name,
                residue_value=route_id,
            ),
        )
    return _observations_from_grouped(
        trace_id=f"{spec.intervention_id}__after_stat",
        instance_id=augmented_instance.instance_id,
        instance_artifact=augmented_instance_artifact,
        grouped_values=by_context,
        metadata={
            "derived_from_route_source": True,
            "residue_field_name": spec.residue_field_name,
            "derivation_mode": "split_by_residue",
        },
    )


def derive_after_route_trace(
    spec: HiddenRecordIntervention,
    augmented_instance: EventPackageInstance,
    route_source: ObservationTrace,
    *,
    augmented_instance_artifact: str,
) -> ObservationTrace:
    grouped = _group_route_observations(
        route_source,
        selected_context_ids=_selected_context_set(spec),
    )
    route_observations: list[RouteObservation] = []
    by_context: dict[str, tuple[str, dict[str, int] | dict[str, float]]] = {}
    for (context_id, route_id), observations in sorted(grouped.items()):
        split_context_id = _suffix_id(context_id, spec.residue_field_name, route_id)
        mode, values = _aggregate_group_observations(observations)
        split_values = _suffix_outcome_values(
            values,
            residue_field_name=spec.residue_field_name,
            residue_value=route_id,
        )
        by_context[split_context_id] = (mode, split_values)
        payload = {
            "preparation_id": f"prep_hidden_record__{spec.residue_field_name}_{route_id}",
            "route_id": route_id,
            "endpoint_id": split_context_id,
            "context_id": split_context_id,
        }
        if mode == "count":
            route_observations.append(
                RouteObservation(
                    **payload,
                    outcome_counts={
                        key: int(value) for key, value in split_values.items()
                    },
                )
            )
        else:
            route_observations.append(
                RouteObservation(
                    **payload,
                    outcome_probabilities={
                        key: float(value) for key, value in split_values.items()
                    },
                )
            )
    trace = _observations_from_grouped(
        trace_id=f"{spec.intervention_id}__after_route",
        instance_id=augmented_instance.instance_id,
        instance_artifact=augmented_instance_artifact,
        grouped_values=by_context,
        metadata={
            "derived_from_route_source": True,
            "residue_field_name": spec.residue_field_name,
            "derivation_mode": "route_split_for_rm",
        },
    )
    return trace.model_copy(update={"route_observations": route_observations})
