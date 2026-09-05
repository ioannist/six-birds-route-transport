from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import statistics
import sys

from ..discovery.models import DiscoveredContextFamily, SharedEventCandidates
from ..provenance.audit import write_provenance_audit_report
from ..reporting.context_discovery_report import write_context_discovery_report
from ..reporting.package_build_report import write_package_build_report
from ..reporting.statistical_report import write_statistical_summary
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance, EqualityProposal
from ..schemas.observation_trace import Observation, ObservationTrace
from ..schemas.result_note import ResultNote
from ..search.models import (
    AtlasStatus,
    TargetedCandidateLabel,
    TargetedNonextendabilitySearch,
    TargetedSearchEvaluation,
    TargetedSearchPoint,
    TargetedSearchRow,
    TargetedSearchTable,
)
from ..solvers.structural_deficit import (
    StructuralDeficitConfig,
    solve_structural_deficit,
)
from ..solvers.structural_exact import solve_exact_structural_feasibility
from ..substrates.engine import load_substrate_config, write_substrate_run
from ..validation import load_model


CLASSIFICATION_RULE_VERSION = "targeted-nonextendability-classifier.v1"


@dataclass(slots=True)
class TargetedSearchArtifacts:
    run_id: str
    run_dir: str
    table_csv_path: str
    table_json_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    table: TargetedSearchTable
    classification_counts: dict[str, int]
    best_candidate_path: str | None
    negative_result_path: str | None


def load_targeted_nonextendability_search(
    path: str | Path,
) -> TargetedNonextendabilitySearch:
    model = load_model(path, kind="targeted-nonextendability-search")
    assert isinstance(model, TargetedNonextendabilitySearch)
    return model


def _load_family(path: str | Path) -> DiscoveredContextFamily:
    model = load_model(path, kind="discovered-context-family")
    assert isinstance(model, DiscoveredContextFamily)
    return model


def _load_candidates(path: str | Path) -> SharedEventCandidates:
    model = load_model(path, kind="shared-event-candidates")
    assert isinstance(model, SharedEventCandidates)
    return model


def _derive_stat_trace(
    *,
    family: DiscoveredContextFamily,
    raw_run,
    instance_id: str,
    instance_artifact: str,
    trace_id: str,
) -> ObservationTrace:
    observations: list[Observation] = []
    for context in family.accepted_contexts:
        label_to_outcome = {
            outcome.observation_label: outcome.outcome_id
            for outcome in context.atomic_outcomes
        }
        counts = Counter()
        for trajectory in raw_run.trajectories:
            if (
                trajectory.preparation_id != context.candidate_key.preparation_id
                or trajectory.protocol_id != context.candidate_key.protocol_id
            ):
                continue
            step = next(
                (
                    step
                    for step in trajectory.steps
                    if step.step_index == context.candidate_key.step_index
                ),
                None,
            )
            if step is None:
                continue
            label = step.observations.get(context.candidate_key.lens_id)
            if label is None:
                continue
            outcome_id = label_to_outcome.get(label)
            if outcome_id is None:
                continue
            counts[outcome_id] += 1
        for outcome in context.atomic_outcomes:
            observations.append(
                Observation(
                    context_id=context.context_id,
                    atom_ids=[outcome.outcome_id],
                    count=counts.get(outcome.outcome_id, 0),
                    status="observed",
                )
            )
    return ObservationTrace(
        trace_format_version="observation-trace.v1",
        trace_id=trace_id,
        instance_id=instance_id,
        instance_artifact=instance_artifact,
        observations=observations,
        metadata={
            "derived_from": "substrate_run",
            "derivation_kind": "targeted_nonextendability_stat_trace",
        },
    )


def _sec_summary(candidates: SharedEventCandidates) -> tuple[AtlasStatus, float | None]:
    scored_rows = [
        row
        for row in candidates.candidate_rows
        if not row.insufficient_data and row.approx_score is not None
    ]
    if not candidates.candidate_rows:
        return ("not_applicable", None)
    if not scored_rows:
        return ("insufficient_data", None)
    accepted_scores = [row.approx_score for row in scored_rows if row.accepted]
    values = accepted_scores or [
        row.approx_score for row in scored_rows if row.approx_score is not None
    ]
    return ("scored", statistics.mean(values))


def _hard_only_instance(instance: EventPackageInstance) -> EventPackageInstance:
    hard_proposals = [
        proposal
        for proposal in instance.equality_proposals
        if proposal.constraint_kind == "hard"
    ]
    kept_weight_keys = {
        proposal.weight_key
        for proposal in hard_proposals
        if proposal.weight_key is not None
    }
    return instance.model_copy(
        update={
            "equality_proposals": [
                EqualityProposal.model_validate(proposal.model_dump(mode="json"))
                for proposal in hard_proposals
            ],
            "weights": {
                key: value
                for key, value in instance.weights.items()
                if key in kept_weight_keys
            },
        }
    )


def _baseline_deficit_evaluation(
    instance: EventPackageInstance,
) -> tuple[AtlasStatus, float | None, str | None]:
    hard_only_instance = _hard_only_instance(instance)
    if not hard_only_instance.equality_proposals:
        return ("solved", 0.0, None)
    exact_result = solve_exact_structural_feasibility(hard_only_instance)
    if exact_result.feasible:
        return ("solved", 0.0, None)
    result = solve_structural_deficit(
        hard_only_instance,
        config=StructuralDeficitConfig(
            allow_relax_hard=True,
            hard_proposal_relax_weight=1.0,
        ),
    )
    if result.solved and result.gpd_str is not None:
        return ("solved", float(result.gpd_str), None)
    return ("unsolved", None, result.reason)


def _candidate_deficit_evaluation(
    instance: EventPackageInstance,
) -> tuple[AtlasStatus, float | None, str | None]:
    exact_result = solve_exact_structural_feasibility(instance, include_soft=True)
    if exact_result.feasible:
        return ("solved", 0.0, None)
    result = solve_structural_deficit(instance, config=StructuralDeficitConfig())
    if result.solved and result.gpd_str is not None:
        return ("solved", float(result.gpd_str), None)
    return ("unsolved", None, result.reason)


def _candidate_classification(
    *,
    row: TargetedSearchRow,
    search: TargetedNonextendabilitySearch,
    blocking_classification: str | None,
) -> TargetedCandidateLabel:
    if row.event_package_path is None or row.accepted_context_count < 2:
        return "trivial_or_nonrecording"

    if row.all_accepted_proposals.gpd_str_status != "solved":
        return "inconclusive"

    provenance_ok = row.provenance_classification == "admissible"
    some_provenance = row.provenance_classification in {
        "admissible",
        "partially_supported",
    }
    has_coarse_proposals = (
        row.accepted_coarse_proposal_count
        >= search.candidate_classification_thresholds.min_accepted_coarse_proposal_count
    )
    candidate_exact_fails = row.all_accepted_proposals.exact_feasible is False
    positive_candidate_deficit = (
        row.all_accepted_proposals.gpd_str is not None
        and row.all_accepted_proposals.gpd_str
        > search.candidate_classification_thresholds.strong_nonextendable_min_gpd_str
    )
    strong_block = (
        row.all_accepted_proposals.exact_respecting_tuple_count == 0
        or blocking_classification == "no_respecting_tuples"
    )

    if (
        provenance_ok
        and has_coarse_proposals
        and candidate_exact_fails
        and positive_candidate_deficit
        and strong_block
    ):
        return "strongly_nonextendable_candidate"

    if (
        provenance_ok
        and row.all_accepted_proposals.exact_feasible is True
        and row.all_accepted_proposals.gpd_str == 0
    ):
        return "extendable_candidate"

    if some_provenance and (
        candidate_exact_fails
        or (
            row.all_accepted_proposals.gpd_str is not None
            and row.all_accepted_proposals.gpd_str > 0
        )
        or (
            row.all_accepted_proposals.gpd_stat_status == "solved"
            and row.all_accepted_proposals.gpd_stat is not None
            and row.all_accepted_proposals.gpd_stat
            > search.candidate_classification_thresholds.near_zero_gpd_stat
        )
    ):
        return "weakly_frustrated_candidate"

    return "inconclusive"


def _row_to_csv_record(row: TargetedSearchRow) -> dict[str, object]:
    return {
        "point_id": row.point_id,
        "config_path": row.config_path,
        "preparation_id": row.preparation_id,
        "protocol_id": row.protocol_id,
        "trajectories": row.trajectories,
        "seed": row.seed,
        "raw_run_path": row.raw_run_path,
        "discovered_context_family_path": row.discovered_context_family_path,
        "event_package_path": row.event_package_path,
        "provenance_classification": row.provenance_classification,
        "accepted_context_count": row.accepted_context_count,
        "accepted_singleton_event_count": row.accepted_singleton_event_count,
        "accepted_coarse_event_count": row.accepted_coarse_event_count,
        "accepted_shared_event_proposal_count": row.accepted_shared_event_proposal_count,
        "accepted_coarse_proposal_count": row.accepted_coarse_proposal_count,
        "baseline_exact_structural_status": row.baseline_hard_only.exact_structural_status,
        "baseline_exact_feasible": row.baseline_hard_only.exact_feasible,
        "baseline_exact_respecting_tuple_count": row.baseline_hard_only.exact_respecting_tuple_count,
        "baseline_gpd_str_status": row.baseline_hard_only.gpd_str_status,
        "baseline_gpd_str": row.baseline_hard_only.gpd_str,
        "baseline_gpd_str_reason": row.baseline_hard_only.gpd_str_reason,
        "baseline_gpd_stat_status": row.baseline_hard_only.gpd_stat_status,
        "baseline_gpd_stat": row.baseline_hard_only.gpd_stat,
        "baseline_gpd_stat_reason": row.baseline_hard_only.gpd_stat_reason,
        "candidate_exact_structural_status": row.all_accepted_proposals.exact_structural_status,
        "candidate_exact_feasible": row.all_accepted_proposals.exact_feasible,
        "candidate_exact_respecting_tuple_count": row.all_accepted_proposals.exact_respecting_tuple_count,
        "candidate_gpd_str_status": row.all_accepted_proposals.gpd_str_status,
        "candidate_gpd_str": row.all_accepted_proposals.gpd_str,
        "candidate_gpd_str_reason": row.all_accepted_proposals.gpd_str_reason,
        "candidate_gpd_stat_status": row.all_accepted_proposals.gpd_stat_status,
        "candidate_gpd_stat": row.all_accepted_proposals.gpd_stat,
        "candidate_gpd_stat_reason": row.all_accepted_proposals.gpd_stat_reason,
        "ccd_status": row.ccd_status,
        "ccd_overall": row.ccd_overall,
        "sec_status": row.sec_status,
        "sec_mean": row.sec_mean,
        "rm_status": row.rm_status,
        "rm_overall": row.rm_overall,
        "candidate_classification": row.candidate_classification,
        "substrate_run_id": row.run_ids.get("substrate_run"),
        "context_discovery_run_id": row.run_ids.get("context_discovery"),
        "package_build_run_id": row.run_ids.get("package_build"),
        "provenance_audit_run_id": row.run_ids.get("provenance_audit"),
        "structural_run_id": row.run_ids.get("structural"),
        "baseline_statistical_run_id": row.run_ids.get("baseline_statistical"),
        "candidate_statistical_run_id": row.run_ids.get("candidate_statistical"),
        "raw_run_artifact": row.artifact_paths.get("raw_run"),
        "family_artifact": row.artifact_paths.get("family"),
        "package_artifact": row.artifact_paths.get("event_package"),
        "provenance_artifact": row.artifact_paths.get("package_provenance"),
        "provenance_summary_artifact": row.artifact_paths.get("provenance_summary"),
        "candidate_artifact": row.artifact_paths.get("shared_event_candidates"),
    }


def _build_result_note(
    *,
    run_id: str,
    table: TargetedSearchTable,
    classification_counts: dict[str, int],
    best_candidate_id: str | None,
    negative_result: bool,
    output_paths: dict[str, str],
) -> ResultNote:
    metrics = {
        "total_point_count": table.row_count,
        "admissible_point_count": sum(
            1 for row in table.rows if row.provenance_classification == "admissible"
        ),
        "candidate_mode_exact_fail_count": sum(
            1
            for row in table.rows
            if row.all_accepted_proposals.exact_feasible is False
        ),
        "negative_result": negative_result,
    }
    for label, count in sorted(classification_counts.items()):
        metrics[f"classification_count_{label}"] = count
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[table.search_id],
        metrics=metrics,
        interpretation=(
            "Targeted search rows distinguish baseline hard-only evaluation from all-accepted-proposals candidate evaluation and do not overclaim strong nonextendability from baseline hard-only structure alone."
        ),
        caveats=[
            "RM is diagnostic-only when present.",
            "Negative-result output is scientifically valid when the committed targeted family yields no strong provenance-admissible discovered candidate.",
        ],
        artifact_refs={
            "table_csv": output_paths["table_csv"],
            "table_json": output_paths["table_json"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
            **(
                {"best_candidate": output_paths["best_candidate"]}
                if best_candidate_id is not None
                else {}
            ),
            **(
                {"negative_result": output_paths["negative_result"]}
                if negative_result
                else {}
            ),
        },
        metadata={
            "classification_rule_version": CLASSIFICATION_RULE_VERSION,
            "best_candidate_id": best_candidate_id,
        },
    )


def _render_note(
    *,
    search: TargetedNonextendabilitySearch,
    table: TargetedSearchTable,
    classification_counts: dict[str, int],
    best_candidate_id: str | None,
    negative_result: bool,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Targeted Nonextendability Search",
        "",
        "## Search ID",
        f"- Search ID: `{search.search_id}`",
        "",
        "## Configs covered",
    ]
    for row in table.rows:
        lines.append(
            f"- `{row.point_id}`: config=`{row.config_path}`, provenance=`{row.provenance_classification}`, coarse_events=`{row.accepted_coarse_event_count}`, coarse_proposals=`{row.accepted_coarse_proposal_count}`, class=`{row.candidate_classification}`"
        )
    lines.extend(
        [
            "",
            "## Discovery / inference / provenance thresholds",
            f"- extraction: `{search.extraction_thresholds.model_dump(mode='json')}`",
            f"- coarse-event generation: `{search.coarse_event_generation_thresholds.model_dump(mode='json')}`",
            f"- shared-event inference: `{search.shared_event_inference_thresholds.model_dump(mode='json')}`",
            f"- provenance required: `{search.provenance_required}`",
            f"- candidate classification: `{search.candidate_classification_thresholds.model_dump(mode='json')}`",
            f"- stop rule: `{search.stop_rule.model_dump(mode='json')}`",
            "",
            "## Evaluation modes",
            "- Baseline hard-only mode uses only hard constraints for exact feasibility and deficit evaluation.",
            "- All-accepted-proposals mode uses accepted inferred proposals as exact constraints for discovered-package obstruction testing.",
            "- Strong endogenous nonextendability claims are assessed only in the all-accepted-proposals mode.",
            "",
            "## Candidate classification counts",
        ]
    )
    for label, count in sorted(classification_counts.items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(
        [
            "",
            "## Outcome",
            (
                f"- Best candidate: `{best_candidate_id}`"
                if best_candidate_id is not None
                else "- No strongly_nonextendable_candidate was found in the committed targeted family."
            ),
            f"- Negative-result emitted: `{negative_result}`",
            "",
            "## Notes",
            "- RM is diagnostic-only.",
            "- unsolved / insufficient-data / not_applicable statuses are preserved explicitly in every row.",
            "",
            "## Artifact references",
            f"- Targeted search CSV: `{output_paths['table_csv']}`",
            f"- Targeted search JSON: `{output_paths['table_json']}`",
            f"- Search summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
        ]
    )
    if best_candidate_id is not None:
        lines.append(f"- Best candidate JSON: `{output_paths['best_candidate']}`")
    if negative_result:
        lines.append(f"- Negative result JSON: `{output_paths['negative_result']}`")
    return "\n".join(lines) + "\n"


def _run_point(
    *,
    point: TargetedSearchPoint,
    search: TargetedNonextendabilitySearch,
    category: str,
    timestamp: str | None,
    root: Path,
    derived_dir: Path,
) -> TargetedSearchRow:
    config = load_substrate_config(point.config_artifact)
    substrate_artifacts = write_substrate_run(
        config,
        config_path=point.config_artifact,
        preparation_id=point.preparation_id,
        protocol_id=point.protocol_id,
        trajectories=point.trajectories,
        seed=point.seed,
        category=category,
        label=f"{search.search_id}-{point.point_id}-substrate",
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "run",
            point.config_artifact,
            "--preparation",
            point.preparation_id,
            "--protocol",
            point.protocol_id,
            "--trajectories",
            str(point.trajectories),
            "--seed",
            str(point.seed),
        ],
    )
    discovery_artifacts = write_context_discovery_report(
        run_paths=[root / substrate_artifacts.run_trace_path],
        category=category,
        label=f"{search.search_id}-{point.point_id}-discover",
        seed=point.seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "discover-contexts",
            substrate_artifacts.run_trace_path,
        ],
        thresholds=search.extraction_thresholds,
    )
    family = _load_family(root / discovery_artifacts.family_path)
    notes = list(point.notes)
    run_ids = {
        "substrate_run": substrate_artifacts.run_id,
        "context_discovery": discovery_artifacts.run_id,
    }
    artifact_paths = {
        "raw_run": substrate_artifacts.run_trace_path,
        "family": discovery_artifacts.family_path,
    }

    if family.diagnostics_summary.accepted_context_count < 2:
        notes.append("no_nontrivial_multi_context_structure")
        return TargetedSearchRow(
            row_format_version="targeted-search-row.v1",
            search_id=search.search_id,
            point_id=point.point_id,
            config_path=point.config_artifact,
            preparation_id=point.preparation_id,
            protocol_id=point.protocol_id,
            trajectories=point.trajectories,
            seed=point.seed,
            raw_run_path=substrate_artifacts.run_trace_path,
            discovered_context_family_path=discovery_artifacts.family_path,
            event_package_path=None,
            provenance_classification=None,
            accepted_context_count=family.diagnostics_summary.accepted_context_count,
            accepted_singleton_event_count=0,
            accepted_coarse_event_count=0,
            accepted_shared_event_proposal_count=0,
            accepted_coarse_proposal_count=0,
            baseline_hard_only=TargetedSearchEvaluation(
                exact_structural_status="not_applicable",
                exact_feasible=None,
                exact_respecting_tuple_count=None,
                gpd_str_status="not_applicable",
                gpd_str=None,
                gpd_str_reason=None,
                gpd_stat_status="not_applicable",
                gpd_stat=None,
                gpd_stat_reason=None,
            ),
            all_accepted_proposals=TargetedSearchEvaluation(
                exact_structural_status="not_applicable",
                exact_feasible=None,
                exact_respecting_tuple_count=None,
                gpd_str_status="not_applicable",
                gpd_str=None,
                gpd_str_reason=None,
                gpd_stat_status="not_applicable",
                gpd_stat=None,
                gpd_stat_reason=None,
            ),
            ccd_status="not_applicable",
            ccd_overall=None,
            sec_status="not_applicable",
            sec_mean=None,
            rm_status="not_applicable",
            rm_overall=None,
            candidate_classification="trivial_or_nonrecording",
            run_ids=run_ids,
            artifact_paths=artifact_paths,
            notes=notes,
        )

    package_artifacts = write_package_build_report(
        family_path=root / discovery_artifacts.family_path,
        run_paths=[root / substrate_artifacts.run_trace_path],
        skeleton_path=(
            None
            if discovery_artifacts.skeleton_path is None
            else root / discovery_artifacts.skeleton_path
        ),
        category=category,
        label=f"{search.search_id}-{point.point_id}-package",
        seed=point.seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "build-event-package",
            discovery_artifacts.family_path,
            "--raw-run",
            substrate_artifacts.run_trace_path,
            "--event-basis",
            search.coarse_event_generation_thresholds.event_basis_mode,
            "--max-union-size",
            str(search.coarse_event_generation_thresholds.max_union_size),
        ],
        thresholds=search.shared_event_inference_thresholds,
        event_thresholds=search.coarse_event_generation_thresholds,
    )
    candidates = _load_candidates(root / package_artifacts.candidates_path)
    run_ids["package_build"] = package_artifacts.run_id
    artifact_paths["discovered_event_family"] = (
        package_artifacts.discovered_event_family_path
    )
    artifact_paths["shared_event_candidates"] = package_artifacts.candidates_path
    artifact_paths["event_package"] = package_artifacts.event_package_path
    artifact_paths["package_provenance"] = package_artifacts.provenance_path
    artifact_paths["package_build_summary"] = package_artifacts.summary_path

    provenance_artifacts = write_provenance_audit_report(
        package_path=root / package_artifacts.event_package_path,
        provenance_path=root / package_artifacts.provenance_path,
        category=category,
        label=f"{search.search_id}-{point.point_id}-provenance",
        seed=point.seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "provenance",
            package_artifacts.event_package_path,
            "--provenance",
            package_artifacts.provenance_path,
        ],
    )
    run_ids["provenance_audit"] = provenance_artifacts.run_id
    artifact_paths["provenance_summary"] = provenance_artifacts.summary_path

    stat_trace = _derive_stat_trace(
        family=family,
        raw_run=substrate_artifacts.run_trace,
        instance_id=package_artifacts.event_package.instance_id,
        instance_artifact=package_artifacts.event_package_path,
        trace_id=f"trace_{search.search_id}_{point.point_id}_stat",
    )
    stat_trace_path = derived_dir / f"{point.point_id}-stat.json"
    stat_trace_path.write_text(
        json.dumps(stat_trace.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    stat_trace_relpath = repo_relative_path(stat_trace_path, root=root)
    artifact_paths["stat_trace"] = stat_trace_relpath

    hard_only_exact = solve_exact_structural_feasibility(
        package_artifacts.event_package
    )
    all_proposals_exact = solve_exact_structural_feasibility(
        package_artifacts.event_package,
        include_soft=True,
    )

    baseline_statistical = write_statistical_summary(
        package_artifacts.event_package,
        [stat_trace],
        instance_path=package_artifacts.event_package_path,
        trace_paths=[stat_trace_relpath],
        category=category,
        label=f"{search.search_id}-{point.point_id}-baseline-statistical",
        seed=point.seed,
        timestamp=timestamp,
        root=root,
        include_soft=False,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "targeted-baseline-statistical",
            stat_trace_relpath,
        ],
    )
    candidate_statistical = write_statistical_summary(
        package_artifacts.event_package,
        [stat_trace],
        instance_path=package_artifacts.event_package_path,
        trace_paths=[stat_trace_relpath],
        category=category,
        label=f"{search.search_id}-{point.point_id}-candidate-statistical",
        seed=point.seed,
        timestamp=timestamp,
        root=root,
        include_soft=True,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "targeted-candidate-statistical",
            stat_trace_relpath,
        ],
    )
    run_ids["baseline_statistical"] = baseline_statistical.run_id
    run_ids["candidate_statistical"] = candidate_statistical.run_id
    artifact_paths["baseline_statistical_summary"] = baseline_statistical.summary_path
    artifact_paths["candidate_statistical_summary"] = candidate_statistical.summary_path

    baseline_gpd_str_status, baseline_gpd_str, baseline_gpd_str_reason = (
        _baseline_deficit_evaluation(package_artifacts.event_package)
    )
    candidate_gpd_str_status, candidate_gpd_str, candidate_gpd_str_reason = (
        _candidate_deficit_evaluation(package_artifacts.event_package)
    )
    baseline_hard_only = TargetedSearchEvaluation(
        exact_structural_status=(
            "feasible" if hard_only_exact.feasible else "infeasible"
        ),
        exact_feasible=hard_only_exact.feasible,
        exact_respecting_tuple_count=hard_only_exact.respecting_tuple_count,
        gpd_str_status=baseline_gpd_str_status,
        gpd_str=baseline_gpd_str,
        gpd_str_reason=baseline_gpd_str_reason,
        gpd_stat_status=(
            "solved" if baseline_statistical.result.solved else "unsolved"
        ),
        gpd_stat=baseline_statistical.result.gpd_stat,
        gpd_stat_reason=baseline_statistical.result.reason,
    )
    all_accepted_proposals = TargetedSearchEvaluation(
        exact_structural_status=(
            "feasible" if all_proposals_exact.feasible else "infeasible"
        ),
        exact_feasible=all_proposals_exact.feasible,
        exact_respecting_tuple_count=all_proposals_exact.respecting_tuple_count,
        gpd_str_status=candidate_gpd_str_status,
        gpd_str=candidate_gpd_str,
        gpd_str_reason=candidate_gpd_str_reason,
        gpd_stat_status=(
            "solved" if candidate_statistical.result.solved else "unsolved"
        ),
        gpd_stat=candidate_statistical.result.gpd_stat,
        gpd_stat_reason=candidate_statistical.result.reason,
    )
    sec_status, sec_mean = _sec_summary(candidates)
    accepted_coarse_proposal_count = sum(
        1
        for row in candidates.candidate_rows
        if row.accepted and (row.left_is_proper_coarse or row.right_is_proper_coarse)
    )
    row = TargetedSearchRow(
        row_format_version="targeted-search-row.v1",
        search_id=search.search_id,
        point_id=point.point_id,
        config_path=point.config_artifact,
        preparation_id=point.preparation_id,
        protocol_id=point.protocol_id,
        trajectories=point.trajectories,
        seed=point.seed,
        raw_run_path=substrate_artifacts.run_trace_path,
        discovered_context_family_path=discovery_artifacts.family_path,
        event_package_path=package_artifacts.event_package_path,
        provenance_classification=provenance_artifacts.result.admissibility_classification,
        accepted_context_count=family.diagnostics_summary.accepted_context_count,
        accepted_singleton_event_count=package_artifacts.discovered_event_family.diagnostics_summary.accepted_singleton_event_count,
        accepted_coarse_event_count=package_artifacts.discovered_event_family.diagnostics_summary.accepted_coarse_event_count,
        accepted_shared_event_proposal_count=len(
            package_artifacts.event_package.equality_proposals
        ),
        accepted_coarse_proposal_count=accepted_coarse_proposal_count,
        baseline_hard_only=baseline_hard_only,
        all_accepted_proposals=all_accepted_proposals,
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status=sec_status,
        sec_mean=sec_mean,
        rm_status="not_applicable",
        rm_overall=None,
        candidate_classification="inconclusive",
        run_ids=run_ids,
        artifact_paths=artifact_paths,
        notes=notes
        + [
            "ccd_not_applicable_without_repeated_read_trace",
            "rm_not_applicable_without_route_observations",
        ],
    )
    return row.model_copy(
        update={
            "candidate_classification": _candidate_classification(
                row=row,
                search=search,
                blocking_classification=(
                    "no_respecting_tuples"
                    if all_proposals_exact.reason == "no_respecting_tuples"
                    else all_proposals_exact.reason
                ),
            )
        }
    )


def run_targeted_nonextendability_search(
    *,
    search_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> TargetedSearchArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    search = load_targeted_nonextendability_search(search_path)
    bundle_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or search.search_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = bundle_dir.parents[2]
    search_relpath = repo_relative_path(search_path, root=effective_root)
    derived_dir = bundle_dir / "derived"
    derived_dir.mkdir()

    rows = [
        _run_point(
            point=point,
            search=search,
            category=category,
            timestamp=timestamp,
            root=effective_root,
            derived_dir=derived_dir,
        )
        for point in search.points
    ]
    table = TargetedSearchTable(
        table_format_version="targeted-search-results.v1",
        search_id=search.search_id,
        row_count=len(rows),
        rows=rows,
        metadata={
            "classification_rule_version": CLASSIFICATION_RULE_VERSION,
            "search_artifact": search_relpath,
        },
    )

    classification_counter = Counter(row.candidate_classification for row in table.rows)
    classification_counts: dict[str, int] = {
        label: classification_counter.get(label, 0)
        for label in [
            "strongly_nonextendable_candidate",
            "weakly_frustrated_candidate",
            "extendable_candidate",
            "trivial_or_nonrecording",
            "inconclusive",
        ]
    }

    strong_candidates = [
        row
        for row in table.rows
        if row.candidate_classification == "strongly_nonextendable_candidate"
    ]
    strong_candidates.sort(
        key=lambda row: (
            -(row.all_accepted_proposals.gpd_str or 0.0),
            row.all_accepted_proposals.exact_respecting_tuple_count
            if row.all_accepted_proposals.exact_respecting_tuple_count is not None
            else 10**9,
            -row.accepted_coarse_proposal_count,
            row.point_id,
        )
    )
    best_candidate = strong_candidates[0] if strong_candidates else None
    negative_result = best_candidate is None

    table_csv_path = bundle_dir / "targeted-search.csv"
    table_json_path = bundle_dir / "targeted-search.json"
    summary_path = bundle_dir / "targeted-search-summary.json"
    note_path = bundle_dir / "targeted-search-note.md"
    result_note_path = bundle_dir / "result-note.json"
    manifest_path = bundle_dir / "run-manifest.json"
    best_candidate_path = bundle_dir / "best-candidate.json"
    negative_result_path = bundle_dir / "negative-result.json"
    output_paths = {
        "table_csv": repo_relative_path(table_csv_path, root=effective_root),
        "table_json": repo_relative_path(table_json_path, root=effective_root),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
        "best_candidate": repo_relative_path(best_candidate_path, root=effective_root),
        "negative_result": repo_relative_path(
            negative_result_path, root=effective_root
        ),
    }

    csv_rows = [_row_to_csv_record(row) for row in table.rows]
    fieldnames = list(csv_rows[0]) if csv_rows else []
    with table_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in csv_rows:
            writer.writerow(record)

    table_json_path.write_text(
        json.dumps(table.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "search_id": search.search_id,
        "config_family": [point.config_artifact for point in search.points],
        "extraction_thresholds": search.extraction_thresholds.model_dump(mode="json"),
        "coarse_event_generation_thresholds": search.coarse_event_generation_thresholds.model_dump(
            mode="json"
        ),
        "shared_event_inference_thresholds": search.shared_event_inference_thresholds.model_dump(
            mode="json"
        ),
        "provenance_required": search.provenance_required,
        "candidate_classification_thresholds": search.candidate_classification_thresholds.model_dump(
            mode="json"
        ),
        "stop_rule": search.stop_rule.model_dump(mode="json"),
        "classification_rule_version": CLASSIFICATION_RULE_VERSION,
        "classification_counts": classification_counts,
        "best_candidate_id": None
        if best_candidate is None
        else best_candidate.point_id,
        "negative_result": negative_result,
        "table_csv_path": output_paths["table_csv"],
        "table_json_path": output_paths["table_json"],
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    note_path.write_text(
        _render_note(
            search=search,
            table=table,
            classification_counts=classification_counts,
            best_candidate_id=None
            if best_candidate is None
            else best_candidate.point_id,
            negative_result=negative_result,
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )

    if best_candidate is not None:
        best_candidate_path.write_text(
            json.dumps(best_candidate.model_dump(mode="json"), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    if negative_result:
        negative_result_path.write_text(
            json.dumps(
                {
                    "search_id": search.search_id,
                    "negative_result": True,
                    "reason": "no_strongly_nonextendable_candidate_found_in_committed_family",
                    "point_count": len(search.points),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    result_note = _build_result_note(
        run_id=run_id,
        table=table,
        classification_counts=classification_counts,
        best_candidate_id=None if best_candidate is None else best_candidate.point_id,
        negative_result=negative_result,
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
            "search",
            "run-targeted-nonextendability",
            search_relpath,
        ],
        seed=seed,
        input_artifacts={"search": search_relpath},
        output_artifacts={
            "table_csv": output_paths["table_csv"],
            "table_json": output_paths["table_json"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
            **(
                {"best_candidate": output_paths["best_candidate"]}
                if best_candidate is not None
                else {"negative_result": output_paths["negative_result"]}
            ),
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "targeted_nonextendability_search",
            "search_id": search.search_id,
            "point_count": table.row_count,
            "classification_rule_version": CLASSIFICATION_RULE_VERSION,
            "negative_result": negative_result,
            "best_candidate_id": None
            if best_candidate is None
            else best_candidate.point_id,
        },
    )
    write_run_manifest(manifest, run_dir=bundle_dir)
    return TargetedSearchArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(bundle_dir, root=effective_root),
        table_csv_path=output_paths["table_csv"],
        table_json_path=output_paths["table_json"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        table=table,
        classification_counts=classification_counts,
        best_candidate_path=(
            None if best_candidate is None else output_paths["best_candidate"]
        ),
        negative_result_path=(
            output_paths["negative_result"] if negative_result else None
        ),
    )
