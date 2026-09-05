from __future__ import annotations

import csv
import json
from dataclasses import dataclass, replace
from fractions import Fraction
from itertools import product
from pathlib import Path
from typing import Any, Iterable

from .analysis import (
    LoopActionUndefinedError,
    TransportMapNotWellDefinedError,
    TransportMapUndefinedError,
    compute_current_loop_action,
    compute_current_partition,
    compute_exact_max_abs_future_gap,
    compute_predictive_loop_action,
    compute_predictive_partition,
    compute_predictive_transport_map,
    enumerate_memory_witnesses,
    resolve_interface_history_ids,
)
from .benchmarks import REPO_ROOT
from .core import RouteTransportPackage, load_route_transport_package_from_config
from .schemas import RouteTransportPackageConfig, SearchSpace
from .search_spaces import load_search_space, load_search_space_for_id, search_space_path_for_id


DISCOVERY_LABELS = ("flat", "dissipative", "coherent_candidate")


@dataclass(frozen=True)
class DiscoveryInterfaceMetrics:
    interface_id: str
    history_count: int
    current_quotient_size: int
    predictive_quotient_size: int
    max_fiber_size: int
    witness_count: int
    discrepancy_metric_name: str
    discrepancy_metric_value: Fraction
    current_loop_score: Fraction
    predictive_loop_score: Fraction


@dataclass(frozen=True)
class DiscoveryTransportCollapseEvidence:
    source_interface_id: str
    target_interface_id: str
    continuation_id: str
    source_predictive_class_count: int
    target_predictive_class_count: int
    class_image_mapping: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveryLoopEvidence:
    interface_id: str
    loop_id: str
    moved_predictive_class_ids: tuple[str, ...]
    class_image_mapping: tuple[str, ...]
    moved_class_fraction: Fraction


@dataclass(frozen=True)
class DiscoveryCandidateSpec:
    search_id: str
    candidate_id: str
    support_size: int
    interface_count: int
    carrier_family: str
    route_update_family: str
    observable_family: str
    continuation_catalog_family: str
    internal_state_count: int
    history_count: int
    continuation_count: int
    loop_count: int


@dataclass(frozen=True)
class DiscoveryCandidateRecord:
    candidate_spec: DiscoveryCandidateSpec
    candidate_label: str
    primary_interface_id: str
    interface_metrics: tuple[DiscoveryInterfaceMetrics, ...]
    transport_collapse_evidence: DiscoveryTransportCollapseEvidence | None = None
    loop_action_evidence: DiscoveryLoopEvidence | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryAtlas:
    search_id: str
    seed: int
    search_config_path: Path
    raw_candidate_count: int
    capped_candidate_count: int
    attempted_candidate_count: int
    realized_candidate_count: int
    evaluated_candidate_count: int
    candidate_records: tuple[DiscoveryCandidateRecord, ...]
    class_counts: tuple[tuple[str, int], ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryRunArtifacts:
    search_id: str
    seed: int
    json_atlas_path: Path
    csv_summary_path: Path
    summary_note_path: Path
    atlas: DiscoveryAtlas


@dataclass(frozen=True)
class _RealizedCandidate:
    spec: DiscoveryCandidateSpec
    config: RouteTransportPackageConfig
    package: RouteTransportPackage
    forward_continuation_ids: tuple[str, ...]


def enumerate_discovery_candidates(
    *,
    search_id: str | None = None,
    search_path: str | Path | None = None,
    search_space: SearchSpace | None = None,
) -> tuple[DiscoveryCandidateSpec, ...]:
    resolved_search_space, _ = _resolve_search_space(
        search_id=search_id,
        search_path=search_path,
        search_space=search_space,
    )
    specs, _, _ = _enumerate_realized_candidates(resolved_search_space)
    return specs


def realize_discovery_candidate(
    candidate_spec: DiscoveryCandidateSpec,
    *,
    search_id: str | None = None,
    search_path: str | Path | None = None,
    search_space: SearchSpace | None = None,
) -> RouteTransportPackage:
    resolved_search_space, _ = _resolve_search_space(
        search_id=search_id,
        search_path=search_path,
        search_space=search_space,
    )
    realized = _realize_candidate(candidate_spec, resolved_search_space)
    return realized.package


def run_discovery_search(
    *,
    search_id: str | None = None,
    search_path: str | Path | None = None,
    seed: int = 0,
    output_root: str | Path | None = None,
) -> DiscoveryRunArtifacts:
    search_space, resolved_search_path = _resolve_search_space(
        search_id=search_id,
        search_path=search_path,
        search_space=None,
    )
    specs, attempted_count, warnings = _enumerate_realized_candidates(search_space)

    records: list[DiscoveryCandidateRecord] = []
    realized_count = 0
    atlas_warnings = list(warnings)
    for spec in specs:
        try:
            realized = _realize_candidate(spec, search_space)
        except Exception as exc:  # pragma: no cover - defensive guard
            atlas_warnings.append(
                f"{spec.candidate_id}: realization failed ({type(exc).__name__}: {exc})"
            )
            continue

        realized_count += 1
        try:
            records.append(_evaluate_realized_candidate(realized))
        except Exception as exc:  # pragma: no cover - defensive guard
            atlas_warnings.append(
                f"{spec.candidate_id}: evaluation failed ({type(exc).__name__}: {exc})"
            )

    ordered_counts = tuple(
        (label, sum(1 for record in records if record.candidate_label == label))
        for label in DISCOVERY_LABELS
    )
    raw_candidate_count = _generation_raw_candidate_count(search_space)
    capped_candidate_count = min(raw_candidate_count, search_space.max_candidates)
    atlas = DiscoveryAtlas(
        search_id=search_space.search_id,
        seed=seed,
        search_config_path=resolved_search_path,
        raw_candidate_count=raw_candidate_count,
        capped_candidate_count=capped_candidate_count,
        attempted_candidate_count=attempted_count,
        realized_candidate_count=realized_count,
        evaluated_candidate_count=len(records),
        candidate_records=tuple(records),
        class_counts=ordered_counts,
        warnings=tuple(atlas_warnings),
    )
    return write_discovery_atlas(atlas=atlas, output_root=output_root)


def write_discovery_atlas(
    *,
    atlas: DiscoveryAtlas,
    output_root: str | Path | None = None,
) -> DiscoveryRunArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    json_path = root / "artifacts" / "results" / "discovery" / f"{atlas.search_id}.atlas.json"
    csv_path = root / "artifacts" / "tables" / f"discovery_{atlas.search_id}.csv"
    note_path = root / "docs" / "results" / f"{atlas.search_id}.atlas.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(_atlas_payload(atlas), indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(atlas, csv_path)
    note_path.write_text(_build_summary_note(atlas, json_path, csv_path, note_path), encoding="utf-8")
    return DiscoveryRunArtifacts(
        search_id=atlas.search_id,
        seed=atlas.seed,
        json_atlas_path=json_path,
        csv_summary_path=csv_path,
        summary_note_path=note_path,
        atlas=atlas,
    )


def _resolve_search_space(
    *,
    search_id: str | None,
    search_path: str | Path | None,
    search_space: SearchSpace | None,
) -> tuple[SearchSpace, Path]:
    provided_count = sum(
        item is not None for item in (search_id, search_path, search_space)
    )
    if provided_count != 1:
        raise ValueError("provide exactly one of search_id, search_path, or search_space")

    if search_space is not None:
        return search_space, search_space_path_for_id(search_space.search_id)
    if search_id is not None:
        return load_search_space_for_id(search_id), search_space_path_for_id(search_id)
    assert search_path is not None
    return load_search_space(search_path), Path(search_path)


def _enumerate_realized_candidates(
    search_space: SearchSpace,
) -> tuple[tuple[DiscoveryCandidateSpec, ...], int, tuple[str, ...]]:
    _validate_discovery_ready_search_space(search_space)
    specs: list[DiscoveryCandidateSpec] = []
    warnings: list[str] = []
    attempted_count = 0
    active_dimensions = (
        search_space.support_size_candidates,
        search_space.interface_count_candidates,
        search_space.carrier_family_candidates,
        search_space.route_update_family_candidates,
        search_space.observable_family_candidates,
        search_space.continuation_catalog_family_candidates,
    )
    for combination in product(*active_dimensions):
        attempted_count += 1
        spec = _spec_for_combination(
            search_space,
            combination,
            candidate_id=f"cand_{len(specs):04d}",
        )
        try:
            realized = _realize_candidate(spec, search_space)
        except Exception as exc:  # pragma: no cover - defensive guard
            warnings.append(
                f"{spec.candidate_id}: realization filter probe failed ({type(exc).__name__}: {exc})"
            )
            continue
        if not _matches_numeric_filters(realized.spec, search_space, realized.config):
            continue
        specs.append(realized.spec)
        if len(specs) >= search_space.max_candidates:
            break
    return tuple(specs), attempted_count, tuple(warnings)


def _validate_discovery_ready_search_space(search_space: SearchSpace) -> None:
    required_lists = (
        ("support_size_candidates", search_space.support_size_candidates),
        ("interface_count_candidates", search_space.interface_count_candidates),
        ("carrier_family_candidates", search_space.carrier_family_candidates),
        ("route_update_family_candidates", search_space.route_update_family_candidates),
        ("observable_family_candidates", search_space.observable_family_candidates),
        (
            "continuation_catalog_family_candidates",
            search_space.continuation_catalog_family_candidates,
        ),
    )
    empty = [name for name, values in required_lists if not values]
    if empty:
        joined = ", ".join(empty)
        raise ValueError(
            "discovery search space requires non-empty candidate lists for: "
            f"{joined}"
        )


def _generation_raw_candidate_count(search_space: SearchSpace) -> int:
    count = 1
    for values in (
        search_space.support_size_candidates,
        search_space.interface_count_candidates,
        search_space.carrier_family_candidates,
        search_space.route_update_family_candidates,
        search_space.observable_family_candidates,
        search_space.continuation_catalog_family_candidates,
    ):
        count *= len(values)
    return count


def _spec_for_combination(
    search_space: SearchSpace,
    combination: tuple[Any, ...],
    *,
    candidate_id: str,
) -> DiscoveryCandidateSpec:
    (
        support_size,
        interface_count,
        carrier_family,
        route_update_family,
        observable_family,
        continuation_catalog_family,
    ) = combination
    return DiscoveryCandidateSpec(
        search_id=search_space.search_id,
        candidate_id=candidate_id,
        support_size=support_size,
        interface_count=interface_count,
        carrier_family=carrier_family,
        route_update_family=route_update_family,
        observable_family=observable_family,
        continuation_catalog_family=continuation_catalog_family,
        internal_state_count=0,
        history_count=0,
        continuation_count=0,
        loop_count=0,
    )


def _realize_candidate(
    candidate_spec: DiscoveryCandidateSpec,
    search_space: SearchSpace,
) -> _RealizedCandidate:
    support_labels = tuple(f"S{index}" for index in range(candidate_spec.support_size))
    interface_ids = tuple(f"i{index}" for index in range(candidate_spec.interface_count))
    carrier_size = _carrier_size(candidate_spec.carrier_family)
    state_ids, support_projection, state_metadata = _build_state_space(
        support_labels,
        carrier_size,
        candidate_spec.carrier_family,
    )
    event_packages = _build_event_packages(
        interface_ids,
        support_labels,
        candidate_spec.observable_family,
    )
    continuations, loops, forward_ids = _build_continuations_and_loops(
        candidate_spec,
        interface_ids,
        state_ids,
        state_metadata,
        support_labels,
        carrier_size,
    )
    histories = _build_histories(
        interface_ids,
        state_ids,
        state_metadata,
        continuations,
        search_space,
    )
    config = RouteTransportPackageConfig.model_validate(
        {
            "schema_version": "route-transport-package.v1",
            "package_id": f"{candidate_spec.search_id}_{candidate_spec.candidate_id}",
            "support": {
                "support_id": f"{candidate_spec.search_id}_support",
                "visible_support_labels": list(support_labels),
                "same_support_required": search_space.same_support_required,
            },
            "state_space": {
                "internal_state_ids": list(state_ids),
                "support_projection": dict(support_projection),
            },
            "interfaces": [
                {"interface_id": interface_id}
                for interface_id in interface_ids
            ],
            "event_packages": event_packages,
            "histories": histories,
            "continuations": continuations,
            "loops": loops,
        }
    )
    package = load_route_transport_package_from_config(config)
    earliest_history_count = sum(
        1 for history in config.histories if history.target_interface_id == interface_ids[0]
    )
    enriched_spec = replace(
        candidate_spec,
        internal_state_count=len(state_ids),
        history_count=earliest_history_count,
        continuation_count=len(config.continuations),
        loop_count=len(config.loops),
    )
    return _RealizedCandidate(
        spec=enriched_spec,
        config=config,
        package=package,
        forward_continuation_ids=forward_ids,
    )


def _build_state_space(
    support_labels: tuple[str, ...],
    carrier_size: int,
    carrier_family: str,
) -> tuple[tuple[str, ...], dict[str, str], dict[str, tuple[int, int]]]:
    state_ids: list[str] = []
    support_projection: dict[str, str] = {}
    state_metadata: dict[str, tuple[int, int]] = {}
    for support_index, support_label in enumerate(support_labels):
        if carrier_family == "none":
            state_id = support_label
            state_ids.append(state_id)
            support_projection[state_id] = support_label
            state_metadata[state_id] = (support_index, 0)
            continue
        for carrier_index in range(carrier_size):
            state_id = f"{support_label}_c{carrier_index}"
            state_ids.append(state_id)
            support_projection[state_id] = support_label
            state_metadata[state_id] = (support_index, carrier_index)
    return tuple(state_ids), support_projection, state_metadata


def _build_event_packages(
    interface_ids: tuple[str, ...],
    support_labels: tuple[str, ...],
    observable_family: str,
) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    last_index = len(interface_ids) - 1
    for interface_index, interface_id in enumerate(interface_ids):
        if observable_family == "support_indicator_basis":
            events = [
                _indicator_event(label, support_labels)
                for label in support_labels
            ]
        elif observable_family == "coarse_support_only":
            events = [_indicator_event("S0", support_labels)]
        elif observable_family == "coarse_plus_indicator":
            if interface_index == last_index:
                events = [
                    _indicator_event(label, support_labels)
                    for label in support_labels
                ]
            else:
                events = [_indicator_event("S0", support_labels)]
        elif observable_family == "paired_partition":
            midpoint = max(1, len(support_labels) // 2)
            first_half = set(support_labels[:midpoint])
            second_half = set(support_labels[midpoint:])
            if not second_half:
                second_half = set(first_half)
            events = [
                _subset_event("first_half", first_half, support_labels),
                _subset_event("second_half", second_half, support_labels),
            ]
        else:  # pragma: no cover - guarded by search config families
            raise ValueError(f"unsupported observable family: {observable_family}")

        packages.append(
            {
                "package_id": f"{interface_id}_events",
                "interface_id": interface_id,
                "events": events,
            }
        )
    return packages


def _build_continuations_and_loops(
    candidate_spec: DiscoveryCandidateSpec,
    interface_ids: tuple[str, ...],
    state_ids: tuple[str, ...],
    state_metadata: dict[str, tuple[int, int]],
    support_labels: tuple[str, ...],
    carrier_size: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], tuple[str, ...]]:
    continuations: list[dict[str, Any]] = []
    loops: list[dict[str, Any]] = []
    forward_ids: list[str] = []

    for index in range(len(interface_ids) - 1):
        continuation_id = f"fwd_{interface_ids[index]}_{interface_ids[index + 1]}"
        continuations.append(
            _build_continuation_spec(
                continuation_id=continuation_id,
                source_interface_id=interface_ids[index],
                target_interface_id=interface_ids[index + 1],
                kernel=_forward_kernel(
                    candidate_spec.route_update_family,
                    state_ids,
                    state_metadata,
                    support_labels,
                    carrier_size,
                ),
            )
        )
        forward_ids.append(continuation_id)

    if candidate_spec.continuation_catalog_family == "forward_only":
        identity_continuation_id = f"id_{interface_ids[-1]}"
        continuations.append(
            _build_continuation_spec(
                continuation_id=identity_continuation_id,
                source_interface_id=interface_ids[-1],
                target_interface_id=interface_ids[-1],
                kernel=_identity_kernel(state_ids),
            )
        )
        loops.append(
            {
                "loop_id": identity_continuation_id,
                "interface_id": interface_ids[-1],
                "continuation_id": identity_continuation_id,
            }
        )
    elif candidate_spec.continuation_catalog_family == "forward_plus_identity":
        for interface_id in interface_ids:
            identity_continuation_id = f"id_{interface_id}"
            continuations.append(
                _build_continuation_spec(
                    continuation_id=identity_continuation_id,
                    source_interface_id=interface_id,
                    target_interface_id=interface_id,
                    kernel=_identity_kernel(state_ids),
                )
            )
            loops.append(
                {
                    "loop_id": identity_continuation_id,
                    "interface_id": interface_id,
                    "continuation_id": identity_continuation_id,
                }
            )
    elif candidate_spec.continuation_catalog_family in (
        "forward_plus_loop",
        "two_step_with_loop",
    ):
        loops.extend(
            _build_active_loops(
                candidate_spec,
                interface_ids[0],
                state_ids,
                state_metadata,
                support_labels,
                carrier_size,
                continuations,
            )
        )
        if (
            candidate_spec.continuation_catalog_family == "two_step_with_loop"
            and len(interface_ids) >= 3
        ):
            continuation_id = f"skip_{interface_ids[0]}_{interface_ids[2]}"
            continuations.append(
                _build_continuation_spec(
                    continuation_id=continuation_id,
                    source_interface_id=interface_ids[0],
                    target_interface_id=interface_ids[2],
                    kernel=_composed_forward_kernel(
                        candidate_spec.route_update_family,
                        state_ids,
                        state_metadata,
                        support_labels,
                        carrier_size,
                        steps=2,
                    ),
                )
            )
            forward_ids.append(continuation_id)
    else:  # pragma: no cover - guarded by search config families
        raise ValueError(
            "unsupported continuation catalog family: "
            f"{candidate_spec.continuation_catalog_family}"
        )

    return continuations, loops, tuple(forward_ids)


def _build_histories(
    interface_ids: tuple[str, ...],
    state_ids: tuple[str, ...],
    state_metadata: dict[str, tuple[int, int]],
    continuations: list[dict[str, Any]],
    search_space: SearchSpace,
) -> list[dict[str, Any]]:
    histories: list[dict[str, Any]] = []
    earliest_interface_id = interface_ids[0]
    ordered_state_ids = sorted(
        state_ids,
        key=lambda state_id: state_metadata[state_id],
    )
    initial_history_count = min(
        max(search_space.history_count_candidates),
        len(ordered_state_ids),
    )
    interface_history_vectors: dict[str, list[tuple[tuple[str, float], ...]]] = {
        earliest_interface_id: []
    }
    for history_index, state_id in enumerate(ordered_state_ids[:initial_history_count]):
        probabilities = {state_id: 1.0}
        histories.append(
            {
                "history_id": f"h_{earliest_interface_id}_{history_index}",
                "source_interface_id": earliest_interface_id,
                "target_interface_id": earliest_interface_id,
                "probabilities": probabilities,
            }
        )
        interface_history_vectors[earliest_interface_id].append(
            tuple(sorted(probabilities.items()))
        )

    continuation_by_id = {item["continuation_id"]: item for item in continuations}
    for interface_index in range(1, len(interface_ids)):
        target_interface_id = interface_ids[interface_index]
        source_interface_id = interface_ids[interface_index - 1]
        continuation_id = f"fwd_{source_interface_id}_{target_interface_id}"
        continuation = continuation_by_id[continuation_id]
        seen_vectors: set[tuple[tuple[str, float], ...]] = set()
        interface_history_vectors[target_interface_id] = []
        for prior_vector in interface_history_vectors[source_interface_id]:
            next_vector = _apply_kernel_to_sparse_distribution(
                prior_vector,
                continuation["kernel"],
                state_ids,
            )
            if next_vector in seen_vectors:
                continue
            seen_vectors.add(next_vector)
            interface_history_vectors[target_interface_id].append(next_vector)
            histories.append(
                {
                    "history_id": (
                        f"h_{target_interface_id}_{len(interface_history_vectors[target_interface_id]) - 1}"
                    ),
                    "source_interface_id": earliest_interface_id,
                    "target_interface_id": target_interface_id,
                    "probabilities": dict(next_vector),
                }
            )
    return histories


def _build_active_loops(
    candidate_spec: DiscoveryCandidateSpec,
    interface_id: str,
    state_ids: tuple[str, ...],
    state_metadata: dict[str, tuple[int, int]],
    support_labels: tuple[str, ...],
    carrier_size: int,
    continuations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    loops: list[dict[str, Any]] = []
    if candidate_spec.route_update_family == "shift_or_identity":
        identity_continuation_id = f"id_{interface_id}"
        continuations.append(
            _build_continuation_spec(
                continuation_id=identity_continuation_id,
                source_interface_id=interface_id,
                target_interface_id=interface_id,
                kernel=_identity_kernel(state_ids),
            )
        )
        loops.append(
            {
                "loop_id": identity_continuation_id,
                "interface_id": interface_id,
                "continuation_id": identity_continuation_id,
            }
        )

    active_continuation_id = f"loop_{interface_id}"
    continuations.append(
        _build_continuation_spec(
            continuation_id=active_continuation_id,
            source_interface_id=interface_id,
            target_interface_id=interface_id,
            kernel=_active_loop_kernel(
                candidate_spec.route_update_family,
                state_ids,
                state_metadata,
                support_labels,
                carrier_size,
            ),
        )
    )
    loops.append(
        {
            "loop_id": active_continuation_id,
            "interface_id": interface_id,
            "continuation_id": active_continuation_id,
        }
    )
    return loops


def _evaluate_realized_candidate(
    realized: _RealizedCandidate,
) -> DiscoveryCandidateRecord:
    package = realized.package
    measured_interfaces = tuple(
        interface.interface_id
        for interface in package.interfaces
        if resolve_interface_history_ids(package, interface.interface_id)
        and interface.interface_id in package.event_package_by_interface_id
    )
    interface_metrics = tuple(
        _compute_interface_metrics(
            package,
            interface_id,
            tuple(
                loop.loop_id for loop in package.loops if loop.interface_id == interface_id
            ),
        )
        for interface_id in measured_interfaces
    )
    label, primary_interface_id, transport_evidence, loop_evidence = _classify_candidate(
        realized,
        interface_metrics,
    )
    return DiscoveryCandidateRecord(
        candidate_spec=realized.spec,
        candidate_label=label,
        primary_interface_id=primary_interface_id,
        interface_metrics=interface_metrics,
        transport_collapse_evidence=transport_evidence,
        loop_action_evidence=loop_evidence,
        warnings=(),
    )


def _compute_interface_metrics(
    package: RouteTransportPackage,
    interface_id: str,
    loop_ids: tuple[str, ...],
) -> DiscoveryInterfaceMetrics:
    history_ids = resolve_interface_history_ids(package, interface_id)
    current_partition = compute_current_partition(package, interface_id, history_ids)
    predictive_partition = compute_predictive_partition(package, interface_id, history_ids)
    witnesses = enumerate_memory_witnesses(package, interface_id, history_ids)
    discrepancy = compute_exact_max_abs_future_gap(package, interface_id, history_ids)
    current_loop_score = Fraction(0, 1)
    predictive_loop_score = Fraction(0, 1)
    for loop_id in loop_ids:
        try:
            current_action = compute_current_loop_action(package, loop_id, history_ids)
            current_loop_score = max(current_loop_score, current_action.moved_class_fraction)
        except LoopActionUndefinedError:
            pass
        try:
            predictive_action = compute_predictive_loop_action(package, loop_id, history_ids)
            predictive_loop_score = max(
                predictive_loop_score,
                predictive_action.moved_class_fraction,
            )
        except LoopActionUndefinedError:
            pass
    return DiscoveryInterfaceMetrics(
        interface_id=interface_id,
        history_count=len(history_ids),
        current_quotient_size=current_partition.class_count,
        predictive_quotient_size=predictive_partition.class_count,
        max_fiber_size=_compute_max_fiber_size(current_partition, predictive_partition),
        witness_count=len(witnesses),
        discrepancy_metric_name=str(discrepancy.metric_name),
        discrepancy_metric_value=discrepancy.metric_value,
        current_loop_score=current_loop_score,
        predictive_loop_score=predictive_loop_score,
    )


def _classify_candidate(
    realized: _RealizedCandidate,
    interface_metrics: tuple[DiscoveryInterfaceMetrics, ...],
) -> tuple[
    str,
    str,
    DiscoveryTransportCollapseEvidence | None,
    DiscoveryLoopEvidence | None,
]:
    if all(_is_flat_metrics(metrics) for metrics in interface_metrics):
        return "flat", interface_metrics[0].interface_id, None, None

    earliest_metrics = interface_metrics[0]
    transport_evidence = _find_transport_collapse_evidence(realized, interface_metrics)
    if _has_residue(earliest_metrics) and transport_evidence is not None:
        return "dissipative", earliest_metrics.interface_id, transport_evidence, None

    for metrics in interface_metrics:
        if (
            metrics.witness_count > 0
            and metrics.discrepancy_metric_value > 0
            and metrics.current_loop_score == 0
            and metrics.predictive_loop_score > 0
        ):
            loop_evidence = _find_loop_evidence(realized.package, metrics.interface_id)
            return "coherent_candidate", metrics.interface_id, None, loop_evidence

    first_non_flat = next(
        metrics for metrics in interface_metrics if not _is_flat_metrics(metrics)
    )
    return "coherent_candidate", first_non_flat.interface_id, None, None


def _find_transport_collapse_evidence(
    realized: _RealizedCandidate,
    interface_metrics: tuple[DiscoveryInterfaceMetrics, ...],
) -> DiscoveryTransportCollapseEvidence | None:
    package = realized.package
    earliest_interface_id = interface_metrics[0].interface_id
    flat_later_interfaces = {
        metrics.interface_id
        for metrics in interface_metrics[1:]
        if _is_flat_metrics(metrics)
    }
    if not flat_later_interfaces:
        return None

    for continuation_id in realized.forward_continuation_ids:
        continuation = package.get_continuation(continuation_id)
        if continuation.source_interface_id != earliest_interface_id:
            continue
        if continuation.target_interface_id not in flat_later_interfaces:
            continue
        source_history_ids = resolve_interface_history_ids(package, earliest_interface_id)
        target_history_ids = resolve_interface_history_ids(
            package,
            continuation.target_interface_id,
        )
        try:
            transport_map = compute_predictive_transport_map(
                package,
                continuation_id,
                source_history_ids=source_history_ids,
                target_history_ids=target_history_ids,
            )
        except (TransportMapUndefinedError, TransportMapNotWellDefinedError):
            continue
        image_targets = [image.target_class_id for image in transport_map.class_images]
        if len(set(image_targets)) == len(image_targets):
            continue
        return DiscoveryTransportCollapseEvidence(
            source_interface_id=transport_map.source_interface_id,
            target_interface_id=transport_map.target_interface_id,
            continuation_id=continuation_id,
            source_predictive_class_count=len(transport_map.source_classes),
            target_predictive_class_count=len(transport_map.target_classes),
            class_image_mapping=tuple(
                f"{image.source_class_id}->{image.target_class_id}"
                for image in transport_map.class_images
            ),
        )
    return None


def _find_loop_evidence(
    package: RouteTransportPackage,
    interface_id: str,
) -> DiscoveryLoopEvidence | None:
    history_ids = resolve_interface_history_ids(package, interface_id)
    for loop in package.loops:
        if loop.interface_id != interface_id:
            continue
        try:
            current_action = compute_current_loop_action(package, loop.loop_id, history_ids)
            predictive_action = compute_predictive_loop_action(package, loop.loop_id, history_ids)
        except LoopActionUndefinedError:
            continue
        if (not current_action.is_trivial) or predictive_action.is_trivial:
            continue
        return DiscoveryLoopEvidence(
            interface_id=interface_id,
            loop_id=loop.loop_id,
            moved_predictive_class_ids=predictive_action.moved_class_ids,
            class_image_mapping=tuple(
                f"{image.source_class_id}->{image.target_class_id}"
                for image in predictive_action.class_images
            ),
            moved_class_fraction=predictive_action.moved_class_fraction,
        )
    return None


def _matches_numeric_filters(
    candidate_spec: DiscoveryCandidateSpec,
    search_space: SearchSpace,
    config: RouteTransportPackageConfig,
) -> bool:
    event_count = len(config.event_packages[0].events)
    return (
        candidate_spec.support_size in search_space.support_size_candidates
        and candidate_spec.interface_count in search_space.interface_count_candidates
        and candidate_spec.internal_state_count in search_space.hidden_state_size_candidates
        and event_count in search_space.event_count_candidates
        and candidate_spec.history_count in search_space.history_count_candidates
        and candidate_spec.continuation_count in search_space.continuation_count_candidates
        and candidate_spec.loop_count in search_space.loop_count_candidates
    )


def _compute_max_fiber_size(current_partition: Any, predictive_partition: Any) -> int:
    max_fiber_size = 0
    for current_class in current_partition.classes:
        predictive_class_ids = {
            predictive_partition.history_to_class_id[history_id]
            for history_id in current_class.member_history_ids
        }
        max_fiber_size = max(max_fiber_size, len(predictive_class_ids))
    return max_fiber_size


def _is_flat_metrics(metrics: DiscoveryInterfaceMetrics) -> bool:
    return (
        metrics.witness_count == 0
        and metrics.discrepancy_metric_value == 0
        and metrics.current_quotient_size == metrics.predictive_quotient_size
        and metrics.max_fiber_size <= 1
        and metrics.current_loop_score == 0
        and metrics.predictive_loop_score == 0
    )


def _has_residue(metrics: DiscoveryInterfaceMetrics) -> bool:
    return (
        metrics.witness_count > 0
        and metrics.discrepancy_metric_value > 0
        and (
            metrics.current_quotient_size < metrics.predictive_quotient_size
            or metrics.max_fiber_size > 1
        )
    )


def _carrier_size(carrier_family: str) -> int:
    return {
        "none": 1,
        "cyclic_z2": 2,
        "cyclic_z3": 3,
        "pair_groupoid_2": 2,
    }[carrier_family]


def _indicator_event(
    active_label: str,
    support_labels: tuple[str, ...],
) -> dict[str, Any]:
    return _subset_event(
        f"indicator_{active_label}",
        {active_label},
        support_labels,
    )


def _subset_event(
    event_id: str,
    active_labels: set[str],
    support_labels: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "weights": {
            label: 1 if label in active_labels else 0 for label in support_labels
        },
    }


def _build_continuation_spec(
    *,
    continuation_id: str,
    source_interface_id: str,
    target_interface_id: str,
    kernel: dict[str, dict[str, float]],
) -> dict[str, Any]:
    return {
        "continuation_id": continuation_id,
        "source_interface_id": source_interface_id,
        "target_interface_id": target_interface_id,
        "kernel": kernel,
    }


def _identity_kernel(state_ids: tuple[str, ...]) -> dict[str, dict[str, float]]:
    return {state_id: {state_id: 1.0} for state_id in state_ids}


def _forward_kernel(
    route_update_family: str,
    state_ids: tuple[str, ...],
    state_metadata: dict[str, tuple[int, int]],
    support_labels: tuple[str, ...],
    carrier_size: int,
) -> dict[str, dict[str, float]]:
    return {
        state_id: {
            _forward_target_state(
                route_update_family,
                state_id,
                state_metadata,
                support_labels,
                carrier_size,
            ): 1.0
        }
        for state_id in state_ids
    }


def _composed_forward_kernel(
    route_update_family: str,
    state_ids: tuple[str, ...],
    state_metadata: dict[str, tuple[int, int]],
    support_labels: tuple[str, ...],
    carrier_size: int,
    *,
    steps: int,
) -> dict[str, dict[str, float]]:
    kernel: dict[str, dict[str, float]] = {}
    for state_id in state_ids:
        current_state_id = state_id
        for _ in range(steps):
            current_state_id = _forward_target_state(
                route_update_family,
                current_state_id,
                state_metadata,
                support_labels,
                carrier_size,
            )
        kernel[state_id] = {current_state_id: 1.0}
    return kernel


def _active_loop_kernel(
    route_update_family: str,
    state_ids: tuple[str, ...],
    state_metadata: dict[str, tuple[int, int]],
    support_labels: tuple[str, ...],
    carrier_size: int,
) -> dict[str, dict[str, float]]:
    if route_update_family == "identity_only":
        return _identity_kernel(state_ids)
    if route_update_family == "merge_to_sink":
        return _identity_kernel(state_ids)
    if route_update_family == "binary_swap":
        if carrier_size < 2:
            return _identity_kernel(state_ids)
        return {
            state_id: {
                _state_id_for_indices(
                    support_index=state_metadata[state_id][0],
                    carrier_index=1 - state_metadata[state_id][1]
                    if state_metadata[state_id][1] in (0, 1)
                    else state_metadata[state_id][1],
                    support_labels=support_labels,
                    carrier_size=carrier_size,
                ): 1.0
            }
            for state_id in state_ids
        }
    if route_update_family in ("cyclic_shift", "shift_or_identity"):
        if carrier_size < 2:
            return _identity_kernel(state_ids)
        return {
            state_id: {
                _state_id_for_indices(
                    support_index=state_metadata[state_id][0],
                    carrier_index=(state_metadata[state_id][1] + 1) % carrier_size,
                    support_labels=support_labels,
                    carrier_size=carrier_size,
                ): 1.0
            }
            for state_id in state_ids
        }
    raise ValueError(f"unsupported route update family: {route_update_family}")


def _forward_target_state(
    route_update_family: str,
    state_id: str,
    state_metadata: dict[str, tuple[int, int]],
    support_labels: tuple[str, ...],
    carrier_size: int,
) -> str:
    support_index, carrier_index = state_metadata[state_id]
    if route_update_family == "identity_only":
        return _state_id_for_indices(
            support_index=support_index,
            carrier_index=carrier_index,
            support_labels=support_labels,
            carrier_size=carrier_size,
        )
    if route_update_family == "merge_to_sink":
        return _state_id_for_indices(
            support_index=0,
            carrier_index=0,
            support_labels=support_labels,
            carrier_size=carrier_size,
        )
    if route_update_family in ("binary_swap", "cyclic_shift", "shift_or_identity"):
        if carrier_size == 1:
            return _state_id_for_indices(
                support_index=support_index,
                carrier_index=carrier_index,
                support_labels=support_labels,
                carrier_size=carrier_size,
            )
        target_support_index = carrier_index % len(support_labels)
        return _state_id_for_indices(
            support_index=target_support_index,
            carrier_index=carrier_index,
            support_labels=support_labels,
            carrier_size=carrier_size,
        )
    raise ValueError(f"unsupported route update family: {route_update_family}")


def _state_id_for_indices(
    *,
    support_index: int,
    carrier_index: int,
    support_labels: tuple[str, ...],
    carrier_size: int,
) -> str:
    support_label = support_labels[support_index]
    if carrier_size == 1:
        return support_label
    return f"{support_label}_c{carrier_index}"


def _apply_kernel_to_sparse_distribution(
    vector_items: tuple[tuple[str, float], ...],
    kernel: dict[str, dict[str, float]],
    state_ids: tuple[str, ...],
) -> tuple[tuple[str, float], ...]:
    dense = {state_id: 0.0 for state_id in state_ids}
    for source_state, probability in vector_items:
        for target_state, weight in kernel[source_state].items():
            dense[target_state] += probability * weight
    return tuple(
        (state_id, value) for state_id, value in dense.items() if value > 0
    )


def _atlas_payload(atlas: DiscoveryAtlas) -> dict[str, Any]:
    return {
        "search_id": atlas.search_id,
        "seed": atlas.seed,
        "search_config_path": _relative_string(atlas.search_config_path),
        "raw_candidate_count": atlas.raw_candidate_count,
        "capped_candidate_count": atlas.capped_candidate_count,
        "attempted_candidate_count": atlas.attempted_candidate_count,
        "realized_candidate_count": atlas.realized_candidate_count,
        "evaluated_candidate_count": atlas.evaluated_candidate_count,
        "class_counts": {label: count for label, count in atlas.class_counts},
        "warnings": list(atlas.warnings),
        "candidates": [_candidate_payload(record) for record in atlas.candidate_records],
    }


def _candidate_payload(record: DiscoveryCandidateRecord) -> dict[str, Any]:
    primary_metrics = next(
        metrics
        for metrics in record.interface_metrics
        if metrics.interface_id == record.primary_interface_id
    )
    payload = {
        "candidate_id": record.candidate_spec.candidate_id,
        "candidate_label": record.candidate_label,
        "candidate_spec": {
            "search_id": record.candidate_spec.search_id,
            "support_size": record.candidate_spec.support_size,
            "interface_count": record.candidate_spec.interface_count,
            "carrier_family": record.candidate_spec.carrier_family,
            "route_update_family": record.candidate_spec.route_update_family,
            "observable_family": record.candidate_spec.observable_family,
            "continuation_catalog_family": record.candidate_spec.continuation_catalog_family,
            "internal_state_count": record.candidate_spec.internal_state_count,
            "history_count": record.candidate_spec.history_count,
            "continuation_count": record.candidate_spec.continuation_count,
            "loop_count": record.candidate_spec.loop_count,
        },
        "primary_interface_id": record.primary_interface_id,
        "primary_metrics": _metrics_payload(primary_metrics),
        "interface_metrics": [_metrics_payload(metrics) for metrics in record.interface_metrics],
        "warnings": list(record.warnings),
    }
    if record.transport_collapse_evidence is not None:
        payload["transport_collapse_evidence"] = {
            "source_interface_id": record.transport_collapse_evidence.source_interface_id,
            "target_interface_id": record.transport_collapse_evidence.target_interface_id,
            "continuation_id": record.transport_collapse_evidence.continuation_id,
            "source_predictive_class_count": (
                record.transport_collapse_evidence.source_predictive_class_count
            ),
            "target_predictive_class_count": (
                record.transport_collapse_evidence.target_predictive_class_count
            ),
            "class_image_mapping": list(record.transport_collapse_evidence.class_image_mapping),
        }
    if record.loop_action_evidence is not None:
        payload["loop_action_evidence"] = {
            "interface_id": record.loop_action_evidence.interface_id,
            "loop_id": record.loop_action_evidence.loop_id,
            "moved_predictive_class_ids": list(record.loop_action_evidence.moved_predictive_class_ids),
            "class_image_mapping": list(record.loop_action_evidence.class_image_mapping),
            "moved_class_fraction": float(record.loop_action_evidence.moved_class_fraction),
            "moved_class_fraction_exact": _fraction_string(
                record.loop_action_evidence.moved_class_fraction
            ),
        }
    return payload


def _metrics_payload(metrics: DiscoveryInterfaceMetrics) -> dict[str, Any]:
    return {
        "interface_id": metrics.interface_id,
        "history_count": metrics.history_count,
        "current_quotient_size": metrics.current_quotient_size,
        "predictive_quotient_size": metrics.predictive_quotient_size,
        "max_fiber_size": metrics.max_fiber_size,
        "witness_count": metrics.witness_count,
        "discrepancy_metric_name": metrics.discrepancy_metric_name,
        "discrepancy_metric_value": float(metrics.discrepancy_metric_value),
        "discrepancy_metric_value_exact": _fraction_string(metrics.discrepancy_metric_value),
        "current_loop_score": float(metrics.current_loop_score),
        "current_loop_score_exact": _fraction_string(metrics.current_loop_score),
        "predictive_loop_score": float(metrics.predictive_loop_score),
        "predictive_loop_score_exact": _fraction_string(metrics.predictive_loop_score),
    }


def _write_csv(atlas: DiscoveryAtlas, csv_path: Path) -> None:
    fieldnames = [
        "search_id",
        "candidate_id",
        "support_size",
        "interface_count",
        "carrier_family",
        "route_update_family",
        "observable_family",
        "continuation_catalog_family",
        "internal_state_count",
        "history_count",
        "continuation_count",
        "loop_count",
        "primary_interface_id",
        "primary_current_quotient_size",
        "primary_predictive_quotient_size",
        "primary_max_fiber_size",
        "primary_witness_count",
        "primary_discrepancy_metric_value",
        "primary_current_loop_score",
        "primary_predictive_loop_score",
        "class_label",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in atlas.candidate_records:
            primary_metrics = next(
                metrics
                for metrics in record.interface_metrics
                if metrics.interface_id == record.primary_interface_id
            )
            writer.writerow(
                {
                    "search_id": atlas.search_id,
                    "candidate_id": record.candidate_spec.candidate_id,
                    "support_size": record.candidate_spec.support_size,
                    "interface_count": record.candidate_spec.interface_count,
                    "carrier_family": record.candidate_spec.carrier_family,
                    "route_update_family": record.candidate_spec.route_update_family,
                    "observable_family": record.candidate_spec.observable_family,
                    "continuation_catalog_family": (
                        record.candidate_spec.continuation_catalog_family
                    ),
                    "internal_state_count": record.candidate_spec.internal_state_count,
                    "history_count": record.candidate_spec.history_count,
                    "continuation_count": record.candidate_spec.continuation_count,
                    "loop_count": record.candidate_spec.loop_count,
                    "primary_interface_id": record.primary_interface_id,
                    "primary_current_quotient_size": primary_metrics.current_quotient_size,
                    "primary_predictive_quotient_size": primary_metrics.predictive_quotient_size,
                    "primary_max_fiber_size": primary_metrics.max_fiber_size,
                    "primary_witness_count": primary_metrics.witness_count,
                    "primary_discrepancy_metric_value": float(
                        primary_metrics.discrepancy_metric_value
                    ),
                    "primary_current_loop_score": float(primary_metrics.current_loop_score),
                    "primary_predictive_loop_score": float(
                        primary_metrics.predictive_loop_score
                    ),
                    "class_label": record.candidate_label,
                }
            )


def _build_summary_note(
    atlas: DiscoveryAtlas,
    json_path: Path,
    csv_path: Path,
    note_path: Path,
) -> str:
    lines = [
        f"# Discovery Atlas: {atlas.search_id}",
        "",
        f"- search_id: {atlas.search_id}",
        f"- search_config_path: {_relative_string(atlas.search_config_path)}",
        f"- seed: {atlas.seed}",
        f"- raw_candidate_count: {atlas.raw_candidate_count}",
        f"- capped_candidate_count: {atlas.capped_candidate_count}",
        f"- attempted_candidate_count: {atlas.attempted_candidate_count}",
        f"- realized_candidate_count: {atlas.realized_candidate_count}",
        f"- evaluated_candidate_count: {atlas.evaluated_candidate_count}",
        f"- json_atlas_path: {_relative_string(json_path)}",
        f"- csv_summary_path: {_relative_string(csv_path)}",
        f"- summary_note_path: {_relative_string(note_path)}",
        "- class_counts:",
    ]
    for label, count in atlas.class_counts:
        lines.append(f"  - {label}: {count}")
    lines.extend(["", "## Top Candidates", ""])
    for record in _top_candidate_records(atlas.candidate_records):
        primary_metrics = next(
            metrics
            for metrics in record.interface_metrics
            if metrics.interface_id == record.primary_interface_id
        )
        lines.extend(
            [
                (
                    f"- {record.candidate_spec.candidate_id}: "
                    f"{record.candidate_label} at {record.primary_interface_id} "
                    f"(discrepancy={_fraction_string(primary_metrics.discrepancy_metric_value)}, "
                    f"witnesses={primary_metrics.witness_count}, "
                    f"current_loop={_fraction_string(primary_metrics.current_loop_score)}, "
                    f"predictive_loop={_fraction_string(primary_metrics.predictive_loop_score)})"
                )
            ]
        )
    lines.extend(["", "## Conclusion", ""])
    if any(label != "flat" and count > 0 for label, count in atlas.class_counts):
        lines.append("- Smoke atlas is informative enough to proceed to HM-019.")
    else:
        lines.append("- Smoke atlas is all-flat; HM-019 should broaden or retarget the search.")
    if atlas.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in atlas.warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def _top_candidate_records(
    records: Iterable[DiscoveryCandidateRecord],
) -> tuple[DiscoveryCandidateRecord, ...]:
    ordered = sorted(
        records,
        key=lambda record: (
            -float(
                next(
                    metrics.discrepancy_metric_value
                    for metrics in record.interface_metrics
                    if metrics.interface_id == record.primary_interface_id
                )
            ),
            record.candidate_spec.candidate_id,
        ),
    )
    return tuple(ordered[:5])


def _relative_string(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _fraction_string(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"
