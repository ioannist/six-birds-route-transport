from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Callable

from ..pica_bridge.ingest import load_pica_export_bundle
from ..schemas.event_package import EventPackageInstance
from ..substrates.engine import load_substrate_run
from ..substrates.run_trace import SubstrateRun
from ..validation import load_model
from .coarse_events import discover_event_family
from .context_discovery import build_event_package_skeleton
from .models import (
    AcceptedContext,
    CandidateKey,
    DiscoveredEventFamily,
    DiscoveredEventGenerationThresholds,
    DiscoveredContextFamily,
    ProbeIndistinguishabilitySignatureEntry,
    ProbeIndistinguishabilitySignatureTable,
    ProbeSignatureComparison,
    SharedEventCandidateRow,
    SharedEventCandidates,
    SharedEventInferenceSummary,
    SharedEventInferenceThresholds,
)
from .structural_signatures import (
    ComputedProbeSignature,
    classify_probe_image_event_kind,
)


DEFAULT_SHARED_EVENT_INFERENCE_THRESHOLDS = SharedEventInferenceThresholds(
    inference_mode="structural_primary",
    min_common_probes=1,
    min_conditioning_count=3,
    min_probe_atom_support_count=1,
    max_mean_tv=0.15,
    exact_tolerance=1e-6,
    proposal_constraint_kind="soft",
)


@dataclass(slots=True)
class PackageBuildArtifacts:
    discovered_event_family: DiscoveredEventFamily
    signatures: ProbeIndistinguishabilitySignatureTable
    candidates: SharedEventCandidates
    event_package: EventPackageInstance


@dataclass(slots=True)
class _ObservedTrajectory:
    support_key: str
    preparation_id: str
    protocol_id: str
    labels_by_context_id: dict[str, str]


@dataclass(slots=True)
class _CandidateEvent:
    context: AcceptedContext
    event_id: str
    event_kind: str
    atom_ids: list[str]
    observation_labels: set[str]
    event_size: int
    outcome_key: str


@dataclass(slots=True)
class SharedEventInferenceArtifacts:
    signatures: ProbeIndistinguishabilitySignatureTable
    candidates: SharedEventCandidates


def load_discovered_context_family(path: str | Path) -> DiscoveredContextFamily:
    model = load_model(path, kind="discovered-context-family")
    assert isinstance(model, DiscoveredContextFamily)
    return model


def load_discovered_event_package_skeleton(path: str | Path) -> EventPackageInstance:
    model = load_model(path, kind="event-package-instance")
    assert isinstance(model, EventPackageInstance)
    return model


def load_substrate_run_files(paths: list[str | Path]) -> list[SubstrateRun]:
    return [load_substrate_run(path) for path in paths]


def _proposal_id(left_event_id: str, right_event_id: str) -> str:
    return f"proposal_{left_event_id}__{right_event_id}"


def _weight_key(proposal_id: str) -> str:
    return f"weight_{proposal_id}"


def _outcome_key(atom_ids: list[str]) -> str:
    return "__".join(atom_ids)


def _context_lookup(
    contexts: list[AcceptedContext],
) -> dict[str, AcceptedContext]:
    return {context.context_id: context for context in contexts}


def _event_to_candidate_events(
    contexts: list[AcceptedContext],
    discovered_event_family: DiscoveredEventFamily,
) -> dict[str, list[_CandidateEvent]]:
    context_lookup = _context_lookup(contexts)
    by_context: dict[str, list[_CandidateEvent]] = {}
    for context_payload in discovered_event_family.contexts:
        context = context_lookup[context_payload.context_id]
        label_by_atom_id = {
            outcome.outcome_id: outcome.observation_label
            for outcome in context.atomic_outcomes
        }
        by_context[context.context_id] = [
            _CandidateEvent(
                context=context,
                event_id=event.event_id,
                event_kind=event.event_kind,
                atom_ids=event.retained_atom_ids,
                observation_labels={
                    label_by_atom_id[atom_id] for atom_id in event.retained_atom_ids
                }
                if event.retained_atom_ids
                else set(),
                event_size=event.event_size,
                outcome_key=(
                    _outcome_key(event.retained_atom_ids)
                    if event.retained_atom_ids
                    else "empty"
                ),
            )
            for event in context_payload.events
            if event.accepted and event.match_eligible
        ]
    return by_context


def _build_observed_trajectories_from_runs(
    runs: list[SubstrateRun],
    *,
    contexts: list[AcceptedContext],
) -> list[_ObservedTrajectory]:
    context_keys = {
        context.context_id: (
            context.candidate_key.lens_id,
            context.candidate_key.step_index,
        )
        for context in contexts
    }
    trajectories: list[_ObservedTrajectory] = []
    for run in runs:
        for trajectory in run.trajectories:
            raw_labels = {
                (lens_id, step.step_index): label
                for step in trajectory.steps
                for lens_id, label in step.observations.items()
            }
            trajectories.append(
                _ObservedTrajectory(
                    support_key=f"{run.run_id}:{trajectory.trajectory_id}",
                    preparation_id=trajectory.preparation_id,
                    protocol_id=trajectory.protocol_id,
                    labels_by_context_id={
                        context_id: raw_labels[key]
                        for context_id, key in context_keys.items()
                        if key in raw_labels
                    },
                )
            )
    return trajectories


def _project_pica_row_label(row, source_metadata) -> str | None:
    mode = source_metadata.projection_mode
    if mode == "observation_label":
        return row.observation_label
    if mode == "macrostate_label":
        return row.macrostate_label
    if mode == "phase_label":
        return row.phase_label
    payload_key = source_metadata.projection_field
    value = row.observation_payload.get(payload_key)
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    edges = list(source_metadata.projection_bin_edges)
    for index, edge in enumerate(edges):
        if value < edge:
            lower = "neg_inf" if index == 0 else str(edges[index - 1]).replace(".", "_")
            upper = str(edge).replace(".", "_")
            return f"{payload_key}__{lower}_to_{upper}"
    return f"{payload_key}__ge_{str(edges[-1]).replace('.', '_')}"


def _build_observed_trajectories_from_pica_bundle(
    family: DiscoveredContextFamily,
    *,
    bundle_path: str | Path,
) -> list[_ObservedTrajectory]:
    resolved = load_pica_export_bundle(
        bundle_path,
        repo_root=_infer_bundle_repo_root(bundle_path),
    )
    labels_by_run_and_trajectory: dict[
        tuple[str, str, str, str],
        dict[str, str],
    ] = {}
    for ledger in resolved.observable_ledgers.values():
        for row in ledger.rows:
            for context in family.accepted_contexts:
                source_metadata = context.source_metadata
                if source_metadata is None:
                    continue
                if row.preparation_id != source_metadata.preparation_id:
                    continue
                if row.protocol_id != source_metadata.protocol_id:
                    continue
                if row.level_id != source_metadata.level_id:
                    continue
                if row.resolution_id != source_metadata.resolution_id:
                    continue
                if row.closure_id != source_metadata.closure_id:
                    continue
                if row.lens_id != source_metadata.lens_id:
                    continue
                if row.step_index != source_metadata.step_index:
                    continue
                if source_metadata.protocol_step_id != row.protocol_step_id:
                    continue
                projected = _project_pica_row_label(row, source_metadata)
                if projected is None:
                    continue
                labels = labels_by_run_and_trajectory.setdefault(
                    (
                        ledger.run_id,
                        row.trajectory_id,
                        row.preparation_id,
                        row.protocol_id,
                    ),
                    {},
                )
                labels[context.context_id] = projected
    return [
        _ObservedTrajectory(
            support_key=f"{run_id}:{trajectory_id}",
            preparation_id=preparation_id,
            protocol_id=protocol_id,
            labels_by_context_id=labels,
        )
        for run_id, trajectory_id, preparation_id, protocol_id, labels in [
            (*key, labels) for key, labels in labels_by_run_and_trajectory.items()
        ]
    ]


def _infer_bundle_repo_root(bundle_path: str | Path) -> Path | None:
    candidate = Path(bundle_path)
    if not candidate.is_absolute():
        return None
    parts = candidate.parts
    if "results" not in parts:
        return None
    index = parts.index("results")
    return Path(*parts[:index]) if index > 0 else Path(parts[0])


def _bundle_artifact_ref(
    *,
    family: DiscoveredContextFamily,
    pica_bundle_path: str | Path | None,
) -> str | None:
    if family.source_mode != "pica_export_bundle":
        return None
    if pica_bundle_path is not None and not Path(pica_bundle_path).is_absolute():
        return str(pica_bundle_path)
    return family.source_bundle_artifact


def _matching_trajectories(
    trajectories: list[_ObservedTrajectory],
    *,
    key: CandidateKey,
) -> list[_ObservedTrajectory]:
    return [
        trajectory
        for trajectory in trajectories
        if trajectory.preparation_id == key.preparation_id
        and trajectory.protocol_id == key.protocol_id
    ]


def _distribution_from_counts(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    if total == 0:
        return {}
    return {
        outcome_id: count / total
        for outcome_id, count in sorted(counts.items())
        if count > 0
    }


def _tv_distance(left: dict[str, float], right: dict[str, float]) -> float:
    support = sorted(set(left) | set(right))
    value = 0.5 * sum(
        abs(left.get(outcome_id, 0.0) - right.get(outcome_id, 0.0))
        for outcome_id in support
    )
    return max(0.0, min(1.0, value))


def _clip_probability(value: float) -> float:
    return max(0.0, min(1.0, value))


def _probe_signature(
    *,
    event: _CandidateEvent,
    probe_context: AcceptedContext,
    trajectories: list[_ObservedTrajectory],
    min_conditioning_count: int,
    min_probe_atom_support_count: int,
) -> ComputedProbeSignature:
    probe_label_to_outcome = {
        outcome.observation_label: outcome.outcome_id
        for outcome in probe_context.atomic_outcomes
    }
    support_counts: Counter[str] = Counter()
    conditioning_count = 0
    for trajectory in trajectories:
        if (
            trajectory.labels_by_context_id.get(event.context.context_id)
            not in event.observation_labels
        ):
            continue
        probe_label = trajectory.labels_by_context_id.get(probe_context.context_id)
        if probe_label is None:
            continue
        outcome_id = probe_label_to_outcome.get(probe_label)
        if outcome_id is None:
            continue
        conditioning_count += 1
        support_counts[outcome_id] += 1
    support_mapping = {
        outcome.outcome_id: support_counts.get(outcome.outcome_id, 0)
        for outcome in probe_context.atomic_outcomes
    }
    probe_image_atom_ids = [
        outcome.outcome_id
        for outcome in probe_context.atomic_outcomes
        if support_mapping.get(outcome.outcome_id, 0) >= min_probe_atom_support_count
    ]
    distribution = _distribution_from_counts(support_mapping)
    return ComputedProbeSignature(
        entry=ProbeIndistinguishabilitySignatureEntry(
            source_event_id=event.event_id,
            source_context_id=event.context.context_id,
            probe_context_id=probe_context.context_id,
            probe_image_atom_ids=probe_image_atom_ids,
            probe_image_event_kind=classify_probe_image_event_kind(
                probe_image_atom_ids,
                probe_context=probe_context,
            ),
            conditioning_support_count=conditioning_count,
            support_by_retained_probe_atom=support_mapping,
            structural_valid=conditioning_count >= min_conditioning_count,
            probe_distribution=distribution,
        ),
        support_counts=support_mapping,
        distribution=distribution,
    )


def _event_support_keys(
    *,
    event: _CandidateEvent,
    trajectories: list[_ObservedTrajectory],
) -> set[str]:
    return {
        trajectory.support_key
        for trajectory in trajectories
        if trajectory.labels_by_context_id.get(event.context.context_id)
        in event.observation_labels
    }


def _support_relation_kind(
    *,
    left_event: _CandidateEvent,
    right_event: _CandidateEvent,
    left_support_keys: set[str],
    right_support_keys: set[str],
) -> str:
    if left_support_keys == right_support_keys:
        if left_event.observation_labels == right_event.observation_labels:
            return "identical_support"
        return "same_support_relabeling"
    shared_support = left_support_keys & right_support_keys
    if not shared_support:
        return "disjoint_support_match"
    if (
        left_support_keys <= right_support_keys
        or right_support_keys <= left_support_keys
    ):
        return "cross_support_match"
    return "crosscutting_match"


def _score_candidate_pair(
    *,
    left_event: _CandidateEvent,
    right_event: _CandidateEvent,
    probe_contexts: list[AcceptedContext],
    trajectories: list[_ObservedTrajectory],
    thresholds: SharedEventInferenceThresholds,
    signature_cache: dict[tuple[str, str], ComputedProbeSignature],
    support_cache: dict[str, set[str]],
) -> SharedEventCandidateRow:
    if left_event.event_id not in support_cache:
        support_cache[left_event.event_id] = _event_support_keys(
            event=left_event,
            trajectories=trajectories,
        )
    left_support_keys = support_cache[left_event.event_id]
    if right_event.event_id not in support_cache:
        support_cache[right_event.event_id] = _event_support_keys(
            event=right_event,
            trajectories=trajectories,
        )
    right_support_keys = support_cache[right_event.event_id]
    shared_support_keys = left_support_keys & right_support_keys
    comparisons: list[ProbeSignatureComparison] = []
    for probe_context in probe_contexts:
        left_cache_key = (left_event.event_id, probe_context.context_id)
        if left_cache_key not in signature_cache:
            signature_cache[left_cache_key] = _probe_signature(
                event=left_event,
                probe_context=probe_context,
                trajectories=trajectories,
                min_conditioning_count=thresholds.min_conditioning_count,
                min_probe_atom_support_count=thresholds.min_probe_atom_support_count,
            )
        left_signature = signature_cache[left_cache_key]
        right_cache_key = (right_event.event_id, probe_context.context_id)
        if right_cache_key not in signature_cache:
            signature_cache[right_cache_key] = _probe_signature(
                event=right_event,
                probe_context=probe_context,
                trajectories=trajectories,
                min_conditioning_count=thresholds.min_conditioning_count,
                min_probe_atom_support_count=thresholds.min_probe_atom_support_count,
            )
        right_signature = signature_cache[right_cache_key]
        if (
            not left_signature.entry.structural_valid
            or not right_signature.entry.structural_valid
        ):
            continue
        structural_mismatch_reasons: list[str] = []
        structural_match = (
            left_signature.entry.probe_image_atom_ids
            == right_signature.entry.probe_image_atom_ids
        )
        if not structural_match:
            structural_mismatch_reasons.append(
                f"probe_image_mismatch:{probe_context.context_id}"
            )
        comparisons.append(
            ProbeSignatureComparison(
                probe_context_id=probe_context.context_id,
                left_conditioning_count=left_signature.entry.conditioning_support_count,
                right_conditioning_count=right_signature.entry.conditioning_support_count,
                left_support_counts=left_signature.support_counts,
                right_support_counts=right_signature.support_counts,
                left_probe_image_atom_ids=left_signature.entry.probe_image_atom_ids,
                right_probe_image_atom_ids=right_signature.entry.probe_image_atom_ids,
                left_probe_image_event_kind=left_signature.entry.probe_image_event_kind,
                right_probe_image_event_kind=right_signature.entry.probe_image_event_kind,
                structural_valid=True,
                structural_match=structural_match,
                structural_mismatch_reasons=structural_mismatch_reasons,
                left_distribution=left_signature.distribution,
                right_distribution=right_signature.distribution,
                tv_distance=_tv_distance(
                    left_signature.distribution,
                    right_signature.distribution,
                ),
            )
        )

    common_probe_ids = [comparison.probe_context_id for comparison in comparisons]
    insufficient_data = len(comparisons) < thresholds.min_common_probes
    structural_mismatch_reasons = [
        reason
        for comparison in comparisons
        for reason in comparison.structural_mismatch_reasons
    ]
    structural_match = (not insufficient_data) and all(
        comparison.structural_match for comparison in comparisons
    )
    mean_tv = None
    max_tv = None
    approx_score = None
    confidence = None
    exact_consistent = None
    rejection_reasons: list[str] = []
    if insufficient_data:
        rejection_reasons.append("insufficient_common_probes")
    else:
        mean_tv = sum(comparison.tv_distance for comparison in comparisons) / len(
            comparisons
        )
        max_tv = max(comparison.tv_distance for comparison in comparisons)
        approx_score = mean_tv
        confidence = _clip_probability(1.0 - mean_tv)
        exact_consistent = all(
            comparison.tv_distance <= thresholds.exact_tolerance
            for comparison in comparisons
        )
        if not structural_match:
            rejection_reasons.extend(structural_mismatch_reasons)

    return SharedEventCandidateRow(
        candidate_id=f"cand_{left_event.event_id}__{right_event.event_id}",
        left_context_id=left_event.context.context_id,
        right_context_id=right_event.context.context_id,
        left_event_id=left_event.event_id,
        right_event_id=right_event.event_id,
        left_outcome_id=left_event.outcome_key,
        right_outcome_id=right_event.outcome_key,
        left_event_kind=left_event.event_kind,
        right_event_kind=right_event.event_kind,
        left_event_atom_ids=left_event.atom_ids,
        right_event_atom_ids=right_event.atom_ids,
        left_event_size=left_event.event_size,
        right_event_size=right_event.event_size,
        left_is_proper_coarse=left_event.event_kind == "proper_coarse",
        right_is_proper_coarse=right_event.event_kind == "proper_coarse",
        common_probe_ids=common_probe_ids,
        common_probe_count=len(common_probe_ids),
        probe_comparisons=comparisons,
        structural_match=structural_match,
        structural_mismatch_count=len(structural_mismatch_reasons),
        structural_mismatch_reasons=structural_mismatch_reasons,
        mean_tv=mean_tv,
        max_tv=max_tv,
        approx_score=approx_score,
        confidence=confidence,
        exact_consistent=exact_consistent,
        left_support_count=len(left_support_keys),
        right_support_count=len(right_support_keys),
        shared_support_count=len(shared_support_keys),
        support_relation_kind=_support_relation_kind(
            left_event=left_event,
            right_event=right_event,
            left_support_keys=left_support_keys,
            right_support_keys=right_support_keys,
        ),
        insufficient_data=insufficient_data,
        accepted=False,
        rejection_reasons=rejection_reasons,
        proposed_proposal_id=None,
    )


def _candidate_rank(
    row: SharedEventCandidateRow,
    *,
    inference_mode: str,
) -> tuple[int, float, int, int, str]:
    secondary_score = row.mean_tv if row.mean_tv is not None else 1.0
    structural_priority = 0 if row.structural_match else 1
    if inference_mode == "legacy_statistical_primary":
        structural_priority = 0 if row.exact_consistent else 1
    return (
        structural_priority,
        secondary_score,
        -row.common_probe_count,
        max(row.left_event_size, row.right_event_size),
        row.candidate_id,
    )


def _apply_mutual_best_policy(
    rows: list[SharedEventCandidateRow],
    *,
    thresholds: SharedEventInferenceThresholds,
) -> list[SharedEventCandidateRow]:
    eligible_rows = [row for row in rows if not row.insufficient_data]
    best_by_left: dict[str, SharedEventCandidateRow] = {}
    best_by_right: dict[str, SharedEventCandidateRow] = {}

    for row in sorted(
        eligible_rows,
        key=lambda item: _candidate_rank(
            item,
            inference_mode=thresholds.inference_mode,
        ),
    ):
        current = best_by_left.get(row.left_event_id)
        if current is None or _candidate_rank(
            row,
            inference_mode=thresholds.inference_mode,
        ) < _candidate_rank(
            current,
            inference_mode=thresholds.inference_mode,
        ):
            best_by_left[row.left_event_id] = row
        current = best_by_right.get(row.right_event_id)
        if current is None or _candidate_rank(
            row,
            inference_mode=thresholds.inference_mode,
        ) < _candidate_rank(
            current,
            inference_mode=thresholds.inference_mode,
        ):
            best_by_right[row.right_event_id] = row

    updated_rows: list[SharedEventCandidateRow] = []
    for row in rows:
        if row.insufficient_data:
            updated_rows.append(row)
            continue
        rejection_reasons: list[str] = []
        accepted = False
        proposal_id = None
        if thresholds.inference_mode == "structural_primary":
            if not row.structural_match:
                rejection_reasons.extend(row.structural_mismatch_reasons)
                if not rejection_reasons:
                    rejection_reasons.append("structural_mismatch")
        elif row.approx_score is not None and row.approx_score > thresholds.max_mean_tv:
            rejection_reasons.append("above_max_mean_tv")
        if (
            best_by_left.get(row.left_event_id) is not row
            or best_by_right.get(row.right_event_id) is not row
        ):
            rejection_reasons.append("not_mutual_best")
        if not rejection_reasons:
            accepted = True
            proposal_id = _proposal_id(row.left_event_id, row.right_event_id)
        updated_rows.append(
            row.model_copy(
                update={
                    "accepted": accepted,
                    "rejection_reasons": rejection_reasons,
                    "proposed_proposal_id": proposal_id,
                }
            )
        )
    return updated_rows


def run_shared_event_inference(
    family: DiscoveredContextFamily,
    runs: list[SubstrateRun] | None,
    *,
    pica_bundle_path: str | Path | None = None,
    thresholds: SharedEventInferenceThresholds | None = None,
    discovered_event_family: DiscoveredEventFamily | None = None,
    event_basis_mode: str = "singleton_only",
    max_union_size: int = 2,
    min_event_support_count: int = 3,
    min_event_support_fraction: float = 0.1,
    inference_id: str,
    source_discovered_context_family_artifact: str,
    source_run_artifacts: list[str],
    skeleton: EventPackageInstance | None = None,
    source_pair_filter: Callable[[AcceptedContext, AcceptedContext], bool]
    | None = None,
) -> SharedEventInferenceArtifacts:
    active_thresholds = thresholds or DEFAULT_SHARED_EVENT_INFERENCE_THRESHOLDS
    contexts = sorted(
        family.accepted_contexts,
        key=lambda context: (
            context.candidate_key.preparation_id,
            context.candidate_key.protocol_id,
            context.candidate_key.lens_id,
            context.candidate_key.step_index,
            context.context_id,
        ),
    )
    if family.source_mode == "pica_export_bundle":
        bundle_path = pica_bundle_path or family.source_bundle_artifact
        if bundle_path is None:
            raise ValueError(
                "pica_bundle_path is required when building candidates from a pica_export_bundle family"
            )
        trajectories = _build_observed_trajectories_from_pica_bundle(
            family,
            bundle_path=bundle_path,
        )
    else:
        if runs is None:
            raise ValueError(
                "runs are required when building candidates from a substrate_runs family"
            )
        trajectories = _build_observed_trajectories_from_runs(runs, contexts=contexts)
    active_event_family = discovered_event_family or discover_event_family(
        family,
        runs or [],
        thresholds=DiscoveredEventGenerationThresholds(
            event_basis_mode=event_basis_mode,
            max_union_size=max_union_size,
            min_event_support_count=min_event_support_count,
            min_event_support_fraction=min_event_support_fraction,
        ),
        event_family_id=f"events_{inference_id}",
        source_discovered_context_family_artifact=source_discovered_context_family_artifact,
        source_run_artifacts=source_run_artifacts,
        skeleton=skeleton,
    )
    events_by_context = _event_to_candidate_events(contexts, active_event_family)
    signature_cache: dict[tuple[str, str], ComputedProbeSignature] = {}
    support_cache: dict[str, set[str]] = {}
    rows: list[SharedEventCandidateRow] = []

    for left_context, right_context in combinations(contexts, 2):
        left_key = left_context.candidate_key
        right_key = right_context.candidate_key
        left_projection_id = (
            left_context.source_metadata.projection_id
            if left_context.source_metadata is not None
            else None
        )
        right_projection_id = (
            right_context.source_metadata.projection_id
            if right_context.source_metadata is not None
            else None
        )
        if source_pair_filter is not None and not source_pair_filter(
            left_context, right_context
        ):
            continue
        if left_key.preparation_id != right_key.preparation_id:
            continue
        if left_key.protocol_id != right_key.protocol_id:
            continue
        if (
            left_key.lens_id == right_key.lens_id
            and left_key.closure_id == right_key.closure_id
            and left_key.resolution_id == right_key.resolution_id
            and left_key.protocol_step_id == right_key.protocol_step_id
            and left_key.step_index == right_key.step_index
            and left_projection_id == right_projection_id
        ):
            continue

        probe_contexts = [
            context
            for context in contexts
            if context.context_id
            not in {left_context.context_id, right_context.context_id}
            and context.candidate_key.preparation_id == left_key.preparation_id
            and context.candidate_key.protocol_id == left_key.protocol_id
        ]
        candidate_trajectories = _matching_trajectories(trajectories, key=left_key)
        pair_rows = [
            _score_candidate_pair(
                left_event=left_event,
                right_event=right_event,
                probe_contexts=probe_contexts,
                trajectories=candidate_trajectories,
                thresholds=active_thresholds,
                signature_cache=signature_cache,
                support_cache=support_cache,
            )
            for left_event in events_by_context[left_context.context_id]
            for right_event in events_by_context[right_context.context_id]
        ]
        rows.extend(_apply_mutual_best_policy(pair_rows, thresholds=active_thresholds))

    accepted_proposal_ids = [
        row.proposed_proposal_id for row in rows if row.proposed_proposal_id is not None
    ]
    signatures = ProbeIndistinguishabilitySignatureTable(
        signatures_format_version="probe-indistinguishability-signature.v1",
        inference_id=inference_id,
        source_discovered_context_family_artifact=source_discovered_context_family_artifact,
        source_run_artifacts=source_run_artifacts,
        source_mode=family.source_mode,
        source_bundle_artifact=_bundle_artifact_ref(
            family=family,
            pica_bundle_path=pica_bundle_path,
        ),
        thresholds=active_thresholds,
        signature_rows=[
            signature.entry
            for _, signature in sorted(
                signature_cache.items(),
                key=lambda item: item[0],
            )
        ],
        metadata={"observable_only": True},
    )
    candidates = SharedEventCandidates(
        candidates_format_version="shared-event-candidates.v1",
        inference_id=inference_id,
        inference_mode=active_thresholds.inference_mode,
        source_discovered_context_family_artifact=source_discovered_context_family_artifact,
        source_run_artifacts=source_run_artifacts,
        source_mode=family.source_mode,
        source_bundle_artifact=_bundle_artifact_ref(
            family=family,
            pica_bundle_path=pica_bundle_path,
        ),
        thresholds=active_thresholds,
        candidate_rows=rows,
        diagnostics_summary=SharedEventInferenceSummary(
            total_candidate_pair_count=len(rows),
            structurally_valid_candidate_pair_count=sum(
                1 for row in rows if row.structural_match
            ),
            accepted_candidate_pair_count=sum(1 for row in rows if row.accepted),
            insufficient_data_candidate_pair_count=sum(
                1 for row in rows if row.insufficient_data
            ),
            rejected_candidate_pair_count=sum(
                1 for row in rows if not row.accepted and not row.insufficient_data
            ),
            accepted_proposal_ids=accepted_proposal_ids,
        ),
        metadata={"observable_only": True},
    )
    return SharedEventInferenceArtifacts(signatures=signatures, candidates=candidates)


def infer_shared_event_candidates(
    family: DiscoveredContextFamily,
    runs: list[SubstrateRun] | None,
    *,
    pica_bundle_path: str | Path | None = None,
    thresholds: SharedEventInferenceThresholds | None = None,
    discovered_event_family: DiscoveredEventFamily | None = None,
    event_basis_mode: str = "singleton_only",
    max_union_size: int = 2,
    min_event_support_count: int = 3,
    min_event_support_fraction: float = 0.1,
    inference_id: str,
    source_discovered_context_family_artifact: str,
    source_run_artifacts: list[str],
    skeleton: EventPackageInstance | None = None,
) -> SharedEventCandidates:
    return run_shared_event_inference(
        family,
        runs,
        pica_bundle_path=pica_bundle_path,
        thresholds=thresholds,
        discovered_event_family=discovered_event_family,
        event_basis_mode=event_basis_mode,
        max_union_size=max_union_size,
        min_event_support_count=min_event_support_count,
        min_event_support_fraction=min_event_support_fraction,
        inference_id=inference_id,
        source_discovered_context_family_artifact=source_discovered_context_family_artifact,
        source_run_artifacts=source_run_artifacts,
        skeleton=skeleton,
    ).candidates


def _weight_from_score(approx_score: float, *, weight_floor: float) -> float:
    return max(weight_floor, 1.0 - approx_score)


def build_event_package_from_candidates(
    family: DiscoveredContextFamily,
    candidates: SharedEventCandidates,
    *,
    discovered_event_family: DiscoveredEventFamily | None = None,
    skeleton: EventPackageInstance | None = None,
    created_at: str | None = None,
    proposal_constraint_kind: str | None = None,
    weight_floor: float = 0.1,
) -> EventPackageInstance:
    base_skeleton = skeleton or build_event_package_skeleton(
        family,
        created_at=created_at
        or datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    )
    if base_skeleton is None:
        raise ValueError("cannot build an event package without accepted contexts")

    events = [event.model_dump(mode="json") for event in base_skeleton.events]
    existing_event_ids = {event["event_id"] for event in events}
    if discovered_event_family is not None:
        context_lookup = {
            context.context_id: context for context in family.accepted_contexts
        }
        for context_payload in discovered_event_family.contexts:
            context = context_lookup[context_payload.context_id]
            label_by_atom_id = {
                outcome.outcome_id: outcome.observation_label
                for outcome in context.atomic_outcomes
            }
            for event in context_payload.events:
                if not event.accepted or event.event_id in existing_event_ids:
                    continue
                if event.event_kind == "empty":
                    label = "empty"
                elif event.event_kind == "full":
                    label = "full"
                else:
                    label = " | ".join(
                        label_by_atom_id[atom_id] for atom_id in event.retained_atom_ids
                    )
                events.append(
                    {
                        "event_id": event.event_id,
                        "context_id": event.context_id,
                        "atom_ids": event.retained_atom_ids,
                        "label": label,
                    }
                )
                existing_event_ids.add(event.event_id)

    effective_kind = (
        proposal_constraint_kind or candidates.thresholds.proposal_constraint_kind
    )
    accepted_rows = [row for row in candidates.candidate_rows if row.accepted]
    weights: dict[str, float] = dict(base_skeleton.weights)
    proposals: list[dict[str, object]] = []
    for row in accepted_rows:
        assert row.proposed_proposal_id is not None
        weight_key = (
            _weight_key(row.proposed_proposal_id) if effective_kind == "soft" else None
        )
        if effective_kind == "soft":
            assert row.approx_score is not None
            weights[weight_key] = _weight_from_score(
                row.approx_score,
                weight_floor=weight_floor,
            )
        proposals.append(
            {
                "proposal_id": row.proposed_proposal_id,
                "left_event_id": row.left_event_id,
                "right_event_id": row.right_event_id,
                "constraint_kind": effective_kind,
                "weight_key": weight_key,
                "notes": (
                    "inferred_shared_event "
                    f"inference_mode={candidates.inference_mode} "
                    f"structural_match={row.structural_match} "
                    f"mean_tv={row.mean_tv} "
                    f"common_probe_count={row.common_probe_count}"
                ),
            }
        )

    accepted_coarse_event_count = (
        0
        if discovered_event_family is None
        else discovered_event_family.diagnostics_summary.accepted_coarse_event_count
    )
    accepted_coarse_proposal_count = sum(
        1
        for row in accepted_rows
        if row.left_is_proper_coarse or row.right_is_proper_coarse
    )
    return EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": f"inst_{family.family_id}_built",
            "contexts": [
                context.model_dump(mode="json") for context in base_skeleton.contexts
            ],
            "events": events,
            "equality_proposals": proposals,
            "weights": weights,
            "notes": "Built from discovered contexts and observable shared-event inference.",
            "metadata": {
                **base_skeleton.metadata,
                "family_id": family.family_id,
                "source_kind": "inferred_event_package",
                "proposal_constraint_kind": effective_kind,
                "observable_only": True,
                "event_basis_mode": (
                    discovered_event_family.thresholds.event_basis_mode
                    if discovered_event_family is not None
                    else "singleton_only"
                ),
                "event_algebra_mode": (
                    discovered_event_family.thresholds.event_algebra_mode
                    if discovered_event_family is not None
                    else None
                ),
                "event_algebra_complete": (
                    all(
                        bool(context.event_algebra_complete)
                        for context in discovered_event_family.contexts
                    )
                    if discovered_event_family is not None
                    else None
                ),
                "accepted_singleton_event_count": (
                    discovered_event_family.diagnostics_summary.accepted_singleton_event_count
                    if discovered_event_family is not None
                    else len(base_skeleton.events)
                ),
                "accepted_coarse_event_count": accepted_coarse_event_count,
                "generated_empty_event_count": (
                    discovered_event_family.diagnostics_summary.generated_empty_event_count
                    if discovered_event_family is not None
                    else 0
                ),
                "generated_full_event_count": (
                    discovered_event_family.diagnostics_summary.generated_full_event_count
                    if discovered_event_family is not None
                    else 0
                ),
                "match_eligible_event_count": (
                    discovered_event_family.diagnostics_summary.match_eligible_event_count
                    if discovered_event_family is not None
                    else len(base_skeleton.events)
                ),
                "accepted_shared_event_proposal_count": len(accepted_rows),
                "accepted_coarse_event_proposal_count": accepted_coarse_proposal_count,
            },
            "audit": {
                "created_at": created_at
                or datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            },
        }
    )


def build_package_from_discovery(
    family: DiscoveredContextFamily,
    runs: list[SubstrateRun] | None,
    *,
    pica_bundle_path: str | Path | None = None,
    thresholds: SharedEventInferenceThresholds | None = None,
    event_thresholds: DiscoveredEventGenerationThresholds | None = None,
    inference_id: str,
    source_discovered_context_family_artifact: str,
    source_run_artifacts: list[str],
    skeleton: EventPackageInstance | None = None,
    created_at: str | None = None,
    source_pair_filter: Callable[[AcceptedContext, AcceptedContext], bool]
    | None = None,
) -> PackageBuildArtifacts:
    active_event_thresholds = (
        event_thresholds
        if event_thresholds is not None
        else DiscoveredEventGenerationThresholds()
    )
    discovered_event_family = discover_event_family(
        family,
        runs or [],
        thresholds=active_event_thresholds,
        event_family_id=f"events_{inference_id}",
        source_discovered_context_family_artifact=source_discovered_context_family_artifact,
        source_run_artifacts=source_run_artifacts,
        skeleton=skeleton,
    )
    inference_artifacts = run_shared_event_inference(
        family,
        runs,
        pica_bundle_path=pica_bundle_path,
        thresholds=thresholds,
        discovered_event_family=discovered_event_family,
        inference_id=inference_id,
        source_discovered_context_family_artifact=source_discovered_context_family_artifact,
        source_run_artifacts=source_run_artifacts,
        skeleton=skeleton,
        source_pair_filter=source_pair_filter,
    )
    candidates = inference_artifacts.candidates
    event_package = build_event_package_from_candidates(
        family,
        candidates,
        discovered_event_family=discovered_event_family,
        skeleton=skeleton,
        created_at=created_at,
    )
    return PackageBuildArtifacts(
        discovered_event_family=discovered_event_family,
        signatures=inference_artifacts.signatures,
        candidates=candidates,
        event_package=event_package,
    )
