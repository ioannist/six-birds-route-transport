from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import comb

from .models import (
    AcceptedContext,
    DiscoveredAtomicOutcome,
    DiscoveredEventContext,
    DiscoveredEventEntry,
    DiscoveredEventGenerationThresholds,
    EventAlgebraCoverage,
    EventAlgebraCoverageContext,
)


def _singleton_event_id(context_id: str, outcome_id: str) -> str:
    return f"event_{context_id}_{outcome_id}"


def _coarse_event_id(context_id: str, atom_ids: list[str]) -> str:
    return f"event_{context_id}__union__{'__'.join(atom_ids)}"


def _empty_event_id(context_id: str) -> str:
    return f"event_{context_id}__empty"


def _full_event_id(context_id: str) -> str:
    return f"event_{context_id}__full"


def event_id_for_atoms(
    *,
    context_id: str,
    atom_ids: list[str],
    all_atom_ids: list[str],
    event_lookup: dict[tuple[str, tuple[str, ...]], str] | None = None,
) -> str:
    lookup = event_lookup or {}
    atom_key = tuple(sorted(atom_ids))
    if not atom_ids:
        return lookup.get((context_id, atom_key), _empty_event_id(context_id))
    if atom_key == tuple(sorted(all_atom_ids)):
        return lookup.get((context_id, atom_key), _full_event_id(context_id))
    if len(atom_ids) == 1:
        return lookup.get(
            (context_id, atom_key), _singleton_event_id(context_id, atom_ids[0])
        )
    return lookup.get((context_id, atom_key), _coarse_event_id(context_id, atom_ids))


def event_kind_for_atoms(atom_ids: list[str], all_atom_ids: list[str]) -> str:
    if not atom_ids:
        return "empty"
    if len(atom_ids) == 1:
        return "singleton"
    if tuple(sorted(atom_ids)) == tuple(sorted(all_atom_ids)):
        return "full"
    return "proper_coarse"


def _support_from_outcomes(
    outcomes: list[DiscoveredAtomicOutcome],
    atom_ids: list[str],
) -> tuple[int, float]:
    selected = [outcome for outcome in outcomes if outcome.outcome_id in set(atom_ids)]
    return (
        sum(outcome.support_count for outcome in selected),
        sum(outcome.support_fraction for outcome in selected),
    )


def _effective_mode(
    *,
    atom_count: int,
    thresholds: DiscoveredEventGenerationThresholds,
) -> str:
    if thresholds.event_algebra_mode == "full_powerset":
        return "full_powerset"
    if thresholds.event_algebra_mode == "conservative_truncation":
        return "conservative_truncation"
    if thresholds.event_algebra_mode == "auto":
        if atom_count <= thresholds.max_full_powerset_atom_count:
            return "full_powerset"
        return "conservative_truncation"
    if thresholds.event_basis_mode == "singleton_plus_small_unions":
        return "legacy_small_unions"
    return "legacy_singleton_only"


def _match_eligible(
    event_kind: str,
    *,
    thresholds: DiscoveredEventGenerationThresholds,
) -> bool:
    if event_kind == "empty":
        return thresholds.match_empty_for_inference
    if event_kind == "full":
        return thresholds.match_full_for_inference
    return event_kind in {"singleton", "proper_coarse"}


def generate_context_event_context(
    *,
    context: AcceptedContext,
    thresholds: DiscoveredEventGenerationThresholds,
    event_lookup: dict[tuple[str, tuple[str, ...]], str] | None = None,
) -> DiscoveredEventContext:
    all_atom_ids = sorted(outcome.outcome_id for outcome in context.atomic_outcomes)
    mode_used = _effective_mode(atom_count=len(all_atom_ids), thresholds=thresholds)
    expected_full_event_count = 2 ** len(all_atom_ids)
    rejection_reason_counts: Counter[str] = Counter()
    events: list[DiscoveredEventEntry] = []

    def add_event(
        atom_ids: list[str],
        *,
        accepted: bool = True,
        rejection_reasons: list[str] | None = None,
    ) -> None:
        event_id = event_id_for_atoms(
            context_id=context.context_id,
            atom_ids=atom_ids,
            all_atom_ids=all_atom_ids,
            event_lookup=event_lookup,
        )
        support_count, support_fraction = _support_from_outcomes(
            context.atomic_outcomes,
            atom_ids,
        )
        if not atom_ids:
            support_count = 0
            support_fraction = 0.0
        event_kind = event_kind_for_atoms(atom_ids, all_atom_ids)
        events.append(
            DiscoveredEventEntry(
                event_id=event_id,
                context_id=context.context_id,
                event_kind=event_kind,
                retained_atom_ids=atom_ids,
                event_size=len(atom_ids),
                conditioning_support_count=support_count,
                conditioning_support_fraction=support_fraction,
                accepted=accepted,
                match_eligible=accepted
                and _match_eligible(event_kind, thresholds=thresholds),
                rejection_reasons=rejection_reasons or [],
            )
        )

    if mode_used == "full_powerset":
        for size in range(0, len(all_atom_ids) + 1):
            for atom_subset in combinations(all_atom_ids, size):
                add_event(list(atom_subset))
        complete = True
        truncation_reason = None
    elif mode_used == "conservative_truncation":
        if thresholds.include_empty_and_full_in_truncation:
            add_event([])
        for size in range(1, len(all_atom_ids) + 1):
            if size == len(all_atom_ids):
                if thresholds.include_empty_and_full_in_truncation:
                    add_event(list(all_atom_ids))
                continue
            if size == 1:
                for atom_subset in combinations(all_atom_ids, size):
                    add_event(list(atom_subset))
                continue
            if size > thresholds.max_union_size:
                rejection_reason_counts["too_large"] += comb(len(all_atom_ids), size)
                continue
            for atom_subset in combinations(all_atom_ids, size):
                add_event(list(atom_subset))
        complete = False
        truncation_reason = (
            "atom_count_exceeds_max_full_powerset_atom_count"
            if thresholds.event_algebra_mode == "auto"
            else "conservative_truncation_requested"
        )
    elif mode_used == "legacy_small_unions":
        for atom_id in all_atom_ids:
            add_event([atom_id])
        max_size = min(thresholds.max_union_size, len(all_atom_ids) - 1)
        for size in range(2, len(all_atom_ids) + 1):
            if size >= len(all_atom_ids):
                rejection_reason_counts["trivial_full_event"] += comb(
                    len(all_atom_ids), size
                )
                continue
            if size > max_size:
                rejection_reason_counts["too_large"] += comb(len(all_atom_ids), size)
                continue
            for atom_subset in combinations(all_atom_ids, size):
                atom_list = list(atom_subset)
                support_count, support_fraction = _support_from_outcomes(
                    context.atomic_outcomes,
                    atom_list,
                )
                accepted = (
                    support_count >= thresholds.min_event_support_count
                    and support_fraction >= thresholds.min_event_support_fraction
                )
                reasons = [] if accepted else ["insufficient_support"]
                if not accepted:
                    rejection_reason_counts["insufficient_support"] += 1
                add_event(atom_list, accepted=accepted, rejection_reasons=reasons)
        complete = False
        truncation_reason = "legacy_small_union_basis"
    else:
        for atom_id in all_atom_ids:
            add_event([atom_id])
        complete = False
        truncation_reason = "legacy_singleton_basis"

    generated_event_count = len(events)
    return DiscoveredEventContext(
        context_id=context.context_id,
        events=events,
        atom_count=len(all_atom_ids),
        expected_full_event_count=expected_full_event_count,
        generated_event_count=generated_event_count,
        match_eligible_event_count=sum(
            1 for event in events if event.accepted and event.match_eligible
        ),
        event_algebra_complete=complete,
        generation_mode_used=mode_used,
        coverage_fraction=(
            generated_event_count / expected_full_event_count
            if expected_full_event_count
            else 1.0
        ),
        truncation_reason=truncation_reason,
        rejection_reason_counts=dict(sorted(rejection_reason_counts.items())),
    )


def build_event_algebra_coverage(
    *,
    source_discovered_context_family_artifact: str,
    thresholds: DiscoveredEventGenerationThresholds,
    contexts: list[DiscoveredEventContext],
) -> EventAlgebraCoverage:
    return EventAlgebraCoverage(
        coverage_format_version="event-algebra-coverage.v1",
        source_discovered_context_family_artifact=source_discovered_context_family_artifact,
        event_algebra_mode=thresholds.event_algebra_mode or thresholds.event_basis_mode,
        max_full_powerset_atom_count=thresholds.max_full_powerset_atom_count,
        contexts=[
            EventAlgebraCoverageContext(
                context_id=context.context_id,
                atom_count=context.atom_count or 0,
                expected_full_event_count=context.expected_full_event_count or 0,
                generated_event_count=context.generated_event_count
                or len(context.events),
                event_algebra_complete=bool(context.event_algebra_complete),
                coverage_fraction=context.coverage_fraction or 0.0,
                generation_mode_used=context.generation_mode_used or "unknown",
                truncation_reason=context.truncation_reason,
                flags=(
                    []
                    if context.event_algebra_complete
                    else ["incomplete_event_algebra"]
                ),
            )
            for context in contexts
        ],
        notes=[
            "Full powerset is required for committed small PICA contexts; truncation remains available only as an explicitly incomplete fallback."
        ],
    )
