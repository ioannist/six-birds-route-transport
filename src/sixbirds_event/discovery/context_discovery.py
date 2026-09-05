from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from math import log2

from ..schemas.event_package import EventPackageInstance
from ..substrates.run_trace import SubstrateRun
from .models import (
    AcceptedContext,
    CandidateKey,
    ContextDiagnostics,
    DiscoverySummary,
    DiscoveredAtomicOutcome,
    DiscoveredContextFamily,
    ExtractionThresholds,
    RejectedCandidate,
)


DEFAULT_THRESHOLDS = ExtractionThresholds(
    min_trajectory_count=10,
    min_atom_count=2,
    min_atom_support_count=2,
    min_atom_support_fraction=0.0,
    min_coverage=0.9,
    max_batch_tv=0.35,
    max_persistence_flip_rate=0.8,
    batch_count=2,
)


@dataclass(slots=True)
class _CandidateEvidence:
    labels: list[str]
    next_label_pairs: list[tuple[str, str]]


@dataclass(slots=True)
class DiscoveryArtifacts:
    family: DiscoveredContextFamily
    event_package_skeleton: EventPackageInstance | None


def _slug(value: str) -> str:
    token = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    compact = "_".join(part for part in token.split("_") if part)
    return compact or "value"


def _context_id_from_key(key: CandidateKey) -> str:
    parts = [
        "ctx",
        _slug(key.preparation_id),
        _slug(key.protocol_id),
    ]
    for value in [key.level_id, key.resolution_id, key.closure_id]:
        if value is not None:
            parts.append(_slug(value))
    parts.append(_slug(key.lens_id))
    if key.protocol_step_id is not None:
        parts.append(_slug(key.protocol_step_id))
    parts.append(f"step{key.step_index}")
    return "_".join(parts)


def _outcome_id_from_label(label: str, *, index: int) -> str:
    return f"atom_{_slug(label)}_{index + 1}"


def _split_batches(values: list[str], batch_count: int) -> list[list[str]]:
    if not values:
        return []
    size, remainder = divmod(len(values), batch_count)
    batches: list[list[str]] = []
    start = 0
    for batch_index in range(batch_count):
        stop = start + size + (1 if batch_index < remainder else 0)
        if stop > start:
            batches.append(values[start:stop])
        start = stop
    return batches


def _distribution_from_labels(
    labels: list[str], support: list[str]
) -> dict[str, float]:
    counts = Counter(label for label in labels if label in set(support))
    total = sum(counts.values())
    if total == 0:
        return {}
    return {label: counts.get(label, 0) / total for label in support}


def _tv_distance(left: dict[str, float], right: dict[str, float]) -> float:
    support = sorted(set(left) | set(right))
    return 0.5 * sum(
        abs(left.get(label, 0.0) - right.get(label, 0.0)) for label in support
    )


def _entropy(distribution: dict[str, float]) -> float:
    return -sum(
        probability * log2(probability)
        for probability in distribution.values()
        if probability > 0
    )


def _compute_diagnostics(
    *,
    labels: list[str],
    retained_labels: list[str],
    next_label_pairs: list[tuple[str, str]],
    thresholds: ExtractionThresholds,
) -> ContextDiagnostics:
    trajectory_count = len(labels)
    retained_distribution = _distribution_from_labels(labels, retained_labels)
    retained_count = sum(1 for label in labels if label in set(retained_labels))
    coverage_fraction = retained_count / trajectory_count if trajectory_count else 0.0
    batches = _split_batches(labels, thresholds.batch_count)
    batch_distributions = [
        _distribution_from_labels(batch, retained_labels) for batch in batches
    ]
    batch_tv_max = 0.0
    for index, left in enumerate(batch_distributions):
        for right in batch_distributions[index + 1 :]:
            batch_tv_max = max(batch_tv_max, _tv_distance(left, right))
    persistence_flip_rate = None
    if next_label_pairs:
        persistence_flip_rate = sum(
            1
            for current_label, next_label in next_label_pairs
            if current_label != next_label
        ) / len(next_label_pairs)
    return ContextDiagnostics(
        trajectory_count=trajectory_count,
        retained_atom_count=len(retained_labels),
        coverage_fraction=coverage_fraction,
        empirical_entropy=_entropy(retained_distribution)
        if retained_distribution
        else 0.0,
        batch_tv_max=batch_tv_max,
        persistence_flip_rate=persistence_flip_rate,
        row_count=trajectory_count,
        support_by_retained_atom={
            label: counts
            for label, counts in Counter(labels).items()
            if label in set(retained_labels)
        },
    )


def _rejection_reasons(
    diagnostics: ContextDiagnostics,
    *,
    thresholds: ExtractionThresholds,
) -> list[str]:
    reasons: list[str] = []
    if diagnostics.trajectory_count < thresholds.min_trajectory_count:
        reasons.append("insufficient_trajectory_count")
    if diagnostics.retained_atom_count < thresholds.min_atom_count:
        reasons.append("trivial_context")
    if diagnostics.coverage_fraction < thresholds.min_coverage:
        reasons.append("low_coverage")
    if diagnostics.batch_tv_max > thresholds.max_batch_tv:
        reasons.append("unstable_batches")
    if (
        diagnostics.persistence_flip_rate is not None
        and thresholds.max_persistence_flip_rate is not None
        and diagnostics.persistence_flip_rate > thresholds.max_persistence_flip_rate
    ):
        reasons.append("high_persistence_flip_rate")
    return reasons


def build_event_package_skeleton(
    family: DiscoveredContextFamily,
    *,
    created_at: str,
) -> EventPackageInstance | None:
    if not family.accepted_contexts:
        return None
    contexts: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    for context in family.accepted_contexts:
        contexts.append(
            {
                "context_id": context.context_id,
                "label": "/".join(
                    [
                        context.candidate_key.preparation_id,
                        context.candidate_key.protocol_id,
                        *(
                            [
                                context.candidate_key.level_id,
                                context.candidate_key.resolution_id,
                                context.candidate_key.closure_id,
                            ]
                            if context.candidate_key.level_id is not None
                            and context.candidate_key.resolution_id is not None
                            and context.candidate_key.closure_id is not None
                            else []
                        ),
                        context.candidate_key.lens_id,
                        context.candidate_key.protocol_step_id
                        or f"step{context.candidate_key.step_index}",
                    ]
                ),
                "atoms": [
                    {"atom_id": outcome.outcome_id, "label": outcome.observation_label}
                    for outcome in context.atomic_outcomes
                ],
            }
        )
        for outcome in context.atomic_outcomes:
            events.append(
                {
                    "event_id": f"event_{context.context_id}_{outcome.outcome_id}",
                    "context_id": context.context_id,
                    "atom_ids": [outcome.outcome_id],
                    "label": outcome.observation_label,
                }
            )
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": f"inst_{family.family_id}_skeleton",
            "contexts": contexts,
            "events": events,
            "equality_proposals": [],
            "weights": {},
            "metadata": {
                "family_id": family.family_id,
                "source_kind": "discovered_context_family",
            },
            "audit": {"created_at": created_at},
        }
    )


def discover_context_family(
    runs: list[SubstrateRun],
    *,
    source_run_artifacts: list[str],
    family_id: str,
    thresholds: ExtractionThresholds | None = None,
    created_at: str | None = None,
) -> DiscoveryArtifacts:
    active_thresholds = thresholds or DEFAULT_THRESHOLDS
    evidence_by_key: dict[tuple[str, str, str, int], _CandidateEvidence] = defaultdict(
        lambda: _CandidateEvidence(labels=[], next_label_pairs=[])
    )

    for run in runs:
        for trajectory in run.trajectories:
            ordered_steps = sorted(trajectory.steps, key=lambda step: step.step_index)
            for step in ordered_steps:
                next_step = (
                    ordered_steps[step.step_index + 1]
                    if step.step_index + 1 < len(ordered_steps)
                    else None
                )
                for lens_id in sorted(step.observations):
                    key = (
                        trajectory.preparation_id,
                        trajectory.protocol_id,
                        lens_id,
                        step.step_index,
                    )
                    evidence = evidence_by_key[key]
                    label = step.observations[lens_id]
                    evidence.labels.append(label)
                    if next_step is not None and lens_id in next_step.observations:
                        evidence.next_label_pairs.append(
                            (label, next_step.observations[lens_id])
                        )

    accepted_contexts: list[AcceptedContext] = []
    rejected_candidates: list[RejectedCandidate] = []
    rejection_reason_counts: Counter[str] = Counter()

    for key_values in sorted(evidence_by_key):
        candidate_key = CandidateKey(
            preparation_id=key_values[0],
            protocol_id=key_values[1],
            lens_id=key_values[2],
            step_index=key_values[3],
        )
        evidence = evidence_by_key[key_values]
        support_counts = Counter(evidence.labels)
        trajectory_count = len(evidence.labels)
        retained_labels = [
            label
            for label, count in sorted(support_counts.items())
            if count >= active_thresholds.min_atom_support_count
            and (count / trajectory_count)
            >= active_thresholds.min_atom_support_fraction
        ]
        diagnostics = _compute_diagnostics(
            labels=evidence.labels,
            retained_labels=retained_labels,
            next_label_pairs=evidence.next_label_pairs,
            thresholds=active_thresholds,
        )
        reasons = _rejection_reasons(diagnostics, thresholds=active_thresholds)
        if reasons:
            rejected_candidates.append(
                RejectedCandidate(
                    candidate_key=candidate_key,
                    rejection_reasons=reasons,
                    diagnostics=diagnostics,
                )
            )
            rejection_reason_counts.update(reasons)
            continue
        accepted_contexts.append(
            AcceptedContext(
                context_id=_context_id_from_key(candidate_key),
                candidate_key=candidate_key,
                atomic_outcomes=[
                    DiscoveredAtomicOutcome(
                        outcome_id=_outcome_id_from_label(label, index=index),
                        observation_label=label,
                        support_count=support_counts[label],
                        support_fraction=support_counts[label] / trajectory_count,
                    )
                    for index, label in enumerate(retained_labels)
                ],
                diagnostics=diagnostics,
            )
        )

    family = DiscoveredContextFamily(
        family_format_version="discovered-context-family.v1",
        family_id=family_id,
        source_run_artifacts=source_run_artifacts,
        thresholds=active_thresholds,
        accepted_contexts=accepted_contexts,
        rejected_candidates=rejected_candidates,
        diagnostics_summary=DiscoverySummary(
            candidate_count=len(accepted_contexts) + len(rejected_candidates),
            accepted_context_count=len(accepted_contexts),
            rejected_candidate_count=len(rejected_candidates),
            rejection_reason_counts=dict(sorted(rejection_reason_counts.items())),
            accepted_context_ids=[context.context_id for context in accepted_contexts],
        ),
        event_package_skeleton_artifact=None,
        metadata={
            "source_run_count": len(runs),
            "observable_only": True,
        },
    )
    skeleton = build_event_package_skeleton(
        family,
        created_at=created_at
        or datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    )
    return DiscoveryArtifacts(
        family=family,
        event_package_skeleton=skeleton,
    )
