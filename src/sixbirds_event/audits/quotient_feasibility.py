from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
import json
from pathlib import Path
import sys
from typing import Iterable

from ..discovery.models import (
    AcceptedContext,
    DiscoveredContextFamily,
    SharedEventCandidateRow,
    SharedEventCandidates,
)
from ..discovery.shared_event_inference import _project_pica_row_label
from ..pica_bridge.ingest import load_pica_export_bundle
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    get_repo_root,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance
from ..schemas.result_note import ResultNote
from ..validation import load_model
from .models import (
    QuotientClassEntry,
    QuotientClassLedger,
    QuotientEvaluationResult,
    QuotientFeasibilityAudit,
    QuotientFeasibilityResult,
    QuotientFailureReason,
    QuotientSummaryBlock,
    QuotientWitnessClassification,
    QuotientWitnessSearchResult,
)


@dataclass(slots=True)
class QuotientFeasibilityArtifacts:
    run_id: str
    run_dir: str
    quotient_class_ledger_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    witness_search_table_path: str | None
    result: QuotientFeasibilityResult


@dataclass(slots=True)
class _PreparedAudit:
    audit: QuotientFeasibilityAudit
    family: DiscoveredContextFamily
    event_package: EventPackageInstance
    candidates: SharedEventCandidates
    repo_root: Path


@dataclass(slots=True)
class _ClassInfo:
    quotient_class_id: str
    trajectory_ids: list[str]
    context_atom_assignments: dict[str, str]
    context_labels: dict[str, str]


def load_quotient_feasibility_audit(
    path: str | Path,
) -> QuotientFeasibilityAudit:
    model = load_model(path, kind="quotient-feasibility-audit")
    assert isinstance(model, QuotientFeasibilityAudit)
    return model


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_prepared_audit(
    audit_path: str | Path, *, root: str | Path | None = None
) -> _PreparedAudit:
    repo_root = get_repo_root(root)
    audit = load_quotient_feasibility_audit(audit_path)
    canonical_root = get_repo_root()

    def _resolve_repo_artifact(path: str) -> Path:
        candidate = repo_root / path
        if candidate.exists():
            return candidate
        fallback = canonical_root / path
        if fallback.exists():
            return fallback
        return candidate

    family = load_model(
        _resolve_repo_artifact(audit.source_discovered_context_family_artifact),
        kind="discovered-context-family",
    )
    assert isinstance(family, DiscoveredContextFamily)
    event_package = load_model(
        _resolve_repo_artifact(audit.source_event_package_artifact),
        kind="event-package-instance",
    )
    assert isinstance(event_package, EventPackageInstance)
    candidates = load_model(
        _resolve_repo_artifact(audit.source_shared_event_candidates_artifact),
        kind="shared-event-candidates",
    )
    assert isinstance(candidates, SharedEventCandidates)
    return _PreparedAudit(
        audit=audit,
        family=family,
        event_package=event_package,
        candidates=candidates,
        repo_root=repo_root,
    )


def _selected_contexts(family: DiscoveredContextFamily) -> list[AcceptedContext]:
    return list(family.accepted_contexts)


def _context_by_id(family: DiscoveredContextFamily) -> dict[str, AcceptedContext]:
    return {context.context_id: context for context in family.accepted_contexts}


def build_quotient_class_ledger(
    audit_path: str | Path,
    *,
    root: str | Path | None = None,
) -> QuotientClassLedger:
    prepared = _load_prepared_audit(audit_path, root=root)
    family = prepared.family
    repo_root = prepared.repo_root
    bundle_artifact = family.source_bundle_artifact
    if bundle_artifact is None:
        raise ValueError("discovered-context-family must carry source_bundle_artifact")
    resolved_bundle = load_pica_export_bundle(bundle_artifact, repo_root=repo_root)
    selected_contexts = _selected_contexts(family)

    context_assignments: dict[str, dict[str, str]] = {}
    context_labels: dict[str, dict[str, str]] = {}
    observable_artifacts: set[str] = set()
    for context in selected_contexts:
        source = context.source_metadata
        if source is None:
            raise ValueError(
                f"context '{context.context_id}' is missing source_metadata required for quotient construction"
            )
        run_id = source.run_ids[0]
        rows = resolved_bundle.filter_rows(
            run_id=run_id,
            preparation_id=source.preparation_id,
            protocol_id=source.protocol_id,
            closure_id=source.closure_id,
            lens_id=source.lens_id,
            level_id=source.level_id,
            resolution_id=source.resolution_id,
            protocol_step_id=source.protocol_step_id,
            step_index=source.step_index,
        )
        observable_ledger_id = source.observable_ledger_ids[0]
        for ledger_ref in resolved_bundle.export_bundle.observable_ledgers:
            if ledger_ref.observable_ledger_id == observable_ledger_id:
                observable_artifacts.add(ledger_ref.artifact_path)
                break
        label_to_outcome = {
            outcome.observation_label: outcome.outcome_id
            for outcome in context.atomic_outcomes
        }
        assignments: dict[str, str] = {}
        label_assignments: dict[str, str] = {}
        for row in rows:
            label = _project_pica_row_label(row, source)
            if label is None:
                continue
            outcome_id = label_to_outcome.get(label)
            if outcome_id is None:
                raise ValueError(
                    f"context '{context.context_id}' has no outcome matching label '{label}'"
                )
            assignments[row.trajectory_id] = outcome_id
            label_assignments[row.trajectory_id] = label
        context_assignments[context.context_id] = assignments
        context_labels[context.context_id] = label_assignments

    trajectory_sets = [set(assignments) for assignments in context_assignments.values()]
    common_trajectories = (
        sorted(set.intersection(*trajectory_sets)) if trajectory_sets else []
    )
    signatures: dict[tuple[tuple[str, str], ...], list[str]] = defaultdict(list)
    ordered_context_ids = [context.context_id for context in selected_contexts]
    for trajectory_id in common_trajectories:
        signature = tuple(
            (context_id, context_assignments[context_id][trajectory_id])
            for context_id in ordered_context_ids
        )
        signatures[signature].append(trajectory_id)

    quotient_classes: list[QuotientClassEntry] = []
    for index, (signature, member_ids) in enumerate(sorted(signatures.items())):
        quotient_class_id = f"qclass_{index:04d}"
        atom_assignments = {
            context_id: outcome_id for context_id, outcome_id in signature
        }
        label_assignments = {
            context_id: context_labels[context_id][member_ids[0]]
            for context_id in ordered_context_ids
        }
        quotient_classes.append(
            QuotientClassEntry(
                quotient_class_id=quotient_class_id,
                member_trajectory_ids=member_ids,
                induced_context_atom_assignments=atom_assignments,
                induced_context_labels=label_assignments,
            )
        )

    return QuotientClassLedger(
        ledger_format_version="quotient-class-ledger.v1",
        ledger_id=f"{prepared.audit.audit_id}_ledger",
        source_discovered_context_family_artifact=prepared.audit.source_discovered_context_family_artifact,
        source_event_package_artifact=prepared.audit.source_event_package_artifact,
        source_shared_event_candidates_artifact=prepared.audit.source_shared_event_candidates_artifact,
        source_bundle_artifact=bundle_artifact,
        source_observable_ledger_artifacts=sorted(observable_artifacts),
        same_slice_selection=prepared.audit.same_slice_selection,
        quotient_context_scope=prepared.audit.quotient_context_scope,
        raw_support_count=len(common_trajectories),
        quotient_class_count=len(quotient_classes),
        selected_context_ids=ordered_context_ids,
        quotient_classes=quotient_classes,
        notes=["quotient_over_selected_accepted_contexts"],
        flags=["same_slice_support_aligned", "observable_first"],
        metadata={"source_family_id": family.family_id},
    )


def _candidate_pool(
    *,
    audit: QuotientFeasibilityAudit,
    family: DiscoveredContextFamily,
    candidates: SharedEventCandidates,
) -> list[SharedEventCandidateRow]:
    context_by_id = _context_by_id(family)
    selection = audit.same_slice_selection
    pool: list[SharedEventCandidateRow] = []
    for row in candidates.candidate_rows:
        left = context_by_id.get(row.left_context_id)
        right = context_by_id.get(row.right_context_id)
        if left is None or right is None:
            continue
        left_source = left.source_metadata
        right_source = right.source_metadata
        if left_source is None or right_source is None:
            continue
        for source in [left_source, right_source]:
            if source.preparation_id != selection.preparation_id:
                break
            if source.protocol_id != selection.protocol_id:
                break
            if source.protocol_step_id != selection.protocol_step_id:
                break
            if source.step_index != selection.step_index:
                break
            if (
                selection.resolution_id is not None
                and source.resolution_id != selection.resolution_id
            ):
                break
        else:
            if selection.candidate_event_scope == "singleton_only" and (
                row.left_event_kind != "singleton"
                or row.right_event_kind != "singleton"
            ):
                continue
            pool.append(row)
    return pool


def _event_by_id(instance: EventPackageInstance) -> dict[str, object]:
    return {event.event_id: event for event in instance.events}


def _quotient_classes_info(ledger: QuotientClassLedger) -> list[_ClassInfo]:
    return [
        _ClassInfo(
            quotient_class_id=entry.quotient_class_id,
            trajectory_ids=list(entry.member_trajectory_ids),
            context_atom_assignments=dict(entry.induced_context_atom_assignments),
            context_labels=dict(entry.induced_context_labels),
        )
        for entry in ledger.quotient_classes
    ]


def _evaluate_candidate_subset(
    *,
    candidate_rows: Iterable[SharedEventCandidateRow],
    ledger: QuotientClassLedger,
    event_package: EventPackageInstance,
    mode: str,
) -> QuotientEvaluationResult:
    event_by_id = _event_by_id(event_package)
    classes = _quotient_classes_info(ledger)
    selected_rows = list(candidate_rows)
    surviving: list[_ClassInfo] = []
    for quotient_class in classes:
        respects = True
        for candidate in selected_rows:
            left_event = event_by_id[candidate.left_event_id]
            right_event = event_by_id[candidate.right_event_id]
            left_member = (
                quotient_class.context_atom_assignments[candidate.left_context_id]
                in left_event.atom_ids
            )
            right_member = (
                quotient_class.context_atom_assignments[candidate.right_context_id]
                in right_event.atom_ids
            )
            if left_member != right_member:
                respects = False
                break
        if respects:
            surviving.append(quotient_class)

    uncovered_atom_refs: list[str] = []
    if surviving:
        for context in event_package.contexts:
            for atom in context.atoms:
                if not any(
                    quotient_class.context_atom_assignments[context.context_id]
                    == atom.atom_id
                    for quotient_class in surviving
                ):
                    uncovered_atom_refs.append(f"{context.context_id}:{atom.atom_id}")
    exact_feasible = bool(surviving) and not uncovered_atom_refs
    failure_reason: QuotientFailureReason | None = None
    if not exact_feasible:
        failure_reason = "no_respecting_tuples" if not surviving else "coverage_failure"
    proposal_ids = [
        candidate.proposed_proposal_id
        for candidate in selected_rows
        if candidate.proposed_proposal_id is not None
    ]
    return QuotientEvaluationResult(
        mode=mode,  # type: ignore[arg-type]
        candidate_ids=[candidate.candidate_id for candidate in selected_rows],
        proposal_ids=proposal_ids,
        survivor_count=len(surviving),
        surviving_quotient_class_ids=[
            quotient_class.quotient_class_id for quotient_class in surviving
        ],
        exact_feasible=exact_feasible,
        exact_failure_reason=failure_reason,
        uncovered_atom_refs=uncovered_atom_refs,
    )


def _derive_natural_pairing_candidates(
    pool: list[SharedEventCandidateRow],
) -> list[SharedEventCandidateRow]:
    return [
        row
        for row in pool
        if row.accepted and row.support_relation_kind == "same_support_relabeling"
    ]


def _witness_classification(
    accepted_result: QuotientEvaluationResult,
    witness_result: QuotientWitnessSearchResult,
) -> QuotientWitnessClassification:
    if not accepted_result.exact_feasible:
        return "accepted_proposal_obstruction"
    if witness_result.witness_found:
        return "candidate_subset_quotient_witness"
    return "no_quotient_obstruction"


def run_quotient_feasibility_audit(
    *,
    audit_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> QuotientFeasibilityArtifacts:
    prepared = _load_prepared_audit(audit_path, root=root)
    repo_root = prepared.repo_root
    canonical_root = get_repo_root()
    audit = prepared.audit
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or audit.output_label or audit.audit_id,
        timestamp=timestamp,
        root=repo_root,
    )
    ledger = build_quotient_class_ledger(audit_path, root=repo_root)
    quotient_class_ledger_path = run_dir / "quotient-class-ledger.json"
    summary_path = run_dir / "quotient-feasibility-summary.json"
    note_path = run_dir / "quotient-feasibility-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    witness_search_path = run_dir / "witness-search-table.json"

    _write_json(quotient_class_ledger_path, ledger.model_dump(mode="json"))

    pool = _candidate_pool(
        audit=audit,
        family=prepared.family,
        candidates=prepared.candidates,
    )
    rows_by_id = {row.candidate_id: row for row in prepared.candidates.candidate_rows}
    accepted_rows = [
        row
        for row in prepared.candidates.candidate_rows
        if row.accepted and row.proposed_proposal_id is not None
    ]
    accepted_result = _evaluate_candidate_subset(
        candidate_rows=accepted_rows,
        ledger=ledger,
        event_package=prepared.event_package,
        mode="accepted_only",
    )

    natural_rows = (
        [
            rows_by_id[candidate_id]
            for candidate_id in audit.natural_pairing_candidate_ids
        ]
        if audit.natural_pairing_candidate_ids
        else _derive_natural_pairing_candidates(pool)
    )
    natural_result = _evaluate_candidate_subset(
        candidate_rows=natural_rows,
        ledger=ledger,
        event_package=prepared.event_package,
        mode="natural_pairing_control",
    )

    forced_result: QuotientEvaluationResult | None = None
    if audit.forced_candidate_ids:
        forced_rows = [
            rows_by_id[candidate_id] for candidate_id in audit.forced_candidate_ids
        ]
        forced_result = _evaluate_candidate_subset(
            candidate_rows=forced_rows,
            ledger=ledger,
            event_package=prepared.event_package,
            mode="forced_candidate_subset",
        )

    witness_rows: list[dict[str, object]] = []
    searched_subset_count = 0
    witness_search = QuotientWitnessSearchResult(
        searched_candidate_count=len(pool),
        searched_subset_count=0,
        max_subset_size=audit.subset_search.max_subset_size,
        witness_found=False,
    )
    if audit.subset_search.enabled:
        best_witness: (
            tuple[list[SharedEventCandidateRow], QuotientEvaluationResult] | None
        ) = None
        for subset_size in range(1, audit.subset_search.max_subset_size + 1):
            for subset in combinations(pool, subset_size):
                searched_subset_count += 1
                evaluation = _evaluate_candidate_subset(
                    candidate_rows=subset,
                    ledger=ledger,
                    event_package=prepared.event_package,
                    mode="forced_candidate_subset",
                )
                witness_rows.append(
                    {
                        "candidate_ids": evaluation.candidate_ids,
                        "proposal_ids": evaluation.proposal_ids,
                        "survivor_count": evaluation.survivor_count,
                        "exact_feasible": evaluation.exact_feasible,
                        "exact_failure_reason": evaluation.exact_failure_reason,
                    }
                )
                if not evaluation.exact_feasible:
                    best_witness = (list(subset), evaluation)
                    if audit.subset_search.stop_at_first_witness:
                        break
            if best_witness is not None and audit.subset_search.stop_at_first_witness:
                break
        if best_witness is not None:
            subset, evaluation = best_witness
            witness_search = QuotientWitnessSearchResult(
                searched_candidate_count=len(pool),
                searched_subset_count=searched_subset_count,
                max_subset_size=audit.subset_search.max_subset_size,
                witness_found=True,
                minimal_witness_size=len(subset),
                witness_candidate_ids=evaluation.candidate_ids,
                witness_proposal_ids=evaluation.proposal_ids,
                witness_survivor_count=evaluation.survivor_count,
                witness_failure_reason=evaluation.exact_failure_reason,
            )
        else:
            witness_search = QuotientWitnessSearchResult(
                searched_candidate_count=len(pool),
                searched_subset_count=searched_subset_count,
                max_subset_size=audit.subset_search.max_subset_size,
                witness_found=False,
            )

    if witness_rows:
        _write_json(witness_search_path, witness_rows)

    classification = _witness_classification(accepted_result, witness_search)
    result = QuotientFeasibilityResult(
        result_format_version="quotient-feasibility-result.v1",
        audit_id=audit.audit_id,
        source_event_package_artifact=audit.source_event_package_artifact,
        source_discovered_context_family_artifact=audit.source_discovered_context_family_artifact,
        source_shared_event_candidates_artifact=audit.source_shared_event_candidates_artifact,
        source_package_provenance_artifact=audit.source_package_provenance_artifact,
        quotient_class_ledger_artifact=repo_relative_path(
            quotient_class_ledger_path, root=repo_root
        ),
        quotient_summary=QuotientSummaryBlock(
            raw_support_count=ledger.raw_support_count,
            quotient_class_count=ledger.quotient_class_count,
            selected_context_count=len(ledger.selected_context_ids),
            selected_context_ids=list(ledger.selected_context_ids),
        ),
        accepted_proposal_set_result=accepted_result,
        natural_pairing_result=natural_result,
        forced_candidate_subset_result=forced_result,
        candidate_subset_witness_result=witness_search,
        witness_classification=classification,
        notes=[
            "current_structural_primary_admissibility_unchanged",
            "quotient_classes_used_as_candidate_global_atoms",
        ],
        flags=["same_slice", "observable_first", "quotient_backend"],
    )
    _write_json(summary_path, result.model_dump(mode="json"))

    note_lines = [
        "# Quotient Feasibility Audit",
        "",
        f"- Source case: `{audit.audit_id}`",
        f"- Same-slice support used: preparation=`{audit.same_slice_selection.preparation_id}`, protocol=`{audit.same_slice_selection.protocol_id}`, protocol_step_id=`{audit.same_slice_selection.protocol_step_id}`, step_index=`{audit.same_slice_selection.step_index}`, resolution_id=`{audit.same_slice_selection.resolution_id or 'all'}`",
        f"- Quotient construction summary: raw_support_count=`{ledger.raw_support_count}`, quotient_class_count=`{ledger.quotient_class_count}`, selected_context_count=`{len(ledger.selected_context_ids)}`",
        "- Proposal pool modes tested:",
        f"  - accepted_only: survivor_count=`{accepted_result.survivor_count}`, exact_feasible=`{accepted_result.exact_feasible}`, failure_reason=`{accepted_result.exact_failure_reason}`",
        f"  - natural_pairing_control: survivor_count=`{natural_result.survivor_count}`, exact_feasible=`{natural_result.exact_feasible}`, failure_reason=`{natural_result.exact_failure_reason}`",
    ]
    if forced_result is not None:
        note_lines.append(
            f"  - forced_candidate_subset: survivor_count=`{forced_result.survivor_count}`, exact_feasible=`{forced_result.exact_feasible}`, failure_reason=`{forced_result.exact_failure_reason}`, candidate_ids=`{','.join(forced_result.candidate_ids)}`"
        )
    note_lines.extend(
        [
            f"  - candidate_subset_search: witness_found=`{witness_search.witness_found}`, searched_candidate_count=`{witness_search.searched_candidate_count}`, searched_subset_count=`{witness_search.searched_subset_count}`, max_subset_size=`{witness_search.max_subset_size}`",
            f"- Final witness classification: `{classification}`",
            "- This audit does not alter current shared-event admissibility.",
            "",
            "## Artifact refs",
            f"- `quotient_class_ledger`: `{repo_relative_path(quotient_class_ledger_path, root=repo_root)}`",
            f"- `summary`: `{repo_relative_path(summary_path, root=repo_root)}`",
        ]
    )
    if witness_rows:
        note_lines.append(
            f"- `witness_search_table`: `{repo_relative_path(witness_search_path, root=repo_root)}`"
        )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    output_paths = {
        "quotient_class_ledger": repo_relative_path(
            quotient_class_ledger_path, root=repo_root
        ),
        "summary": repo_relative_path(summary_path, root=repo_root),
        "note": repo_relative_path(note_path, root=repo_root),
        "result_note": repo_relative_path(result_note_path, root=repo_root),
        "manifest": repo_relative_path(manifest_path, root=repo_root),
    }
    if witness_rows:
        output_paths["witness_search_table"] = repo_relative_path(
            witness_search_path, root=repo_root
        )

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[audit.audit_id],
        metrics={
            "raw_support_count": ledger.raw_support_count,
            "quotient_class_count": ledger.quotient_class_count,
            "accepted_only_survivor_count": accepted_result.survivor_count,
            "natural_pairing_survivor_count": natural_result.survivor_count,
            "candidate_subset_witness_found": witness_search.witness_found,
            "candidate_subset_search_depth": witness_search.max_subset_size,
        },
        interpretation=(
            "The quotient-feasibility audit keeps discovery admissibility fixed and recomputes global realization over quotient classes induced by the selected context family."
        ),
        caveats=[
            "Current structural_primary acceptance remains unchanged.",
            "Candidate-subset witnesses may involve rejected candidates from the saved candidate table.",
        ],
        artifact_refs=output_paths,
        metadata={"witness_classification": classification},
    )
    _write_json(result_note_path, result_note.model_dump(mode="json"))
    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "quotient-feasibility",
            repo_relative_path(audit_path, root=repo_root),
        ],
        seed=seed,
        input_artifacts={
            "audit_config": repo_relative_path(
                audit_path,
                root=repo_root
                if Path(audit_path).resolve().is_relative_to(repo_root)
                else canonical_root,
            )
        },
        output_artifacts=output_paths,
        status="succeeded",
        git_commit=detect_git_commit(root=repo_root),
        metadata={"analysis_kind": "quotient_feasibility_audit"},
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return QuotientFeasibilityArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=repo_root),
        quotient_class_ledger_path=output_paths["quotient_class_ledger"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        witness_search_table_path=output_paths.get("witness_search_table"),
        result=result,
    )
