from __future__ import annotations

from pathlib import Path

import pytest

from sixbirds_event.audits.shared_event_consistency import (
    compute_shared_event_consistency,
)
from sixbirds_event.reporting.sec_report import load_observation_trace_files
from sixbirds_event.reporting.structural_report import load_event_package_instance
from sixbirds_event.statistics.probe_signatures import extract_probe_signatures
from sixbirds_event.traces.builders import (
    build_observation_trace,
    make_downstream_probe,
    make_observation,
)


SEC_INSTANCE = Path("experiments/instances/smoke/sec-instance.json")
SEC_TRACE_DIR = Path("experiments/instances/smoke/traces")


def test_identical_shared_events_score_zero_and_pass_exact_mode() -> None:
    instance = load_event_package_instance(SEC_INSTANCE)
    traces = load_observation_trace_files([SEC_TRACE_DIR / "sec-identical.json"])
    result = compute_shared_event_consistency(instance, traces, exact_tolerance=1e-6)
    scored_pairs = [
        pair for pair in result.event_pair_results if not pair.insufficient_data
    ]
    assert scored_pairs
    assert all((pair.approx_score or 0.0) < 1e-9 for pair in scored_pairs)
    assert all(pair.exact_consistent is True for pair in scored_pairs)


def test_distinguishable_shared_events_score_higher() -> None:
    instance = load_event_package_instance(SEC_INSTANCE)
    identical = compute_shared_event_consistency(
        instance,
        load_observation_trace_files([SEC_TRACE_DIR / "sec-identical.json"]),
        exact_tolerance=1e-6,
    )
    distinguishable = compute_shared_event_consistency(
        instance,
        load_observation_trace_files([SEC_TRACE_DIR / "sec-distinguishable.json"]),
        exact_tolerance=1e-6,
    )
    identical_score = max(
        pair.approx_score or 0.0
        for pair in identical.event_pair_results
        if not pair.insufficient_data
    )
    distinguishable_score = max(
        pair.approx_score or 0.0
        for pair in distinguishable.event_pair_results
        if not pair.insufficient_data
    )
    assert distinguishable_score > identical_score
    assert any(
        pair.exact_consistent is False
        for pair in distinguishable.event_pair_results
        if not pair.insufficient_data
    )


def test_event_and_context_level_summaries_are_emitted() -> None:
    instance = load_event_package_instance(SEC_INSTANCE)
    traces = load_observation_trace_files([SEC_TRACE_DIR / "sec-identical.json"])
    result = compute_shared_event_consistency(instance, traces)
    assert result.event_pair_results
    assert result.context_pair_results
    assert result.context_pair_results[0].scored_pair_count >= 1


def test_count_based_probe_signatures_normalize_correctly() -> None:
    instance = load_event_package_instance(SEC_INSTANCE)
    trace_a = build_observation_trace(
        trace_id="trace_counts_a",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_a", atom_ids=["a0"], count=1)],
        downstream_probes=[
            make_downstream_probe(
                event_id="event_a0",
                context_id="ctx_a",
                probe_id="probe_alpha",
                signature="probe_alpha",
                outcome_counts={"hit": 3, "miss": 1},
            )
        ],
    )
    trace_b = build_observation_trace(
        trace_id="trace_counts_b",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_a", atom_ids=["a0"], count=1)],
        downstream_probes=[
            make_downstream_probe(
                event_id="event_a0",
                context_id="ctx_a",
                probe_id="probe_alpha",
                signature="probe_alpha",
                outcome_counts={"hit": 1, "miss": 1},
            )
        ],
    )
    signatures = extract_probe_signatures([trace_a, trace_b], instance=instance)
    assert signatures["event_a0"]["probe_alpha"] == {"hit": 2 / 3, "miss": 1 / 3}


def test_probability_based_probe_signatures_normalize_correctly() -> None:
    instance = load_event_package_instance(SEC_INSTANCE)
    trace_a = build_observation_trace(
        trace_id="trace_probs_a",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_b", atom_ids=["b1"], count=1)],
        downstream_probes=[
            make_downstream_probe(
                event_id="event_b1",
                context_id="ctx_b",
                probe_id="probe_beta",
                signature="probe_beta",
                outcome_probabilities={"on": 0.2, "off": 0.8},
            )
        ],
    )
    trace_b = build_observation_trace(
        trace_id="trace_probs_b",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_b", atom_ids=["b1"], count=1)],
        downstream_probes=[
            make_downstream_probe(
                event_id="event_b1",
                context_id="ctx_b",
                probe_id="probe_beta",
                signature="probe_beta",
                outcome_probabilities={"on": 0.4, "off": 0.6},
            )
        ],
    )
    signatures = extract_probe_signatures([trace_a, trace_b], instance=instance)
    assert signatures["event_b1"]["probe_beta"]["off"] == pytest.approx(0.7)
    assert signatures["event_b1"]["probe_beta"]["on"] == pytest.approx(0.3)


def test_mixed_count_and_probability_within_probe_group_is_rejected() -> None:
    instance = load_event_package_instance(SEC_INSTANCE)
    trace_a = build_observation_trace(
        trace_id="trace_mixed_a",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_a", atom_ids=["a0"], count=1)],
        downstream_probes=[
            make_downstream_probe(
                event_id="event_a0",
                context_id="ctx_a",
                probe_id="probe_alpha",
                signature="probe_alpha",
                outcome_counts={"hit": 1},
            )
        ],
    )
    trace_b = build_observation_trace(
        trace_id="trace_mixed_b",
        instance_id=instance.instance_id,
        observations=[make_observation(context_id="ctx_a", atom_ids=["a0"], count=1)],
        downstream_probes=[
            make_downstream_probe(
                event_id="event_a0",
                context_id="ctx_a",
                probe_id="probe_alpha",
                signature="probe_alpha",
                outcome_probabilities={"hit": 1.0},
            )
        ],
    )
    with pytest.raises(ValueError, match="mixes count and probability"):
        extract_probe_signatures([trace_a, trace_b], instance=instance)


def test_insufficient_data_pairs_are_reported() -> None:
    instance = load_event_package_instance(SEC_INSTANCE)
    traces = load_observation_trace_files([SEC_TRACE_DIR / "sec-identical.json"])
    result = compute_shared_event_consistency(instance, traces)
    insufficient = [
        pair for pair in result.event_pair_results if pair.insufficient_data
    ]
    assert insufficient
    assert all(pair.exact_consistent is None for pair in insufficient)
