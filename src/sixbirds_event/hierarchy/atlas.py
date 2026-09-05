from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from pathlib import Path
import sys
from typing import Any

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
from .models import (
    BestEvidenceByAxis,
    BestEvidenceEntry,
    ClaimStrengthRegistry,
    ClaimStrengthRegistryEntry,
    ThreeAxisHierarchyConfig,
    ThreeAxisHierarchyResults,
    ThreeAxisHierarchyRow,
    hierarchy_claim_level_rank,
)


@dataclass(slots=True)
class ThreeAxisHierarchyArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    table_csv_path: str
    claim_strength_registry_path: str
    best_evidence_by_axis_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    strongest_axis: str
    results: ThreeAxisHierarchyResults


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _resolve_repo_artifact(path: str | Path, *, root: Path) -> Path:
    candidate = root / path
    if candidate.exists():
        return candidate
    canonical_root = get_repo_root()
    fallback = canonical_root / path
    if fallback.exists():
        return fallback
    return candidate


def _load_json(path: str | Path, *, root: Path) -> dict[str, Any]:
    resolved = _resolve_repo_artifact(path, root=root)
    return json.loads(resolved.read_text(encoding="utf-8"))


def _artifact_ref(path: str | Path) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return repo_relative_path(candidate, root=get_repo_root())
    return candidate.as_posix()


def load_three_axis_hierarchy_config(path: str | Path) -> ThreeAxisHierarchyConfig:
    model = load_model(path, kind="three-axis-hierarchy-config")
    assert isinstance(model, ThreeAxisHierarchyConfig)
    return model


def _count_regime_statuses(regimes: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "accepted_proposal_obstruction": 0,
        "candidate_subset_quotient_witness": 0,
        "no_quotient_obstruction": 0,
    }
    for regime in regimes:
        status = regime.get("quotient_witness_status")
        if status in counts:
            counts[status] += 1
    return counts


def _max_claim_level(claim_counts: dict[str, int]) -> str:
    if not claim_counts:
        raise ValueError("claim_counts must not be empty")
    return max(
        claim_counts,
        key=lambda level: (hierarchy_claim_level_rank(level), claim_counts[level]),
    )


def _mechanism_axis_row(
    *,
    config: ThreeAxisHierarchyConfig,
    root: Path,
) -> tuple[ThreeAxisHierarchyRow, ClaimStrengthRegistryEntry, BestEvidenceEntry]:
    campaign_summary = _load_json(config.mechanism_campaign_summary_ref, root=root)
    witness_summary = _load_json(config.mechanism_witness_summary_ref, root=root)
    witness_status = witness_summary["witness_classification"]
    claim_level = _max_claim_level(campaign_summary["counts_by_claim_level"])
    campaign_outcome_kind = (
        "design_inadequate"
        if campaign_summary.get("design_inadequate")
        else "negative_result"
    )
    primary_refs = {
        "campaign_summary": config.mechanism_campaign_summary_ref,
        "witness_summary": config.mechanism_witness_summary_ref,
    }
    supporting_refs = {
        "campaign_table": config.mechanism_campaign_table_ref,
        "campaign_outcome": (
            Path(config.mechanism_campaign_summary_ref)
            .with_name("design-inadequate-result.json")
            .as_posix()
        ),
    }
    caveat_flags = [
        "campaign_design_inadequate",
        "committed_witness_outside_axis_wide_campaign_success",
        "claim_ceiling_below_same_system_theorem_level",
    ]
    row = ThreeAxisHierarchyRow(
        row_format_version="three-axis-hierarchy-row.v1",
        row_id="axis_mechanism",
        hierarchy_id=config.hierarchy_id,
        axis="mechanism",
        axis_campaign_outcome_kind=campaign_outcome_kind,
        axis_campaign_outcome_label="design_inadequate_campaign_with_committed_witness",
        best_evidence_type="committed_witness_case",
        best_witness_label="exp104_p6_row_all_n64_seed0",
        best_witness_status=witness_status,
        accepted_proposal_obstruction_count=(
            1 if witness_status == "accepted_proposal_obstruction" else 0
        ),
        candidate_subset_quotient_witness_count=(
            1 if witness_status == "candidate_subset_quotient_witness" else 0
        ),
        no_quotient_obstruction_count=(
            1 if witness_status == "no_quotient_obstruction" else 0
        ),
        claim_level_supported=claim_level,
        caveat_flags=caveat_flags,
        primary_artifact_refs=primary_refs,
        supporting_artifact_refs=supporting_refs,
        notes=[
            "The mechanism-axis campaign remained design_inadequate.",
            "A committed quotient-backed accepted obstruction witness exists on EXP-104 / P6_row_all / n=64 / seed 0.",
            "The axis claim ceiling remains below same-system theorem-level obstruction.",
        ],
        flags=["campaign_inadequate", "committed_witness_present"],
    )
    claim_entry = ClaimStrengthRegistryEntry(
        claim_id="mechanism_axis_regime_dependence_with_committed_witness",
        axis="mechanism",
        claim_level=claim_level,
        best_evidence_row_id=row.row_id,
        primary_artifact_refs=primary_refs,
        supporting_artifact_refs=supporting_refs,
        caveat_flags=caveat_flags,
        notes=[
            "Best evidence is a committed witness case rather than an axis-wide successful mechanism campaign."
        ],
    )
    evidence_entry = BestEvidenceEntry(
        axis="mechanism",
        best_evidence_type="committed_witness_case",
        best_evidence_status=witness_status,
        primary_artifact_refs=primary_refs,
        supporting_artifact_refs=supporting_refs,
        reason_for_selection=(
            "The EXP-104 committed witness is the strongest current mechanism-side quotient-backed evidence despite the design-inadequate campaign outcome."
        ),
        caveat_flags=caveat_flags,
        notes=["Mechanism evidence is preserved separately from the campaign outcome."],
    )
    return row, claim_entry, evidence_entry


def _lens_axis_row(
    *,
    config: ThreeAxisHierarchyConfig,
    root: Path,
) -> tuple[ThreeAxisHierarchyRow, ClaimStrengthRegistryEntry, BestEvidenceEntry]:
    final_summary = _load_json(config.lens_final_summary_ref, root=root)
    regime_counts = _count_regime_statuses(final_summary["regimes"])
    primary_refs = {
        "final_summary": config.lens_final_summary_ref,
        "flagship_quotient_summary": final_summary[
            "cross_resolution_quotient_summary_artifact"
        ],
    }
    supporting_refs = {
        "same_step_negative_summary": final_summary[
            "same_step_negative_summary_artifact"
        ],
        "same_step_negative_outcome": final_summary[
            "same_step_negative_outcome_artifact"
        ],
        "same_step_table": final_summary["same_step_table_artifact"],
    }
    caveat_flags = [
        "same_step_bounded_negative_subregime_preserved",
        "cross_resolution_strict_extension_flagship",
    ]
    row = ThreeAxisHierarchyRow(
        row_format_version="three-axis-hierarchy-row.v1",
        row_id="axis_lens",
        hierarchy_id=config.hierarchy_id,
        axis="lens",
        axis_campaign_outcome_kind="finalized_axis_closure",
        axis_campaign_outcome_label=final_summary["final_axis_status"],
        best_evidence_type="canonical_flagship_regime",
        best_witness_label=final_summary["canonical_flagship_case_id"],
        best_witness_status=(
            "accepted_proposal_obstruction"
            if final_summary["accepted_proposal_obstruction"]
            else "candidate_subset_quotient_witness"
        ),
        accepted_proposal_obstruction_count=regime_counts[
            "accepted_proposal_obstruction"
        ],
        candidate_subset_quotient_witness_count=regime_counts[
            "candidate_subset_quotient_witness"
        ],
        no_quotient_obstruction_count=regime_counts["no_quotient_obstruction"],
        claim_level_supported=final_summary["final_claim_level"],
        caveat_flags=caveat_flags,
        primary_artifact_refs=primary_refs,
        supporting_artifact_refs=supporting_refs,
        notes=[
            "The same-step bounded-negative subregime remains part of the final lens-axis record.",
            "The cross-resolution strict-extension accepted obstruction is the canonical lens-axis flagship.",
            "The final lens-axis status is stronger than the mechanism axis.",
        ],
        flags=["axis_finalized", "cross_resolution_flagship"],
    )
    claim_entry = ClaimStrengthRegistryEntry(
        claim_id="lens_axis_cross_resolution_flagship_obstruction",
        axis="lens",
        claim_level=final_summary["final_claim_level"],
        best_evidence_row_id=row.row_id,
        primary_artifact_refs=primary_refs,
        supporting_artifact_refs=supporting_refs,
        caveat_flags=caveat_flags,
        notes=[
            "The accepted obstruction is lens-axis evidence under a cross-resolution strict-extension regime on fixed mechanism and support."
        ],
    )
    evidence_entry = BestEvidenceEntry(
        axis="lens",
        best_evidence_type="canonical_flagship_regime",
        best_evidence_status="accepted_proposal_obstruction",
        primary_artifact_refs=primary_refs,
        supporting_artifact_refs=supporting_refs,
        reason_for_selection=(
            "The finalized cross-resolution flagship is the strongest current same-system lens-axis evidence and preserves the earlier same-step bounded-negative subregime."
        ),
        caveat_flags=caveat_flags,
        notes=["Lens evidence is summarized as a two-regime closure result."],
    )
    return row, claim_entry, evidence_entry


def _packaging_axis_row(
    *,
    config: ThreeAxisHierarchyConfig,
    root: Path,
) -> tuple[ThreeAxisHierarchyRow, ClaimStrengthRegistryEntry, BestEvidenceEntry]:
    campaign_summary = _load_json(config.packaging_campaign_summary_ref, root=root)
    campaign_table = _load_json(config.packaging_campaign_table_ref, root=root)
    best_candidate = _load_json(config.packaging_best_candidate_ref, root=root)
    best_point_id = best_candidate["best_point_id"]
    row_payload = next(
        row for row in campaign_table["rows"] if row["point_id"] == best_point_id
    )
    quotient_counts = campaign_summary["counts_by_quotient_witness_status"]
    campaign_outcome_kind = "best_candidate"
    if campaign_summary.get("design_inadequate"):
        campaign_outcome_kind = "design_inadequate"
    elif campaign_summary.get("negative_result"):
        campaign_outcome_kind = "negative_result"
    primary_refs = {
        "campaign_summary": config.packaging_campaign_summary_ref,
        "best_candidate": config.packaging_best_candidate_ref,
        "flagship_quotient_summary": (
            Path(config.packaging_campaign_summary_ref).parent
            / f"{best_point_id}_quotient-feasibility-summary.json"
        ).as_posix(),
    }
    supporting_refs = {
        "campaign_table": config.packaging_campaign_table_ref,
        "package_conflict_diagnostics": (
            Path(config.packaging_campaign_summary_ref).parent
            / "package-conflict-diagnostics.json"
        ).as_posix(),
        "quotient_feasibility_diagnostics": (
            Path(config.packaging_campaign_summary_ref).parent
            / "quotient-feasibility-diagnostics.json"
        ).as_posix(),
    }
    caveat_flags = [
        "selector_branch_divergence",
        "fixed_operator_family_source",
        "not_broad_multi_family_packaging_landscape",
    ]
    row = ThreeAxisHierarchyRow(
        row_format_version="three-axis-hierarchy-row.v1",
        row_id="axis_packaging",
        hierarchy_id=config.hierarchy_id,
        axis="packaging",
        axis_campaign_outcome_kind=campaign_outcome_kind,
        axis_campaign_outcome_label="best_candidate_with_packaging_caveat",
        best_evidence_type="campaign_best_candidate",
        best_witness_label=best_point_id,
        best_witness_status=row_payload["quotient_witness_status"],
        accepted_proposal_obstruction_count=quotient_counts.get(
            "accepted_proposal_obstruction", 0
        ),
        candidate_subset_quotient_witness_count=quotient_counts.get(
            "candidate_subset_quotient_witness", 0
        ),
        no_quotient_obstruction_count=quotient_counts.get("no_quotient_obstruction", 0),
        claim_level_supported=row_payload["claim_level_supported"],
        caveat_flags=caveat_flags,
        primary_artifact_refs=primary_refs,
        supporting_artifact_refs=supporting_refs,
        notes=[
            "The bounded packaging-axis campaign produced a strong accepted candidate.",
            "The flagship packaging result is currently the strongest axis-level evidence in the repo.",
            "The current packaging flagship is driven by selector-branch divergence on fixed operator/family/source.",
        ],
        flags=["campaign_best_candidate", "selector_branch_flagship"],
    )
    claim_entry = ClaimStrengthRegistryEntry(
        claim_id="packaging_axis_selector_branch_flagship_obstruction",
        axis="packaging",
        claim_level=row_payload["claim_level_supported"],
        best_evidence_row_id=row.row_id,
        primary_artifact_refs=primary_refs,
        supporting_artifact_refs=supporting_refs,
        caveat_flags=caveat_flags,
        notes=[
            "The accepted obstruction is packaging-axis evidence, but the current landscape is still selector-branch-driven on fixed operator/family/source."
        ],
    )
    evidence_entry = BestEvidenceEntry(
        axis="packaging",
        best_evidence_type="campaign_best_candidate",
        best_evidence_status=row_payload["quotient_witness_status"],
        primary_artifact_refs=primary_refs,
        supporting_artifact_refs=supporting_refs,
        reason_for_selection=(
            "The packaging-axis campaign itself produced a provenance-admissible accepted obstruction candidate, currently the strongest axis-level result."
        ),
        caveat_flags=caveat_flags,
        notes=["Packaging evidence must keep the selector-branch caveat visible."],
    )
    return row, claim_entry, evidence_entry


def _comparison_rows(rows: list[ThreeAxisHierarchyRow]) -> list[dict[str, object]]:
    return [
        {
            "axis": row.axis,
            "campaign_outcome": row.axis_campaign_outcome_label,
            "campaign_outcome_kind": row.axis_campaign_outcome_kind,
            "best_evidence_type": row.best_evidence_type,
            "best_witness_label": row.best_witness_label,
            "best_witness_status": row.best_witness_status,
            "accepted_proposal_obstruction_count": row.accepted_proposal_obstruction_count,
            "candidate_subset_quotient_witness_count": row.candidate_subset_quotient_witness_count,
            "no_quotient_obstruction_count": row.no_quotient_obstruction_count,
            "claim_level_supported": row.claim_level_supported,
            "caveat_flags": "|".join(row.caveat_flags),
        }
        for row in rows
    ]


def _figure_axis_rows(rows: list[ThreeAxisHierarchyRow]) -> list[dict[str, object]]:
    return [
        {
            "axis": row.axis,
            "campaign_outcome": row.axis_campaign_outcome_label,
            "best_witness_status": row.best_witness_status,
            "accepted_obstruction_present": row.accepted_proposal_obstruction_count > 0,
            "candidate_subset_witness_present": (
                row.candidate_subset_quotient_witness_count > 0
            ),
            "claim_level": row.claim_level_supported,
            "caveat_count": len(row.caveat_flags),
        }
        for row in rows
    ]


def _figure_quotient_rows(rows: list[ThreeAxisHierarchyRow]) -> list[dict[str, object]]:
    return [
        {
            "axis": row.axis,
            "accepted_proposal_obstruction_count": row.accepted_proposal_obstruction_count,
            "candidate_subset_witness_count": row.candidate_subset_quotient_witness_count,
            "no_witness_count": row.no_quotient_obstruction_count,
            "flagship_witness_label": row.best_witness_label,
        }
        for row in rows
    ]


def _figure_claim_rows(rows: list[ThreeAxisHierarchyRow]) -> list[dict[str, object]]:
    return [
        {
            "axis": row.axis,
            "claim_level": row.claim_level_supported,
            "best_evidence_label": row.best_witness_label,
            "caveat_flag": bool(row.caveat_flags),
            "axis_wide_outcome": row.axis_campaign_outcome_label,
        }
        for row in rows
    ]


def _build_note(
    *,
    results: ThreeAxisHierarchyResults,
    best_evidence: BestEvidenceByAxis,
    output_paths: dict[str, str],
) -> str:
    row_map = {row.axis: row for row in results.rows}
    lines = [
        "# Three-axis hierarchy atlas",
        "",
        "## Source outputs",
        "- TH3 mechanism-axis campaign summary plus committed EXP-104 quotient witness",
        "- TH4 lens-axis finalization summary with preserved same-step negative subregime",
        "- TH5 packaging-axis campaign summary and best-candidate artifact",
        "",
        "## Axis campaign outcomes",
        f"- mechanism: `{row_map['mechanism'].axis_campaign_outcome_label}`",
        f"- lens: `{row_map['lens'].axis_campaign_outcome_label}`",
        f"- packaging: `{row_map['packaging'].axis_campaign_outcome_label}`",
        "",
        "## Best witness / flagship by axis",
        f"- mechanism: `{row_map['mechanism'].best_witness_label}` / `{row_map['mechanism'].best_witness_status}`",
        f"- lens: `{row_map['lens'].best_witness_label}` / `{row_map['lens'].best_witness_status}`",
        f"- packaging: `{row_map['packaging'].best_witness_label}` / `{row_map['packaging'].best_witness_status}`",
        "",
        "## Quotient-feasibility status by axis",
        f"- mechanism: accepted={row_map['mechanism'].accepted_proposal_obstruction_count}, candidate={row_map['mechanism'].candidate_subset_quotient_witness_count}, none={row_map['mechanism'].no_quotient_obstruction_count}",
        f"- lens: accepted={row_map['lens'].accepted_proposal_obstruction_count}, candidate={row_map['lens'].candidate_subset_quotient_witness_count}, none={row_map['lens'].no_quotient_obstruction_count}",
        f"- packaging: accepted={row_map['packaging'].accepted_proposal_obstruction_count}, candidate={row_map['packaging'].candidate_subset_quotient_witness_count}, none={row_map['packaging'].no_quotient_obstruction_count}",
        "",
        "## Claim levels",
        f"- mechanism: `{row_map['mechanism'].claim_level_supported}`",
        f"- lens: `{row_map['lens'].claim_level_supported}`",
        f"- packaging: `{row_map['packaging'].claim_level_supported}`",
        "",
        "## Main caveats",
        f"- mechanism: `{'`, `'.join(row_map['mechanism'].caveat_flags)}`",
        f"- lens: `{'`, `'.join(row_map['lens'].caveat_flags)}`",
        f"- packaging: `{'`, `'.join(row_map['packaging'].caveat_flags)}`",
        "",
        "## Comparative conclusion",
        f"- Strongest current axis: `{results.strongest_current_axis}`",
        "- Mechanism preserves the distinction between a design-inadequate campaign and a committed witness case.",
        "- Lens preserves both the bounded same-step negative subregime and the cross-resolution accepted-obstruction flagship.",
        "- Packaging currently carries the strongest axis-level accepted obstruction evidence, with the selector-branch caveat still explicit.",
        "",
        "## Artifacts",
    ]
    for key, value in sorted(output_paths.items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Best evidence map",
        ]
    )
    for entry in best_evidence.entries:
        lines.append(
            f"- {entry.axis}: `{entry.best_evidence_type}` / `{entry.best_evidence_status}`"
        )
    return "\n".join(lines) + "\n"


def build_three_axis_hierarchy(
    *,
    config_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> ThreeAxisHierarchyArtifacts:
    output_root = get_repo_root(root)
    config = load_three_axis_hierarchy_config(
        _resolve_repo_artifact(config_path, root=output_root)
    )

    mechanism_row, mechanism_claim, mechanism_evidence = _mechanism_axis_row(
        config=config, root=output_root
    )
    lens_row, lens_claim, lens_evidence = _lens_axis_row(
        config=config, root=output_root
    )
    packaging_row, packaging_claim, packaging_evidence = _packaging_axis_row(
        config=config, root=output_root
    )

    rows = [mechanism_row, lens_row, packaging_row]
    claim_level_ordering = [
        row.axis
        for row in sorted(
            rows,
            key=lambda row: hierarchy_claim_level_rank(row.claim_level_supported),
            reverse=True,
        )
    ]
    strongest_current_axis = claim_level_ordering[0]

    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or config.output_label or config.hierarchy_id,
        timestamp=timestamp,
        root=output_root,
    )
    summary_path = run_dir / "three-axis-hierarchy-summary.json"
    table_csv_path = run_dir / "three-axis-hierarchy.csv"
    claim_registry_path = run_dir / "claim-strength-registry.json"
    best_evidence_path = run_dir / "best-evidence-by-axis.json"
    figure_axis_path = run_dir / "figure-axis-comparison.csv"
    figure_quotient_path = run_dir / "figure-quotient-status.csv"
    figure_claim_path = run_dir / "figure-claim-strength.csv"
    table_axis_summary_path = run_dir / "table-axis-summary.json"
    table_best_evidence_path = run_dir / "table-best-evidence.json"
    note_path = run_dir / "three-axis-hierarchy-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"

    output_paths = {
        "summary": repo_relative_path(summary_path, root=output_root),
        "table_csv": repo_relative_path(table_csv_path, root=output_root),
        "claim_strength_registry": repo_relative_path(
            claim_registry_path, root=output_root
        ),
        "best_evidence_by_axis": repo_relative_path(
            best_evidence_path, root=output_root
        ),
        "figure_axis_comparison": repo_relative_path(
            figure_axis_path, root=output_root
        ),
        "figure_quotient_status": repo_relative_path(
            figure_quotient_path, root=output_root
        ),
        "figure_claim_strength": repo_relative_path(
            figure_claim_path, root=output_root
        ),
        "table_axis_summary": repo_relative_path(
            table_axis_summary_path, root=output_root
        ),
        "table_best_evidence": repo_relative_path(
            table_best_evidence_path, root=output_root
        ),
        "note": repo_relative_path(note_path, root=output_root),
        "result_note": repo_relative_path(result_note_path, root=output_root),
        "manifest": repo_relative_path(manifest_path, root=output_root),
    }

    results = ThreeAxisHierarchyResults(
        table_format_version="three-axis-hierarchy-results.v1",
        hierarchy_id=config.hierarchy_id,
        row_count=len(rows),
        rows=rows,
        strongest_current_axis=strongest_current_axis,
        accepted_obstruction_exists_on_mechanism=(
            mechanism_row.accepted_proposal_obstruction_count > 0
        ),
        accepted_obstruction_exists_on_lens=(
            lens_row.accepted_proposal_obstruction_count > 0
        ),
        accepted_obstruction_exists_on_packaging=(
            packaging_row.accepted_proposal_obstruction_count > 0
        ),
        claim_level_ordering=claim_level_ordering,
        comparative_conclusions={
            "mechanism_campaign_inadequate_but_witness_present": True,
            "lens_preserves_dual_subregime_structure": True,
            "lens_supports_accepted_obstruction": True,
            "packaging_supports_accepted_obstruction": True,
            "packaging_is_strongest_current_axis": strongest_current_axis
            == "packaging",
            "mechanism_tension_does_not_disappear_up_axis": True,
        },
        output_paths=output_paths,
        notes=[
            "Campaign outcomes, best witnesses, and caveats remain separate for each axis.",
            "The hierarchy atlas is aggregation-first and does not rerun the underlying searches.",
        ],
        flags=["interim_hierarchy_closed", "quotient_backed_synthesis"],
        metadata={
            "mechanism_campaign_outcome_kind": mechanism_row.axis_campaign_outcome_kind,
            "lens_campaign_outcome_kind": lens_row.axis_campaign_outcome_kind,
            "packaging_campaign_outcome_kind": packaging_row.axis_campaign_outcome_kind,
        },
    )

    claim_registry = ClaimStrengthRegistry(
        registry_format_version="claim-strength-registry.v1",
        registry_id=f"{config.hierarchy_id}_claim_strength",
        entries=[mechanism_claim, lens_claim, packaging_claim],
        metadata={"strongest_current_axis": strongest_current_axis},
    )
    best_evidence = BestEvidenceByAxis(
        mapping_format_version="best-evidence-by-axis.v1",
        mapping_id=f"{config.hierarchy_id}_best_evidence",
        entries=[mechanism_evidence, lens_evidence, packaging_evidence],
        metadata={"strongest_current_axis": strongest_current_axis},
    )

    _write_json(summary_path, results.model_dump(mode="json"))
    _write_csv(table_csv_path, _comparison_rows(rows))
    _write_json(claim_registry_path, claim_registry.model_dump(mode="json"))
    _write_json(best_evidence_path, best_evidence.model_dump(mode="json"))
    _write_csv(figure_axis_path, _figure_axis_rows(rows))
    _write_csv(figure_quotient_path, _figure_quotient_rows(rows))
    _write_csv(figure_claim_path, _figure_claim_rows(rows))
    _write_json(
        table_axis_summary_path,
        {
            "hierarchy_id": config.hierarchy_id,
            "rows": [row.model_dump(mode="json") for row in rows],
            "strongest_current_axis": strongest_current_axis,
            "claim_level_ordering": claim_level_ordering,
        },
    )
    _write_json(
        table_best_evidence_path,
        {
            "hierarchy_id": config.hierarchy_id,
            "entries": [
                entry.model_dump(mode="json") for entry in best_evidence.entries
            ],
        },
    )
    note_path.write_text(
        _build_note(
            results=results, best_evidence=best_evidence, output_paths=output_paths
        ),
        encoding="utf-8",
    )

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[config.hierarchy_id, "mechanism", "lens", "packaging"],
        metrics={
            "accepted_obstruction_axis_count": sum(
                int(value)
                for value in [
                    results.accepted_obstruction_exists_on_mechanism,
                    results.accepted_obstruction_exists_on_lens,
                    results.accepted_obstruction_exists_on_packaging,
                ]
            ),
            "strongest_axis_is_packaging": strongest_current_axis == "packaging",
            "mechanism_campaign_design_inadequate": (
                mechanism_row.axis_campaign_outcome_kind == "design_inadequate"
            ),
            "lens_accepted_obstruction_present": (
                lens_row.accepted_proposal_obstruction_count > 0
            ),
            "packaging_accepted_obstruction_present": (
                packaging_row.accepted_proposal_obstruction_count > 0
            ),
            "packaging_caveat_count": len(packaging_row.caveat_flags),
        },
        interpretation=(
            "The interim three-axis hierarchy closes with mechanism preserving a committed witness despite a design-inadequate campaign, lens closed by a cross-resolution accepted-obstruction flagship with the same-step negative subregime preserved, and packaging carrying the strongest current accepted obstruction signal with an explicit selector-branch caveat."
        ),
        caveats=[
            "Mechanism campaign outcome and committed witness remain separate pieces of evidence.",
            "Lens-axis same-step bounded negative and cross-resolution flagship are distinct subregimes.",
            "Packaging-axis strongest evidence still carries a selector-branch-on-fixed-operator/family/source caveat.",
        ],
        artifact_refs=output_paths,
        metadata={
            "strongest_current_axis": strongest_current_axis,
            "mechanism_claim_level": mechanism_row.claim_level_supported,
            "lens_claim_level": lens_row.claim_level_supported,
            "packaging_claim_level": packaging_row.claim_level_supported,
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
            "hierarchy",
            "build-three-axis",
            str(config_path),
        ],
        seed=seed,
        input_artifacts={
            "hierarchy_config": _artifact_ref(config_path),
            "mechanism_campaign_summary": config.mechanism_campaign_summary_ref,
            "mechanism_campaign_table": config.mechanism_campaign_table_ref,
            "mechanism_witness_summary": config.mechanism_witness_summary_ref,
            "lens_final_summary": config.lens_final_summary_ref,
            "packaging_campaign_summary": config.packaging_campaign_summary_ref,
            "packaging_campaign_table": config.packaging_campaign_table_ref,
            "packaging_best_candidate": config.packaging_best_candidate_ref,
        },
        output_artifacts=output_paths,
        status="succeeded",
        git_commit=detect_git_commit(root=output_root),
        metadata={
            "hierarchy_id": config.hierarchy_id,
            "strongest_current_axis": strongest_current_axis,
            "claim_level_ordering": claim_level_ordering,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return ThreeAxisHierarchyArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=output_root),
        summary_path=output_paths["summary"],
        table_csv_path=output_paths["table_csv"],
        claim_strength_registry_path=output_paths["claim_strength_registry"],
        best_evidence_by_axis_path=output_paths["best_evidence_by_axis"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        strongest_axis=strongest_current_axis,
        results=results,
    )
