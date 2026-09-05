from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys

from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance
from ..schemas.result_note import ResultNote
from ..solvers.structural_deficit import (
    StructuralDeficitConfig,
    StructuralDeficitResult,
    solve_structural_deficit,
)
from ..solvers.structural_exact import (
    StructuralFeasibilityResult,
    solve_exact_structural_feasibility,
)
from ..validation import load_model


@dataclass(slots=True)
class StructuralReportSummary:
    instance_id: str
    run_id: str
    exact_extendable_hard_only: bool
    exact_extendable_all_proposals: bool
    gpd_str: float | None
    total_candidate_tuple_count: int
    hard_only_respecting_tuple_count: int
    all_proposals_respecting_tuple_count: int
    best_plan_respecting_tuple_count: int
    hard_only_enforced_proposal_ids: list[str]
    all_proposals_enforced_proposal_ids: list[str]
    relaxed_proposal_ids: list[str]
    relaxed_atoms: dict[str, list[str]]
    hard_only_uncovered_atoms: dict[str, list[str]]
    all_proposals_uncovered_atoms: dict[str, list[str]]
    blocking_explanation: dict[str, object]
    deficit_config: dict[str, float | bool]
    hard_only_witness_tuples: list[dict[str, str]] | None
    all_proposals_witness_tuples: list[dict[str, str]] | None
    best_fit_witness_tuples: list[dict[str, str]] | None
    instance_path: str
    output_paths: dict[str, str]


@dataclass(slots=True)
class StructuralReportArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    summary: StructuralReportSummary


def load_event_package_instance(
    path: str | Path,
) -> EventPackageInstance:
    model = load_model(path, kind="event-package-instance")
    assert isinstance(model, EventPackageInstance)
    return model


def _blocking_explanation(
    hard_only_result: StructuralFeasibilityResult,
    all_proposals_result: StructuralFeasibilityResult,
    deficit_result: StructuralDeficitResult,
) -> dict[str, object]:
    if all_proposals_result.feasible:
        return {
            "classification": "exact_extendable",
            "hard_only_reason": hard_only_result.reason,
            "all_proposals_reason": None,
            "relaxed_proposal_ids": [],
            "relaxed_atoms": {},
        }

    if deficit_result.relaxed_proposal_ids:
        classification = "relax_soft_proposal_restores_cover"
    elif all_proposals_result.reason == "no_respecting_tuples":
        classification = "no_respecting_tuples"
    else:
        classification = "coverage_failure"

    return {
        "classification": classification,
        "hard_only_reason": hard_only_result.reason,
        "all_proposals_reason": all_proposals_result.reason,
        "hard_only_uncovered_atoms": hard_only_result.uncovered_atoms,
        "all_proposals_uncovered_atoms": all_proposals_result.uncovered_atoms,
        "relaxed_proposal_ids": deficit_result.relaxed_proposal_ids,
        "relaxed_atoms": deficit_result.relaxed_atoms,
    }


def _render_structural_note(summary: StructuralReportSummary) -> str:
    hard_only_line = (
        "exactly extendable"
        if summary.exact_extendable_hard_only
        else "not exactly extendable"
    )
    all_proposals_line = (
        "exactly extendable"
        if summary.exact_extendable_all_proposals
        else "not exactly extendable"
    )
    best_witness_label = "best-fit witness from minimum-deficit plan"
    lines = [
        "# Structural Report",
        "",
        "## Instance",
        f"- Instance ID: `{summary.instance_id}`",
        f"- Run ID: `{summary.run_id}`",
        f"- Instance path: `{summary.instance_path}`",
        "",
        "## Exact feasibility",
        f"- Hard-only exact extendable: `{summary.exact_extendable_hard_only}`",
        f"- All-proposals exact extendable: `{summary.exact_extendable_all_proposals}`",
        f"- Hard-only exact feasibility status: `{hard_only_line}`",
        f"- All-proposals exact feasibility status: `{all_proposals_line}`",
        f"- Hard-only uncovered atoms: `{json.dumps(summary.hard_only_uncovered_atoms, sort_keys=True)}`",
        f"- All-proposals uncovered atoms: `{json.dumps(summary.all_proposals_uncovered_atoms, sort_keys=True)}`",
        "",
        "## Tuple counts",
        f"- Total candidate tuple count: `{summary.total_candidate_tuple_count}`",
        f"- Hard-only respecting tuple count: `{summary.hard_only_respecting_tuple_count}`",
        f"- All-proposals respecting tuple count: `{summary.all_proposals_respecting_tuple_count}`",
        f"- Best-plan respecting tuple count: `{summary.best_plan_respecting_tuple_count}`",
        "",
        "## Structural deficit",
        f"- `gpd_str`: `{summary.gpd_str}`",
        f"- Deficit config: `{summary.deficit_config}`",
        f"- Relaxed proposal IDs: `{summary.relaxed_proposal_ids}`",
        f"- Relaxed atoms: `{summary.relaxed_atoms}`",
        "",
        "## Blocking explanation",
        f"- Classification: `{summary.blocking_explanation['classification']}`",
        f"- Detail: `{json.dumps(summary.blocking_explanation, sort_keys=True)}`",
        "",
        "## Witness summary",
        f"- Hard-only witness: `{summary.hard_only_witness_tuples}`",
        f"- All-proposals witness: `{summary.all_proposals_witness_tuples}`",
        f"- {best_witness_label}: `{summary.best_fit_witness_tuples}`",
        "",
        "## Technical interpretation",
        f"- The current structural stack finds that this instance is `{hard_only_line}` under hard-only exact feasibility and `{all_proposals_line}` when all proposals are enforced; `gpd_str = {summary.gpd_str}` summarizes the minimum-deficit plan used for the best-fit witness.",
        "",
        "## Caveats",
        "- The blocker explanation is a deterministic near-minimal report derived from the exact infeasibility result and the minimum-deficit plan; it is not an exact MUS/MCS computation.",
        "- The solver backend is exact and intended for small finite instances.",
        "",
        "## Artifact references",
        f"- Summary JSON: `{summary.output_paths['summary']}`",
        f"- Result note JSON: `{summary.output_paths['result_note']}`",
        f"- Run manifest: `{summary.output_paths['manifest']}`",
    ]
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    summary: StructuralReportSummary,
) -> ResultNote:
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{summary.run_id}",
        run_id=summary.run_id,
        instance_ids=[summary.instance_id],
        metrics={
            "exact_extendable_hard_only": summary.exact_extendable_hard_only,
            "exact_extendable_all_proposals": summary.exact_extendable_all_proposals,
            "gpd_str": summary.gpd_str if summary.gpd_str is not None else -1.0,
            "total_candidate_tuple_count": summary.total_candidate_tuple_count,
            "hard_only_respecting_tuple_count": summary.hard_only_respecting_tuple_count,
            "all_proposals_respecting_tuple_count": summary.all_proposals_respecting_tuple_count,
            "best_plan_respecting_tuple_count": summary.best_plan_respecting_tuple_count,
        },
        interpretation=(
            "Instance is exactly extendable under both hard-only and all-proposals structural semantics."
            if summary.exact_extendable_all_proposals
            else "Instance is not exactly extendable under all proposals; the reported best-fit witness comes from the minimum-deficit structural plan and the report distinguishes hard-only from all-proposals exactness."
        ),
        caveats=[
            "Blocking explanation is deterministic and near-minimal, not an exact MUS/MCS computation.",
            "Results are intended for small finite instances.",
        ],
        artifact_refs={
            "summary": summary.output_paths["summary"],
            "note": summary.output_paths["note"],
            "manifest": summary.output_paths["manifest"],
        },
        metadata={
            "blocking_classification": str(
                summary.blocking_explanation["classification"]
            ),
        },
    )


def generate_structural_report(
    instance: EventPackageInstance,
    *,
    instance_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
    deficit_config: StructuralDeficitConfig | None = None,
) -> StructuralReportArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    active_deficit_config = deficit_config or StructuralDeficitConfig()
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    instance_relpath = repo_relative_path(instance_path, root=effective_root)

    hard_only_result = solve_exact_structural_feasibility(instance)
    all_proposals_result = solve_exact_structural_feasibility(
        instance,
        include_soft=True,
    )
    deficit_result = solve_structural_deficit(instance, config=active_deficit_config)

    summary_path = run_dir / "structural-summary.json"
    note_path = run_dir / "structural-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"

    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    summary = StructuralReportSummary(
        instance_id=instance.instance_id,
        run_id=run_id,
        exact_extendable_hard_only=hard_only_result.feasible,
        exact_extendable_all_proposals=all_proposals_result.feasible,
        gpd_str=deficit_result.gpd_str,
        total_candidate_tuple_count=hard_only_result.total_candidate_tuple_count,
        hard_only_respecting_tuple_count=hard_only_result.respecting_tuple_count,
        all_proposals_respecting_tuple_count=all_proposals_result.respecting_tuple_count,
        best_plan_respecting_tuple_count=deficit_result.respecting_tuple_count,
        hard_only_enforced_proposal_ids=hard_only_result.enforced_proposal_ids,
        all_proposals_enforced_proposal_ids=all_proposals_result.enforced_proposal_ids,
        relaxed_proposal_ids=deficit_result.relaxed_proposal_ids,
        relaxed_atoms=deficit_result.relaxed_atoms,
        hard_only_uncovered_atoms=hard_only_result.uncovered_atoms,
        all_proposals_uncovered_atoms=all_proposals_result.uncovered_atoms,
        blocking_explanation=_blocking_explanation(
            hard_only_result,
            all_proposals_result,
            deficit_result,
        ),
        deficit_config={
            "allow_relax_hard": active_deficit_config.allow_relax_hard,
            "atom_relax_weight": active_deficit_config.atom_relax_weight,
            "hard_proposal_relax_weight": active_deficit_config.hard_proposal_relax_weight,
        },
        hard_only_witness_tuples=hard_only_result.witness_tuples,
        all_proposals_witness_tuples=all_proposals_result.witness_tuples,
        best_fit_witness_tuples=(
            None
            if all_proposals_result.feasible
            else deficit_result.best_fit_witness_tuples
        ),
        instance_path=instance_relpath,
        output_paths=output_paths,
    )

    summary_path.write_text(
        json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(_render_structural_note(summary), encoding="utf-8")

    result_note = _build_result_note(summary=summary)
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
            "structural",
            "report",
            instance_relpath,
        ],
        seed=seed,
        input_artifacts={"instance": instance_relpath},
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "structural_report",
            "exact_extendable_hard_only": summary.exact_extendable_hard_only,
            "exact_extendable_all_proposals": summary.exact_extendable_all_proposals,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return StructuralReportArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=output_paths["manifest"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        summary=summary,
    )
