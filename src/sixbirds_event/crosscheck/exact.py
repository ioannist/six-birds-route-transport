from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EqualityProposal, EventPackageInstance
from ..schemas.result_note import ResultNote
from ..solvers.structural_exact import (
    _build_event_atom_sets,
    _build_context_atoms,
    _build_event_lookup,
    _enforced_proposals,
    _enumerate_candidate_tuples,
    _filter_respecting_tuples,
    _tuple_as_mapping,
    _uncovered_atoms,
)
from ..validation import load_model
from .models import (
    BlockingProxyResult,
    CrosscheckStatus,
    ExactCrosscheck,
    ExactCrosscheckResults,
    ExactCrosscheckRow,
    ExactCrosscheckTarget,
    SingleProposalBlockingResult,
)


@dataclass(slots=True)
class ExactCrosscheckArtifacts:
    run_id: str
    run_dir: str
    results_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    model_path: str | None
    solution_path: str | None
    results: ExactCrosscheckResults


@dataclass(slots=True)
class _MilpCrosscheckResult:
    feasible: bool
    reason: str | None
    total_candidate_tuple_count: int
    respecting_tuple_count: int
    exact_selected_tuple_count: int | None
    selected_tuple_indices: list[int]
    selected_tuples: list[dict[str, str]]
    uncovered_atoms: dict[str, list[str]]
    context_order: list[str]
    enforced_proposal_ids: list[str]
    model_payload: dict[str, object]


def load_exact_crosscheck(path: str | Path) -> ExactCrosscheck:
    model = load_model(path, kind="exact-crosscheck")
    assert isinstance(model, ExactCrosscheck)
    return model


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _include_soft_for_mode(evaluation_mode: str) -> bool:
    return evaluation_mode == "all_proposals"


def _load_package(path: str | Path) -> EventPackageInstance:
    model = load_model(path, kind="event-package-instance")
    assert isinstance(model, EventPackageInstance)
    return model


def _cover_constraints(
    *,
    respecting_tuples: list[tuple[str, ...]],
    context_order: list[str],
    atoms_by_context: dict[str, list[str]],
) -> tuple[np.ndarray, list[dict[str, object]]]:
    rows: list[list[float]] = []
    exported: list[dict[str, object]] = []
    for context_index, context_id in enumerate(context_order):
        for atom_id in atoms_by_context[context_id]:
            row = [
                1.0 if tuple_values[context_index] == atom_id else 0.0
                for tuple_values in respecting_tuples
            ]
            rows.append(row)
            exported.append(
                {
                    "context_id": context_id,
                    "atom_id": atom_id,
                    "respecting_tuple_count": int(sum(row)),
                }
            )
    if not rows:
        return np.zeros((0, len(respecting_tuples))), exported
    return np.asarray(rows, dtype=float), exported


def _solve_cover_milp(
    *,
    respecting_tuples: list[tuple[str, ...]],
    context_order: list[str],
    atoms_by_context: dict[str, list[str]],
) -> tuple[bool, list[int]]:
    if not respecting_tuples:
        return False, []
    constraint_matrix, _ = _cover_constraints(
        respecting_tuples=respecting_tuples,
        context_order=context_order,
        atoms_by_context=atoms_by_context,
    )
    variable_count = len(respecting_tuples)
    if variable_count == 0:
        return False, []
    objective = np.ones(variable_count, dtype=float)
    constraints = [
        LinearConstraint(
            constraint_matrix,
            lb=np.ones(constraint_matrix.shape[0], dtype=float),
            ub=np.full(constraint_matrix.shape[0], np.inf, dtype=float),
        )
    ]
    result = milp(
        c=objective,
        integrality=np.ones(variable_count, dtype=int),
        bounds=Bounds(
            lb=np.zeros(variable_count, dtype=float),
            ub=np.ones(variable_count, dtype=float),
        ),
        constraints=constraints,
        options={"disp": False},
    )
    if not result.success or result.x is None:
        return False, []
    selected = [index for index, value in enumerate(result.x) if value >= 0.5]
    return True, selected


def _run_milp_crosscheck(
    instance: EventPackageInstance,
    *,
    evaluation_mode: str,
) -> _MilpCrosscheckResult:
    context_order = [context.context_id for context in instance.contexts]
    atoms_by_context = _build_context_atoms(instance)
    event_by_id = _build_event_lookup(instance)
    event_atom_sets = _build_event_atom_sets(instance)
    proposals = _enforced_proposals(
        instance, include_soft=_include_soft_for_mode(evaluation_mode)
    )
    candidate_tuples = _enumerate_candidate_tuples(context_order, atoms_by_context)
    respecting_tuples = _filter_respecting_tuples(
        candidate_tuples,
        context_order=context_order,
        proposals=proposals,
        event_by_id=event_by_id,
        event_atom_sets=event_atom_sets,
    )
    covered_constraints, covered_constraint_exports = _cover_constraints(
        respecting_tuples=respecting_tuples,
        context_order=context_order,
        atoms_by_context=atoms_by_context,
    )

    if not respecting_tuples:
        uncovered = _uncovered_atoms(
            [],
            context_order=context_order,
            atoms_by_context=atoms_by_context,
        )
        return _MilpCrosscheckResult(
            feasible=False,
            reason="no_respecting_tuples",
            total_candidate_tuple_count=len(candidate_tuples),
            respecting_tuple_count=0,
            exact_selected_tuple_count=None,
            selected_tuple_indices=[],
            selected_tuples=[],
            uncovered_atoms=uncovered,
            context_order=context_order,
            enforced_proposal_ids=[proposal.proposal_id for proposal in proposals],
            model_payload={
                "package_path": None,
                "evaluation_mode": evaluation_mode,
                "context_order": context_order,
                "total_candidate_tuple_count": len(candidate_tuples),
                "respecting_tuple_count": 0,
                "covered_atom_constraints": covered_constraint_exports,
                "enforced_proposal_ids": [
                    proposal.proposal_id for proposal in proposals
                ],
                "backend_label": "scipy_milp_v1",
            },
        )

    feasible, selected_tuple_indices = _solve_cover_milp(
        respecting_tuples=respecting_tuples,
        context_order=context_order,
        atoms_by_context=atoms_by_context,
    )
    selected_tuples_raw = [respecting_tuples[index] for index in selected_tuple_indices]
    selected_tuples = [
        _tuple_as_mapping(tuple_values, context_order)
        for tuple_values in selected_tuples_raw
    ]
    if feasible:
        uncovered = {}
        reason = None
        exact_selected_tuple_count = len(selected_tuple_indices)
    else:
        uncovered = _uncovered_atoms(
            respecting_tuples,
            context_order=context_order,
            atoms_by_context=atoms_by_context,
        )
        reason = "coverage_failure"
        exact_selected_tuple_count = None

    model_payload = {
        "package_path": None,
        "evaluation_mode": evaluation_mode,
        "context_order": context_order,
        "total_candidate_tuple_count": len(candidate_tuples),
        "respecting_tuple_count": len(respecting_tuples),
        "covered_atom_constraints": covered_constraint_exports,
        "enforced_proposal_ids": [proposal.proposal_id for proposal in proposals],
        "backend_label": "scipy_milp_v1",
        "constraint_matrix_shape": list(covered_constraints.shape),
    }
    return _MilpCrosscheckResult(
        feasible=feasible,
        reason=reason,
        total_candidate_tuple_count=len(candidate_tuples),
        respecting_tuple_count=len(respecting_tuples),
        exact_selected_tuple_count=exact_selected_tuple_count,
        selected_tuple_indices=selected_tuple_indices,
        selected_tuples=selected_tuples,
        uncovered_atoms=uncovered,
        context_order=context_order,
        enforced_proposal_ids=[proposal.proposal_id for proposal in proposals],
        model_payload=model_payload,
    )


def _proposal_by_mode(
    instance: EventPackageInstance, *, evaluation_mode: str
) -> list[EqualityProposal]:
    return _enforced_proposals(
        instance, include_soft=_include_soft_for_mode(evaluation_mode)
    )


def _remove_proposal(
    instance: EventPackageInstance, *, proposal_id: str
) -> EventPackageInstance:
    return instance.model_copy(
        update={
            "equality_proposals": [
                proposal
                for proposal in instance.equality_proposals
                if proposal.proposal_id != proposal_id
            ]
        }
    )


def _run_blocking_proxy(
    instance: EventPackageInstance,
    *,
    evaluation_mode: str,
    enabled: bool,
) -> BlockingProxyResult:
    if not enabled:
        return BlockingProxyResult(
            status="not_applicable",
            notes=["single_proposal_leave_one_out_disabled"],
        )
    proposals = _proposal_by_mode(instance, evaluation_mode=evaluation_mode)
    if not proposals:
        return BlockingProxyResult(
            status="not_applicable",
            notes=["no_enforced_proposals_in_selected_mode"],
        )
    rows: list[SingleProposalBlockingResult] = []
    blocking_ids: list[str] = []
    for proposal in proposals:
        try:
            reduced = _remove_proposal(instance, proposal_id=proposal.proposal_id)
            result = _run_milp_crosscheck(reduced, evaluation_mode=evaluation_mode)
        except Exception as exc:  # pragma: no cover - defensive fallback
            rows.append(
                SingleProposalBlockingResult(
                    proposal_id=proposal.proposal_id,
                    feasibility_status="unsolved",
                    reason=str(exc),
                )
            )
            continue
        feasibility_status = "feasible" if result.feasible else "infeasible"
        if result.feasible:
            blocking_ids.append(proposal.proposal_id)
        rows.append(
            SingleProposalBlockingResult(
                proposal_id=proposal.proposal_id,
                feasibility_status=feasibility_status,
                exact_respecting_tuple_count=result.respecting_tuple_count,
                exact_selected_tuple_count=result.exact_selected_tuple_count,
                reason=result.reason,
            )
        )
    status: CrosscheckStatus = (
        "unsolved"
        if any(row.feasibility_status == "unsolved" for row in rows)
        else "solved"
    )
    notes: list[str] = []
    if blocking_ids:
        notes.append("leave_one_out_restores_feasibility_for_at_least_one_proposal")
    return BlockingProxyResult(
        status=status,
        blocking_proposal_ids=blocking_ids,
        single_proposal_results=rows,
        notes=notes,
    )


def _write_target_artifacts(
    *,
    target_dir: Path,
    target: ExactCrosscheckTarget,
    package_path: str,
    backend_label: str,
    crosscheck_result: _MilpCrosscheckResult,
    blocking_proxy: BlockingProxyResult,
    root: Path,
) -> tuple[str, str, str, str | None]:
    model_path = target_dir / "crosscheck-model.json"
    summary_path = target_dir / "crosscheck-summary.json"
    note_path = target_dir / "crosscheck-note.md"
    solution_path = target_dir / "crosscheck-solution.json"

    model_payload = dict(crosscheck_result.model_payload)
    model_payload["package_path"] = package_path
    model_payload["backend_label"] = backend_label
    _write_json(model_path, model_payload)

    solution_artifact: str | None = None
    if crosscheck_result.feasible:
        _write_json(
            solution_path,
            {
                "selected_tuple_indices": crosscheck_result.selected_tuple_indices,
                "selected_tuples": crosscheck_result.selected_tuples,
                "selected_tuple_count": crosscheck_result.exact_selected_tuple_count,
                "uncovered_atoms": crosscheck_result.uncovered_atoms,
            },
        )
        solution_artifact = repo_relative_path(solution_path, root=root)

    summary_payload = {
        "target_id": target.target_id,
        "package_path": package_path,
        "evaluation_mode": target.evaluation_mode,
        "backend_label": backend_label,
        "feasibility_status": "feasible"
        if crosscheck_result.feasible
        else "infeasible",
        "exact_respecting_tuple_count": crosscheck_result.respecting_tuple_count,
        "exact_selected_tuple_count": crosscheck_result.exact_selected_tuple_count,
        "reason": crosscheck_result.reason,
        "single_proposal_blocking_analysis": blocking_proxy.model_dump(
            mode="json", exclude_none=True
        ),
        "artifact_refs": {
            "model": repo_relative_path(model_path, root=root),
            "summary": repo_relative_path(summary_path, root=root),
            "note": repo_relative_path(note_path, root=root),
            **(
                {"solution": solution_artifact} if solution_artifact is not None else {}
            ),
        },
        "notes": [
            "semantic_alignment_exact_cover_over_respecting_tuples",
        ],
    }
    _write_json(summary_path, summary_payload)

    note_lines = [
        f"# Exact Crosscheck: {target.target_id}",
        "",
        "## Target",
        f"- Target type: `{target.target_type}`",
        f"- Package path: `{package_path}`",
        f"- Evaluation mode: `{target.evaluation_mode}`",
        f"- Backend: `{backend_label}`",
        "",
        "## Counts",
        f"- Total candidate tuple count: `{crosscheck_result.total_candidate_tuple_count}`",
        f"- Respecting tuple count: `{crosscheck_result.respecting_tuple_count}`",
        f"- Exact selected tuple count: `{crosscheck_result.exact_selected_tuple_count}`",
        "",
        "## Feasibility",
        f"- Feasibility status: `{'feasible' if crosscheck_result.feasible else 'infeasible'}`",
        f"- Reason: `{crosscheck_result.reason}`",
        "",
        "## Blocking proxy",
        f"- Blocking proxy status: `{blocking_proxy.status}`",
        f"- Blocking proposal IDs: `{blocking_proxy.blocking_proposal_ids}`",
        "",
        "## Semantics",
        "- Semantic alignment: exact feasibility is encoded as a 0-1 cover over respecting context-tuples.",
        "",
        "## Artifact references",
        f"- Model: `{repo_relative_path(model_path, root=root)}`",
        f"- Summary: `{repo_relative_path(summary_path, root=root)}`",
        f"- Note: `{repo_relative_path(note_path, root=root)}`",
    ]
    if solution_artifact is not None:
        note_lines.append(f"- Solution: `{solution_artifact}`")
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    return (
        repo_relative_path(model_path, root=root),
        repo_relative_path(summary_path, root=root),
        repo_relative_path(note_path, root=root),
        solution_artifact,
    )


def _result_note_for_bundle(
    *,
    run_id: str,
    crosscheck_id: str,
    rows: list[ExactCrosscheckRow],
    artifact_refs: dict[str, str],
) -> ResultNote:
    infeasible_targets = [
        row.target_id
        for row in rows
        if row.crosscheck_status == "solved" and row.feasibility_status == "infeasible"
    ]
    not_applicable_targets = [
        row.target_id for row in rows if row.crosscheck_status == "not_applicable"
    ]
    interpretation = (
        "exact_crosscheck_detected_infeasibility"
        if infeasible_targets
        else "exact_crosscheck_completed_without_infeasible_targets"
    )
    caveats: list[str] = []
    if not_applicable_targets:
        caveats.append(
            "some configured targets were recorded as not_applicable rather than solved"
        )
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"{crosscheck_id}_result_note",
        run_id=run_id,
        instance_ids=[row.target_id for row in rows],
        metrics={
            "target_count": len(rows),
            "infeasible_target_count": len(infeasible_targets),
            "not_applicable_target_count": len(not_applicable_targets),
        },
        interpretation=interpretation,
        caveats=caveats,
        artifact_refs=artifact_refs,
        metadata={
            "analysis_kind": "exact_crosscheck",
        },
    )


def run_exact_crosscheck(
    *,
    config_path: str,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> ExactCrosscheckArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    config = load_exact_crosscheck(config_path)
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or config.output_label or config.crosscheck_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    results_path = run_dir / "crosscheck-results.json"
    model_path = run_dir / "crosscheck-model.json"
    solution_path = run_dir / "crosscheck-solution.json"
    summary_path = run_dir / "crosscheck-summary.json"
    note_path = run_dir / "crosscheck-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"

    rows: list[ExactCrosscheckRow] = []
    applicable_rows: list[ExactCrosscheckRow] = []
    top_level_model_path: str | None = None
    top_level_solution_path: str | None = None

    for target in config.targets:
        if target.applicability_override_status == "not_applicable":
            row = ExactCrosscheckRow(
                row_format_version="exact-crosscheck-row.v1",
                crosscheck_id=config.crosscheck_id,
                target_id=target.target_id,
                target_type=target.target_type,
                package_path=None,
                evaluation_mode=target.evaluation_mode,
                backend_label=config.backend_label,
                crosscheck_status="not_applicable",
                feasibility_status=None,
                exact_respecting_tuple_count=None,
                exact_selected_tuple_count=None,
                model_artifact_path=None,
                summary_artifact_path=None,
                note_artifact_path=None,
                solution_artifact_path=None,
                blocking_proxy=BlockingProxyResult(
                    status="not_applicable",
                    notes=["target_recorded_as_not_applicable_in_config"],
                ),
                applicability_reason=target.applicability_reason,
                notes=target.notes,
            )
            rows.append(row)
            continue

        assert target.package_artifact is not None
        try:
            instance = _load_package(Path.cwd() / target.package_artifact)
            result = _run_milp_crosscheck(
                instance,
                evaluation_mode=target.evaluation_mode,
            )
            blocking_proxy = _run_blocking_proxy(
                instance,
                evaluation_mode=target.evaluation_mode,
                enabled=(
                    config.blocking_analysis.single_proposal_leave_one_out
                    and not result.feasible
                ),
            )
            target_dir = run_dir / target.target_id
            target_dir.mkdir(parents=True, exist_ok=False)
            model_artifact, summary_artifact, note_artifact, solution_artifact = (
                _write_target_artifacts(
                    target_dir=target_dir,
                    target=target,
                    package_path=target.package_artifact,
                    backend_label=config.backend_label,
                    crosscheck_result=result,
                    blocking_proxy=blocking_proxy,
                    root=effective_root,
                )
            )
            row = ExactCrosscheckRow(
                row_format_version="exact-crosscheck-row.v1",
                crosscheck_id=config.crosscheck_id,
                target_id=target.target_id,
                target_type=target.target_type,
                package_path=target.package_artifact,
                evaluation_mode=target.evaluation_mode,
                backend_label=config.backend_label,
                crosscheck_status="solved",
                feasibility_status="feasible" if result.feasible else "infeasible",
                exact_respecting_tuple_count=result.respecting_tuple_count,
                exact_selected_tuple_count=result.exact_selected_tuple_count,
                model_artifact_path=model_artifact,
                summary_artifact_path=summary_artifact,
                note_artifact_path=note_artifact,
                solution_artifact_path=solution_artifact,
                blocking_proxy=blocking_proxy,
                applicability_reason=None,
                notes=target.notes
                + ([f"reason:{result.reason}"] if result.reason is not None else []),
            )
            rows.append(row)
            applicable_rows.append(row)
        except Exception as exc:  # pragma: no cover - defensive fallback
            row = ExactCrosscheckRow(
                row_format_version="exact-crosscheck-row.v1",
                crosscheck_id=config.crosscheck_id,
                target_id=target.target_id,
                target_type=target.target_type,
                package_path=target.package_artifact,
                evaluation_mode=target.evaluation_mode,
                backend_label=config.backend_label,
                crosscheck_status="unsolved",
                feasibility_status=None,
                exact_respecting_tuple_count=None,
                exact_selected_tuple_count=None,
                model_artifact_path=None,
                summary_artifact_path=None,
                note_artifact_path=None,
                solution_artifact_path=None,
                blocking_proxy=BlockingProxyResult(
                    status="unsolved",
                    notes=[str(exc)],
                ),
                applicability_reason=str(exc),
                notes=target.notes + ["crosscheck_failed"],
            )
            rows.append(row)

    results = ExactCrosscheckResults(
        result_format_version="exact-crosscheck-result.v1",
        crosscheck_id=config.crosscheck_id,
        row_count=len(rows),
        rows=rows,
        metadata=config.metadata,
    )
    results_path.write_text(
        json.dumps(results.model_dump(mode="json", exclude_none=True), indent=2) + "\n",
        encoding="utf-8",
    )

    if len(applicable_rows) == 1:
        assert applicable_rows[0].model_artifact_path is not None
        shutil.copyfile(
            effective_root / applicable_rows[0].model_artifact_path,
            model_path,
        )
        top_level_model_path = repo_relative_path(model_path, root=effective_root)
        if applicable_rows[0].solution_artifact_path is not None:
            shutil.copyfile(
                effective_root / applicable_rows[0].solution_artifact_path,
                solution_path,
            )
            top_level_solution_path = repo_relative_path(
                solution_path, root=effective_root
            )

    summary_payload = {
        "crosscheck_id": config.crosscheck_id,
        "backend_label": config.backend_label,
        "target_count": len(rows),
        "solved_count": sum(row.crosscheck_status == "solved" for row in rows),
        "unsolved_count": sum(row.crosscheck_status == "unsolved" for row in rows),
        "not_applicable_count": sum(
            row.crosscheck_status == "not_applicable" for row in rows
        ),
        "infeasible_targets": [
            row.target_id for row in rows if row.feasibility_status == "infeasible"
        ],
        "results_path": repo_relative_path(results_path, root=effective_root),
        "rows": [
            {
                "target_id": row.target_id,
                "target_type": row.target_type,
                "evaluation_mode": row.evaluation_mode,
                "crosscheck_status": row.crosscheck_status,
                "feasibility_status": row.feasibility_status,
                "exact_respecting_tuple_count": row.exact_respecting_tuple_count,
                "blocking_proposal_ids": row.blocking_proxy.blocking_proposal_ids,
                "applicability_reason": row.applicability_reason,
            }
            for row in rows
        ],
    }
    _write_json(summary_path, summary_payload)

    note_lines = [
        f"# Exact Crosscheck Bundle: {config.crosscheck_id}",
        "",
        "## Backend",
        f"- Backend: `{config.backend_label}`",
        "",
        "## Targets",
    ]
    for row in rows:
        note_lines.extend(
            [
                f"- `{row.target_id}`: mode=`{row.evaluation_mode}`, status=`{row.crosscheck_status}`, feasibility=`{row.feasibility_status}`, respecting_tuple_count=`{row.exact_respecting_tuple_count}`, blocking_proposal_ids=`{row.blocking_proxy.blocking_proposal_ids}`",
            ]
        )
    note_lines.extend(
        [
            "",
            "## Semantics",
            "- Semantic alignment with exact feasibility: candidate global atoms are context-tuples, respecting tuples satisfy enforced event equalities, and feasibility is decided by a 0-1 cover over all context-atoms.",
            "",
            "## Artifact references",
            f"- Results: `{repo_relative_path(results_path, root=effective_root)}`",
            f"- Summary: `{repo_relative_path(summary_path, root=effective_root)}`",
            f"- Note: `{repo_relative_path(note_path, root=effective_root)}`",
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    artifact_refs = {
        "results": repo_relative_path(results_path, root=effective_root),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
    }
    if top_level_model_path is not None:
        artifact_refs["model"] = top_level_model_path
    if top_level_solution_path is not None:
        artifact_refs["solution"] = top_level_solution_path
    result_note = _result_note_for_bundle(
        run_id=run_id,
        crosscheck_id=config.crosscheck_id,
        rows=rows,
        artifact_refs=artifact_refs,
    )
    result_note_path.write_text(
        json.dumps(result_note.model_dump(mode="json", exclude_none=True), indent=2)
        + "\n",
        encoding="utf-8",
    )

    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [sys.executable, "-m", "sixbirds_event", "crosscheck", "run", config_path],
        seed=seed,
        input_artifacts={
            "config": repo_relative_path(config_path, root=effective_root),
        },
        output_artifacts={
            "results": repo_relative_path(results_path, root=effective_root),
            "summary": repo_relative_path(summary_path, root=effective_root),
            "note": repo_relative_path(note_path, root=effective_root),
            "result_note": repo_relative_path(result_note_path, root=effective_root),
            **(
                {"model": top_level_model_path}
                if top_level_model_path is not None
                else {}
            ),
            **(
                {"solution": top_level_solution_path}
                if top_level_solution_path is not None
                else {}
            ),
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "exact_crosscheck",
            "backend_label": config.backend_label,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return ExactCrosscheckArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        results_path=repo_relative_path(results_path, root=effective_root),
        summary_path=repo_relative_path(summary_path, root=effective_root),
        note_path=repo_relative_path(note_path, root=effective_root),
        result_note_path=repo_relative_path(result_note_path, root=effective_root),
        manifest_path=repo_relative_path(manifest_path, root=effective_root),
        model_path=top_level_model_path,
        solution_path=top_level_solution_path,
        results=results,
    )
