from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import ObservationTrace, RouteObservation


@dataclass(slots=True)
class RouteSignature:
    preparation_kind: str
    preparation_id: str
    endpoint_id: str
    route_id: str
    context_id: str | None
    distribution: dict[str, float]


def _normalize_counts(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    if total <= 0:
        raise ValueError("route outcome_counts must sum to a positive total")
    return {outcome: value / total for outcome, value in sorted(counts.items())}


def _normalize_probabilities(
    probabilities: dict[str, float],
    *,
    tolerance: float,
) -> dict[str, float]:
    total = sum(probabilities.values())
    if abs(total - 1.0) > tolerance:
        raise ValueError(
            f"route outcome_probabilities must sum to 1 within tolerance; observed total {total}"
        )
    return {
        outcome: value / total if total else 0.0
        for outcome, value in sorted(probabilities.items())
    }


def _start_key(route_observation: RouteObservation) -> tuple[str, str]:
    if route_observation.preparation_id is not None:
        return ("preparation_id", route_observation.preparation_id)
    assert route_observation.macrostate_id is not None
    return ("macrostate_id", route_observation.macrostate_id)


def extract_route_signatures(
    traces: list[ObservationTrace],
    *,
    instance: EventPackageInstance | None = None,
    tolerance: float = 1e-9,
) -> dict[tuple[str, str, str], dict[str, RouteSignature]]:
    if not traces:
        raise ValueError("at least one trace is required for RM")

    known_context_ids = (
        {context.context_id for context in instance.contexts}
        if instance is not None
        else None
    )
    grouped: dict[
        tuple[str, str, str, str],
        list[tuple[str, dict[str, int] | dict[str, float], str | None]],
    ] = defaultdict(list)

    for trace in traces:
        if (
            instance is not None
            and trace.instance_id is not None
            and trace.instance_id != instance.instance_id
        ):
            raise ValueError("trace instance_id must match the provided instance_id")
        for route_observation in trace.route_observations:
            if (
                known_context_ids is not None
                and route_observation.context_id is not None
                and route_observation.context_id not in known_context_ids
            ):
                raise ValueError(
                    f"unknown context_id '{route_observation.context_id}' in route observation"
                )
            preparation_kind, preparation_id = _start_key(route_observation)
            key = (
                preparation_kind,
                preparation_id,
                route_observation.endpoint_id,
                route_observation.route_id,
            )
            if route_observation.outcome_counts is not None:
                grouped[key].append(
                    (
                        "count",
                        route_observation.outcome_counts,
                        route_observation.context_id,
                    )
                )
            else:
                assert route_observation.outcome_probabilities is not None
                grouped[key].append(
                    (
                        "probability",
                        route_observation.outcome_probabilities,
                        route_observation.context_id,
                    )
                )

    signatures: dict[tuple[str, str, str], dict[str, RouteSignature]] = defaultdict(
        dict
    )
    for (
        preparation_kind,
        preparation_id,
        endpoint_id,
        route_id,
    ), contributions in sorted(grouped.items()):
        modes = {mode for mode, _, _ in contributions}
        if len(modes) != 1:
            raise ValueError(
                f"route group ({preparation_id}, {route_id}, {endpoint_id}) mixes count and probability inputs"
            )
        context_ids = {
            context_id for _, _, context_id in contributions if context_id is not None
        }
        if len(context_ids) > 1:
            raise ValueError(
                f"route group ({preparation_id}, {route_id}, {endpoint_id}) has inconsistent context_id values"
            )
        context_id = next(iter(context_ids)) if context_ids else None
        mode = next(iter(modes))
        if mode == "count":
            totals: dict[str, int] = defaultdict(int)
            for _, counts, _ in contributions:
                assert isinstance(counts, dict)
                for outcome, value in counts.items():
                    totals[outcome] += int(value)
            distribution = _normalize_counts(dict(totals))
        else:
            normalized = [
                _normalize_probabilities(probabilities, tolerance=tolerance)
                for _, probabilities, _ in contributions
            ]
            outcomes = sorted({outcome for item in normalized for outcome in item})
            distribution = {
                outcome: sum(item.get(outcome, 0.0) for item in normalized)
                / len(normalized)
                for outcome in outcomes
            }
        signatures[(preparation_kind, preparation_id, endpoint_id)][route_id] = (
            RouteSignature(
                preparation_kind=preparation_kind,
                preparation_id=preparation_id,
                endpoint_id=endpoint_id,
                route_id=route_id,
                context_id=context_id,
                distribution=distribution,
            )
        )
    return dict(signatures)
