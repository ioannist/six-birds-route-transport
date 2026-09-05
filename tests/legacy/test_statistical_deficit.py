from __future__ import annotations

import pytest

from sixbirds_event.reporting.statistical_report import write_statistical_summary
from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.traces.builders import build_observation_trace, make_observation
from sixbirds_event.validation import load_model
from sixbirds_event.solvers.statistical_deficit import (
    extract_empirical_marginals,
    solve_statistical_global_packaging,
    solve_statistical_deficit_from_trace,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.run_manifest import RunManifest


def build_matching_instance() -> EventPackageInstance:
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": "inst_matching",
            "contexts": [
                {
                    "context_id": "ctx_a",
                    "atoms": [{"atom_id": "a0"}, {"atom_id": "a1"}],
                },
                {
                    "context_id": "ctx_b",
                    "atoms": [{"atom_id": "b0"}, {"atom_id": "b1"}],
                },
            ],
            "events": [
                {"event_id": "event_a0", "context_id": "ctx_a", "atom_ids": ["a0"]},
                {"event_id": "event_a1", "context_id": "ctx_a", "atom_ids": ["a1"]},
                {"event_id": "event_b0", "context_id": "ctx_b", "atom_ids": ["b0"]},
                {"event_id": "event_b1", "context_id": "ctx_b", "atom_ids": ["b1"]},
            ],
            "equality_proposals": [
                {
                    "proposal_id": "p_a0_b0",
                    "left_event_id": "event_a0",
                    "right_event_id": "event_b0",
                    "constraint_kind": "hard",
                },
                {
                    "proposal_id": "p_a1_b1",
                    "left_event_id": "event_a1",
                    "right_event_id": "event_b1",
                    "constraint_kind": "hard",
                },
            ],
            "weights": {},
            "metadata": {},
            "audit": {"created_at": "2026-03-25T00:00:00Z"},
        }
    )


def build_soft_conflict_instance() -> EventPackageInstance:
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": "inst_stat_soft_conflict",
            "contexts": [
                {
                    "context_id": "ctx_a",
                    "atoms": [{"atom_id": "a0"}, {"atom_id": "a1"}],
                },
                {
                    "context_id": "ctx_b",
                    "atoms": [{"atom_id": "b0"}, {"atom_id": "b1"}],
                },
            ],
            "events": [
                {"event_id": "event_a0", "context_id": "ctx_a", "atom_ids": ["a0"]},
                {"event_id": "event_a1", "context_id": "ctx_a", "atom_ids": ["a1"]},
                {"event_id": "event_b0", "context_id": "ctx_b", "atom_ids": ["b0"]},
                {"event_id": "event_b1", "context_id": "ctx_b", "atom_ids": ["b1"]},
                {"event_id": "event_empty", "context_id": "ctx_b", "atom_ids": []},
            ],
            "equality_proposals": [
                {
                    "proposal_id": "p_a0_b0",
                    "left_event_id": "event_a0",
                    "right_event_id": "event_b0",
                    "constraint_kind": "hard",
                },
                {
                    "proposal_id": "p_a1_b1",
                    "left_event_id": "event_a1",
                    "right_event_id": "event_b1",
                    "constraint_kind": "hard",
                },
                {
                    "proposal_id": "p_soft",
                    "left_event_id": "event_a1",
                    "right_event_id": "event_empty",
                    "constraint_kind": "soft",
                    "weight_key": "wk1",
                },
            ],
            "weights": {"wk1": 1.0},
            "metadata": {},
            "audit": {"created_at": "2026-03-25T00:00:00Z"},
        }
    )


def build_no_respecting_instance() -> EventPackageInstance:
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": "inst_no_respecting",
            "contexts": [
                {
                    "context_id": "ctx_a",
                    "atoms": [{"atom_id": "a0"}, {"atom_id": "a1"}],
                },
                {
                    "context_id": "ctx_b",
                    "atoms": [{"atom_id": "b0"}, {"atom_id": "b1"}],
                },
            ],
            "events": [
                {"event_id": "event_a0", "context_id": "ctx_a", "atom_ids": ["a0"]},
                {"event_id": "event_b0", "context_id": "ctx_b", "atom_ids": ["b0"]},
                {"event_id": "event_b1", "context_id": "ctx_b", "atom_ids": ["b1"]},
            ],
            "equality_proposals": [
                {
                    "proposal_id": "p1",
                    "left_event_id": "event_a0",
                    "right_event_id": "event_b0",
                    "constraint_kind": "hard",
                },
                {
                    "proposal_id": "p2",
                    "left_event_id": "event_a0",
                    "right_event_id": "event_b1",
                    "constraint_kind": "hard",
                },
            ],
            "weights": {},
            "metadata": {},
            "audit": {"created_at": "2026-03-25T00:00:00Z"},
        }
    )


def build_count_trace(instance: EventPackageInstance) -> object:
    return build_observation_trace(
        trace_id="trace_counts",
        instance_id=instance.instance_id,
        observations=[
            make_observation(context_id="ctx_a", atom_ids=["a0"], count=7),
            make_observation(context_id="ctx_a", atom_ids=["a1"], count=3),
            make_observation(context_id="ctx_b", atom_ids=["b0"], count=7),
            make_observation(context_id="ctx_b", atom_ids=["b1"], count=3),
        ],
    )


def build_probability_trace(instance: EventPackageInstance) -> object:
    return build_observation_trace(
        trace_id="trace_probabilities",
        instance_id=instance.instance_id,
        observations=[
            make_observation(context_id="ctx_a", atom_ids=["a0"], probability=0.8),
            make_observation(context_id="ctx_a", atom_ids=["a1"], probability=0.2),
            make_observation(context_id="ctx_b", atom_ids=["b0"], probability=0.1),
            make_observation(context_id="ctx_b", atom_ids=["b1"], probability=0.9),
        ],
    )


def test_clean_extendable_data_has_near_zero_gpd_stat() -> None:
    instance = build_matching_instance()
    trace = build_count_trace(instance)
    result = solve_statistical_deficit_from_trace(instance, trace)
    assert result.solved
    assert result.gpd_stat is not None
    assert result.gpd_stat < 1e-9
    assert result.context_residuals["ctx_a"].total_variation < 1e-9
    assert result.context_residuals["ctx_b"].total_variation < 1e-9
    assert (
        abs(sum(item.probability for item in result.fitted_tuple_distribution) - 1.0)
        < 1e-9
    )


def test_incompatible_marginals_with_nonempty_support_have_positive_gpd_stat() -> None:
    instance = build_matching_instance()
    trace = build_probability_trace(instance)
    result = solve_statistical_deficit_from_trace(instance, trace)
    assert result.solved
    assert result.gpd_stat is not None
    assert result.gpd_stat > 0
    assert any(
        residual.total_variation > 0 for residual in result.context_residuals.values()
    )


def test_per_context_residuals_are_reported() -> None:
    instance = build_matching_instance()
    trace = build_probability_trace(instance)
    result = solve_statistical_deficit_from_trace(instance, trace)
    assert set(result.context_residuals) == {"ctx_a", "ctx_b"}
    assert result.context_residuals["ctx_a"].l1 >= 0


def test_count_based_trace_normalizes_correctly() -> None:
    instance = build_matching_instance()
    marginals = extract_empirical_marginals(build_count_trace(instance), instance)
    assert marginals["ctx_a"].mode == "count"
    assert marginals["ctx_a"].probabilities == {"a0": 0.7, "a1": 0.3}


def test_probability_based_trace_is_accepted() -> None:
    instance = build_matching_instance()
    marginals = extract_empirical_marginals(build_probability_trace(instance), instance)
    assert marginals["ctx_b"].mode == "probability"
    assert marginals["ctx_b"].probabilities == {"b0": 0.1, "b1": 0.9}


def test_count_and_probability_inputs_can_encode_the_same_marginals() -> None:
    instance = build_matching_instance()
    count_marginals = extract_empirical_marginals(build_count_trace(instance), instance)
    probability_trace = build_observation_trace(
        trace_id="trace_prob_same",
        instance_id=instance.instance_id,
        observations=[
            make_observation(context_id="ctx_a", atom_ids=["a0"], probability=0.7),
            make_observation(context_id="ctx_a", atom_ids=["a1"], probability=0.3),
            make_observation(context_id="ctx_b", atom_ids=["b0"], probability=0.7),
            make_observation(context_id="ctx_b", atom_ids=["b1"], probability=0.3),
        ],
    )
    probability_marginals = extract_empirical_marginals(probability_trace, instance)
    assert (
        count_marginals["ctx_a"].probabilities
        == probability_marginals["ctx_a"].probabilities
    )


def test_mixed_count_and_probability_within_context_is_rejected() -> None:
    instance = build_matching_instance()
    trace = build_observation_trace(
        trace_id="trace_mixed",
        instance_id=instance.instance_id,
        observations=[
            make_observation(context_id="ctx_a", atom_ids=["a0"], count=3),
            make_observation(context_id="ctx_a", atom_ids=["a1"], probability=0.5),
            make_observation(context_id="ctx_b", atom_ids=["b0"], count=1),
        ],
    )
    with pytest.raises(ValueError, match="mixes count and probability"):
        extract_empirical_marginals(trace, instance)


def test_unknown_context_or_atom_is_rejected_when_instance_is_provided() -> None:
    instance = build_matching_instance()
    trace = build_observation_trace(
        trace_id="trace_unknown",
        instance_id=instance.instance_id,
        observations=[
            make_observation(context_id="ctx_x", atom_ids=["x0"], count=1),
        ],
    )
    with pytest.raises(ValueError, match="unknown context_id"):
        extract_empirical_marginals(trace, instance)


def test_default_hard_only_behavior_ignores_soft_conflicts() -> None:
    instance = build_soft_conflict_instance()
    trace = build_count_trace(instance)
    result = solve_statistical_deficit_from_trace(instance, trace)
    assert result.solved
    assert result.gpd_stat is not None
    assert result.gpd_stat < 1e-9


def test_include_soft_enforces_soft_conflicts() -> None:
    instance = build_soft_conflict_instance()
    trace = build_count_trace(instance)
    result = solve_statistical_deficit_from_trace(instance, trace, include_soft=True)
    assert result.solved
    assert result.gpd_stat is not None
    assert result.gpd_stat > 0


def test_no_respecting_tuples_reports_unsolved_case() -> None:
    instance = build_no_respecting_instance()
    trace = build_count_trace(instance)
    result = solve_statistical_deficit_from_trace(instance, trace)
    assert not result.solved
    assert result.reason == "no_respecting_tuples"
    assert result.gpd_stat is None


def test_multi_trace_solver_reports_mode_and_trace_ids() -> None:
    instance = build_matching_instance()
    trace_a = build_count_trace(instance)
    trace_b = build_count_trace(instance)
    trace_b.trace_id = "trace_counts_b"
    result = solve_statistical_global_packaging(instance, [trace_a, trace_b])
    assert result.solved
    assert result.mode == "hard_only"
    assert result.trace_ids == ["trace_counts", "trace_counts_b"]
    assert result.candidate_tuple_count == result.total_candidate_tuple_count
    assert result.allowed_tuple_count == result.respecting_tuple_count


def test_statistical_summary_writer_uses_run_registry(tmp_path) -> None:
    instance = build_matching_instance()
    trace = build_count_trace(instance)
    trace_path = tmp_path / "trace.json"
    trace_path.write_text("{}", encoding="utf-8")
    artifacts = write_statistical_summary(
        instance,
        [trace],
        trace_paths=[trace_path],
        category="benchmarks",
        label="stat-fit",
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
    )
    assert (tmp_path / artifacts.summary_path).exists()
    manifest = load_model(
        tmp_path / artifacts.manifest_path, kind=SchemaKind.RUN_MANIFEST
    )
    assert isinstance(manifest, RunManifest)
    assert manifest.output_artifacts["summary"] == artifacts.summary_path
