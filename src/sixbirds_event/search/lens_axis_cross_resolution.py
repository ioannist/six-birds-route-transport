from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from ..audits.models import QuotientClassLedger, QuotientFeasibilityResult
from ..audits.quotient_feasibility import (
    load_quotient_feasibility_audit,
    run_quotient_feasibility_audit,
)
from ..discovery.models import AcceptedContext, DiscoveredContextFamily
from ..pica_bridge.ingest import load_pica_export_bundle
from ..pica_bridge.packaging_surface import resolve_pica_packaging_surface
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    get_repo_root,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from ..validation import load_model
from .models import LensAxisCrossResolutionAdjudication, LensFamilyAdmissibility


@dataclass(slots=True)
class LensAxisCrossResolutionClosureArtifacts:
    run_id: str
    run_dir: str
    adjudication_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    outcome_path: str
    outcome_kind: str
    adjudication: LensAxisCrossResolutionAdjudication
    quotient_result: QuotientFeasibilityResult


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_family(path: str, *, root: Path) -> DiscoveredContextFamily:
    resolved = _resolve_repo_artifact(path, root=root)
    model = load_model(resolved, kind="discovered-context-family")
    assert isinstance(model, DiscoveredContextFamily)
    return model


def _load_lens_admissibility(path: str, *, root: Path) -> LensFamilyAdmissibility:
    resolved = _resolve_repo_artifact(path, root=root)
    model = load_model(resolved, kind="lens-family-admissibility")
    assert isinstance(model, LensFamilyAdmissibility)
    return model


def _resolve_repo_artifact(path: str | Path, *, root: Path) -> Path:
    candidate = root / path
    if candidate.exists():
        return candidate
    canonical_root = get_repo_root()
    fallback = canonical_root / path
    if fallback.exists():
        return fallback
    return candidate


def _context_rows(
    context: AcceptedContext,
    *,
    bundle_artifact: str,
    repo_root: Path,
) -> set[str]:
    if context.source_metadata is None:
        return set()
    resolved = load_pica_export_bundle(bundle_artifact, repo_root=repo_root)
    source = context.source_metadata
    rows = resolved.filter_rows(
        run_id=source.run_ids[0],
        preparation_id=source.preparation_id,
        protocol_id=source.protocol_id,
        closure_id=source.closure_id,
        lens_id=source.lens_id,
        level_id=source.level_id,
        resolution_id=source.resolution_id,
        protocol_step_id=source.protocol_step_id,
        step_index=source.step_index,
    )
    return {row.trajectory_id for row in rows}


def _build_adjudication(
    *,
    witness_case_id: str,
    source_discovered_context_family_artifact: str,
    source_package_provenance_artifact: str,
    audit_path: str,
    family: DiscoveredContextFamily,
    lens_admissibility_path: str | None,
    quotient_result: QuotientFeasibilityResult,
    quotient_ledger: QuotientClassLedger,
    repo_root: Path,
) -> LensAxisCrossResolutionAdjudication:
    contexts = list(family.accepted_contexts)
    sources = [
        context.source_metadata for context in contexts if context.source_metadata
    ]
    if not sources:
        raise ValueError("cross-resolution witness family must contain source metadata")

    run_ids = {run_id for source in sources for run_id in source.run_ids}
    preparation_ids = {source.preparation_id for source in sources}
    protocol_ids = {source.protocol_id for source in sources}
    step_keys = {
        (source.protocol_step_id, source.step_index, source.resolution_id)
        for source in sources
    }
    resolution_ids = {source.resolution_id for source in sources}
    trajectory_sets = [
        _context_rows(
            context,
            bundle_artifact=family.source_bundle_artifact
            or quotient_ledger.source_bundle_artifact,
            repo_root=repo_root,
        )
        for context in contexts
    ]
    nonempty_sets = [rows for rows in trajectory_sets if rows]
    same_support_status = bool(nonempty_sets) and all(
        rows == nonempty_sets[0] for rows in nonempty_sets[1:]
    )
    same_run_status = len(run_ids) == 1
    same_step_status = len(step_keys) == 1
    cross_resolution_status = len(step_keys) > 1 and len(resolution_ids) > 1

    packaging_surface = resolve_pica_packaging_surface(
        family.source_bundle_artifact or quotient_ledger.source_bundle_artifact,
        repo_root=get_repo_root(),
    )
    same_evaluation_regime_status = (
        len(preparation_ids) == 1
        and len(protocol_ids) == 1
        and same_run_status
        and packaging_surface.surface.distinct_packaging_family_count >= 1
    )

    theory_alignment_flags: list[str] = []
    if same_support_status:
        theory_alignment_flags.append("same_support_rows_fixed")
    if same_run_status:
        theory_alignment_flags.append("same_run_fixed")
    if same_evaluation_regime_status:
        theory_alignment_flags.append("fixed_evaluation_regime")
    if cross_resolution_status:
        theory_alignment_flags.append("cross_resolution_strict_extension")

    rationale_notes = [
        "Original TH4 required same frozen slice and same support for primary comparisons.",
        "This witness keeps support, mechanism, and evaluation regime fixed but varies resolution and lens on the same run.",
        "Cross-resolution is accepted here only because the involved projection family remains primary_context and packaging_outcome on the same support object.",
        "No stage-derived-only or diagnostic-only projection family participates in the witness.",
    ]

    if lens_admissibility_path is not None:
        admissibility = _load_lens_admissibility(
            lens_admissibility_path, root=repo_root
        )
        admissible_rows = [
            row
            for row in admissibility.rows
            if row.allowed_role == "primary_context"
            and row.projection_kind in {"packaging_outcome", "derived_row_outcome"}
        ]
        if admissible_rows:
            theory_alignment_flags.append("primary_projection_family")
        else:
            rationale_notes.append(
                "Projection-family admissibility did not certify a primary_context packaging_outcome / derived_row_outcome family."
            )

    final_adjudication = (
        "accepted_as_lens_axis_strict_extension"
        if same_support_status
        and same_run_status
        and same_evaluation_regime_status
        and cross_resolution_status
        else "rejected_as_out_of_contract"
    )
    if final_adjudication == "accepted_as_lens_axis_strict_extension":
        theory_alignment_flags.append("paper_aligned_strict_extension")

    consulted_paper_refs = [
        "docs/papers/Tsiokos_2026_A_Six_Birds_Eye_View_of_Quantum_Theory_Operational_Closure_Semantics_for_Measurement_Contextuality_and_Record_Stability.tex:748-764",
        "docs/papers/Tsiokos_2026_Six_Birds_for_Incompleteness_Fixed_Packages_Package_Change_and_Conditional_Arithmetic_Lift.tex:205-225",
        "docs/papers/Tsiokos_2026_Six_Birds_for_Incompleteness_Fixed_Packages_Package_Change_and_Conditional_Arithmetic_Lift.tex:759-761",
        "docs/papers/Tsiokos_2026_Strict_Theory_Extension_on_a_Lawful_Continuous_Cantor_Shell.tex:223-225",
        "docs/papers/Tsiokos_2026_Strict_Theory_Extension_on_a_Lawful_Continuous_Cantor_Shell.tex:323-326",
        "docs/papers/Tsiokos_2026_Strict_Theory_Extension_on_a_Lawful_Continuous_Cantor_Shell.tex:729-733",
    ]

    return LensAxisCrossResolutionAdjudication(
        adjudication_format_version="lens-axis-cross-resolution-adjudication.v1",
        witness_case_id=witness_case_id,
        source_discovered_context_family_artifact=source_discovered_context_family_artifact,
        source_event_package_artifact=quotient_result.source_event_package_artifact,
        source_package_provenance_artifact=source_package_provenance_artifact,
        source_quotient_feasibility_audit_artifact=repo_relative_path(
            repo_root / audit_path, root=repo_root
        ),
        source_lens_family_admissibility_artifact=lens_admissibility_path,
        same_support_status=same_support_status,
        same_run_status=same_run_status,
        same_evaluation_regime_status=same_evaluation_regime_status,
        same_step_status=same_step_status,
        cross_resolution_status=cross_resolution_status,
        theory_alignment_flags=theory_alignment_flags,
        consulted_paper_refs=consulted_paper_refs,
        final_adjudication=final_adjudication,
        rationale_notes=rationale_notes,
        metadata={
            "quotient_witness_classification": quotient_result.witness_classification,
            "quotient_class_count": quotient_result.quotient_summary.quotient_class_count,
            "selected_context_count": quotient_result.quotient_summary.selected_context_count,
        },
    )


def run_lens_axis_cross_resolution_closure(
    *,
    audit_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> LensAxisCrossResolutionClosureArtifacts:
    repo_root = get_repo_root(root)
    audit = load_quotient_feasibility_audit(audit_path)
    quotient_artifacts = run_quotient_feasibility_audit(
        audit_path=audit_path,
        category=category,
        label=f"{label or audit.output_label or audit.audit_id}_quotient",
        seed=seed,
        timestamp=timestamp,
        root=repo_root,
        command=command,
    )
    quotient_result = quotient_artifacts.result
    quotient_ledger = load_model(
        repo_root / quotient_artifacts.quotient_class_ledger_path,
        kind="quotient-class-ledger",
    )
    assert isinstance(quotient_ledger, QuotientClassLedger)

    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or f"{audit.audit_id}_closure",
        timestamp=timestamp,
        root=repo_root,
    )
    adjudication_path = run_dir / "cross-resolution-adjudication.json"
    summary_path = run_dir / "cross-resolution-summary.json"
    note_path = run_dir / "cross-resolution-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"

    audit_rel = repo_relative_path(repo_root / audit_path, root=repo_root)
    family = _load_family(
        audit.source_discovered_context_family_artifact, root=repo_root
    )
    lens_admissibility_candidate = Path(audit_path).with_name(
        "lens-family-admissibility.json"
    )
    lens_admissibility_rel = (
        repo_relative_path(lens_admissibility_candidate, root=repo_root)
        if lens_admissibility_candidate.exists()
        else None
    )
    adjudication = _build_adjudication(
        witness_case_id=audit.audit_id,
        source_discovered_context_family_artifact=audit.source_discovered_context_family_artifact,
        source_package_provenance_artifact=audit.source_package_provenance_artifact
        or "",
        audit_path=audit_rel,
        family=family,
        lens_admissibility_path=lens_admissibility_rel,
        quotient_result=quotient_result,
        quotient_ledger=quotient_ledger,
        repo_root=repo_root,
    )
    _write_json(adjudication_path, adjudication.model_dump(mode="json"))

    outcome_filename = (
        "th4-accepted-obstruction.json"
        if adjudication.final_adjudication == "accepted_as_lens_axis_strict_extension"
        and quotient_result.witness_classification == "accepted_proposal_obstruction"
        else "th4-rejected-out-of-contract.json"
    )
    outcome_kind = (
        "accepted_obstruction"
        if outcome_filename == "th4-accepted-obstruction.json"
        else "rejected_out_of_contract"
    )
    outcome_path = run_dir / outcome_filename

    engineering_path = (
        "designated_witness_runner_using_committed_assets_and_existing_quotient_backend"
    )
    summary = {
        "witness_case_id": audit.audit_id,
        "source_artifacts": {
            "quotient_feasibility_audit": audit_rel,
            "discovered_context_family": audit.source_discovered_context_family_artifact,
            "event_package": audit.source_event_package_artifact,
            "package_provenance": audit.source_package_provenance_artifact,
            "shared_event_candidates": audit.source_shared_event_candidates_artifact,
            "quotient_class_ledger": quotient_artifacts.quotient_class_ledger_path,
            "quotient_feasibility_summary": quotient_artifacts.summary_path,
        },
        "same_support_status": adjudication.same_support_status,
        "same_run_status": adjudication.same_run_status,
        "same_evaluation_regime_status": adjudication.same_evaluation_regime_status,
        "same_step_status": adjudication.same_step_status,
        "cross_resolution_status": adjudication.cross_resolution_status,
        "accepted_proposal_result": {
            "survivor_count": quotient_result.accepted_proposal_set_result.survivor_count,
            "exact_feasible": quotient_result.accepted_proposal_set_result.exact_feasible,
            "failure_reason": quotient_result.accepted_proposal_set_result.exact_failure_reason,
        },
        "natural_pairing_result": {
            "survivor_count": quotient_result.natural_pairing_result.survivor_count
            if quotient_result.natural_pairing_result is not None
            else None,
            "exact_feasible": quotient_result.natural_pairing_result.exact_feasible
            if quotient_result.natural_pairing_result is not None
            else None,
            "failure_reason": quotient_result.natural_pairing_result.exact_failure_reason
            if quotient_result.natural_pairing_result is not None
            else None,
        },
        "candidate_subset_result": {
            "searched_candidate_count": quotient_result.candidate_subset_witness_result.searched_candidate_count,
            "searched_subset_count": quotient_result.candidate_subset_witness_result.searched_subset_count,
            "witness_found": quotient_result.candidate_subset_witness_result.witness_found,
            "minimal_witness_size": quotient_result.candidate_subset_witness_result.minimal_witness_size,
            "witness_candidate_ids": quotient_result.candidate_subset_witness_result.witness_candidate_ids,
        },
        "quotient_summary": {
            "raw_support_count": quotient_result.quotient_summary.raw_support_count,
            "quotient_class_count": quotient_result.quotient_summary.quotient_class_count,
            "selected_context_ids": quotient_result.quotient_summary.selected_context_ids,
        },
        "quotient_witness_classification": quotient_result.witness_classification,
        "engineering_path_used": engineering_path,
        "adjudication_result": adjudication.final_adjudication,
        "final_th4_closure_decision": outcome_kind,
    }
    _write_json(summary_path, summary)

    outcome_payload = {
        "result_kind": outcome_kind,
        "witness_case_id": audit.audit_id,
        "adjudication_result": adjudication.final_adjudication,
        "quotient_witness_classification": quotient_result.witness_classification,
        "accepted_only_survivor_count": quotient_result.accepted_proposal_set_result.survivor_count,
        "natural_pairing_survivor_count": None
        if quotient_result.natural_pairing_result is None
        else quotient_result.natural_pairing_result.survivor_count,
        "artifact_refs": {
            "adjudication": repo_relative_path(adjudication_path, root=repo_root),
            "summary": repo_relative_path(summary_path, root=repo_root),
            "quotient_summary": quotient_artifacts.summary_path,
        },
    }
    _write_json(outcome_path, outcome_payload)

    note_lines = [
        "# Lens-Axis Cross-Resolution Reconciliation",
        "",
        f"- Witness case: `{audit.audit_id}`",
        "- Original TH4 contract: fixed mechanism, fixed support object, admissible lens variation, same-slice discipline.",
        "- Cross-resolution witness setup: same run and support family, observation-label primary contexts, resolution pair `k=4` / `k=20`.",
        f"- Same-support status: `{adjudication.same_support_status}`",
        f"- Same-run status: `{adjudication.same_run_status}`",
        f"- Same-evaluation-regime status: `{adjudication.same_evaluation_regime_status}`",
        f"- Same-step status: `{adjudication.same_step_status}`",
        f"- Cross-resolution status: `{adjudication.cross_resolution_status}`",
        "- Relevant theory passages consulted:",
    ]
    for ref in adjudication.consulted_paper_refs:
        note_lines.append(f"  - `{ref}`")
    note_lines.extend(
        [
            "- Quotient-feasibility comparison:",
            f"  - accepted_only: survivor_count=`{quotient_result.accepted_proposal_set_result.survivor_count}`, exact_feasible=`{quotient_result.accepted_proposal_set_result.exact_feasible}`, failure_reason=`{quotient_result.accepted_proposal_set_result.exact_failure_reason}`",
            f"  - natural_pairing_control: survivor_count=`{quotient_result.natural_pairing_result.survivor_count if quotient_result.natural_pairing_result is not None else 'not_applicable'}`, exact_feasible=`{quotient_result.natural_pairing_result.exact_feasible if quotient_result.natural_pairing_result is not None else 'not_applicable'}`",
            f"  - candidate_subset_search: witness_found=`{quotient_result.candidate_subset_witness_result.witness_found}`, searched_subset_count=`{quotient_result.candidate_subset_witness_result.searched_subset_count}`",
            f"- Engineering path used: `{engineering_path}`",
            f"- Adjudication result: `{adjudication.final_adjudication}`",
            f"- Final TH4 closure decision: `{outcome_kind}`",
            "- This closure does not alter current shared-event admissibility; it reconciles the committed witness with the lens-axis contract.",
            "",
            "## Artifact refs",
            f"- `adjudication`: `{repo_relative_path(adjudication_path, root=repo_root)}`",
            f"- `summary`: `{repo_relative_path(summary_path, root=repo_root)}`",
            f"- `quotient_summary`: `{quotient_artifacts.summary_path}`",
            f"- `outcome`: `{repo_relative_path(outcome_path, root=repo_root)}`",
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    output_paths = {
        "adjudication": repo_relative_path(adjudication_path, root=repo_root),
        "summary": repo_relative_path(summary_path, root=repo_root),
        "note": repo_relative_path(note_path, root=repo_root),
        "result_note": repo_relative_path(result_note_path, root=repo_root),
        "manifest": repo_relative_path(manifest_path, root=repo_root),
        "quotient_summary": quotient_artifacts.summary_path,
        "quotient_class_ledger": quotient_artifacts.quotient_class_ledger_path,
        "outcome": repo_relative_path(outcome_path, root=repo_root),
    }
    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[audit.audit_id],
        metrics={
            "quotient_class_count": quotient_result.quotient_summary.quotient_class_count,
            "accepted_only_survivor_count": quotient_result.accepted_proposal_set_result.survivor_count,
            "natural_pairing_survivor_count": None
            if quotient_result.natural_pairing_result is None
            else quotient_result.natural_pairing_result.survivor_count,
            "candidate_subset_witness_found": quotient_result.candidate_subset_witness_result.witness_found,
        },
        interpretation=(
            "The closure path reconciles a committed cross-resolution witness with the lens-axis contract while preserving the existing quotient-backed theorem object."
        ),
        caveats=[
            "The adjudication is specific to the committed k=4 / k=20 witness case.",
            "The closure decision does not enlarge current shared-event admissibility.",
        ],
        artifact_refs=output_paths,
        metadata={
            "final_adjudication": adjudication.final_adjudication,
            "outcome_kind": outcome_kind,
        },
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
            "search",
            "close-lens-cross-resolution",
            audit_rel,
        ],
        seed=seed,
        input_artifacts={
            "quotient_feasibility_audit": audit_rel,
            "discovered_context_family": audit.source_discovered_context_family_artifact,
            "event_package": audit.source_event_package_artifact,
            "shared_event_candidates": audit.source_shared_event_candidates_artifact,
        },
        output_artifacts=output_paths,
        status="succeeded",
        git_commit=detect_git_commit(root=repo_root),
        metadata={"analysis_kind": "lens_axis_cross_resolution_closure"},
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return LensAxisCrossResolutionClosureArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=repo_root),
        adjudication_path=output_paths["adjudication"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        outcome_path=output_paths["outcome"],
        outcome_kind=outcome_kind,
        adjudication=adjudication,
        quotient_result=quotient_result,
    )
