from __future__ import annotations

from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.solvers.structural_deficit import (
    StructuralDeficitConfig,
    solve_structural_deficit,
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


def build_coverage_gap_instance() -> EventPackageInstance:
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": "inst_coverage_gap",
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


def build_soft_conflict_instance(*, soft_weight: float) -> EventPackageInstance:
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": "inst_soft_conflict",
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
                    "proposal_id": "p_soft_conflict",
                    "left_event_id": "event_a1",
                    "right_event_id": "event_empty",
                    "constraint_kind": "soft",
                    "weight_key": "wk_soft",
                },
            ],
            "weights": {"wk_soft": soft_weight},
            "metadata": {},
            "audit": {"created_at": "2026-03-25T00:00:00Z"},
        }
    )


def build_hard_conflict_instance() -> EventPackageInstance:
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": "inst_hard_conflict",
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
                    "proposal_id": "p_hard_b0",
                    "left_event_id": "event_a0",
                    "right_event_id": "event_b0",
                    "constraint_kind": "hard",
                },
                {
                    "proposal_id": "p_hard_b1",
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


def test_exactly_extendable_instance_has_zero_structural_deficit() -> None:
    result = solve_structural_deficit(build_extendable_instance())
    assert result.solved
    assert result.feasible_without_relaxation
    assert result.gpd_str == 0.0
    assert result.relaxed_proposal_ids == []
    assert result.relaxed_atoms == {}
    assert result.best_fit_witness_tuples


def test_nonextendable_coverage_case_relaxes_atoms() -> None:
    result = solve_structural_deficit(build_coverage_gap_instance())
    assert result.solved
    assert not result.feasible_without_relaxation
    assert result.gpd_str == 2.0
    assert result.relaxed_proposal_ids == []
    assert result.relaxed_atoms == {"ctx_a": ["a1"], "ctx_b": ["b1"]}


def test_conflicting_soft_proposal_is_relaxed_when_cheaper_than_atoms() -> None:
    result = solve_structural_deficit(build_soft_conflict_instance(soft_weight=0.5))
    assert result.solved
    assert result.gpd_str == 0.5
    assert result.relaxed_proposal_ids == ["p_soft_conflict"]
    assert result.relaxed_atoms == {}


def test_proposal_weights_affect_the_chosen_optimum() -> None:
    result = solve_structural_deficit(build_soft_conflict_instance(soft_weight=3.0))
    assert result.solved
    assert result.gpd_str == 2.0
    assert result.relaxed_proposal_ids == []
    assert result.relaxed_atoms == {"ctx_a": ["a1"], "ctx_b": ["b1"]}


def test_hard_proposals_are_not_relaxed_by_default() -> None:
    result = solve_structural_deficit(build_hard_conflict_instance())
    assert not result.solved
    assert result.gpd_str is None
    assert result.reason == "no_valid_relaxation_plan"


def test_hard_proposals_can_be_relaxed_when_enabled() -> None:
    result = solve_structural_deficit(
        build_hard_conflict_instance(),
        config=StructuralDeficitConfig(
            allow_relax_hard=True,
            hard_proposal_relax_weight=2.5,
        ),
    )
    assert result.solved
    assert result.gpd_str == 2.5
    assert result.relaxed_proposal_ids == ["p_hard_b0"]
    assert result.relaxed_atoms == {}
