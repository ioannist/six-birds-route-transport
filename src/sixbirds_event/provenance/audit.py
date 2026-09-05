from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys

from ..discovery.models import DiscoveredContextFamily, SharedEventCandidates
from ..discovery.models import DiscoveredEventFamily
from ..interventions.models import HiddenRecordIntervention
from ..pica_bridge.ingest import PicaBundleResolved, load_pica_export_bundle
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance
from ..schemas.result_note import ResultNote
from ..validation import load_model
from .models import (
    AdmissibilityClassification,
    ContextProvenanceEntry,
    EventProvenanceEntry,
    PackageProvenance,
    ProposalProvenanceEntry,
    ProvenanceAuditResult,
    ProvenanceSourceRef,
)


@dataclass(slots=True)
class ProvenanceAuditArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    result: ProvenanceAuditResult


def load_package_provenance(path: str | Path) -> PackageProvenance:
    model = load_model(path, kind="package-provenance")
    assert isinstance(model, PackageProvenance)
    return model


def _load_package(path: str | Path) -> EventPackageInstance:
    model = load_model(path, kind="event-package-instance")
    assert isinstance(model, EventPackageInstance)
    return model


def _load_family(path: Path) -> DiscoveredContextFamily:
    model = load_model(path, kind="discovered-context-family")
    assert isinstance(model, DiscoveredContextFamily)
    return model


def _load_candidates(path: Path) -> SharedEventCandidates:
    model = load_model(path, kind="shared-event-candidates")
    assert isinstance(model, SharedEventCandidates)
    return model


def _load_discovered_event_family(path: Path) -> DiscoveredEventFamily:
    model = load_model(path, kind="discovered-event-family")
    assert isinstance(model, DiscoveredEventFamily)
    return model


def _existing_refinement_flags(package: EventPackageInstance) -> list[str]:
    flags: list[str] = []
    for context in package.contexts:
        if _looks_like_refinement_id(context.context_id):
            flags.append(f"context_refinement_like_id:{context.context_id}")
    for event in package.events:
        if _looks_like_refinement_id(event.event_id):
            flags.append(f"event_refinement_like_id:{event.event_id}")
    for proposal in package.equality_proposals:
        if _looks_like_refinement_id(proposal.proposal_id):
            flags.append(f"proposal_refinement_like_id:{proposal.proposal_id}")
    return flags


_REFINEMENT_LIKE_ID_PATTERN = re.compile(r"__([A-Za-z][A-Za-z0-9]*)_([A-Za-z0-9-]+)$")


def _looks_like_refinement_id(value: str) -> bool:
    return (
        value.count("__") == 1 and _REFINEMENT_LIKE_ID_PATTERN.search(value) is not None
    )


def _outcome_exists(family: DiscoveredContextFamily, source_item_id: str) -> bool:
    if "::" not in source_item_id:
        return False
    context_id, outcome_id = source_item_id.split("::", maxsplit=1)
    for context in family.accepted_contexts:
        if context.context_id != context_id:
            continue
        return any(
            outcome.outcome_id == outcome_id for outcome in context.atomic_outcomes
        )
    return False


def _accepted_proposal_exists(
    candidates: SharedEventCandidates, source_item_id: str
) -> bool:
    return source_item_id in candidates.diagnostics_summary.accepted_proposal_ids


def _source_ref_resolves(
    *,
    source_ref: ProvenanceSourceRef,
    package_root: Path,
    entry_kind: str,
    pica_bundle_cache: dict[Path, PicaBundleResolved],
) -> bool:
    if source_ref.pica_ref is not None:
        return _pica_source_ref_resolves(
            source_ref=source_ref,
            package_root=package_root,
            pica_bundle_cache=pica_bundle_cache,
        )
    candidate_paths = [
        package_root / source_ref.artifact,
        Path.cwd() / source_ref.artifact,
    ]
    artifact_path = next(
        (path for path in candidate_paths if path.exists()), candidate_paths[0]
    )
    if not artifact_path.exists():
        return False
    if source_ref.source_item_id is None:
        return True
    model = load_model(artifact_path)
    if isinstance(model, EventPackageInstance):
        if entry_kind == "context":
            return any(
                context.context_id == source_ref.source_item_id
                for context in model.contexts
            )
        if entry_kind == "event":
            return any(
                event.event_id == source_ref.source_item_id for event in model.events
            )
        if entry_kind == "proposal":
            return any(
                proposal.proposal_id == source_ref.source_item_id
                for proposal in model.equality_proposals
            )
        return False
    if isinstance(model, DiscoveredContextFamily):
        if entry_kind == "context":
            return any(
                context.context_id == source_ref.source_item_id
                for context in model.accepted_contexts
            )
        if entry_kind == "event":
            return _outcome_exists(model, source_ref.source_item_id)
        return False
    if isinstance(model, DiscoveredEventFamily):
        if entry_kind == "context":
            return any(
                context.context_id == source_ref.source_item_id
                for context in model.contexts
            )
        if entry_kind == "event":
            return any(
                event.event_id == source_ref.source_item_id
                for context in model.contexts
                for event in context.events
            )
        return False
    if isinstance(model, SharedEventCandidates):
        if entry_kind == "proposal":
            return _accepted_proposal_exists(model, source_ref.source_item_id)
        return False
    if isinstance(model, HiddenRecordIntervention):
        if entry_kind == "context":
            return source_ref.source_item_id in model.selected_context_ids
        if entry_kind == "proposal":
            return any(
                assignment.proposal_id == source_ref.source_item_id
                for assignment in model.proposal_residue_assignments
            )
        return False
    return True


def _load_pica_bundle(
    artifact: str,
    *,
    package_root: Path,
    pica_bundle_cache: dict[Path, PicaBundleResolved],
) -> PicaBundleResolved | None:
    candidate_paths = [
        package_root / artifact,
        Path.cwd() / artifact,
    ]
    artifact_path = next(
        (path.resolve() for path in candidate_paths if path.exists()), None
    )
    if artifact_path is None:
        return None
    bundle = pica_bundle_cache.get(artifact_path)
    if bundle is None:
        bundle = load_pica_export_bundle(artifact_path, repo_root=package_root)
        pica_bundle_cache[artifact_path] = bundle
    return bundle


def _matches_pica_row_filters(
    *,
    row_filters: dict[str, str | int],
    rows: list[object],
) -> bool:
    if not row_filters:
        return bool(rows)
    for row in rows:
        if all(getattr(row, key, None) == value for key, value in row_filters.items()):
            return True
    return False


def _pica_source_ref_resolves(
    *,
    source_ref: ProvenanceSourceRef,
    package_root: Path,
    pica_bundle_cache: dict[Path, PicaBundleResolved],
) -> bool:
    assert source_ref.pica_ref is not None
    bundle = _load_pica_bundle(
        source_ref.artifact,
        package_root=package_root,
        pica_bundle_cache=pica_bundle_cache,
    )
    if bundle is None:
        return False
    pica_ref = source_ref.pica_ref
    if bundle.export_bundle.export_bundle_id != pica_ref.export_bundle_id:
        return False
    campaign = bundle.campaigns.get(pica_ref.campaign_id)
    run = bundle.runs.get(pica_ref.run_id)
    ledger = bundle.observable_ledgers.get(pica_ref.observable_ledger_id)
    if campaign is None or run is None or ledger is None:
        return False
    if run.campaign_id != campaign.campaign_id or ledger.run_id != run.run_id:
        return False
    if run.preparation_id != pica_ref.preparation_id:
        return False
    if run.protocol_id != pica_ref.protocol_id:
        return False
    if not any(
        step.protocol_step_id == pica_ref.protocol_step_id
        if pica_ref.protocol_step_id is not None
        else step.step_index == pica_ref.step_index
        for step in run.protocol_steps
    ):
        return False
    closure_catalog = bundle.closure_catalogs.get(run.closure_catalog_id)
    if closure_catalog is None:
        return False
    if not any(level.level_id == pica_ref.level_id for level in closure_catalog.levels):
        return False
    if not any(
        resolution.resolution_id == pica_ref.resolution_id
        for resolution in closure_catalog.resolutions
    ):
        return False
    if not any(
        closure.closure_id == pica_ref.closure_id
        for closure in closure_catalog.closures
    ):
        return False
    if not any(lens.lens_id == pica_ref.lens_id for lens in closure_catalog.lenses):
        return False
    if pica_ref.packaging_selection_ledger_id is not None:
        packaging_ledger = bundle.packaging_selection_ledgers.get(
            pica_ref.packaging_selection_ledger_id
        )
        if packaging_ledger is None or packaging_ledger.run_id != pica_ref.run_id:
            return False
        matching_packaging_rows = [
            row
            for row in packaging_ledger.rows
            if row.run_id == pica_ref.run_id
            and row.preparation_id == pica_ref.preparation_id
            and row.protocol_id == pica_ref.protocol_id
            and row.closure_id == pica_ref.closure_id
            and row.level_id == pica_ref.level_id
            and row.resolution_id == pica_ref.resolution_id
            and (row.lens_id or pica_ref.lens_id) == pica_ref.lens_id
            and (
                pica_ref.protocol_step_id is None
                or row.protocol_step_id == pica_ref.protocol_step_id
            )
            and (pica_ref.step_index is None or row.step_index == pica_ref.step_index)
            and (
                pica_ref.packaging_selection_row_id is None
                or row.selection_row_id == pica_ref.packaging_selection_row_id
            )
            and (
                pica_ref.packaging_operator_id is None
                or row.packaging_operator_id == pica_ref.packaging_operator_id
            )
            and (
                pica_ref.packaging_family_id is None
                or row.packaging_family_id == pica_ref.packaging_family_id
            )
            and (
                pica_ref.packaging_source is None
                or row.packaging_source == pica_ref.packaging_source
            )
        ]
        if not matching_packaging_rows:
            return False
    rows = bundle.filter_rows(
        run_id=pica_ref.run_id,
        preparation_id=pica_ref.preparation_id,
        protocol_id=pica_ref.protocol_id,
        closure_id=pica_ref.closure_id,
        lens_id=pica_ref.lens_id,
        level_id=pica_ref.level_id,
        resolution_id=pica_ref.resolution_id,
        protocol_step_id=pica_ref.protocol_step_id,
        step_index=pica_ref.step_index,
    )
    return _matches_pica_row_filters(
        row_filters=pica_ref.source_row_filters,
        rows=rows,
    )


def _count_unknown_row_filter_fields(
    entries: list[
        ContextProvenanceEntry | EventProvenanceEntry | ProposalProvenanceEntry
    ],
) -> int:
    count = 0
    for entry in entries:
        for source_ref in entry.source_refs:
            if source_ref.pica_ref is not None:
                count += len(source_ref.pica_ref.unknown_row_filter_fields)
    return count


def _unsupported_entry_count(
    entries: list[
        ContextProvenanceEntry | EventProvenanceEntry | ProposalProvenanceEntry
    ],
    *,
    package_root: Path,
    entry_kind: str,
    pica_bundle_cache: dict[Path, PicaBundleResolved],
) -> tuple[int, int, int]:
    unsupported_count = 0
    missing_source_ref_count = 0
    unresolved_source_ref_count = 0
    for entry in entries:
        if not entry.source_refs:
            missing_source_ref_count += 1
            unsupported_count += 1
            continue
        unresolved_entry = False
        for source_ref in entry.source_refs:
            if not _source_ref_resolves(
                source_ref=source_ref,
                package_root=package_root,
                entry_kind=entry_kind,
                pica_bundle_cache=pica_bundle_cache,
            ):
                unresolved_source_ref_count += 1
                unresolved_entry = True
        if unresolved_entry:
            unsupported_count += 1
    return unsupported_count, missing_source_ref_count, unresolved_source_ref_count


def _refinement_warning_count(
    entries: list[
        ContextProvenanceEntry | EventProvenanceEntry | ProposalProvenanceEntry
    ],
    *,
    entry_label: str,
) -> tuple[int, list[str]]:
    warning_count = 0
    flags: list[str] = []
    for entry in entries:
        is_refinement_kind = (
            "intervention" in entry.origin_kind or "split" in entry.origin_kind
        )
        has_refinement_like_id = _looks_like_refinement_id(
            getattr(
                entry,
                {
                    "context": "context_id",
                    "event": "event_id",
                    "proposal": "proposal_id",
                }[entry_label],
            )
        )
        if (is_refinement_kind or has_refinement_like_id) and entry.refinement is None:
            warning_count += 1
            flags.append(
                f"missing_refinement_metadata:{entry_label}:{getattr(entry, {'context': 'context_id', 'event': 'event_id', 'proposal': 'proposal_id'}[entry_label])}"
            )
    return warning_count, flags


def _classify(
    *,
    provenance_missing: bool,
    total_items: int,
    covered_items: int,
    unsupported_items: int,
    unresolved_source_ref_count: int,
    unknown_row_filter_field_count: int,
    refinement_warning_count: int,
) -> AdmissibilityClassification:
    if provenance_missing:
        return "unsupported"
    if (
        unsupported_items == 0
        and covered_items == total_items
        and unresolved_source_ref_count == 0
        and unknown_row_filter_field_count == 0
        and refinement_warning_count == 0
    ):
        return "admissible"
    if covered_items > 0:
        return "partially_supported"
    return "unsupported"


def _render_note(
    *,
    result: ProvenanceAuditResult,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Provenance Audit",
        "",
        "## Package under audit",
        f"- Package artifact: `{result.package_artifact}`",
        f"- Provenance artifact: `{result.provenance_artifact}`",
        "",
        "## Coverage summary",
        f"- Contexts covered/missing: `{result.context_covered_count}` / `{result.context_missing_count}`",
        f"- Events covered/missing: `{result.event_covered_count}` / `{result.event_missing_count}`",
        f"- Proposals covered/missing: `{result.proposal_covered_count}` / `{result.proposal_missing_count}`",
        "",
        "## Unresolved / unsupported items",
        f"- Unsupported contexts/events/proposals: `{result.unsupported_context_count}` / `{result.unsupported_event_count}` / `{result.unsupported_proposal_count}`",
        f"- Missing source-ref count: `{result.missing_source_ref_count}`",
        f"- Unresolved source-ref count: `{result.unresolved_source_ref_count}`",
        f"- Unknown row-filter field count: `{result.unknown_row_filter_field_count}`",
        f"- Refinement warning count: `{result.refinement_warning_count}`",
        f"- Suspicious refinement flags: `{result.suspicious_refinement_flags}`",
        "",
        "## Final admissibility classification",
        f"- Classification: `{result.admissibility_classification}`",
        "",
        "## Artifact references",
        f"- Summary: `{output_paths['summary']}`",
        f"- Result note: `{output_paths['result_note']}`",
        f"- Manifest: `{output_paths['manifest']}`",
    ]
    return "\n".join(lines) + "\n"


def audit_package_provenance(
    *,
    package_path: str | Path,
    provenance_path: str | Path | None = None,
    root: str | Path | None = None,
) -> ProvenanceAuditResult:
    effective_root = Path(root).resolve() if root is not None else Path.cwd()
    package_relpath = repo_relative_path(package_path, root=effective_root)
    provenance_relpath = (
        repo_relative_path(provenance_path, root=effective_root)
        if provenance_path is not None
        else None
    )
    package = _load_package(package_path)
    provenance = (
        load_package_provenance(provenance_path)
        if provenance_path is not None
        else None
    )
    provenance_missing = provenance is None

    package_context_ids = {context.context_id for context in package.contexts}
    package_event_ids = {event.event_id for event in package.events}
    package_proposal_ids = {
        proposal.proposal_id for proposal in package.equality_proposals
    }
    pica_bundle_cache: dict[Path, PicaBundleResolved] = {}

    if provenance is None:
        context_entries: list[ContextProvenanceEntry] = []
        event_entries: list[EventProvenanceEntry] = []
        proposal_entries: list[ProposalProvenanceEntry] = []
        context_covered_count = 0
        event_covered_count = 0
        proposal_covered_count = 0
        context_missing_count = len(package_context_ids)
        event_missing_count = len(package_event_ids)
        proposal_missing_count = len(package_proposal_ids)
        unsupported_context_count = len(package_context_ids)
        unsupported_event_count = len(package_event_ids)
        unsupported_proposal_count = len(package_proposal_ids)
        missing_source_ref_count = 0
        unresolved_source_ref_count = 0
        unknown_row_filter_field_count = 0
        refinement_warning_count = 0
        suspicious_flags = _existing_refinement_flags(package)
        notes = ["no_provenance_manifest_supplied"]
    else:
        context_entries = provenance.context_entries
        event_entries = provenance.event_entries
        proposal_entries = provenance.proposal_entries
        context_covered_ids = {
            entry.context_id
            for entry in context_entries
            if entry.context_id in package_context_ids
        }
        event_covered_ids = {
            entry.event_id
            for entry in event_entries
            if entry.event_id in package_event_ids
        }
        proposal_covered_ids = {
            entry.proposal_id
            for entry in proposal_entries
            if entry.proposal_id in package_proposal_ids
        }
        context_covered_count = len(context_covered_ids)
        event_covered_count = len(event_covered_ids)
        proposal_covered_count = len(proposal_covered_ids)
        context_missing_count = len(package_context_ids - context_covered_ids)
        event_missing_count = len(package_event_ids - event_covered_ids)
        proposal_missing_count = len(package_proposal_ids - proposal_covered_ids)
        unsupported_context_count, missing_source_ref_count_ctx, unresolved_ctx = (
            _unsupported_entry_count(
                context_entries,
                package_root=effective_root,
                entry_kind="context",
                pica_bundle_cache=pica_bundle_cache,
            )
        )
        unsupported_event_count, missing_source_ref_count_evt, unresolved_evt = (
            _unsupported_entry_count(
                event_entries,
                package_root=effective_root,
                entry_kind="event",
                pica_bundle_cache=pica_bundle_cache,
            )
        )
        unsupported_proposal_count, missing_source_ref_count_prop, unresolved_prop = (
            _unsupported_entry_count(
                proposal_entries,
                package_root=effective_root,
                entry_kind="proposal",
                pica_bundle_cache=pica_bundle_cache,
            )
        )
        missing_source_ref_count = (
            missing_source_ref_count_ctx
            + missing_source_ref_count_evt
            + missing_source_ref_count_prop
        )
        unresolved_source_ref_count = unresolved_ctx + unresolved_evt + unresolved_prop
        unknown_row_filter_field_count = (
            _count_unknown_row_filter_fields(context_entries)
            + _count_unknown_row_filter_fields(event_entries)
            + _count_unknown_row_filter_fields(proposal_entries)
        )
        refinement_warning_contexts, context_flags = _refinement_warning_count(
            context_entries, entry_label="context"
        )
        refinement_warning_events, event_flags = _refinement_warning_count(
            event_entries, entry_label="event"
        )
        refinement_warning_proposals, proposal_flags = _refinement_warning_count(
            proposal_entries, entry_label="proposal"
        )
        refinement_warning_count = (
            refinement_warning_contexts
            + refinement_warning_events
            + refinement_warning_proposals
        )
        suspicious_flags = (
            _existing_refinement_flags(package)
            + context_flags
            + event_flags
            + proposal_flags
        )
        notes = []

    total_items = (
        len(package_context_ids) + len(package_event_ids) + len(package_proposal_ids)
    )
    covered_items = context_covered_count + event_covered_count + proposal_covered_count
    unsupported_items = (
        unsupported_context_count
        + unsupported_event_count
        + unsupported_proposal_count
        + context_missing_count
        + event_missing_count
        + proposal_missing_count
    )
    classification = _classify(
        provenance_missing=provenance_missing,
        total_items=total_items,
        covered_items=covered_items,
        unsupported_items=unsupported_items,
        unresolved_source_ref_count=unresolved_source_ref_count,
        unknown_row_filter_field_count=unknown_row_filter_field_count,
        refinement_warning_count=refinement_warning_count,
    )
    return ProvenanceAuditResult(
        audit_format_version="provenance-audit-result.v1",
        package_artifact=package_relpath,
        provenance_artifact=provenance_relpath,
        package_id=package.instance_id,
        audit_status="completed",
        context_total_count=len(package_context_ids),
        context_covered_count=context_covered_count,
        context_missing_count=context_missing_count,
        event_total_count=len(package_event_ids),
        event_covered_count=event_covered_count,
        event_missing_count=event_missing_count,
        proposal_total_count=len(package_proposal_ids),
        proposal_covered_count=proposal_covered_count,
        proposal_missing_count=proposal_missing_count,
        unsupported_context_count=unsupported_context_count,
        unsupported_event_count=unsupported_event_count,
        unsupported_proposal_count=unsupported_proposal_count,
        missing_source_ref_count=missing_source_ref_count,
        unresolved_source_ref_count=unresolved_source_ref_count,
        unknown_row_filter_field_count=unknown_row_filter_field_count,
        refinement_warning_count=refinement_warning_count,
        suspicious_refinement_flags=suspicious_flags,
        admissibility_classification=classification,
        artifact_refs={},
        notes=notes,
    )


def write_provenance_audit_report(
    *,
    package_path: str | Path,
    provenance_path: str | Path | None = None,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> ProvenanceAuditArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    package_relpath = repo_relative_path(package_path, root=effective_root)
    provenance_relpath = (
        repo_relative_path(provenance_path, root=effective_root)
        if provenance_path is not None
        else None
    )
    package = _load_package(package_path)

    summary_path = run_dir / "provenance-audit-summary.json"
    note_path = run_dir / "provenance-audit-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    result = audit_package_provenance(
        package_path=package_path,
        provenance_path=provenance_path,
        root=effective_root,
    ).model_copy(update={"artifact_refs": output_paths})
    summary_path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(
        _render_note(result=result, output_paths=output_paths),
        encoding="utf-8",
    )
    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[package.instance_id],
        metrics={
            "context_missing_count": result.context_missing_count,
            "event_missing_count": result.event_missing_count,
            "proposal_missing_count": result.proposal_missing_count,
            "missing_source_ref_count": result.missing_source_ref_count,
            "unresolved_source_ref_count": result.unresolved_source_ref_count,
            "refinement_warning_count": result.refinement_warning_count,
        },
        interpretation=(
            f"Package provenance audit classified the package as {result.admissibility_classification}."
        ),
        caveats=[
            "Refinement-like ID warnings are auxiliary and do not replace explicit provenance checks.",
            "Missing or unresolved provenance is preserved explicitly rather than coerced into a pass.",
        ],
        artifact_refs=output_paths,
        metadata={"admissibility_classification": result.admissibility_classification},
    )
    result_note_path.write_text(
        json.dumps(result_note.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "provenance",
            package_relpath,
        ],
        seed=seed,
        input_artifacts={
            "package": package_relpath,
            **({"provenance": provenance_relpath} if provenance_relpath else {}),
        },
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "provenance_audit",
            "package_id": package.instance_id,
            "admissibility_classification": result.admissibility_classification,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return ProvenanceAuditArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        result=result,
    )
