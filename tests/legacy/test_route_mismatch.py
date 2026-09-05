from __future__ import annotations

from pathlib import Path

import pytest

from sixbirds_event.audits.route_mismatch import compute_route_mismatch
from sixbirds_event.reporting.rm_report import load_observation_trace_files
from sixbirds_event.reporting.structural_report import load_event_package_instance
from sixbirds_event.statistics.route_signatures import extract_route_signatures
from sixbirds_event.traces.builders import (
    build_observation_trace,
    make_observation,
    make_route_observation,
)


SMOKE_INSTANCE = Path("experiments/instances/smoke/exact-extendable.json")
SMOKE_TRACE_DIR = Path("experiments/instances/smoke/traces")


def test_commuting_route_example_gives_zero_or_near_zero_mismatch() -> None:
    traces = load_observation_trace_files([SMOKE_TRACE_DIR / "rm-commuting.json"])
    result = compute_route_mismatch(traces, exact_tolerance=1e-6)
    assert result.overall_rm == 0.0
    assert result.route_pair_results
    assert all(pair.tv_distance == 0.0 for pair in result.route_pair_results)
    assert all(pair.exact_agreement for pair in result.route_pair_results)


def test_route_dependent_example_gives_higher_mismatch() -> None:
    commuting = compute_route_mismatch(
        load_observation_trace_files([SMOKE_TRACE_DIR / "rm-commuting.json"]),
        exact_tolerance=1e-6,
    )
    route_dependent = compute_route_mismatch(
        load_observation_trace_files([SMOKE_TRACE_DIR / "rm-route-dependent.json"]),
        exact_tolerance=1e-6,
    )
    assert route_dependent.overall_rm is not None
    assert commuting.overall_rm is not None
    assert route_dependent.overall_rm > commuting.overall_rm
    assert any(not pair.exact_agreement for pair in route_dependent.route_pair_results)


def test_route_pair_and_preparation_endpoint_summaries_are_emitted() -> None:
    result = compute_route_mismatch(
        load_observation_trace_files([SMOKE_TRACE_DIR / "rm-commuting.json"])
    )
    assert result.route_pair_results
    assert result.preparation_endpoint_results


def test_count_based_route_observations_normalize_correctly() -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    trace_a = build_observation_trace(
        trace_id="trace_rm_counts_a",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_a", atom_ids=["a0"], count=1)],
        route_observations=[
            make_route_observation(
                preparation_id="prep_alpha",
                route_id="route_left",
                endpoint_id="endpoint_readout",
                context_id="ctx_a",
                outcome_counts={"x0": 3, "x1": 1},
            )
        ],
    )
    trace_b = build_observation_trace(
        trace_id="trace_rm_counts_b",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_a", atom_ids=["a0"], count=1)],
        route_observations=[
            make_route_observation(
                preparation_id="prep_alpha",
                route_id="route_left",
                endpoint_id="endpoint_readout",
                context_id="ctx_a",
                outcome_counts={"x0": 1, "x1": 1},
            )
        ],
    )
    signatures = extract_route_signatures([trace_a, trace_b], instance=instance)
    distribution = signatures[("preparation_id", "prep_alpha", "endpoint_readout")][
        "route_left"
    ].distribution
    assert distribution == {"x0": 2 / 3, "x1": 1 / 3}


def test_probability_based_route_observations_normalize_correctly() -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    trace_a = build_observation_trace(
        trace_id="trace_rm_probs_a",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_a", atom_ids=["a1"], count=1)],
        route_observations=[
            make_route_observation(
                preparation_id="prep_alpha",
                route_id="route_left",
                endpoint_id="endpoint_readout",
                context_id="ctx_a",
                outcome_probabilities={"x0": 0.2, "x1": 0.8},
            )
        ],
    )
    trace_b = build_observation_trace(
        trace_id="trace_rm_probs_b",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_a", atom_ids=["a1"], count=1)],
        route_observations=[
            make_route_observation(
                preparation_id="prep_alpha",
                route_id="route_left",
                endpoint_id="endpoint_readout",
                context_id="ctx_a",
                outcome_probabilities={"x0": 0.4, "x1": 0.6},
            )
        ],
    )
    signatures = extract_route_signatures([trace_a, trace_b], instance=instance)
    distribution = signatures[("preparation_id", "prep_alpha", "endpoint_readout")][
        "route_left"
    ].distribution
    assert distribution["x0"] == pytest.approx(0.3)
    assert distribution["x1"] == pytest.approx(0.7)


def test_mixed_count_and_probability_within_route_group_is_rejected() -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    trace_a = build_observation_trace(
        trace_id="trace_rm_mixed_a",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_a", atom_ids=["a0"], count=1)],
        route_observations=[
            make_route_observation(
                preparation_id="prep_alpha",
                route_id="route_left",
                endpoint_id="endpoint_readout",
                context_id="ctx_a",
                outcome_counts={"x0": 1},
            )
        ],
    )
    trace_b = build_observation_trace(
        trace_id="trace_rm_mixed_b",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_a", atom_ids=["a0"], count=1)],
        route_observations=[
            make_route_observation(
                preparation_id="prep_alpha",
                route_id="route_left",
                endpoint_id="endpoint_readout",
                context_id="ctx_a",
                outcome_probabilities={"x0": 1.0},
            )
        ],
    )
    with pytest.raises(ValueError, match="mixes count and probability"):
        extract_route_signatures([trace_a, trace_b], instance=instance)


def test_insufficient_data_group_is_reported() -> None:
    result = compute_route_mismatch(
        load_observation_trace_files([SMOKE_TRACE_DIR / "rm-commuting.json"])
    )
    assert result.insufficient_data_groups
    assert any(group.insufficient_data for group in result.preparation_endpoint_results)
