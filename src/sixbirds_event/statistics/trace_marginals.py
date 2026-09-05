from __future__ import annotations

from dataclasses import dataclass

from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import ObservationTrace


@dataclass(slots=True)
class ContextMarginal:
    context_id: str
    mode: str
    probabilities: dict[str, float]
    total_input: float


@dataclass(slots=True)
class EmpiricalMarginalBundle:
    trace_ids: list[str]
    context_marginals: dict[str, ContextMarginal]


def extract_empirical_marginals(
    trace: ObservationTrace,
    instance: EventPackageInstance | None = None,
    *,
    tolerance: float = 1e-9,
) -> dict[str, ContextMarginal]:
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    if instance is not None:
        if trace.instance_id is not None and trace.instance_id != instance.instance_id:
            raise ValueError(
                "trace instance_id must match the provided EventPackageInstance"
            )
        context_atoms = {
            context.context_id: [atom.atom_id for atom in context.atoms]
            for context in instance.contexts
        }
    else:
        context_atoms: dict[str, list[str]] = {}

    grouped: dict[str, list[object]] = {}
    for observation in trace.observations:
        grouped.setdefault(observation.context_id, []).append(observation)

    marginals: dict[str, ContextMarginal] = {}
    for context_id, observations in grouped.items():
        if instance is not None and context_id not in context_atoms:
            raise ValueError(f"unknown context_id '{context_id}' in observation trace")

        mode: str | None = None
        totals: dict[str, float] = {}
        for observation in observations:
            has_count = observation.count is not None
            has_probability = observation.probability is not None
            if has_count == has_probability:
                raise ValueError(
                    f"context '{context_id}' observations must use exactly one of count or probability"
                )
            current_mode = "count" if has_count else "probability"
            if mode is None:
                mode = current_mode
            elif mode != current_mode:
                raise ValueError(
                    f"context '{context_id}' mixes count and probability observations"
                )
            weight = float(observation.count if has_count else observation.probability)
            for atom_id in observation.atom_ids:
                if instance is not None and atom_id not in context_atoms[context_id]:
                    raise ValueError(
                        f"unknown atom_id '{atom_id}' for context '{context_id}'"
                    )
                totals[atom_id] = totals.get(atom_id, 0.0) + weight

        assert mode is not None
        total_input = sum(totals.values())
        if mode == "count":
            if total_input <= 0:
                raise ValueError(
                    f"context '{context_id}' count observations must sum to a positive total"
                )
            probabilities = {
                atom_id: value / total_input for atom_id, value in totals.items()
            }
        else:
            if abs(total_input - 1.0) > tolerance:
                raise ValueError(
                    f"context '{context_id}' probability observations must sum to 1 within tolerance"
                )
            probabilities = dict(totals)

        if instance is not None:
            probabilities = {
                atom_id: probabilities.get(atom_id, 0.0)
                for atom_id in context_atoms[context_id]
            }

        marginals[context_id] = ContextMarginal(
            context_id=context_id,
            mode=mode,
            probabilities=probabilities,
            total_input=total_input,
        )

    return marginals


def aggregate_empirical_marginals(
    traces: list[ObservationTrace],
    instance: EventPackageInstance | None = None,
    *,
    tolerance: float = 1e-9,
) -> EmpiricalMarginalBundle:
    if not traces:
        raise ValueError("at least one trace is required")

    extracted = [
        extract_empirical_marginals(trace, instance, tolerance=tolerance)
        for trace in traces
    ]
    trace_ids = [trace.trace_id for trace in traces]
    context_ids = set().union(*(marginals.keys() for marginals in extracted))
    aggregated: dict[str, ContextMarginal] = {}

    # Aggregate normalized per-trace context marginals with equal weight per
    # contributing trace segment. This keeps count and probability inputs on the
    # same explicit footing after each trace is normalized locally.
    for context_id in sorted(context_ids):
        contributions = [
            marginals[context_id] for marginals in extracted if context_id in marginals
        ]
        atom_ids = sorted(
            set().union(
                *(contribution.probabilities.keys() for contribution in contributions)
            )
        )
        probabilities = {
            atom_id: sum(
                contribution.probabilities.get(atom_id, 0.0)
                for contribution in contributions
            )
            / len(contributions)
            for atom_id in atom_ids
        }
        total_input = sum(contribution.total_input for contribution in contributions)
        aggregated[context_id] = ContextMarginal(
            context_id=context_id,
            mode="aggregated",
            probabilities=probabilities,
            total_input=total_input,
        )

    return EmpiricalMarginalBundle(
        trace_ids=trace_ids,
        context_marginals=aggregated,
    )
