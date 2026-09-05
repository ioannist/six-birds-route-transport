from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from scipy.optimize import linprog

from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import ObservationTrace
from ..statistics.trace_marginals import (
    ContextMarginal,
    aggregate_empirical_marginals,
    extract_empirical_marginals,
)
from .structural_exact import (
    PublicTuple,
    _build_event_atom_sets,
    _build_context_atoms,
    _build_event_lookup,
    _enforced_proposals,
    _enumerate_candidate_tuples,
    _filter_respecting_tuples,
    _tuple_as_mapping,
)


@dataclass(slots=True)
class ContextResidual:
    context_id: str
    total_variation: float
    l1: float


@dataclass(slots=True)
class FittedTupleProbability:
    tuple: PublicTuple
    probability: float


@dataclass(slots=True)
class StatisticalDeficitResult:
    instance_id: str
    trace_ids: list[str]
    mode: str
    solved: bool
    reason: str | None
    gpd_stat: float | None
    objective_kind: str
    enforced_proposal_ids: list[str]
    candidate_tuple_count: int
    allowed_tuple_count: int
    total_candidate_tuple_count: int
    respecting_tuple_count: int
    total_residual: float | None
    context_residuals: dict[str, ContextResidual]
    fitted_tuple_distribution: list[FittedTupleProbability]
    fitted_context_marginals: dict[str, dict[str, float]]
    observed_context_marginals: dict[str, dict[str, float]]


def _context_atom_order(instance: EventPackageInstance) -> dict[str, list[str]]:
    return _build_context_atoms(instance)


def _fit_distribution(
    instance: EventPackageInstance,
    observed: dict[str, ContextMarginal],
    *,
    include_soft: bool,
    trace_ids: list[str] | None = None,
) -> StatisticalDeficitResult:
    context_order = [context.context_id for context in instance.contexts]
    atoms_by_context = _context_atom_order(instance)
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
    if not respecting_tuples:
        return StatisticalDeficitResult(
            instance_id=instance.instance_id,
            trace_ids=trace_ids or [],
            mode="all_proposals" if include_soft else "hard_only",
            solved=False,
            reason="no_respecting_tuples",
            gpd_stat=None,
            objective_kind="sum_total_variation",
            enforced_proposal_ids=[proposal.proposal_id for proposal in proposals],
            candidate_tuple_count=len(candidate_tuples),
            allowed_tuple_count=0,
            total_candidate_tuple_count=len(candidate_tuples),
            respecting_tuple_count=0,
            total_residual=None,
            context_residuals={},
            fitted_tuple_distribution=[],
            fitted_context_marginals={},
            observed_context_marginals={
                context_id: marginal.probabilities
                for context_id, marginal in observed.items()
            },
        )

    residual_index: list[tuple[str, str]] = []
    for context_id in context_order:
        for atom_id in atoms_by_context[context_id]:
            residual_index.append((context_id, atom_id))

    n_tuples = len(respecting_tuples)
    n_residuals = len(residual_index)
    objective = [0.0] * n_tuples + [0.5] * n_residuals
    bounds = [(0.0, None)] * (n_tuples + n_residuals)

    a_eq = [[1.0] * n_tuples + [0.0] * n_residuals]
    b_eq = [1.0]

    a_ub: list[list[float]] = []
    b_ub: list[float] = []

    for residual_pos, (context_id, atom_id) in enumerate(residual_index):
        fitted_coeffs = [
            1.0 if tuple_values[context_order.index(context_id)] == atom_id else 0.0
            for tuple_values in respecting_tuples
        ]
        residual_column = [0.0] * n_residuals
        residual_column[residual_pos] = -1.0
        observed_value = observed[context_id].probabilities[atom_id]
        a_ub.append(fitted_coeffs + residual_column)
        b_ub.append(observed_value)
        a_ub.append([-value for value in fitted_coeffs] + residual_column)
        b_ub.append(-observed_value)

    result = linprog(
        c=objective,
        A_ub=a_ub,
        b_ub=b_ub,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    if not result.success or result.x is None:
        return StatisticalDeficitResult(
            instance_id=instance.instance_id,
            trace_ids=trace_ids or [],
            mode="all_proposals" if include_soft else "hard_only",
            solved=False,
            reason="optimization_failed",
            gpd_stat=None,
            objective_kind="sum_total_variation",
            enforced_proposal_ids=[proposal.proposal_id for proposal in proposals],
            candidate_tuple_count=len(candidate_tuples),
            allowed_tuple_count=len(respecting_tuples),
            total_candidate_tuple_count=len(candidate_tuples),
            respecting_tuple_count=len(respecting_tuples),
            total_residual=None,
            context_residuals={},
            fitted_tuple_distribution=[],
            fitted_context_marginals={},
            observed_context_marginals={
                context_id: marginal.probabilities
                for context_id, marginal in observed.items()
            },
        )

    x_values = result.x[:n_tuples]
    fitted_distribution = [
        FittedTupleProbability(
            tuple=_tuple_as_mapping(tuple_values, context_order),
            probability=float(probability),
        )
        for tuple_values, probability in zip(respecting_tuples, x_values, strict=True)
        if probability > 1e-9
    ]

    fitted_context_marginals: dict[str, dict[str, float]] = {}
    context_residuals: dict[str, ContextResidual] = {}
    for context_id in context_order:
        marginal: dict[str, float] = {}
        for atom_id in atoms_by_context[context_id]:
            probability = sum(
                x
                for tuple_values, x in zip(respecting_tuples, x_values, strict=True)
                if tuple_values[context_order.index(context_id)] == atom_id
            )
            marginal[atom_id] = float(probability)
        fitted_context_marginals[context_id] = marginal
        l1 = sum(
            abs(marginal[atom_id] - observed[context_id].probabilities[atom_id])
            for atom_id in atoms_by_context[context_id]
        )
        context_residuals[context_id] = ContextResidual(
            context_id=context_id,
            total_variation=0.5 * l1,
            l1=l1,
        )

    gpd_stat = sum(residual.total_variation for residual in context_residuals.values())
    if not isfinite(gpd_stat):
        raise ValueError("computed gpd_stat must be finite")

    return StatisticalDeficitResult(
        instance_id=instance.instance_id,
        trace_ids=trace_ids or [],
        mode="all_proposals" if include_soft else "hard_only",
        solved=True,
        reason=None,
        gpd_stat=float(gpd_stat),
        objective_kind="sum_total_variation",
        enforced_proposal_ids=[proposal.proposal_id for proposal in proposals],
        candidate_tuple_count=len(candidate_tuples),
        allowed_tuple_count=len(respecting_tuples),
        total_candidate_tuple_count=len(candidate_tuples),
        respecting_tuple_count=len(respecting_tuples),
        total_residual=float(gpd_stat),
        context_residuals=context_residuals,
        fitted_tuple_distribution=fitted_distribution,
        fitted_context_marginals=fitted_context_marginals,
        observed_context_marginals={
            context_id: marginal.probabilities
            for context_id, marginal in observed.items()
        },
    )


def solve_statistical_deficit(
    instance: EventPackageInstance,
    empirical_marginals: dict[str, ContextMarginal],
    *,
    include_soft: bool = False,
    trace_ids: list[str] | None = None,
) -> StatisticalDeficitResult:
    expected_contexts = {context.context_id for context in instance.contexts}
    if set(empirical_marginals) != expected_contexts:
        missing = sorted(expected_contexts - set(empirical_marginals))
        extra = sorted(set(empirical_marginals) - expected_contexts)
        fragments: list[str] = []
        if missing:
            fragments.append(f"missing contexts: {', '.join(missing)}")
        if extra:
            fragments.append(f"unknown contexts: {', '.join(extra)}")
        raise ValueError("; ".join(fragments))
    return _fit_distribution(
        instance,
        empirical_marginals,
        include_soft=include_soft,
        trace_ids=trace_ids,
    )


def solve_statistical_deficit_from_trace(
    instance: EventPackageInstance,
    trace: ObservationTrace,
    *,
    include_soft: bool = False,
    tolerance: float = 1e-9,
) -> StatisticalDeficitResult:
    marginals = extract_empirical_marginals(
        trace,
        instance,
        tolerance=tolerance,
    )
    return solve_statistical_deficit(
        instance,
        marginals,
        include_soft=include_soft,
        trace_ids=[trace.trace_id],
    )


def solve_statistical_global_packaging(
    instance: EventPackageInstance,
    traces: list[ObservationTrace],
    *,
    include_soft: bool = False,
    tolerance: float = 1e-9,
) -> StatisticalDeficitResult:
    bundle = aggregate_empirical_marginals(
        traces,
        instance,
        tolerance=tolerance,
    )
    return solve_statistical_deficit(
        instance,
        bundle.context_marginals,
        include_soft=include_soft,
        trace_ids=bundle.trace_ids,
    )
