from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
import math

from ..schemas.event_package import EqualityProposal, Event, EventPackageInstance
from .structural_exact import (
    PublicTuple,
    _build_event_atom_sets,
    _build_context_atoms,
    _build_event_lookup,
    _enumerate_candidate_tuples,
    _filter_respecting_tuples,
    _tuple_as_mapping,
    _tuple_respects_proposal,
    _uncovered_atoms,
    solve_exact_structural_feasibility,
)

AtomKey = tuple[str, str]


@dataclass(slots=True)
class StructuralDeficitConfig:
    allow_relax_hard: bool = False
    atom_relax_weight: float = 1.0
    hard_proposal_relax_weight: float = 1.0
    atom_weight_overrides: dict[AtomKey, float] = field(default_factory=dict)
    proposal_weight_overrides: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_weight(self.atom_relax_weight, label="atom_relax_weight")
        _ensure_weight(
            self.hard_proposal_relax_weight,
            label="hard_proposal_relax_weight",
        )
        for atom_key, weight in self.atom_weight_overrides.items():
            if len(atom_key) != 2:
                raise ValueError(
                    "atom_weight_overrides keys must be (context_id, atom_id)"
                )
            _ensure_weight(weight, label=f"atom_weight_overrides[{atom_key!r}]")
        for proposal_id, weight in self.proposal_weight_overrides.items():
            if not proposal_id:
                raise ValueError("proposal_weight_overrides keys must be non-empty")
            _ensure_weight(weight, label=f"proposal_weight_overrides[{proposal_id!r}]")


@dataclass(slots=True)
class StructuralDeficitResult:
    instance_id: str
    gpd_str: float | None
    solved: bool
    feasible_without_relaxation: bool
    relaxed_proposal_ids: list[str]
    relaxed_atoms: dict[str, list[str]]
    enforced_proposal_ids: list[str]
    best_fit_witness_tuples: list[PublicTuple] | None
    total_candidate_tuple_count: int
    respecting_tuple_count: int
    reason: str | None = None


@dataclass(slots=True)
class _PlanCandidate:
    cost: float
    relaxed_proposal_ids: list[str]
    relaxed_atoms: dict[str, list[str]]
    enforced_proposal_ids: list[str]
    witness_tuples: list[PublicTuple]
    respecting_tuple_count: int


def _ensure_weight(value: float, *, label: str) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and non-negative")


def _proposal_weight(
    proposal: EqualityProposal,
    *,
    instance: EventPackageInstance,
    config: StructuralDeficitConfig,
) -> float:
    override = config.proposal_weight_overrides.get(proposal.proposal_id)
    if override is not None:
        return override
    if proposal.constraint_kind == "soft":
        assert proposal.weight_key is not None
        return instance.weights[proposal.weight_key]
    return config.hard_proposal_relax_weight


def _atom_weight(
    context_id: str,
    atom_id: str,
    *,
    config: StructuralDeficitConfig,
) -> float:
    override = config.atom_weight_overrides.get((context_id, atom_id))
    if override is not None:
        return override
    return config.atom_relax_weight


def _relaxable_proposals(
    instance: EventPackageInstance,
    *,
    config: StructuralDeficitConfig,
) -> list[EqualityProposal]:
    proposals = [p for p in instance.equality_proposals if p.constraint_kind == "soft"]
    if config.allow_relax_hard:
        proposals.extend(
            p for p in instance.equality_proposals if p.constraint_kind == "hard"
        )
    return sorted(proposals, key=lambda proposal: proposal.proposal_id)


def _enumerate_relaxed_proposal_sets(
    proposals: list[EqualityProposal],
) -> list[tuple[EqualityProposal, ...]]:
    subsets: list[tuple[EqualityProposal, ...]] = []
    for size in range(len(proposals) + 1):
        subsets.extend(combinations(proposals, size))
    return subsets


def _required_atoms_from_uncovered(
    atoms_by_context: dict[str, list[str]],
    uncovered_atoms: dict[str, list[str]],
) -> dict[str, set[str]]:
    return {
        context_id: set(atoms) - set(uncovered_atoms.get(context_id, []))
        for context_id, atoms in atoms_by_context.items()
    }


def _covers_required_atoms(
    tuple_family: list[tuple[str, ...]],
    *,
    context_order: list[str],
    required_atoms: dict[str, set[str]],
) -> bool:
    covered = {context_id: set() for context_id in context_order}
    for tuple_values in tuple_family:
        for context_id, atom_id in zip(context_order, tuple_values, strict=True):
            if atom_id in required_atoms[context_id]:
                covered[context_id].add(atom_id)
    return all(
        covered[context_id] == required_atoms[context_id]
        for context_id in context_order
    )


def _find_witness_for_required_atoms(
    respecting_tuples: list[tuple[str, ...]],
    *,
    context_order: list[str],
    required_atoms: dict[str, set[str]],
) -> list[tuple[str, ...]] | None:
    if not respecting_tuples:
        return None

    uncovered = {
        context_id: set(atom_ids) for context_id, atom_ids in required_atoms.items()
    }
    if all(not atom_ids for atom_ids in uncovered.values()):
        return [min(respecting_tuples)]

    ordered_candidates = sorted(respecting_tuples)
    witness: list[tuple[str, ...]] = []
    while any(uncovered[context_id] for context_id in context_order):
        best_tuple: tuple[str, ...] | None = None
        best_gain = 0
        for tuple_values in ordered_candidates:
            gain = sum(
                1
                for context_id, atom_id in zip(context_order, tuple_values, strict=True)
                if atom_id in uncovered[context_id]
            )
            if gain > best_gain:
                best_gain = gain
                best_tuple = tuple_values
        if best_tuple is None or best_gain == 0:
            return None
        witness.append(best_tuple)
        for context_id, atom_id in zip(context_order, best_tuple, strict=True):
            uncovered[context_id].discard(atom_id)
        ordered_candidates = [
            tuple_values
            for tuple_values in ordered_candidates
            if tuple_values != best_tuple
        ]

    return witness


def _plan_sort_key(
    plan: _PlanCandidate,
) -> tuple[float, int, int, int, tuple[str, ...], tuple[str, ...]]:
    relaxed_atom_ids = tuple(
        f"{context_id}:{atom_id}"
        for context_id in sorted(plan.relaxed_atoms)
        for atom_id in plan.relaxed_atoms[context_id]
    )
    witness_ids = tuple(
        "|".join(
            f"{context_id}={tuple_map[context_id]}" for context_id in sorted(tuple_map)
        )
        for tuple_map in plan.witness_tuples
    )
    return (
        plan.cost,
        len(plan.relaxed_proposal_ids),
        sum(len(atom_ids) for atom_ids in plan.relaxed_atoms.values()),
        len(plan.witness_tuples),
        tuple(plan.relaxed_proposal_ids),
        relaxed_atom_ids + witness_ids,
    )


def _solve_structural_deficit_exhaustive(
    instance: EventPackageInstance,
    *,
    active_config: StructuralDeficitConfig,
    feasible_without_relaxation: bool,
    context_order: list[str],
    atoms_by_context: dict[str, list[str]],
    event_by_id: dict[str, Event],
    event_atom_sets: dict[str, set[str]],
    candidate_tuples: list[tuple[str, ...]],
    all_proposals: dict[str, EqualityProposal],
    relaxable: list[EqualityProposal],
) -> StructuralDeficitResult:
    best_plan: _PlanCandidate | None = None
    for relaxed_subset in _enumerate_relaxed_proposal_sets(relaxable):
        relaxed_ids = {proposal.proposal_id for proposal in relaxed_subset}
        enforced = [
            proposal
            for proposal in instance.equality_proposals
            if proposal.proposal_id not in relaxed_ids
        ]
        respecting_tuples = _filter_respecting_tuples(
            candidate_tuples,
            context_order=context_order,
            proposals=enforced,
            event_by_id=event_by_id,
            event_atom_sets=event_atom_sets,
        )
        if not respecting_tuples:
            continue

        relaxed_atoms = _uncovered_atoms(
            respecting_tuples,
            context_order=context_order,
            atoms_by_context=atoms_by_context,
        )
        required_atoms = _required_atoms_from_uncovered(atoms_by_context, relaxed_atoms)
        witness = _find_witness_for_required_atoms(
            respecting_tuples,
            context_order=context_order,
            required_atoms=required_atoms,
        )
        if witness is None:
            continue

        proposal_cost = sum(
            _proposal_weight(
                all_proposals[proposal_id], instance=instance, config=active_config
            )
            for proposal_id in sorted(relaxed_ids)
        )
        atom_cost = sum(
            _atom_weight(context_id, atom_id, config=active_config)
            for context_id, atom_ids in relaxed_atoms.items()
            for atom_id in atom_ids
        )
        plan = _PlanCandidate(
            cost=proposal_cost + atom_cost,
            relaxed_proposal_ids=sorted(relaxed_ids),
            relaxed_atoms={key: value[:] for key, value in relaxed_atoms.items()},
            enforced_proposal_ids=[proposal.proposal_id for proposal in enforced],
            witness_tuples=[
                _tuple_as_mapping(tuple_values, context_order)
                for tuple_values in witness
            ],
            respecting_tuple_count=len(respecting_tuples),
        )
        if best_plan is None or _plan_sort_key(plan) < _plan_sort_key(best_plan):
            best_plan = plan

    if best_plan is None:
        return StructuralDeficitResult(
            instance_id=instance.instance_id,
            gpd_str=None,
            solved=False,
            feasible_without_relaxation=feasible_without_relaxation,
            relaxed_proposal_ids=[],
            relaxed_atoms={},
            enforced_proposal_ids=[
                proposal.proposal_id for proposal in instance.equality_proposals
            ],
            best_fit_witness_tuples=None,
            total_candidate_tuple_count=len(candidate_tuples),
            respecting_tuple_count=0,
            reason="no_valid_relaxation_plan",
        )

    return StructuralDeficitResult(
        instance_id=instance.instance_id,
        gpd_str=best_plan.cost,
        solved=True,
        feasible_without_relaxation=feasible_without_relaxation,
        relaxed_proposal_ids=best_plan.relaxed_proposal_ids,
        relaxed_atoms=best_plan.relaxed_atoms,
        enforced_proposal_ids=best_plan.enforced_proposal_ids,
        best_fit_witness_tuples=best_plan.witness_tuples,
        total_candidate_tuple_count=len(candidate_tuples),
        respecting_tuple_count=best_plan.respecting_tuple_count,
        reason=None,
    )


def _solve_structural_deficit_milp(
    instance: EventPackageInstance,
    *,
    active_config: StructuralDeficitConfig,
    feasible_without_relaxation: bool,
    context_order: list[str],
    atoms_by_context: dict[str, list[str]],
    event_by_id: dict[str, Event],
    event_atom_sets: dict[str, set[str]],
    candidate_tuples: list[tuple[str, ...]],
    all_proposals: dict[str, EqualityProposal],
    relaxable: list[EqualityProposal],
) -> StructuralDeficitResult | None:
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp

    proposal_index = {
        proposal.proposal_id: index for index, proposal in enumerate(relaxable)
    }
    atom_keys = [
        (context_id, atom_id)
        for context_id in context_order
        for atom_id in atoms_by_context[context_id]
    ]

    tuple_count = len(candidate_tuples)
    proposal_count = len(relaxable)
    atom_count = len(atom_keys)
    if tuple_count == 0:
        return None

    total_vars = tuple_count + proposal_count + atom_count
    objective = np.zeros(total_vars, dtype=float)
    for proposal_id, index in proposal_index.items():
        objective[tuple_count + index] = _proposal_weight(
            all_proposals[proposal_id], instance=instance, config=active_config
        )
    for index, (context_id, atom_id) in enumerate(atom_keys):
        objective[tuple_count + proposal_count + index] = _atom_weight(
            context_id,
            atom_id,
            config=active_config,
        )

    rows: list[list[float]] = []
    lbs: list[float] = []
    ubs: list[float] = []

    # At least one tuple must remain selected.
    row = [0.0] * total_vars
    for tuple_index in range(tuple_count):
        row[tuple_index] = 1.0
    rows.append(row)
    lbs.append(1.0)
    ubs.append(float("inf"))

    for atom_offset, (context_id, atom_id) in enumerate(atom_keys):
        row = [0.0] * total_vars
        context_index = context_order.index(context_id)
        for tuple_index, tuple_values in enumerate(candidate_tuples):
            if tuple_values[context_index] == atom_id:
                row[tuple_index] = 1.0
        row[tuple_count + proposal_count + atom_offset] = 1.0
        rows.append(row)
        lbs.append(1.0)
        ubs.append(float("inf"))

    for proposal in instance.equality_proposals:
        violating_indices: list[int] = []
        for tuple_index, tuple_values in enumerate(candidate_tuples):
            if not _tuple_respects_proposal(
                tuple_values,
                context_order,
                proposal,
                event_by_id,
                event_atom_sets,
            ):
                violating_indices.append(tuple_index)
        if not violating_indices:
            continue
        relax_index = proposal_index.get(proposal.proposal_id)
        for tuple_index in violating_indices:
            row = [0.0] * total_vars
            row[tuple_index] = 1.0
            if relax_index is not None:
                row[tuple_count + relax_index] = -1.0
                rows.append(row)
                lbs.append(float("-inf"))
                ubs.append(0.0)
            else:
                rows.append(row)
                lbs.append(float("-inf"))
                ubs.append(0.0)

    result = milp(
        c=objective,
        integrality=np.ones(total_vars, dtype=int),
        bounds=Bounds(
            lb=np.zeros(total_vars, dtype=float),
            ub=np.ones(total_vars, dtype=float),
        ),
        constraints=[
            LinearConstraint(
                np.asarray(rows, dtype=float),
                lb=np.asarray(lbs, dtype=float),
                ub=np.asarray(ubs, dtype=float),
            )
        ],
        options={"disp": False},
    )
    if not result.success or result.x is None:
        return None

    selected_tuple_indices = [
        index for index, value in enumerate(result.x[:tuple_count]) if value >= 0.5
    ]
    relaxed_proposal_ids = [
        proposal_id
        for proposal_id, index in proposal_index.items()
        if result.x[tuple_count + index] >= 0.5
    ]
    relaxed_atoms: dict[str, list[str]] = {}
    for atom_offset, (context_id, atom_id) in enumerate(atom_keys):
        if result.x[tuple_count + proposal_count + atom_offset] >= 0.5:
            relaxed_atoms.setdefault(context_id, []).append(atom_id)
    for atom_ids in relaxed_atoms.values():
        atom_ids.sort()
    enforced = [
        proposal
        for proposal in instance.equality_proposals
        if proposal.proposal_id not in set(relaxed_proposal_ids)
    ]
    respecting_tuples = _filter_respecting_tuples(
        candidate_tuples,
        context_order=context_order,
        proposals=enforced,
        event_by_id=event_by_id,
        event_atom_sets=event_atom_sets,
    )
    witness = [
        _tuple_as_mapping(candidate_tuples[index], context_order)
        for index in selected_tuple_indices
    ]
    return StructuralDeficitResult(
        instance_id=instance.instance_id,
        gpd_str=float(result.fun),
        solved=True,
        feasible_without_relaxation=feasible_without_relaxation,
        relaxed_proposal_ids=sorted(relaxed_proposal_ids),
        relaxed_atoms=relaxed_atoms,
        enforced_proposal_ids=[proposal.proposal_id for proposal in enforced],
        best_fit_witness_tuples=witness,
        total_candidate_tuple_count=len(candidate_tuples),
        respecting_tuple_count=len(respecting_tuples),
        reason=None,
    )


def solve_structural_deficit(
    instance: EventPackageInstance,
    *,
    config: StructuralDeficitConfig | None = None,
) -> StructuralDeficitResult:
    active_config = config or StructuralDeficitConfig()
    exact_result = solve_exact_structural_feasibility(instance, include_soft=True)
    feasible_without_relaxation = exact_result.feasible

    context_order = [context.context_id for context in instance.contexts]
    atoms_by_context = _build_context_atoms(instance)
    event_by_id = _build_event_lookup(instance)
    event_atom_sets = _build_event_atom_sets(instance)
    candidate_tuples = _enumerate_candidate_tuples(context_order, atoms_by_context)
    all_proposals = {
        proposal.proposal_id: proposal for proposal in instance.equality_proposals
    }
    relaxable = _relaxable_proposals(instance, config=active_config)
    if len(relaxable) <= 12:
        return _solve_structural_deficit_exhaustive(
            instance,
            active_config=active_config,
            feasible_without_relaxation=feasible_without_relaxation,
            context_order=context_order,
            atoms_by_context=atoms_by_context,
            event_by_id=event_by_id,
            event_atom_sets=event_atom_sets,
            candidate_tuples=candidate_tuples,
            all_proposals=all_proposals,
            relaxable=relaxable,
        )
    milp_result = _solve_structural_deficit_milp(
        instance,
        active_config=active_config,
        feasible_without_relaxation=feasible_without_relaxation,
        context_order=context_order,
        atoms_by_context=atoms_by_context,
        event_by_id=event_by_id,
        event_atom_sets=event_atom_sets,
        candidate_tuples=candidate_tuples,
        all_proposals=all_proposals,
        relaxable=relaxable,
    )
    if milp_result is not None:
        return milp_result
    return _solve_structural_deficit_exhaustive(
        instance,
        active_config=active_config,
        feasible_without_relaxation=feasible_without_relaxation,
        context_order=context_order,
        atoms_by_context=atoms_by_context,
        event_by_id=event_by_id,
        event_atom_sets=event_atom_sets,
        candidate_tuples=candidate_tuples,
        all_proposals=all_proposals,
        relaxable=relaxable,
    )
