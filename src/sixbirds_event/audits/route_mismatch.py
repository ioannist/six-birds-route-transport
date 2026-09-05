from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import ObservationTrace
from ..statistics.route_signatures import extract_route_signatures


@dataclass(slots=True)
class RoutePairMismatchResult:
    preparation_id: str
    preparation_kind: str
    endpoint_id: str
    left_route_id: str
    right_route_id: str
    tv_distance: float
    exact_agreement: bool


@dataclass(slots=True)
class PreparationEndpointRMResult:
    preparation_id: str
    preparation_kind: str
    endpoint_id: str
    route_count: int
    scored_pair_count: int
    mean_pairwise_tv: float | None
    max_pairwise_tv: float | None
    exact_pass_count: int
    exact_pass_fraction: float | None
    insufficient_data: bool


@dataclass(slots=True)
class RouteMismatchResult:
    trace_ids: list[str]
    instance_id: str | None
    overall_rm: float | None
    exact_tolerance: float
    route_pair_results: list[RoutePairMismatchResult]
    preparation_endpoint_results: list[PreparationEndpointRMResult]
    insufficient_data_groups: list[str]
    aggregation_policy: dict[str, str]


def _tv_distance(left: dict[str, float], right: dict[str, float]) -> float:
    outcomes = sorted(set(left) | set(right))
    return 0.5 * sum(
        abs(left.get(outcome, 0.0) - right.get(outcome, 0.0)) for outcome in outcomes
    )


def compute_route_mismatch(
    traces: list[ObservationTrace],
    *,
    instance: EventPackageInstance | None = None,
    exact_tolerance: float = 1e-6,
) -> RouteMismatchResult:
    signatures = extract_route_signatures(
        traces,
        instance=instance,
    )
    route_pair_results: list[RoutePairMismatchResult] = []
    preparation_endpoint_results: list[PreparationEndpointRMResult] = []
    insufficient_data_groups: list[str] = []

    for (
        preparation_kind,
        preparation_id,
        endpoint_id,
    ), route_map in sorted(signatures.items()):
        route_ids = sorted(route_map)
        if len(route_ids) < 2:
            insufficient_data_groups.append(
                f"{preparation_kind}:{preparation_id}:{endpoint_id}"
            )
            preparation_endpoint_results.append(
                PreparationEndpointRMResult(
                    preparation_id=preparation_id,
                    preparation_kind=preparation_kind,
                    endpoint_id=endpoint_id,
                    route_count=len(route_ids),
                    scored_pair_count=0,
                    mean_pairwise_tv=None,
                    max_pairwise_tv=None,
                    exact_pass_count=0,
                    exact_pass_fraction=None,
                    insufficient_data=True,
                )
            )
            continue

        pair_distances: list[float] = []
        exact_pass_count = 0
        for left_route_id, right_route_id in combinations(route_ids, 2):
            distance = _tv_distance(
                route_map[left_route_id].distribution,
                route_map[right_route_id].distribution,
            )
            exact_agreement = distance <= exact_tolerance
            if exact_agreement:
                exact_pass_count += 1
            pair_distances.append(distance)
            route_pair_results.append(
                RoutePairMismatchResult(
                    preparation_id=preparation_id,
                    preparation_kind=preparation_kind,
                    endpoint_id=endpoint_id,
                    left_route_id=left_route_id,
                    right_route_id=right_route_id,
                    tv_distance=distance,
                    exact_agreement=exact_agreement,
                )
            )

        scored_pair_count = len(pair_distances)
        preparation_endpoint_results.append(
            PreparationEndpointRMResult(
                preparation_id=preparation_id,
                preparation_kind=preparation_kind,
                endpoint_id=endpoint_id,
                route_count=len(route_ids),
                scored_pair_count=scored_pair_count,
                mean_pairwise_tv=sum(pair_distances) / scored_pair_count,
                max_pairwise_tv=max(pair_distances),
                exact_pass_count=exact_pass_count,
                exact_pass_fraction=exact_pass_count / scored_pair_count,
                insufficient_data=False,
            )
        )

    scored_group_means = [
        result.mean_pairwise_tv
        for result in preparation_endpoint_results
        if not result.insufficient_data and result.mean_pairwise_tv is not None
    ]
    overall_rm = (
        sum(scored_group_means) / len(scored_group_means)
        if scored_group_means
        else None
    )
    return RouteMismatchResult(
        trace_ids=[trace.trace_id for trace in traces],
        instance_id=instance.instance_id if instance is not None else None,
        overall_rm=overall_rm,
        exact_tolerance=exact_tolerance,
        route_pair_results=route_pair_results,
        preparation_endpoint_results=preparation_endpoint_results,
        insufficient_data_groups=insufficient_data_groups,
        aggregation_policy={
            "count_policy": "sum counts across contributions, then normalize",
            "probability_policy": "average normalized distributions across contributions",
            "distance": "total_variation",
            "overall_rm": "equal-weight mean of mean_pairwise_tv across scored preparation-endpoint groups",
        },
    )
