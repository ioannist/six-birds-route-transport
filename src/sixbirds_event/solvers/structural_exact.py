from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import product

from ..schemas.event_package import EqualityProposal, Event, EventPackageInstance


PublicTuple = dict[str, str]


@dataclass(slots=True)
class StructuralFeasibilityResult:
    feasible: bool
    instance_id: str
    enforced_proposal_ids: list[str]
    total_candidate_tuple_count: int
    respecting_tuple_count: int
    witness_tuples: list[PublicTuple] | None
    uncovered_atoms: dict[str, list[str]]
    respecting_tuples: list[PublicTuple]
    context_order: list[str]
    reason: str | None = None


def _build_event_lookup(instance: EventPackageInstance) -> dict[str, Event]:
    return {event.event_id: event for event in instance.events}


def _build_event_atom_sets(instance: EventPackageInstance) -> dict[str, set[str]]:
    return {event.event_id: set(event.atom_ids) for event in instance.events}


def _build_context_atoms(instance: EventPackageInstance) -> dict[str, list[str]]:
    return {
        context.context_id: [atom.atom_id for atom in context.atoms]
        for context in instance.contexts
    }


def _enforced_proposals(
    instance: EventPackageInstance, *, include_soft: bool
) -> list[EqualityProposal]:
    allowed_kinds = {"hard", "soft"} if include_soft else {"hard"}
    return [
        proposal
        for proposal in instance.equality_proposals
        if proposal.constraint_kind in allowed_kinds
    ]


def _enumerate_candidate_tuples(
    context_order: list[str], atoms_by_context: dict[str, list[str]]
) -> list[tuple[str, ...]]:
    atom_lists = [atoms_by_context[context_id] for context_id in context_order]
    return list(product(*atom_lists))


def _tuple_as_mapping(
    tuple_values: tuple[str, ...], context_order: list[str]
) -> dict[str, str]:
    return dict(zip(context_order, tuple_values, strict=True))


def _tuple_respects_proposal(
    tuple_values: tuple[str, ...],
    context_order: list[str],
    proposal: EqualityProposal,
    event_by_id: dict[str, Event],
    event_atom_sets: dict[str, set[str]],
) -> bool:
    tuple_map = _tuple_as_mapping(tuple_values, context_order)
    left_event = event_by_id[proposal.left_event_id]
    right_event = event_by_id[proposal.right_event_id]
    left_member = (
        tuple_map[left_event.context_id] in event_atom_sets[left_event.event_id]
    )
    right_member = (
        tuple_map[right_event.context_id] in event_atom_sets[right_event.event_id]
    )
    return left_member == right_member


def _filter_respecting_tuples(
    candidate_tuples: list[tuple[str, ...]],
    *,
    context_order: list[str],
    proposals: list[EqualityProposal],
    event_by_id: dict[str, Event],
    event_atom_sets: dict[str, set[str]],
) -> list[tuple[str, ...]]:
    respecting: list[tuple[str, ...]] = []
    for tuple_values in candidate_tuples:
        if all(
            _tuple_respects_proposal(
                tuple_values,
                context_order,
                proposal,
                event_by_id,
                event_atom_sets,
            )
            for proposal in proposals
        ):
            respecting.append(tuple_values)
    return respecting


def _coverage_from_tuples(
    tuple_family: list[tuple[str, ...]],
    *,
    context_order: list[str],
) -> dict[str, set[str]]:
    coverage = {context_id: set() for context_id in context_order}
    for tuple_values in tuple_family:
        for context_id, atom_id in zip(context_order, tuple_values, strict=True):
            coverage[context_id].add(atom_id)
    return coverage


def _uncovered_atoms(
    tuple_family: list[tuple[str, ...]],
    *,
    context_order: list[str],
    atoms_by_context: dict[str, list[str]],
) -> dict[str, list[str]]:
    coverage = _coverage_from_tuples(tuple_family, context_order=context_order)
    uncovered: dict[str, list[str]] = {}
    for context_id in context_order:
        missing = [
            atom_id
            for atom_id in atoms_by_context[context_id]
            if atom_id not in coverage[context_id]
        ]
        if missing:
            uncovered[context_id] = missing
    return uncovered


def _find_covering_witness(
    respecting_tuples: list[tuple[str, ...]],
    *,
    context_order: list[str],
    atoms_by_context: dict[str, list[str]],
) -> list[tuple[str, ...]] | None:
    if not respecting_tuples:
        return None
    selected_indices = _solve_cover_milp_indices(
        respecting_tuples=respecting_tuples,
        context_order=context_order,
        atoms_by_context=atoms_by_context,
    )
    if selected_indices is not None:
        return [respecting_tuples[index] for index in selected_indices]

    ordered_atoms = [
        (context_id, atom_id)
        for context_id in context_order
        for atom_id in atoms_by_context[context_id]
    ]
    atom_index = {atom_key: index for index, atom_key in enumerate(ordered_atoms)}
    full_mask = (1 << len(atom_index)) - 1
    tuple_masks = [
        sum(
            1 << atom_index[(context_id, atom_id)]
            for context_id, atom_id in zip(context_order, tuple_values, strict=True)
        )
        for tuple_values in respecting_tuples
    ]
    order = sorted(
        range(len(respecting_tuples)),
        key=lambda index: tuple_masks[index].bit_count(),
        reverse=True,
    )
    ordered_tuples = [respecting_tuples[index] for index in order]
    ordered_masks = [tuple_masks[index] for index in order]
    covering_indices: dict[int, list[int]] = {
        bit: [index for index, mask in enumerate(ordered_masks) if mask & (1 << bit)]
        for bit in range(len(atom_index))
    }
    suffix_union = [0] * (len(ordered_masks) + 1)
    for index in range(len(ordered_masks) - 1, -1, -1):
        suffix_union[index] = suffix_union[index + 1] | ordered_masks[index]

    @lru_cache(maxsize=None)
    def _search(
        start_index: int,
        covered_mask: int,
        remaining_slots: int,
    ) -> tuple[int, ...] | None:
        if covered_mask == full_mask:
            return ()
        if remaining_slots == 0:
            return None
        if (covered_mask | suffix_union[start_index]) != full_mask:
            return None

        uncovered_mask = full_mask & ~covered_mask
        next_bit = (uncovered_mask & -uncovered_mask).bit_length() - 1
        for candidate_index in covering_indices[next_bit]:
            if candidate_index < start_index:
                continue
            candidate_mask = ordered_masks[candidate_index]
            if (candidate_mask | covered_mask) == covered_mask:
                continue
            tail = _search(
                candidate_index + 1,
                covered_mask | candidate_mask,
                remaining_slots - 1,
            )
            if tail is not None:
                return (candidate_index, *tail)
        return None

    for size in range(1, len(ordered_tuples) + 1):
        witness_indices = _search(0, 0, size)
        if witness_indices is not None:
            return [ordered_tuples[index] for index in witness_indices]
    return None


def _solve_cover_milp_indices(
    *,
    respecting_tuples: list[tuple[str, ...]],
    context_order: list[str],
    atoms_by_context: dict[str, list[str]],
) -> list[int] | None:
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp

    rows: list[list[float]] = []
    for context_index, context_id in enumerate(context_order):
        for atom_id in atoms_by_context[context_id]:
            rows.append(
                [
                    1.0 if tuple_values[context_index] == atom_id else 0.0
                    for tuple_values in respecting_tuples
                ]
            )
    if not rows:
        return []
    matrix = np.asarray(rows, dtype=float)
    variable_count = len(respecting_tuples)
    result = milp(
        c=np.ones(variable_count, dtype=float),
        integrality=np.ones(variable_count, dtype=int),
        bounds=Bounds(
            lb=np.zeros(variable_count, dtype=float),
            ub=np.ones(variable_count, dtype=float),
        ),
        constraints=[
            LinearConstraint(
                matrix,
                lb=np.ones(matrix.shape[0], dtype=float),
                ub=np.full(matrix.shape[0], np.inf, dtype=float),
            )
        ],
        options={"disp": False},
    )
    if not result.success or result.x is None:
        return None
    return [index for index, value in enumerate(result.x) if value >= 0.5]


def solve_exact_structural_feasibility(
    instance: EventPackageInstance,
    *,
    include_soft: bool = False,
) -> StructuralFeasibilityResult:
    context_order = [context.context_id for context in instance.contexts]
    atoms_by_context = _build_context_atoms(instance)
    event_by_id = _build_event_lookup(instance)
    event_atom_sets = _build_event_atom_sets(instance)
    proposals = _enforced_proposals(instance, include_soft=include_soft)

    candidate_tuples = _enumerate_candidate_tuples(context_order, atoms_by_context)
    respecting_tuples = _filter_respecting_tuples(
        candidate_tuples,
        context_order=context_order,
        proposals=proposals,
        event_by_id=event_by_id,
        event_atom_sets=event_atom_sets,
    )
    witness = _find_covering_witness(
        respecting_tuples,
        context_order=context_order,
        atoms_by_context=atoms_by_context,
    )

    respecting_public = [
        _tuple_as_mapping(tuple_values, context_order)
        for tuple_values in respecting_tuples
    ]
    witness_public = (
        [_tuple_as_mapping(tuple_values, context_order) for tuple_values in witness]
        if witness is not None
        else None
    )
    uncovered = _uncovered_atoms(
        witness or respecting_tuples,
        context_order=context_order,
        atoms_by_context=atoms_by_context,
    )

    reason = None
    if witness is None:
        reason = "no_respecting_tuples" if not respecting_tuples else "coverage_failure"

    return StructuralFeasibilityResult(
        feasible=witness is not None,
        instance_id=instance.instance_id,
        enforced_proposal_ids=[proposal.proposal_id for proposal in proposals],
        total_candidate_tuple_count=len(candidate_tuples),
        respecting_tuple_count=len(respecting_tuples),
        witness_tuples=witness_public,
        uncovered_atoms=uncovered,
        respecting_tuples=respecting_public,
        context_order=context_order,
        reason=reason,
    )
