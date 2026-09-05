from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import statistics
import sys

from ..audits import compute_shared_event_consistency
from ..provenance.audit import write_provenance_audit_report
from ..reporting.flattening_report import write_flattening_intervention_report
from ..reporting.hidden_record_report import write_hidden_record_intervention_report
from ..reporting.statistical_report import write_statistical_summary
from ..robustness.models import (
    NoiseRobustnessSweep,
    NoiseRobustnessTarget,
    RobustnessTraceArtifacts,
)
from ..robustness.noise_runner import run_noise_robustness_sweep
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import DownstreamProbe, ObservationTrace
from ..schemas.result_note import ResultNote
from ..search.models import TargetedSearchEvaluation
from ..search.targeted_nonextendability import (
    _baseline_deficit_evaluation,
    _candidate_deficit_evaluation,
    _derive_stat_trace,
    _load_candidates,
    _load_family,
)
from ..solvers.structural_exact import solve_exact_structural_feasibility
from ..validation import load_model
from .models import (
    DiscoveredCaseFalsification,
    DiscoveredCaseFalsificationResult,
    DiscoveredCaseVerdict,
    FalsificationInterventionResult,
    RobustnessSubrunResult,
)


VERDICT_RULE_VERSION = "discovered-case-falsification.v1"


@dataclass(slots=True)
class DiscoveredCaseFalsificationArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    result: DiscoveredCaseFalsificationResult


def load_discovered_case_falsification(
    path: str | Path,
) -> DiscoveredCaseFalsification:
    model = load_model(path, kind="discovered-case-falsification")
    assert isinstance(model, DiscoveredCaseFalsification)
    return model


def _load_package(path: str | Path) -> EventPackageInstance:
    model = load_model(path, kind="event-package-instance")
    assert isinstance(model, EventPackageInstance)
    return model


def _load_raw_run(path: str | Path):
    model = load_model(path, kind="substrate-run")
    assert model is not None
    return model


def _write_trace(path: Path, trace: ObservationTrace) -> str:
    path.write_text(
        json.dumps(trace.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path.as_posix()


def _derive_sec_trace(
    *,
    instance: EventPackageInstance,
    candidates,
    stat_trace: ObservationTrace,
    trace_id: str,
) -> ObservationTrace | None:
    accepted_rows = [
        row
        for row in candidates.candidate_rows
        if row.accepted
        and row.proposed_proposal_id is not None
        and row.probe_comparisons
    ]
    if not accepted_rows:
        return None

    grouped_counts: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for row in accepted_rows:
        for comparison in row.probe_comparisons:
            grouped_counts[
                (row.left_event_id, row.left_context_id, comparison.probe_context_id)
            ].update(comparison.left_support_counts)
            grouped_counts[
                (row.right_event_id, row.right_context_id, comparison.probe_context_id)
            ].update(comparison.right_support_counts)

    downstream_probes = [
        DownstreamProbe(
            probe_id=probe_id,
            event_id=event_id,
            context_id=context_id,
            signature=f"{event_id}::{probe_id}",
            outcome_counts=dict(sorted(counts.items())),
        )
        for (event_id, context_id, probe_id), counts in sorted(grouped_counts.items())
    ]

    if not downstream_probes:
        return None

    return ObservationTrace(
        trace_format_version="observation-trace.v1",
        trace_id=trace_id,
        instance_id=instance.instance_id,
        instance_artifact=stat_trace.instance_artifact,
        observations=stat_trace.observations,
        downstream_probes=downstream_probes,
        metadata={
            "derived_from": "shared_event_candidates",
            "derivation_kind": "discovered_case_sec_trace",
        },
    )


def _sec_summary(
    instance: EventPackageInstance, sec_trace: ObservationTrace | None
) -> tuple[str, float | None]:
    if sec_trace is None:
        return ("not_applicable", None)
    result = compute_shared_event_consistency(instance, [sec_trace])
    scores = [
        row.approx_score
        for row in result.event_pair_results
        if row.approx_score is not None and not row.insufficient_data
    ]
    if not result.event_pair_results:
        return ("not_applicable", None)
    if not scores:
        return ("insufficient_data", None)
    return ("scored", statistics.mean(scores))


def _baseline_evaluations(
    *,
    instance: EventPackageInstance,
    instance_artifact: str,
    family,
    raw_run,
    bundle_dir: Path,
    category: str,
    label_prefix: str,
    seed: int,
    timestamp: str | None,
    root: Path,
) -> tuple[
    object, object, TargetedSearchEvaluation, TargetedSearchEvaluation, str, str
]:
    stat_trace = _derive_stat_trace(
        family=family,
        raw_run=raw_run,
        instance_id=instance.instance_id,
        instance_artifact=instance_artifact,
        trace_id=f"trace_{label_prefix}_stat",
    )
    derived_dir = bundle_dir / "derived"
    derived_dir.mkdir(exist_ok=True)
    stat_trace_path = derived_dir / "stat-clean.json"
    _write_trace(stat_trace_path, stat_trace)
    stat_trace_relpath = repo_relative_path(stat_trace_path, root=root)

    baseline_statistical = write_statistical_summary(
        instance,
        [stat_trace],
        instance_path=instance_artifact,
        trace_paths=[stat_trace_relpath],
        category=category,
        label=f"{label_prefix}-baseline-statistical",
        seed=seed,
        timestamp=timestamp,
        root=root,
        include_soft=False,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "falsification",
            "run-discovered-case",
            instance_artifact,
        ],
    )
    candidate_statistical = write_statistical_summary(
        instance,
        [stat_trace],
        instance_path=instance_artifact,
        trace_paths=[stat_trace_relpath],
        category=category,
        label=f"{label_prefix}-candidate-statistical",
        seed=seed,
        timestamp=timestamp,
        root=root,
        include_soft=True,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "falsification",
            "run-discovered-case",
            instance_artifact,
        ],
    )

    hard_only_exact = solve_exact_structural_feasibility(instance)
    all_proposals_exact = solve_exact_structural_feasibility(
        instance, include_soft=True
    )
    baseline_gpd_status, baseline_gpd_str, baseline_gpd_reason = (
        _baseline_deficit_evaluation(instance)
    )
    candidate_gpd_status, candidate_gpd_str, candidate_gpd_reason = (
        _candidate_deficit_evaluation(instance)
    )

    baseline_hard_only = TargetedSearchEvaluation(
        exact_structural_status=(
            "feasible" if hard_only_exact.feasible else "infeasible"
        ),
        exact_feasible=hard_only_exact.feasible,
        exact_respecting_tuple_count=hard_only_exact.respecting_tuple_count,
        gpd_str_status=baseline_gpd_status,
        gpd_str=baseline_gpd_str,
        gpd_str_reason=baseline_gpd_reason,
        gpd_stat_status=(
            "solved" if baseline_statistical.result.solved else "unsolved"
        ),
        gpd_stat=baseline_statistical.result.gpd_stat,
        gpd_stat_reason=baseline_statistical.result.reason,
    )
    baseline_all_accepted = TargetedSearchEvaluation(
        exact_structural_status=(
            "feasible" if all_proposals_exact.feasible else "infeasible"
        ),
        exact_feasible=all_proposals_exact.feasible,
        exact_respecting_tuple_count=all_proposals_exact.respecting_tuple_count,
        gpd_str_status=candidate_gpd_status,
        gpd_str=candidate_gpd_str,
        gpd_str_reason=candidate_gpd_reason,
        gpd_stat_status=(
            "solved" if candidate_statistical.result.solved else "unsolved"
        ),
        gpd_stat=candidate_statistical.result.gpd_stat,
        gpd_stat_reason=candidate_statistical.result.reason,
    )
    return (
        baseline_statistical,
        candidate_statistical,
        baseline_hard_only,
        baseline_all_accepted,
        stat_trace_relpath,
        repo_relative_path(derived_dir, root=root),
    )


def _run_hidden_record(
    config,
    *,
    category: str,
    label_prefix: str,
    seed: int,
    timestamp: str | None,
    root: Path,
) -> FalsificationInterventionResult:
    if not config.applicable:
        return FalsificationInterventionResult(
            applicability_status="not_applicable",
            outcome=None,
            reason=config.reason or "hidden_record_not_configured_for_selected_case",
        )
    report = write_hidden_record_intervention_report(
        intervention_path=config.intervention_artifact,
        category=category,
        label=f"{label_prefix}-hidden-record",
        seed=seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "interventions",
            "hidden-record",
            config.intervention_artifact,
        ],
    )
    return FalsificationInterventionResult(
        applicability_status="completed",
        outcome=report.conclusion,
        reason=None,
        run_id=report.run_id,
        summary_artifact=report.summary_path,
        note_artifact=report.note_path,
        result_note_artifact=report.result_note_path,
        manifest_artifact=report.manifest_path,
    )


def _run_flattening(
    config,
    *,
    category: str,
    label_prefix: str,
    seed: int,
    timestamp: str | None,
    root: Path,
) -> FalsificationInterventionResult:
    if not config.applicable:
        return FalsificationInterventionResult(
            applicability_status="not_applicable",
            outcome=None,
            reason=config.reason or "flattening_not_configured_for_selected_case",
        )
    report = write_flattening_intervention_report(
        intervention_path=config.intervention_artifact,
        category=category,
        label=f"{label_prefix}-flattening",
        seed=seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "interventions",
            "flattening",
            config.intervention_artifact,
        ],
    )
    return FalsificationInterventionResult(
        applicability_status="completed",
        outcome=report.conclusion,
        reason=None,
        run_id=report.run_id,
        summary_artifact=report.summary_path,
        note_artifact=report.note_path,
        result_note_artifact=report.result_note_path,
        manifest_artifact=report.manifest_path,
    )


def _run_robustness(
    *,
    falsification: DiscoveredCaseFalsification,
    bundle_dir: Path,
    root: Path,
    category: str,
    label_prefix: str,
    stat_trace_artifact: str,
    sec_trace_artifact: str | None,
    seed: int,
    timestamp: str | None,
) -> RobustnessSubrunResult:
    sweep = NoiseRobustnessSweep(
        sweep_format_version="noise-robustness-sweep.v1",
        sweep_id=f"{falsification.falsification_id}_robustness",
        targets=[
            NoiseRobustnessTarget(
                target_id=falsification.selected_case.case_id,
                target_type="discovered_package",
                event_package_artifact=falsification.selected_case.event_package_artifact,
                trace_artifacts=RobustnessTraceArtifacts(
                    stat=stat_trace_artifact,
                    sec=sec_trace_artifact,
                ),
                notes=["selected_discovered_case"],
            )
        ],
        noise_grid=falsification.robustness.noise_grid,
        noise_model=falsification.robustness.noise_model,
        metric_thresholds=falsification.robustness.metric_thresholds,
        metadata={
            "falsification_id": falsification.falsification_id,
            "selected_case_id": falsification.selected_case.case_id,
        },
    )
    sweep_path = bundle_dir / "derived" / "robustness-input.json"
    sweep_path.write_text(
        json.dumps(sweep.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    artifacts = run_noise_robustness_sweep(
        sweep_path=sweep_path,
        category=category,
        label=f"{label_prefix}-robustness",
        seed=seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "robustness",
            "run-sweep",
            repo_relative_path(sweep_path, root=root),
        ],
    )
    target_crossings = artifacts.threshold_crossings["targets"][
        falsification.selected_case.case_id
    ]
    first_crossings = {
        metric: details["first_crossing_noise_level"]
        for metric, details in target_crossings.items()
    }
    return RobustnessSubrunResult(
        applicability_status="completed",
        run_id=artifacts.run_id,
        summary_artifact=artifacts.summary_path,
        note_artifact=artifacts.note_path,
        threshold_crossings_artifact=artifacts.threshold_crossings_path,
        result_note_artifact=artifacts.result_note_path,
        manifest_artifact=artifacts.manifest_path,
        first_crossings=first_crossings,
        notes=["rm_or_ccd_may_be_not_applicable_if_no_clean_trace_was_derivable"],
    )


def _verdict(
    *,
    baseline_all_accepted,
    hidden_record: FalsificationInterventionResult,
    flattening: FalsificationInterventionResult,
) -> DiscoveredCaseVerdict:
    if (
        baseline_all_accepted.exact_feasible is True
        and baseline_all_accepted.gpd_str_status == "solved"
        and baseline_all_accepted.gpd_str == 0
    ):
        return "no_baseline_obstruction"
    if hidden_record.outcome == "disappeared" or flattening.outcome == "repairable":
        return "disappeared"
    if hidden_record.outcome == "weakened" or flattening.outcome == "weakened":
        return "weakened"
    if baseline_all_accepted.gpd_str_status != "solved":
        return "inconclusive"
    return "survived"


def _build_result_note(
    *,
    run_id: str,
    result: DiscoveredCaseFalsificationResult,
    output_paths: dict[str, str],
) -> ResultNote:
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[result.selected_case_id],
        metrics={
            "baseline_candidate_exact_feasible": result.baseline_all_accepted_proposals.exact_feasible,
            "baseline_candidate_gpd_str": result.baseline_all_accepted_proposals.gpd_str,
            "baseline_hard_only_exact_feasible": result.baseline_hard_only.exact_feasible,
            "sec_mean": result.sec_mean,
            "final_verdict": result.final_verdict,
        },
        interpretation=(
            "The selected discovered case is assessed under baseline hard-only and all-accepted-proposals modes, then stress-tested with intervention and robustness subruns before assigning a falsification verdict."
        ),
        caveats=[
            "RM is diagnostic-only when present.",
            "not_applicable / unsolved / insufficient_data statuses are preserved explicitly.",
        ],
        artifact_refs=output_paths,
        metadata={"verdict_rule_version": VERDICT_RULE_VERSION},
    )


def _render_note(
    *,
    falsification: DiscoveredCaseFalsification,
    selection_payload: dict[str, object],
    result: DiscoveredCaseFalsificationResult,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Discovered Case Falsification",
        "",
        "## Selected discovered case",
        f"- Case ID: `{result.selected_case_id}`",
        f"- Selection artifact: `{falsification.selected_case.selection_artifact}`",
        f"- Selection rationale: `{selection_payload.get('selection_rationale')}`",
        "",
        "## Baseline evaluation modes",
        f"- Hard-only exact feasible: `{result.baseline_hard_only.exact_feasible}`",
        f"- Hard-only `gpd_str`: `{result.baseline_hard_only.gpd_str}`",
        f"- Hard-only `gpd_stat`: `{result.baseline_hard_only.gpd_stat}`",
        f"- All-accepted-proposals exact feasible: `{result.baseline_all_accepted_proposals.exact_feasible}`",
        f"- All-accepted-proposals `gpd_str`: `{result.baseline_all_accepted_proposals.gpd_str}`",
        f"- All-accepted-proposals `gpd_stat`: `{result.baseline_all_accepted_proposals.gpd_stat}`",
        f"- SEC status / mean: `{result.sec_status}` / `{result.sec_mean}`",
        f"- CCD status / overall: `{result.ccd_status}` / `{result.ccd_overall}`",
        f"- RM status / overall: `{result.rm_status}` / `{result.rm_overall}`",
        "",
        "## Hidden-record outcome",
        f"- Applicability: `{result.hidden_record.applicability_status}`",
        f"- Outcome: `{result.hidden_record.outcome}`",
        f"- Reason: `{result.hidden_record.reason}`",
        "",
        "## Flattening outcome",
        f"- Applicability: `{result.flattening.applicability_status}`",
        f"- Outcome: `{result.flattening.outcome}`",
        f"- Reason: `{result.flattening.reason}`",
        "",
        "## Robustness summary",
        f"- Applicability: `{result.robustness.applicability_status}`",
        f"- First crossings: `{result.robustness.first_crossings}`",
        "",
        "## Final verdict",
        f"- Verdict: `{result.final_verdict}`",
        "",
        "## Notes",
        "- All-accepted-proposals mode is the primary obstruction-testing mode for discovered packages.",
        "- RM is diagnostic-only where present.",
        "- not_applicable / unsolved / insufficient_data statuses are preserved explicitly.",
        "",
        "## Artifact references",
    ]
    for key, value in output_paths.items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def run_discovered_case_falsification(
    *,
    falsification_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> DiscoveredCaseFalsificationArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    source_root = Path.cwd().resolve()
    falsification = load_discovered_case_falsification(falsification_path)
    bundle_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or falsification.falsification_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = bundle_dir.parents[2]
    derived_dir = bundle_dir / "derived"
    derived_dir.mkdir()

    package = _load_package(
        source_root / falsification.selected_case.event_package_artifact
    )
    family = _load_family(
        source_root / falsification.selected_case.discovered_context_family_artifact
    )
    raw_run = _load_raw_run(source_root / falsification.selected_case.raw_run_artifact)
    candidates = _load_candidates(
        source_root / falsification.selected_case.shared_event_candidates_artifact
    )
    selection_payload = json.loads(
        (source_root / falsification.selected_case.selection_artifact).read_text(
            encoding="utf-8"
        )
    )

    local_case_dir = derived_dir / "selected-case"
    local_case_dir.mkdir()
    local_package_path = local_case_dir / "event-package.json"
    local_package_path.write_text(
        (source_root / falsification.selected_case.event_package_artifact).read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    local_provenance_path = local_case_dir / "package-provenance.json"
    local_provenance_path.write_text(
        (
            source_root / falsification.selected_case.package_provenance_artifact
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    provenance_artifacts = write_provenance_audit_report(
        package_path=local_package_path,
        provenance_path=local_provenance_path,
        category=category,
        label=f"{falsification.falsification_id}-provenance",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "provenance",
            falsification.selected_case.event_package_artifact,
            "--provenance",
            falsification.selected_case.package_provenance_artifact,
        ],
    )

    (
        baseline_statistical,
        candidate_statistical,
        baseline_hard_only,
        baseline_all_accepted,
        stat_trace_artifact,
        _,
    ) = _baseline_evaluations(
        instance=package,
        instance_artifact=falsification.selected_case.event_package_artifact,
        family=family,
        raw_run=raw_run,
        bundle_dir=bundle_dir,
        category=category,
        label_prefix=falsification.falsification_id,
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
    )

    stat_trace_model = load_model(
        effective_root / stat_trace_artifact, kind="observation-trace"
    )
    assert isinstance(stat_trace_model, ObservationTrace)
    sec_trace_model = _derive_sec_trace(
        instance=package,
        candidates=candidates,
        stat_trace=stat_trace_model,
        trace_id=f"trace_{falsification.falsification_id}_sec",
    )
    sec_trace_artifact: str | None = None
    if sec_trace_model is not None:
        sec_trace_path = derived_dir / "sec-clean.json"
        _write_trace(sec_trace_path, sec_trace_model)
        sec_trace_artifact = repo_relative_path(sec_trace_path, root=effective_root)

    sec_status, sec_mean = _sec_summary(package, sec_trace_model)
    hidden_record = _run_hidden_record(
        falsification.hidden_record,
        category=category,
        label_prefix=falsification.falsification_id,
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
    )
    flattening = _run_flattening(
        falsification.flattening,
        category=category,
        label_prefix=falsification.falsification_id,
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
    )
    robustness = _run_robustness(
        falsification=falsification,
        bundle_dir=bundle_dir,
        root=effective_root,
        category=category,
        label_prefix=falsification.falsification_id,
        stat_trace_artifact=stat_trace_artifact,
        sec_trace_artifact=sec_trace_artifact,
        seed=seed,
        timestamp=timestamp,
    )
    verdict = _verdict(
        baseline_all_accepted=baseline_all_accepted,
        hidden_record=hidden_record,
        flattening=flattening,
    )

    summary_path = bundle_dir / "falsification-summary.json"
    note_path = bundle_dir / "falsification-note.md"
    result_note_path = bundle_dir / "result-note.json"
    manifest_path = bundle_dir / "run-manifest.json"
    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
        "selection": falsification.selected_case.selection_artifact,
        "event_package": falsification.selected_case.event_package_artifact,
        "package_provenance": falsification.selected_case.package_provenance_artifact,
        "raw_run": falsification.selected_case.raw_run_artifact,
        "discovered_context_family": falsification.selected_case.discovered_context_family_artifact,
        "shared_event_candidates": falsification.selected_case.shared_event_candidates_artifact,
        "provenance_audit_summary": provenance_artifacts.summary_path,
        "baseline_statistical_summary": baseline_statistical.summary_path,
        "candidate_statistical_summary": candidate_statistical.summary_path,
        "stat_trace": stat_trace_artifact,
    }
    if sec_trace_artifact is not None:
        output_paths["sec_trace"] = sec_trace_artifact
    if hidden_record.summary_artifact is not None:
        output_paths["hidden_record_summary"] = hidden_record.summary_artifact
    if flattening.summary_artifact is not None:
        output_paths["flattening_summary"] = flattening.summary_artifact
    output_paths["robustness_summary"] = robustness.summary_artifact or ""
    output_paths["robustness_threshold_crossings"] = (
        robustness.threshold_crossings_artifact or ""
    )

    result = DiscoveredCaseFalsificationResult(
        result_format_version="discovered-case-falsification-result.v1",
        falsification_id=falsification.falsification_id,
        selected_case_id=falsification.selected_case.case_id,
        selected_source_refs={
            "event_package": falsification.selected_case.event_package_artifact,
            "package_provenance": falsification.selected_case.package_provenance_artifact,
            "raw_run": falsification.selected_case.raw_run_artifact,
            "discovered_context_family": falsification.selected_case.discovered_context_family_artifact,
            "shared_event_candidates": falsification.selected_case.shared_event_candidates_artifact,
            "source_config": falsification.selected_case.source_config_artifact,
            "selection": falsification.selected_case.selection_artifact,
        },
        provenance_classification=provenance_artifacts.result.admissibility_classification,
        baseline_hard_only=baseline_hard_only,
        baseline_all_accepted_proposals=baseline_all_accepted,
        sec_status=sec_status,
        sec_mean=sec_mean,
        ccd_status="not_applicable",
        ccd_overall=None,
        rm_status="not_applicable",
        rm_overall=None,
        hidden_record=hidden_record,
        flattening=flattening,
        robustness=robustness,
        final_verdict=verdict,
        artifact_refs={key: value for key, value in output_paths.items() if value},
        notes=[
            "selected_from_t31_negative_result_family",
            "candidate_mode_is_primary_for_obstruction_testing",
        ],
    )
    summary_path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(
        _render_note(
            falsification=falsification,
            selection_payload=selection_payload,
            result=result,
            output_paths={key: value for key, value in output_paths.items() if value},
        ),
        encoding="utf-8",
    )

    result_note = _build_result_note(
        run_id=run_id,
        result=result,
        output_paths={key: value for key, value in output_paths.items() if value},
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
            "falsification",
            "run-discovered-case",
            repo_relative_path(falsification_path, root=effective_root),
        ],
        seed=seed,
        input_artifacts={
            "falsification": repo_relative_path(falsification_path, root=effective_root)
        },
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "discovered_case_falsification",
            "falsification_id": falsification.falsification_id,
            "selected_case_id": falsification.selected_case.case_id,
            "final_verdict": verdict,
            "verdict_rule_version": VERDICT_RULE_VERSION,
        },
    )
    write_run_manifest(manifest, run_dir=bundle_dir)
    return DiscoveredCaseFalsificationArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(bundle_dir, root=effective_root),
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=repo_relative_path(manifest_path, root=effective_root),
        result=result,
    )
