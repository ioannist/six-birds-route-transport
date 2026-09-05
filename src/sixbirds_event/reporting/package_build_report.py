from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import statistics
import sys
from typing import Callable

from ..discovery.models import (
    AcceptedContext,
    DiscoveredContextFamily,
    EventAlgebraCoverage,
    DiscoveredEventFamily,
    DiscoveredEventGenerationThresholds,
    ProbeIndistinguishabilitySignatureTable,
    SharedEventCandidates,
    SharedEventInferenceThresholds,
)
from ..discovery.event_algebra import build_event_algebra_coverage
from ..discovery.shared_event_inference import (
    DEFAULT_SHARED_EVENT_INFERENCE_THRESHOLDS,
    build_package_from_discovery,
    load_discovered_context_family,
    load_discovered_event_package_skeleton,
    load_substrate_run_files,
)
from ..provenance.models import (
    ContextProvenanceEntry,
    EventProvenanceEntry,
    PackageProvenance,
    ProposalProvenanceEntry,
    ProvenanceSourceRef,
)
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance
from ..schemas.result_note import ResultNote


@dataclass(slots=True)
class PackageBuildReportArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    discovered_event_family_path: str
    event_algebra_coverage_path: str
    signatures_path: str
    candidates_path: str
    event_package_path: str
    provenance_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    discovered_event_family: DiscoveredEventFamily
    event_algebra_coverage: EventAlgebraCoverage
    signatures: ProbeIndistinguishabilitySignatureTable
    candidates: SharedEventCandidates
    event_package: EventPackageInstance


def _accepted_scores(candidates: SharedEventCandidates) -> list[float]:
    return [
        row.approx_score
        for row in candidates.candidate_rows
        if row.accepted and row.approx_score is not None
    ]


def _accepted_coarse_proposal_count(candidates: SharedEventCandidates) -> int:
    return sum(
        1
        for row in candidates.candidate_rows
        if row.accepted and (row.left_is_proper_coarse or row.right_is_proper_coarse)
    )


def _build_summary(
    *,
    family_path: str,
    run_paths: list[str],
    pica_bundle_path: str | None,
    skeleton_path: str | None,
    discovered_event_family_path: str,
    event_algebra_coverage_path: str,
    signatures_path: str,
    candidates_path: str,
    event_package_path: str,
    provenance_path: str,
    discovered_event_family: DiscoveredEventFamily,
    event_algebra_coverage: EventAlgebraCoverage,
    candidates: SharedEventCandidates,
    event_package: EventPackageInstance,
    weight_mapping_rule: str,
) -> dict[str, object]:
    accepted_scores = _accepted_scores(candidates)
    return {
        "source_discovered_context_family_artifact": family_path,
        "source_run_artifacts": run_paths,
        "source_pica_export_bundle_artifact": pica_bundle_path,
        "source_skeleton_artifact": skeleton_path,
        "discovered_event_family_artifact": discovered_event_family_path,
        "event_algebra_coverage_artifact": event_algebra_coverage_path,
        "probe_indistinguishability_signatures_artifact": signatures_path,
        "inference_mode": candidates.inference_mode,
        "event_basis_mode": discovered_event_family.thresholds.event_basis_mode,
        "event_algebra_mode": discovered_event_family.thresholds.event_algebra_mode,
        "max_full_powerset_atom_count": discovered_event_family.thresholds.max_full_powerset_atom_count,
        "coarse_event_generation_thresholds": discovered_event_family.thresholds.model_dump(
            mode="json"
        ),
        "accepted_context_count": len(event_package.contexts),
        "per_context_atom_counts": {
            context.context_id: context.atom_count
            for context in discovered_event_family.contexts
        },
        "per_context_expected_full_event_counts": {
            context.context_id: context.expected_full_event_count
            for context in discovered_event_family.contexts
        },
        "per_context_generated_event_counts": {
            context.context_id: context.generated_event_count
            for context in discovered_event_family.contexts
        },
        "per_context_completeness_flags": {
            context.context_id: context.event_algebra_complete
            for context in discovered_event_family.contexts
        },
        "total_candidate_pair_count": candidates.diagnostics_summary.total_candidate_pair_count,
        "structurally_valid_candidate_pair_count": candidates.diagnostics_summary.structurally_valid_candidate_pair_count,
        "accepted_candidate_pair_count": candidates.diagnostics_summary.accepted_candidate_pair_count,
        "insufficient_data_candidate_pair_count": candidates.diagnostics_summary.insufficient_data_candidate_pair_count,
        "generated_singleton_event_count": discovered_event_family.diagnostics_summary.generated_singleton_event_count,
        "generated_proper_coarse_event_count": discovered_event_family.diagnostics_summary.generated_proper_coarse_event_count,
        "generated_empty_full_event_count": (
            discovered_event_family.diagnostics_summary.generated_empty_event_count
            + discovered_event_family.diagnostics_summary.generated_full_event_count
        ),
        "total_match_eligible_event_count": discovered_event_family.diagnostics_summary.match_eligible_event_count,
        "accepted_shared_event_proposal_count": len(event_package.equality_proposals),
        "accepted_singleton_proposal_count": sum(
            1
            for row in candidates.candidate_rows
            if row.accepted
            and not (row.left_is_proper_coarse or row.right_is_proper_coarse)
        ),
        "accepted_singleton_event_count": discovered_event_family.diagnostics_summary.accepted_singleton_event_count,
        "accepted_coarse_event_count": discovered_event_family.diagnostics_summary.accepted_coarse_event_count,
        "accepted_coarse_proposal_count": _accepted_coarse_proposal_count(candidates),
        "structural_signature_thresholds": candidates.thresholds.model_dump(
            mode="json"
        ),
        "thresholds": candidates.thresholds.model_dump(mode="json"),
        "proposal_constraint_kind": candidates.thresholds.proposal_constraint_kind,
        "weight_mapping_rule": weight_mapping_rule,
        "built_event_package_artifact": event_package_path,
        "shared_event_candidates_artifact": candidates_path,
        "package_provenance_artifact": provenance_path,
        "accepted_proposal_ids": candidates.diagnostics_summary.accepted_proposal_ids,
        "mean_accepted_tv": statistics.mean(accepted_scores)
        if accepted_scores
        else None,
        "max_accepted_tv": max(accepted_scores) if accepted_scores else None,
        "built_package_validated": True,
        "package_provenance_validated": True,
    }


def _render_note(
    *,
    family_path: str,
    run_paths: list[str],
    pica_bundle_path: str | None,
    discovered_event_family: DiscoveredEventFamily,
    event_algebra_coverage: EventAlgebraCoverage,
    candidates: SharedEventCandidates,
    summary: dict[str, object],
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Package Build Report",
        "",
        "## Source discovered contexts",
        f"- `{family_path}`",
        "",
        "## Source raw runs / PICA bundle refs",
    ]
    for path in run_paths:
        lines.append(f"- `{path}`")
    if pica_bundle_path is not None:
        lines.append(f"- `{pica_bundle_path}`")
    lines.extend(
        [
            "",
            "## Event algebra mode",
            f"- Event-basis mode: `{summary['event_basis_mode']}`",
            f"- Event-algebra mode: `{summary['event_algebra_mode']}`",
            f"- Max full-powerset atom count: `{summary['max_full_powerset_atom_count']}`",
            "",
            "## Full-vs-truncated policy",
            f"- `max_union_size`: `{discovered_event_family.thresholds.max_union_size}`",
            f"- `min_event_support_count`: `{discovered_event_family.thresholds.min_event_support_count}`",
            f"- `min_event_support_fraction`: `{discovered_event_family.thresholds.min_event_support_fraction}`",
            f"- Complete contexts: `{sum(1 for context in event_algebra_coverage.contexts if context.event_algebra_complete)}` / `{len(event_algebra_coverage.contexts)}`",
            "",
            "## Threshold configuration",
            f"- Inference mode: `{summary['inference_mode']}`",
            f"- `min_common_probes`: `{candidates.thresholds.min_common_probes}`",
            f"- `min_conditioning_count`: `{candidates.thresholds.min_conditioning_count}`",
            f"- `min_probe_atom_support_count`: `{candidates.thresholds.min_probe_atom_support_count}`",
            f"- `max_mean_tv`: `{candidates.thresholds.max_mean_tv}`",
            f"- `exact_tolerance`: `{candidates.thresholds.exact_tolerance}`",
            "",
            "## Structural rule",
            "- Admissible probe contexts come from the same preparation/protocol and exclude the two source contexts.",
            "- Structural acceptance requires equal probe-image events on all common structurally valid probes.",
            "- TV is retained only as secondary ranking and confidence metadata.",
            "",
            "## Candidate totals",
            f"- Total candidate pairs: `{summary['total_candidate_pair_count']}`",
            f"- Structurally valid candidate pairs: `{summary['structurally_valid_candidate_pair_count']}`",
            f"- Accepted candidate pairs: `{summary['accepted_candidate_pair_count']}`",
            f"- Insufficient-data candidate pairs: `{summary['insufficient_data_candidate_pair_count']}`",
            f"- Generated singleton events: `{summary['generated_singleton_event_count']}`",
            f"- Generated proper coarse events: `{summary['generated_proper_coarse_event_count']}`",
            f"- Generated empty/full events: `{summary['generated_empty_full_event_count']}`",
            f"- Match-eligible events: `{summary['total_match_eligible_event_count']}`",
            f"- Accepted shared-event proposals: `{summary['accepted_shared_event_proposal_count']}`",
            f"- Accepted singleton proposals: `{summary['accepted_singleton_proposal_count']}`",
            f"- Accepted coarse proposals: `{summary['accepted_coarse_proposal_count']}`",
            "",
            "## Completeness / coverage diagnostics",
        ]
    )
    for context in event_algebra_coverage.contexts:
        lines.append(
            f"- `{context.context_id}`: atom_count=`{context.atom_count}`, expected_full_event_count=`{context.expected_full_event_count}`, generated_event_count=`{context.generated_event_count}`, completeness=`{context.event_algebra_complete}`, coverage_fraction=`{context.coverage_fraction}`, generation_mode_used=`{context.generation_mode_used}`, truncation_reason=`{context.truncation_reason}`"
        )
    lines.extend(
        [
            "",
            "## Accepted shared-event proposals",
        ]
    )
    for proposal_id in candidates.diagnostics_summary.accepted_proposal_ids:
        lines.append(f"- `{proposal_id}`")
    if not candidates.diagnostics_summary.accepted_proposal_ids:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Secondary statistical summary",
            f"- Mean accepted TV: `{summary['mean_accepted_tv']}`",
            f"- Max accepted TV: `{summary['max_accepted_tv']}`",
            "",
            "## Weight / proposal policy",
            f"- Proposal constraint kind: `{summary['proposal_constraint_kind']}`",
            f"- Weight mapping rule: `{summary['weight_mapping_rule']}`",
            "",
            "## Built package validation",
            f"- Built event package validated: `{summary['built_package_validated']}`",
            f"- Package provenance validated: `{summary['package_provenance_validated']}`",
            "",
            "## Artifact references",
            f"- Discovered event family: `{output_paths['discovered_event_family']}`",
            f"- Event algebra coverage: `{output_paths['event_algebra_coverage']}`",
            f"- Probe-indistinguishability signatures: `{output_paths['signatures']}`",
            f"- Shared-event candidates: `{output_paths['candidates']}`",
            f"- Event package: `{output_paths['event_package']}`",
            f"- Package provenance: `{output_paths['provenance']}`",
            f"- Summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    discovered_event_family: DiscoveredEventFamily,
    event_package: EventPackageInstance,
    candidates: SharedEventCandidates,
    output_paths: dict[str, str],
) -> ResultNote:
    accepted_scores = _accepted_scores(candidates)
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[event_package.instance_id],
        metrics={
            "accepted_context_count": len(event_package.contexts),
            "generated_singleton_event_count": discovered_event_family.diagnostics_summary.generated_singleton_event_count,
            "generated_proper_coarse_event_count": discovered_event_family.diagnostics_summary.generated_proper_coarse_event_count,
            "generated_empty_event_count": discovered_event_family.diagnostics_summary.generated_empty_event_count,
            "generated_full_event_count": discovered_event_family.diagnostics_summary.generated_full_event_count,
            "match_eligible_event_count": discovered_event_family.diagnostics_summary.match_eligible_event_count,
            "total_candidate_pair_count": candidates.diagnostics_summary.total_candidate_pair_count,
            "structurally_valid_candidate_pair_count": candidates.diagnostics_summary.structurally_valid_candidate_pair_count,
            "accepted_candidate_pair_count": candidates.diagnostics_summary.accepted_candidate_pair_count,
            "insufficient_data_candidate_pair_count": candidates.diagnostics_summary.insufficient_data_candidate_pair_count,
            "accepted_shared_event_proposal_count": len(
                event_package.equality_proposals
            ),
            "accepted_coarse_proposal_count": _accepted_coarse_proposal_count(
                candidates
            ),
            "mean_accepted_tv": statistics.mean(accepted_scores)
            if accepted_scores
            else None,
            "max_accepted_tv": max(accepted_scores) if accepted_scores else None,
        },
        interpretation=(
            "Shared-event inference used observable-conditioned probe signatures derived from discovered contexts, discovered event bases, and either raw substrate runs or PICA observable ledgers; hidden-state IDs were not used in event generation, candidate matching, thresholding, or proposal acceptance."
        ),
        caveats=[
            "Event algebra completeness is explicit; truncation modes are reported as incomplete rather than being presented as full Boolean algebras.",
            "Structural-primary mode accepts only probe-image matches; TV is secondary metadata.",
        ],
        artifact_refs={
            "discovered_event_family": output_paths["discovered_event_family"],
            "event_algebra_coverage": output_paths["event_algebra_coverage"],
            "probe_indistinguishability_signatures": output_paths["signatures"],
            "shared_event_candidates": output_paths["candidates"],
            "event_package": output_paths["event_package"],
            "package_provenance": output_paths["provenance"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
        },
        metadata={
            "observable_only": True,
            "event_basis_mode": discovered_event_family.thresholds.event_basis_mode,
            "event_algebra_mode": discovered_event_family.thresholds.event_algebra_mode,
            "inference_mode": candidates.inference_mode,
        },
    )


def _build_package_provenance(
    *,
    family: DiscoveredContextFamily,
    discovered_event_family: DiscoveredEventFamily,
    family_path: str,
    run_paths: list[str],
    pica_bundle_path: str | None,
    skeleton_path: str | None,
    discovered_event_family_path: str,
    candidates_path: str,
    event_package_path: str,
    event_package: EventPackageInstance,
    candidates: SharedEventCandidates,
) -> PackageProvenance:
    family_contexts = {
        context.context_id: context for context in family.accepted_contexts
    }
    source_artifacts = {
        "discovered_context_family": family_path,
        "discovered_event_family": discovered_event_family_path,
        "shared_event_candidates": candidates_path,
        **(
            {"pica_export_bundle": pica_bundle_path}
            if pica_bundle_path is not None
            else {}
        ),
        **{
            f"raw_substrate_run_{index}": path
            for index, path in enumerate(run_paths, start=1)
        },
        **(
            {"event_package_skeleton": skeleton_path}
            if skeleton_path is not None
            else {}
        ),
    }
    context_entries = [
        ContextProvenanceEntry(
            context_id=context.context_id,
            origin_kind="derived_context",
            source_refs=[
                ProvenanceSourceRef(
                    artifact=family_path,
                    source_kind="derived_context",
                    source_item_id=context.context_id,
                )
            ],
        )
        for context in event_package.contexts
    ]
    discovered_event_by_id = {
        event.event_id: event
        for context in discovered_event_family.contexts
        for event in context.events
    }
    event_entries: list[EventProvenanceEntry] = []
    for event in event_package.events:
        source_refs: list[ProvenanceSourceRef] = [
            ProvenanceSourceRef(
                artifact=discovered_event_family_path,
                source_kind="derived_event_basis",
                source_item_id=event.event_id,
            )
        ]
        if pica_bundle_path is not None and event.context_id in family_contexts:
            source_metadata = family_contexts[event.context_id].source_metadata
            if source_metadata is not None:
                source_refs.append(
                    ProvenanceSourceRef(
                        artifact=pica_bundle_path,
                        source_kind="pica_export_bundle",
                        source_item_id=event.context_id,
                        pica_ref={
                            "export_bundle_id": source_metadata.export_bundle_id,
                            "campaign_id": source_metadata.campaign_id,
                            "run_id": source_metadata.run_ids[0],
                            "observable_ledger_id": source_metadata.observable_ledger_ids[
                                0
                            ],
                            "closure_id": source_metadata.closure_id,
                            "lens_id": source_metadata.lens_id,
                            "level_id": source_metadata.level_id,
                            "resolution_id": source_metadata.resolution_id,
                            "preparation_id": source_metadata.preparation_id,
                            "protocol_id": source_metadata.protocol_id,
                            "protocol_step_id": source_metadata.protocol_step_id,
                            "step_index": source_metadata.step_index,
                        },
                    )
                )
        source_refs.extend(
            ProvenanceSourceRef(
                artifact=path,
                source_kind="raw_substrate_run",
            )
            for path in run_paths
        )
        if event.context_id in family_contexts and len(event.atom_ids) == 1:
            source_refs.append(
                ProvenanceSourceRef(
                    artifact=family_path,
                    source_kind="derived_atomic_outcome",
                    source_item_id=f"{event.context_id}::{event.atom_ids[0]}",
                )
            )
        discovered_event = discovered_event_by_id.get(event.event_id)
        event_entries.append(
            EventProvenanceEntry(
                event_id=event.event_id,
                origin_kind="derived_event",
                source_context_id=event.context_id,
                source_atom_ids=sorted(event.atom_ids),
                source_refs=source_refs,
                notes=(
                    []
                    if discovered_event is None
                    else [
                        f"event_kind:{discovered_event.event_kind}",
                        f"event_algebra_mode:{discovered_event_family.thresholds.event_algebra_mode or discovered_event_family.thresholds.event_basis_mode}",
                        *(
                            ["coarse_event_union_of_retained_atoms"]
                            if discovered_event.event_kind == "proper_coarse"
                            else []
                        ),
                        *(
                            ["empty_event_from_retained_atom_set"]
                            if discovered_event.event_kind == "empty"
                            else []
                        ),
                        *(
                            ["full_event_from_retained_atom_set"]
                            if discovered_event.event_kind == "full"
                            else []
                        ),
                    ]
                ),
            )
        )
    accepted_proposal_ids = set(candidates.diagnostics_summary.accepted_proposal_ids)
    accepted_rows_by_proposal_id = {
        row.proposed_proposal_id: row
        for row in candidates.candidate_rows
        if row.accepted and row.proposed_proposal_id is not None
    }
    proposal_entries: list[ProposalProvenanceEntry] = []
    for proposal in event_package.equality_proposals:
        source_refs: list[ProvenanceSourceRef] = []
        notes: list[str] = []
        if proposal.proposal_id in accepted_proposal_ids:
            source_refs.append(
                ProvenanceSourceRef(
                    artifact=candidates_path,
                    source_kind="derived_shared_event_match",
                    source_item_id=proposal.proposal_id,
                )
            )
            if pica_bundle_path is not None:
                source_refs.append(
                    ProvenanceSourceRef(
                        artifact=pica_bundle_path,
                        source_kind="pica_export_bundle",
                    )
                )
            source_refs.extend(
                ProvenanceSourceRef(
                    artifact=path,
                    source_kind="raw_substrate_run",
                )
                for path in run_paths
            )
            row = accepted_rows_by_proposal_id.get(proposal.proposal_id)
            if row is not None:
                notes = [
                    f"inference_mode:{candidates.inference_mode}",
                    f"left_event_id:{row.left_event_id}",
                    f"right_event_id:{row.right_event_id}",
                    *[
                        f"common_probe_id:{probe_id}"
                        for probe_id in row.common_probe_ids
                    ],
                    *[
                        f"left_source_atom_id:{atom_id}"
                        for atom_id in row.left_event_atom_ids
                    ],
                    *[
                        f"right_source_atom_id:{atom_id}"
                        for atom_id in row.right_event_atom_ids
                    ],
                ]
        elif skeleton_path is not None:
            source_refs.append(
                ProvenanceSourceRef(
                    artifact=skeleton_path,
                    source_kind="derived_skeleton_proposal",
                    source_item_id=proposal.proposal_id,
                )
            )
        proposal_entries.append(
            ProposalProvenanceEntry(
                proposal_id=proposal.proposal_id,
                origin_kind="derived_proposal",
                source_refs=source_refs,
                notes=notes,
            )
        )
    return PackageProvenance(
        provenance_format_version="package-provenance.v1",
        package_artifact=event_package_path,
        package_id=event_package.instance_id,
        provenance_mode="derived",
        source_artifacts=source_artifacts,
        context_entries=context_entries,
        event_entries=event_entries,
        proposal_entries=proposal_entries,
        metadata={
            "observable_only": True,
            "event_basis_mode": discovered_event_family.thresholds.event_basis_mode,
            "event_algebra_mode": discovered_event_family.thresholds.event_algebra_mode,
        },
    )


def write_package_build_report(
    *,
    family_path: str | Path,
    run_paths: list[str | Path] | None = None,
    pica_bundle_path: str | Path | None = None,
    skeleton_path: str | Path | None = None,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
    thresholds: SharedEventInferenceThresholds | None = None,
    event_thresholds: DiscoveredEventGenerationThresholds | None = None,
    source_pair_filter: Callable[[AcceptedContext, AcceptedContext], bool]
    | None = None,
) -> PackageBuildReportArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    family_relpath = repo_relative_path(family_path, root=effective_root)
    run_relpaths = (
        [repo_relative_path(path, root=effective_root) for path in run_paths]
        if run_paths is not None
        else []
    )
    pica_bundle_relpath = (
        repo_relative_path(pica_bundle_path, root=effective_root)
        if pica_bundle_path is not None
        else None
    )

    family = load_discovered_context_family(family_path)
    effective_pica_bundle_path = (
        pica_bundle_path
        if pica_bundle_path is not None
        else family.source_bundle_artifact
    )
    effective_pica_bundle_relpath = (
        pica_bundle_relpath
        if pica_bundle_relpath is not None
        else (
            repo_relative_path(effective_pica_bundle_path, root=effective_root)
            if effective_pica_bundle_path is not None
            else None
        )
    )
    runs = load_substrate_run_files(run_paths) if run_paths is not None else None
    effective_skeleton_path = (
        skeleton_path
        if skeleton_path is not None
        else family.event_package_skeleton_artifact
    )
    skeleton = (
        load_discovered_event_package_skeleton(effective_skeleton_path)
        if effective_skeleton_path is not None
        else None
    )
    skeleton_relpath = (
        repo_relative_path(effective_skeleton_path, root=effective_root)
        if effective_skeleton_path is not None
        else None
    )

    built = build_package_from_discovery(
        family,
        runs,
        pica_bundle_path=effective_pica_bundle_path,
        thresholds=thresholds or DEFAULT_SHARED_EVENT_INFERENCE_THRESHOLDS,
        event_thresholds=event_thresholds,
        inference_id=f"infer_{run_id}",
        source_discovered_context_family_artifact=family_relpath,
        source_run_artifacts=run_relpaths,
        skeleton=skeleton,
        created_at=manifest_timestamp,
        source_pair_filter=source_pair_filter,
    )

    discovered_event_family_path = run_dir / "discovered-event-family.json"
    event_algebra_coverage_path = run_dir / "event-algebra-coverage.json"
    signatures_path = run_dir / "probe-indistinguishability-signatures.json"
    candidates_path = run_dir / "shared-event-candidates.json"
    event_package_path = run_dir / "event-package.json"
    provenance_path = run_dir / "package-provenance.json"
    summary_path = run_dir / "package-build-summary.json"
    note_path = run_dir / "package-build-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "discovered_event_family": repo_relative_path(
            discovered_event_family_path, root=effective_root
        ),
        "event_algebra_coverage": repo_relative_path(
            event_algebra_coverage_path, root=effective_root
        ),
        "signatures": repo_relative_path(signatures_path, root=effective_root),
        "candidates": repo_relative_path(candidates_path, root=effective_root),
        "event_package": repo_relative_path(event_package_path, root=effective_root),
        "provenance": repo_relative_path(provenance_path, root=effective_root),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }
    discovered_event_family = built.discovered_event_family.model_copy(
        update={"built_event_package_artifact": output_paths["event_package"]}
    )
    signatures = built.signatures
    candidates = built.candidates.model_copy(
        update={"built_event_package_artifact": output_paths["event_package"]}
    )
    event_algebra_coverage = build_event_algebra_coverage(
        source_discovered_context_family_artifact=family_relpath,
        thresholds=discovered_event_family.thresholds,
        contexts=discovered_event_family.contexts,
    )
    weight_mapping_rule = "weight = max(0.1, 1 - approx_score)"
    summary = _build_summary(
        family_path=family_relpath,
        run_paths=run_relpaths,
        pica_bundle_path=effective_pica_bundle_relpath,
        skeleton_path=skeleton_relpath,
        discovered_event_family_path=output_paths["discovered_event_family"],
        event_algebra_coverage_path=output_paths["event_algebra_coverage"],
        signatures_path=output_paths["signatures"],
        candidates_path=output_paths["candidates"],
        event_package_path=output_paths["event_package"],
        provenance_path=output_paths["provenance"],
        discovered_event_family=discovered_event_family,
        event_algebra_coverage=event_algebra_coverage,
        candidates=candidates,
        event_package=built.event_package,
        weight_mapping_rule=weight_mapping_rule,
    )
    provenance = _build_package_provenance(
        family=family,
        discovered_event_family=discovered_event_family,
        family_path=family_relpath,
        run_paths=run_relpaths,
        pica_bundle_path=effective_pica_bundle_relpath,
        skeleton_path=skeleton_relpath,
        discovered_event_family_path=output_paths["discovered_event_family"],
        candidates_path=output_paths["candidates"],
        event_package_path=output_paths["event_package"],
        event_package=built.event_package,
        candidates=candidates,
    )
    discovered_event_family_path.write_text(
        json.dumps(
            discovered_event_family.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    event_algebra_coverage_path.write_text(
        json.dumps(
            event_algebra_coverage.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    signatures_path.write_text(
        json.dumps(signatures.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    candidates_path.write_text(
        json.dumps(candidates.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    event_package_path.write_text(
        json.dumps(
            built.event_package.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    provenance_path.write_text(
        json.dumps(
            provenance.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(
        _render_note(
            family_path=family_relpath,
            run_paths=run_relpaths,
            pica_bundle_path=effective_pica_bundle_relpath,
            discovered_event_family=discovered_event_family,
            event_algebra_coverage=event_algebra_coverage,
            candidates=candidates,
            summary=summary,
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        discovered_event_family=discovered_event_family,
        event_package=built.event_package,
        candidates=candidates,
        output_paths=output_paths,
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
            "substrates",
            "build-event-package",
            family_relpath,
            *sum((["--raw-run", path] for path in run_relpaths), []),
            *(
                ["--pica-bundle", effective_pica_bundle_relpath]
                if effective_pica_bundle_relpath is not None
                else []
            ),
        ],
        seed=seed,
        input_artifacts={
            "discovered_context_family": family_relpath,
            **{
                f"substrate_run_{index}": path
                for index, path in enumerate(run_relpaths, start=1)
            },
            **(
                {"pica_export_bundle": effective_pica_bundle_relpath}
                if effective_pica_bundle_relpath is not None
                else {}
            ),
            **(
                {"event_package_skeleton_input": skeleton_relpath}
                if skeleton_relpath is not None
                else {}
            ),
        },
        output_artifacts={
            "discovered_event_family": output_paths["discovered_event_family"],
            "event_algebra_coverage": output_paths["event_algebra_coverage"],
            "probe_indistinguishability_signatures": output_paths["signatures"],
            "shared_event_candidates": output_paths["candidates"],
            "event_package": output_paths["event_package"],
            "package_provenance": output_paths["provenance"],
            "package_build_summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "package_build",
            "accepted_context_count": len(built.event_package.contexts),
            "inference_mode": candidates.inference_mode,
            "event_basis_mode": discovered_event_family.thresholds.event_basis_mode,
            "event_algebra_mode": discovered_event_family.thresholds.event_algebra_mode,
            "event_algebra_complete": all(
                bool(context.event_algebra_complete)
                for context in discovered_event_family.contexts
            ),
            "accepted_singleton_event_count": discovered_event_family.diagnostics_summary.accepted_singleton_event_count,
            "accepted_coarse_event_count": discovered_event_family.diagnostics_summary.accepted_coarse_event_count,
            "generated_empty_event_count": discovered_event_family.diagnostics_summary.generated_empty_event_count,
            "generated_full_event_count": discovered_event_family.diagnostics_summary.generated_full_event_count,
            "match_eligible_event_count": discovered_event_family.diagnostics_summary.match_eligible_event_count,
            "structurally_valid_candidate_pair_count": candidates.diagnostics_summary.structurally_valid_candidate_pair_count,
            "accepted_shared_event_proposal_count": len(
                built.event_package.equality_proposals
            ),
            "observable_only": True,
            "proposal_constraint_kind": candidates.thresholds.proposal_constraint_kind,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return PackageBuildReportArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=output_paths["manifest"],
        discovered_event_family_path=output_paths["discovered_event_family"],
        event_algebra_coverage_path=output_paths["event_algebra_coverage"],
        signatures_path=output_paths["signatures"],
        candidates_path=output_paths["candidates"],
        event_package_path=output_paths["event_package"],
        provenance_path=output_paths["provenance"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        discovered_event_family=discovered_event_family,
        event_algebra_coverage=event_algebra_coverage,
        signatures=signatures,
        candidates=candidates,
        event_package=built.event_package,
    )
