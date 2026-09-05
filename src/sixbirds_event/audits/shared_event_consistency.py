from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import ObservationTrace
from ..statistics.probe_signatures import extract_probe_signatures


@dataclass(slots=True)
class EventPairSECResult:
    proposal_id: str
    left_event_id: str
    right_event_id: str
    left_context_id: str
    right_context_id: str
    common_probe_ids: list[str]
    per_probe_distances: dict[str, float]
    approx_score: float | None
    exact_consistent: bool | None
    insufficient_data: bool


@dataclass(slots=True)
class ContextPairSECResult:
    left_context_id: str
    right_context_id: str
    scored_pair_count: int
    insufficient_data_pair_count: int
    mean_approx_score: float | None
    max_approx_score: float | None
    exact_pass_count: int
    exact_pass_fraction: float | None


@dataclass(slots=True)
class SharedEventConsistencyResult:
    trace_ids: list[str]
    instance_id: str
    event_pair_results: list[EventPairSECResult]
    context_pair_results: list[ContextPairSECResult]
    exact_tolerance: float
    aggregation_policy: dict[str, str]


def _tv_distance(
    left: dict[str, float],
    right: dict[str, float],
) -> float:
    outcomes = sorted(set(left) | set(right))
    return 0.5 * sum(
        abs(left.get(outcome, 0.0) - right.get(outcome, 0.0)) for outcome in outcomes
    )


def compute_shared_event_consistency(
    instance: EventPackageInstance,
    traces: list[ObservationTrace],
    *,
    exact_tolerance: float = 1e-6,
) -> SharedEventConsistencyResult:
    signatures = extract_probe_signatures(traces, instance=instance)
    event_by_id = {event.event_id: event for event in instance.events}

    event_pair_results: list[EventPairSECResult] = []
    grouped: dict[tuple[str, str], list[EventPairSECResult]] = defaultdict(list)

    for proposal in instance.equality_proposals:
        left_event = event_by_id[proposal.left_event_id]
        right_event = event_by_id[proposal.right_event_id]
        if left_event.context_id == right_event.context_id:
            continue

        left_probes = signatures.get(left_event.event_id, {})
        right_probes = signatures.get(right_event.event_id, {})
        common_probe_ids = sorted(set(left_probes) & set(right_probes))
        per_probe_distances = {
            probe_id: _tv_distance(left_probes[probe_id], right_probes[probe_id])
            for probe_id in common_probe_ids
        }
        insufficient_data = not common_probe_ids
        approx_score = (
            sum(per_probe_distances.values()) / len(per_probe_distances)
            if per_probe_distances
            else None
        )
        exact_consistent = (
            all(
                distance <= exact_tolerance for distance in per_probe_distances.values()
            )
            if per_probe_distances
            else None
        )
        pair_result = EventPairSECResult(
            proposal_id=proposal.proposal_id,
            left_event_id=left_event.event_id,
            right_event_id=right_event.event_id,
            left_context_id=left_event.context_id,
            right_context_id=right_event.context_id,
            common_probe_ids=common_probe_ids,
            per_probe_distances=per_probe_distances,
            approx_score=approx_score,
            exact_consistent=exact_consistent,
            insufficient_data=insufficient_data,
        )
        event_pair_results.append(pair_result)
        context_key = tuple(sorted((left_event.context_id, right_event.context_id)))
        grouped[context_key].append(pair_result)

    context_pair_results: list[ContextPairSECResult] = []
    for (left_context_id, right_context_id), pair_results in sorted(grouped.items()):
        scored = [result for result in pair_results if not result.insufficient_data]
        approx_scores = [
            result.approx_score for result in scored if result.approx_score is not None
        ]
        exact_pass_count = sum(1 for result in scored if result.exact_consistent)
        scored_pair_count = len(scored)
        context_pair_results.append(
            ContextPairSECResult(
                left_context_id=left_context_id,
                right_context_id=right_context_id,
                scored_pair_count=scored_pair_count,
                insufficient_data_pair_count=sum(
                    1 for result in pair_results if result.insufficient_data
                ),
                mean_approx_score=(
                    sum(approx_scores) / len(approx_scores) if approx_scores else None
                ),
                max_approx_score=max(approx_scores) if approx_scores else None,
                exact_pass_count=exact_pass_count,
                exact_pass_fraction=(
                    exact_pass_count / scored_pair_count if scored_pair_count else None
                ),
            )
        )

    return SharedEventConsistencyResult(
        trace_ids=[trace.trace_id for trace in traces],
        instance_id=instance.instance_id,
        event_pair_results=event_pair_results,
        context_pair_results=context_pair_results,
        exact_tolerance=exact_tolerance,
        aggregation_policy={
            "count_policy": "sum counts across traces, then normalize",
            "probability_policy": "average normalized distributions across trace contributions",
            "distance": "total_variation",
        },
    )
