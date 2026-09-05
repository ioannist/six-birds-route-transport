from __future__ import annotations

from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.solvers.structural_exact import (
    solve_exact_structural_feasibility,
)


def build_extendable_instance() -> EventPackageInstance:
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": "inst_extendable",
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
                {
                    "event_id": "event_a0",
                    "context_id": "ctx_a",
                    "atom_ids": ["a0"],
                },
                {
                    "event_id": "event_a1",
                    "context_id": "ctx_a",
                    "atom_ids": ["a1"],
                },
                {
                    "event_id": "event_b0",
                    "context_id": "ctx_b",
                    "atom_ids": ["b0"],
                },
                {
                    "event_id": "event_b1",
                    "context_id": "ctx_b",
                    "atom_ids": ["b1"],
                },
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


def build_nonextendable_instance() -> EventPackageInstance:
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": "inst_nonextendable",
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
                {"event_id": "event_e", "context_id": "ctx_a", "atom_ids": ["a1"]},
                {"event_id": "event_f", "context_id": "ctx_b", "atom_ids": ["b1"]},
                {"event_id": "event_g", "context_id": "ctx_b", "atom_ids": []},
            ],
            "equality_proposals": [
                {
                    "proposal_id": "p_e_f",
                    "left_event_id": "event_e",
                    "right_event_id": "event_f",
                    "constraint_kind": "hard",
                },
                {
                    "proposal_id": "p_e_g",
                    "left_event_id": "event_e",
                    "right_event_id": "event_g",
                    "constraint_kind": "hard",
                },
            ],
            "weights": {},
            "metadata": {},
            "audit": {"created_at": "2026-03-25T00:00:00Z"},
        }
    )


def build_soft_only_instance() -> EventPackageInstance:
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": "inst_soft_only",
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
                {"event_id": "event_a1", "context_id": "ctx_a", "atom_ids": ["a1"]},
                {"event_id": "event_empty", "context_id": "ctx_b", "atom_ids": []},
            ],
            "equality_proposals": [
                {
                    "proposal_id": "p_soft",
                    "left_event_id": "event_a1",
                    "right_event_id": "event_empty",
                    "constraint_kind": "soft",
                    "weight_key": "wk1",
                }
            ],
            "weights": {"wk1": 1.0},
            "metadata": {},
            "audit": {"created_at": "2026-03-25T00:00:00Z"},
        }
    )


def test_trivial_extendable_instance_is_feasible() -> None:
    result = solve_exact_structural_feasibility(build_extendable_instance())
    assert result.feasible
    assert result.total_candidate_tuple_count == 4
    assert result.respecting_tuple_count == 2
    assert result.enforced_proposal_ids == ["p_a0_b0", "p_a1_b1"]
    assert result.reason is None


def test_feasible_witness_tuples_cover_all_atoms_and_respect_constraints() -> None:
    result = solve_exact_structural_feasibility(build_extendable_instance())
    assert result.witness_tuples == [
        {"ctx_a": "a0", "ctx_b": "b0"},
        {"ctx_a": "a1", "ctx_b": "b1"},
    ]
    assert result.uncovered_atoms == {}
    assert all(
        tuple_map in result.respecting_tuples for tuple_map in result.witness_tuples
    )


def test_trivial_nonextendable_instance_is_infeasible() -> None:
    result = solve_exact_structural_feasibility(build_nonextendable_instance())
    assert not result.feasible
    assert result.total_candidate_tuple_count == 4
    assert result.respecting_tuple_count == 1
    assert result.witness_tuples is None
    assert result.reason == "coverage_failure"
    assert result.uncovered_atoms == {"ctx_a": ["a1"], "ctx_b": ["b1"]}


def test_default_behavior_enforces_hard_proposals_only() -> None:
    result = solve_exact_structural_feasibility(build_soft_only_instance())
    assert result.feasible
    assert result.enforced_proposal_ids == []
    assert result.respecting_tuple_count == 4


def test_include_soft_enforces_soft_proposals_exactly() -> None:
    result = solve_exact_structural_feasibility(
        build_soft_only_instance(),
        include_soft=True,
    )
    assert not result.feasible
    assert result.enforced_proposal_ids == ["p_soft"]
    assert result.respecting_tuple_count == 2
    assert result.reason == "coverage_failure"
