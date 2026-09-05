from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from math import log2

from ..pica_bridge.ingest import PicaBundleResolved
from ..pica_bridge.models import PicaObservableRow
from ..schemas.event_package import EventPackageInstance
from .context_discovery import build_event_package_skeleton
from .models import (
    AcceptedContext,
    CandidateKey,
    ContextDiagnostics,
    DiscoverySummary,
    DiscoveredAtomicOutcome,
    DiscoveredContextFamily,
    PicaContextDiscoveryConfig,
    PicaContextSourceMetadata,
    RejectedCandidate,
)


DEFAULT_PICA_CONTEXT_DISCOVERY = PicaContextDiscoveryConfig(
    schema_version="pica-context-discovery.v1",
    bundle_artifact="experiments/contracts/pica/pilot/exp100_multiseed/pica-export-bundle.json",
    selected_run_ids=[],
    selected_point_ids=[],
    projection={
        "projection_mode": "payload_numeric_bins",
        "payload_key": "macro_gap",
        "bin_edges": [0.35, 0.5, 0.65],
    },
    grouping_key_fields=[
        "preparation_id",
        "protocol_id",
        "level_id",
        "resolution_id",
        "closure_id",
        "lens_id",
        "protocol_step_id",
    ],
    thresholds={
        "min_row_count": 2,
        "min_atom_count": 2,
        "min_atom_support_count": 1,
        "min_atom_support_fraction": 0.0,
        "min_coverage": 1.0,
        "max_batch_tv": 1.0,
        "batch_count": 2,
    },
    notes=["Default PICA-native multilayer discovery settings."],
)


@dataclass(slots=True)
class PicaContextDiscoveryArtifacts:
    family: DiscoveredContextFamily
    event_package_skeleton: EventPackageInstance | None


@dataclass(slots=True)
class _EvidenceRow:
    run_id: str
    point_id: str
    observable_ledger_id: str
    campaign_id: str
    row: PicaObservableRow
    projected_label: str


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


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
    labels: list[str], retained_labels: list[str]
) -> dict[str, float]:
    support = set(retained_labels)
    counts = Counter(label for label in labels if label in support)
    total = sum(counts.values())
    if total == 0:
        return {}
    return {label: counts.get(label, 0) / total for label in retained_labels}


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


def _project_row_label(
    row: PicaObservableRow, config: PicaContextDiscoveryConfig
) -> str | None:
    mode = config.projection.projection_mode
    if mode == "observation_label":
        return row.observation_label
    if mode == "macrostate_label":
        return row.macrostate_label
    if mode == "phase_label":
        return row.phase_label
    payload_key = config.projection.payload_key
    if payload_key is None:
        return None
    value = row.observation_payload.get(payload_key)
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    edges = config.projection.bin_edges
    for index, edge in enumerate(edges):
        if value < edge:
            lower = "neg_inf" if index == 0 else str(edges[index - 1]).replace(".", "_")
            upper = str(edge).replace(".", "_")
            return f"{payload_key}__{lower}_to_{upper}"
    return f"{payload_key}__ge_{str(edges[-1]).replace('.', '_')}"


def _context_id_from_key(key: CandidateKey) -> str:
    parts = [
        "ctx_pica",
        _slug(key.preparation_id),
        _slug(key.protocol_id),
        _slug(key.level_id or "unknown_level"),
        _slug(key.resolution_id or "unknown_resolution"),
        _slug(key.closure_id or "unknown_closure"),
        _slug(key.lens_id),
        _slug(key.protocol_step_id or f"step{key.step_index}"),
    ]
    return "_".join(part for part in parts if part)


def _outcome_id(label: str, *, index: int) -> str:
    return f"atom_{_slug(label)}_{index + 1}"


def _diagnostics(
    labels: list[str],
    retained_labels: list[str],
    *,
    batch_count: int,
) -> ContextDiagnostics:
    row_count = len(labels)
    support = Counter(labels)
    retained_count = sum(support[label] for label in retained_labels)
    coverage_fraction = retained_count / row_count if row_count else 0.0
    distributions = [
        _distribution_from_labels(batch, retained_labels)
        for batch in _split_batches(labels, batch_count)
    ]
    batch_tv_max = 0.0
    for index, left in enumerate(distributions):
        for right in distributions[index + 1 :]:
            batch_tv_max = max(batch_tv_max, _tv_distance(left, right))
    retained_distribution = _distribution_from_labels(labels, retained_labels)
    return ContextDiagnostics(
        trajectory_count=row_count,
        row_count=row_count,
        retained_atom_count=len(retained_labels),
        coverage_fraction=coverage_fraction,
        empirical_entropy=_entropy(retained_distribution)
        if retained_distribution
        else 0.0,
        batch_tv_max=batch_tv_max,
        persistence_flip_rate=None,
        support_by_retained_atom={label: support[label] for label in retained_labels},
    )


def _rejection_reasons(
    diagnostics: ContextDiagnostics,
    *,
    config: PicaContextDiscoveryConfig,
) -> list[str]:
    reasons: list[str] = []
    thresholds = config.thresholds
    row_count = diagnostics.row_count or diagnostics.trajectory_count
    if row_count < thresholds.min_row_count:
        reasons.append("insufficient_row_count")
    if diagnostics.retained_atom_count < thresholds.min_atom_count:
        reasons.append("trivial_context")
    if diagnostics.coverage_fraction < thresholds.min_coverage:
        reasons.append("low_coverage")
    if diagnostics.batch_tv_max > thresholds.max_batch_tv:
        reasons.append("unstable_batches")
    return reasons


def discover_pica_context_family(
    resolved: PicaBundleResolved,
    *,
    config: PicaContextDiscoveryConfig | None = None,
    family_id: str,
    bundle_artifact: str,
    created_at: str | None = None,
) -> PicaContextDiscoveryArtifacts:
    active = config or DEFAULT_PICA_CONTEXT_DISCOVERY
    evidence: dict[
        tuple[str, str, str, str, str, str, str, int],
        list[_EvidenceRow],
    ] = defaultdict(list)

    ledger_by_run = resolved.observable_ledgers_by_run()
    selected_run_ids = (
        set(active.selected_run_ids) if active.selected_run_ids else set(ledger_by_run)
    )
    selected_point_ids = set(active.selected_point_ids)

    for run_id in sorted(selected_run_ids):
        run = resolved.runs.get(run_id)
        ledger = ledger_by_run.get(run_id)
        if run is None or ledger is None:
            continue
        if selected_point_ids and run.point_id not in selected_point_ids:
            continue
        campaign_id = run.campaign_id
        rows = sorted(
            ledger.rows,
            key=lambda row: (
                row.step_index,
                row.protocol_step_id,
                row.closure_id,
                row.lens_id,
                row.trajectory_id,
            ),
        )
        for row in rows:
            projected = _project_row_label(row, active)
            if projected is None:
                continue
            key = (
                row.preparation_id,
                row.protocol_id,
                row.level_id,
                row.resolution_id,
                row.closure_id,
                row.lens_id,
                row.protocol_step_id,
                row.step_index,
            )
            evidence[key].append(
                _EvidenceRow(
                    run_id=run_id,
                    point_id=run.point_id,
                    observable_ledger_id=ledger.observable_ledger_id,
                    campaign_id=campaign_id,
                    row=row,
                    projected_label=projected,
                )
            )

    accepted_contexts: list[AcceptedContext] = []
    rejected_candidates: list[RejectedCandidate] = []
    rejection_reason_counts: Counter[str] = Counter()

    for key_values in sorted(evidence):
        rows = evidence[key_values]
        candidate_key = CandidateKey(
            preparation_id=key_values[0],
            protocol_id=key_values[1],
            level_id=key_values[2],
            resolution_id=key_values[3],
            closure_id=key_values[4],
            lens_id=key_values[5],
            protocol_step_id=key_values[6],
            step_index=key_values[7],
        )
        labels = [item.projected_label for item in rows]
        support_counts = Counter(labels)
        row_count = len(labels)
        retained_labels = [
            label
            for label, count in sorted(support_counts.items())
            if count >= active.thresholds.min_atom_support_count
            and (count / row_count) >= active.thresholds.min_atom_support_fraction
        ]
        diagnostics = _diagnostics(
            labels,
            retained_labels,
            batch_count=active.thresholds.batch_count,
        )
        source_metadata = PicaContextSourceMetadata(
            source_mode="pica_export_bundle",
            source_kind="pica_multilayer_group",
            export_bundle_id=resolved.export_bundle.export_bundle_id,
            campaign_id=rows[0].campaign_id,
            run_ids=sorted({item.run_id for item in rows}),
            observable_ledger_ids=sorted({item.observable_ledger_id for item in rows}),
            level_id=candidate_key.level_id or "",
            resolution_id=candidate_key.resolution_id or "",
            closure_id=candidate_key.closure_id or "",
            lens_id=candidate_key.lens_id,
            preparation_id=candidate_key.preparation_id,
            protocol_id=candidate_key.protocol_id,
            protocol_step_id=candidate_key.protocol_step_id or "",
            step_index=candidate_key.step_index,
            projection_mode=active.projection.projection_mode,
            projection_field=active.projection.payload_key
            or active.projection.projection_mode,
            projection_bin_edges=list(active.projection.bin_edges),
        )
        reasons = _rejection_reasons(diagnostics, config=active)
        if reasons:
            rejected_candidates.append(
                RejectedCandidate(
                    candidate_key=candidate_key,
                    rejection_reasons=reasons,
                    diagnostics=diagnostics,
                    source_metadata=source_metadata,
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
                        outcome_id=_outcome_id(label, index=index),
                        observation_label=label,
                        support_count=support_counts[label],
                        support_fraction=support_counts[label] / row_count,
                    )
                    for index, label in enumerate(retained_labels)
                ],
                diagnostics=diagnostics,
                source_metadata=source_metadata,
            )
        )

    family = DiscoveredContextFamily(
        family_format_version="discovered-context-family.v1",
        family_id=family_id,
        source_run_artifacts=[bundle_artifact],
        thresholds={
            "min_trajectory_count": active.thresholds.min_row_count,
            "min_atom_count": active.thresholds.min_atom_count,
            "min_atom_support_count": active.thresholds.min_atom_support_count,
            "min_atom_support_fraction": active.thresholds.min_atom_support_fraction,
            "min_coverage": active.thresholds.min_coverage,
            "max_batch_tv": active.thresholds.max_batch_tv,
            "max_persistence_flip_rate": None,
            "batch_count": active.thresholds.batch_count,
        },
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
        source_mode="pica_export_bundle",
        source_bundle_artifact=bundle_artifact,
        metadata={
            "observable_only": True,
            "projection_mode": active.projection.projection_mode,
            "projection_field": active.projection.payload_key
            or active.projection.projection_mode,
            "selected_run_count": len(selected_run_ids),
            "distinct_level_count": len(
                {
                    ctx.candidate_key.level_id
                    for ctx in accepted_contexts
                    if ctx.candidate_key.level_id is not None
                }
            ),
            "distinct_resolution_count": len(
                {
                    ctx.candidate_key.resolution_id
                    for ctx in accepted_contexts
                    if ctx.candidate_key.resolution_id is not None
                }
            ),
            "distinct_closure_count": len(
                {
                    ctx.candidate_key.closure_id
                    for ctx in accepted_contexts
                    if ctx.candidate_key.closure_id is not None
                }
            ),
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
    return PicaContextDiscoveryArtifacts(
        family=family,
        event_package_skeleton=skeleton,
    )
