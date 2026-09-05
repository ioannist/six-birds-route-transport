from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import sys

from ..audits.models import QuotientFeasibilityResult
from ..discovery.models import DiscoveredContextFamily, SharedEventCandidates
from ..discovery.shared_event_inference import _project_pica_row_label
from ..pica_bridge.ingest import load_pica_export_bundle
from ..robustness.models import (
    NoiseRobustnessSweep,
    NoiseRobustnessTarget,
    RobustnessTraceArtifacts,
)
from ..robustness.noise_runner import (
    NoiseRobustnessArtifacts,
    run_noise_robustness_sweep,
)
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import DownstreamProbe, Observation, ObservationTrace
from ..schemas.result_note import ResultNote
from ..solvers.statistical_deficit import solve_statistical_deficit_from_trace
from ..validation import load_model
from .models import (
    FlagshipControlBundle,
    FlagshipControlCaseConfig,
    FlagshipControlCaseResult,
    FlagshipControlResult,
    FlagshipControlSummary,
    FlagshipControlVerdict,
    FlagshipMetricSnapshot,
    FlagshipMetricValue,
)


VERDICT_RULE_VERSION = "flagship-control-bundle.v1"


@dataclass(slots=True)
class FlagshipControlBundleArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    note_path: str
    table_json_path: str
    table_csv_path: str
    result_note_path: str
    manifest_path: str
    result: FlagshipControlResult


def load_flagship_control_bundle(path: str | Path) -> FlagshipControlBundle:
    model = load_model(path, kind="flagship-control-bundle")
    assert isinstance(model, FlagshipControlBundle)
    return model


def _load_event_package(path: str | Path) -> EventPackageInstance:
    model = load_model(path, kind="event-package-instance")
    assert isinstance(model, EventPackageInstance)
    return model


def _load_family(path: str | Path) -> DiscoveredContextFamily:
    model = load_model(path, kind="discovered-context-family")
    assert isinstance(model, DiscoveredContextFamily)
    return model


def _load_candidates(path: str | Path) -> SharedEventCandidates:
    model = load_model(path, kind="shared-event-candidates")
    assert isinstance(model, SharedEventCandidates)
    return model


def _load_quotient_result(path: str | Path) -> QuotientFeasibilityResult:
    model = load_model(path, kind="quotient-feasibility-result")
    assert isinstance(model, QuotientFeasibilityResult)
    return model


def _resolve_source_path(path: str | Path, *, source_root: Path) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate.resolve()
    rooted = source_root / candidate
    if rooted.exists():
        return rooted.resolve()
    raise FileNotFoundError(f"referenced source artifact not found: {path}")


def _copy_repo_artifact(source_path: Path, destination_path: Path) -> str:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(
        source_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return destination_path.as_posix()


def _write_trace(path: Path, trace: ObservationTrace) -> str:
    path.write_text(
        json.dumps(trace.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path.as_posix()


def _default_metric(reason: str) -> FlagshipMetricValue:
    return FlagshipMetricValue(status="not_applicable", value=None, reason=reason)


def _metric_from_statistical_trace(
    *,
    instance: EventPackageInstance,
    trace: ObservationTrace,
) -> FlagshipMetricValue:
    try:
        result = solve_statistical_deficit_from_trace(
            instance, trace, include_soft=True
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        return FlagshipMetricValue(
            status="unsolved",
            value=None,
            reason=f"statistical_deficit_failed:{type(exc).__name__}",
        )
    if result.solved and result.gpd_stat is not None:
        return FlagshipMetricValue(status="solved", value=float(result.gpd_stat))
    return FlagshipMetricValue(
        status="unsolved",
        value=None,
        reason=result.reason or "statistical_deficit_unsolved",
    )


def _metric_with_override(
    override: FlagshipMetricValue | None,
    *,
    default_reason: str,
) -> FlagshipMetricValue:
    if override is not None:
        return override
    return _default_metric(default_reason)


def _snapshot_from_quotient(
    *,
    quotient_result: QuotientFeasibilityResult,
    gpd_str: FlagshipMetricValue,
    gpd_stat: FlagshipMetricValue,
) -> FlagshipMetricSnapshot:
    accepted = quotient_result.accepted_proposal_set_result
    return FlagshipMetricSnapshot(
        witness_classification=quotient_result.witness_classification,
        exact_feasible=accepted.exact_feasible,
        survivor_count=accepted.survivor_count,
        failure_reason=accepted.exact_failure_reason,
        quotient_class_count=quotient_result.quotient_summary.quotient_class_count,
        uncovered_atom_count=len(accepted.uncovered_atom_refs),
        gpd_str=gpd_str,
        gpd_stat=gpd_stat,
    )


def _derive_stat_trace_from_pica_bundle(
    *,
    family: DiscoveredContextFamily,
    instance_id: str,
    event_package_artifact: str,
    bundle_path: str | Path,
    source_root: Path,
    trace_id: str,
) -> ObservationTrace:
    resolved = load_pica_export_bundle(
        _resolve_source_path(bundle_path, source_root=source_root),
        repo_root=source_root,
    )
    observations: list[Observation] = []
    for context in family.accepted_contexts:
        metadata = context.source_metadata
        run_id = metadata.run_ids[0] if len(metadata.run_ids) == 1 else None
        rows = resolved.filter_rows(
            run_id=run_id,
            preparation_id=metadata.preparation_id,
            protocol_id=metadata.protocol_id,
            closure_id=metadata.closure_id,
            lens_id=metadata.lens_id,
            level_id=metadata.level_id,
            resolution_id=metadata.resolution_id,
            protocol_step_id=metadata.protocol_step_id,
            step_index=metadata.step_index,
        )
        label_to_outcome = {
            outcome.observation_label: outcome.outcome_id
            for outcome in context.atomic_outcomes
        }
        counts: Counter[str] = Counter()
        for row in rows:
            label = _project_pica_row_label(row, metadata)
            if label is None:
                continue
            outcome_id = label_to_outcome.get(label)
            if outcome_id is not None:
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
        instance_artifact=event_package_artifact,
        observations=observations,
        metadata={
            "derived_from": "pica_export_bundle",
            "derivation_kind": "flagship_control_bundle_stat_trace",
        },
    )


def _derive_sec_trace(
    *,
    instance: EventPackageInstance,
    candidates: SharedEventCandidates,
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
            "derivation_kind": "flagship_control_bundle_sec_trace",
        },
    )


def _not_applicable_summary(
    *,
    baseline: FlagshipMetricSnapshot,
    reason: str,
) -> FlagshipControlSummary:
    return FlagshipControlSummary(
        applicability_status="not_applicable",
        verdict="not_applicable",
        reason=reason,
        pre_control=baseline,
        post_control=None,
        run_id=None,
        artifact_refs={},
        first_crossings={},
        notes=[],
    )


def _robustness_verdict(
    *,
    baseline: FlagshipMetricSnapshot,
    post: FlagshipMetricSnapshot,
) -> FlagshipControlVerdict:
    if post.exact_feasible is True or (
        post.witness_classification != "accepted_proposal_obstruction"
    ):
        return "disappeared"
    if post.gpd_stat.status == "unsolved":
        return "inconclusive"
    return "survived"


def _run_robustness_control(
    *,
    bundle: FlagshipControlBundle,
    case: FlagshipControlCaseConfig,
    baseline: FlagshipMetricSnapshot,
    event_package: EventPackageInstance,
    family: DiscoveredContextFamily,
    candidates: SharedEventCandidates,
    quotient_result: QuotientFeasibilityResult,
    bundle_dir: Path,
    source_root: Path,
    effective_root: Path,
    category: str,
    seed: int,
    timestamp: str | None,
) -> FlagshipControlSummary:
    if not case.robustness.applicable:
        return _not_applicable_summary(
            baseline=baseline,
            reason=case.robustness.reason
            or "robustness_control_not_configured_for_flagship_case",
        )

    local_case_dir = bundle_dir / "derived" / case.case_id
    local_case_dir.mkdir(parents=True, exist_ok=True)
    local_event_package_path = local_case_dir / "event-package.json"
    _copy_repo_artifact(
        _resolve_source_path(
            case.source_refs.event_package_artifact, source_root=source_root
        ),
        local_event_package_path,
    )
    local_event_package_rel = repo_relative_path(
        local_event_package_path, root=effective_root
    )

    stat_trace = _derive_stat_trace_from_pica_bundle(
        family=family,
        instance_id=event_package.instance_id,
        event_package_artifact=local_event_package_rel,
        bundle_path=case.source_refs.source_pica_bundle_artifact
        or family.source_bundle_artifact,
        source_root=source_root,
        trace_id=f"{case.case_id}_stat_trace",
    )
    stat_trace_path = local_case_dir / "stat-clean.json"
    _write_trace(stat_trace_path, stat_trace)
    stat_trace_rel = repo_relative_path(stat_trace_path, root=effective_root)

    sec_trace: ObservationTrace | None = None
    sec_trace_rel: str | None = None
    if "sec" in case.robustness.trace_families:
        sec_trace = _derive_sec_trace(
            instance=event_package,
            candidates=candidates,
            stat_trace=stat_trace,
            trace_id=f"{case.case_id}_sec_trace",
        )
        if sec_trace is not None:
            sec_trace_path = local_case_dir / "sec-clean.json"
            _write_trace(sec_trace_path, sec_trace)
            sec_trace_rel = repo_relative_path(sec_trace_path, root=effective_root)

    sweep = NoiseRobustnessSweep(
        sweep_format_version="noise-robustness-sweep.v1",
        sweep_id=f"{bundle.bundle_id}_{case.case_id}_robustness",
        targets=[
            NoiseRobustnessTarget(
                target_id=case.case_id,
                target_type="discovered_package",
                event_package_artifact=local_event_package_rel,
                trace_artifacts=RobustnessTraceArtifacts(
                    stat=stat_trace_rel
                    if "stat" in case.robustness.trace_families
                    else None,
                    sec=sec_trace_rel,
                ),
                notes=[case.case_type, "flagship_control_bundle"],
            )
        ],
        noise_grid=case.robustness.noise_grid,
        noise_model=case.robustness.noise_model,
        metric_thresholds=case.robustness.metric_thresholds,
        metadata={
            "bundle_id": bundle.bundle_id,
            "case_id": case.case_id,
            "case_type": case.case_type,
        },
    )
    sweep_path = local_case_dir / "robustness-input.json"
    sweep_path.write_text(
        json.dumps(sweep.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    robustness_artifacts: NoiseRobustnessArtifacts = run_noise_robustness_sweep(
        sweep_path=sweep_path,
        category=category,
        label=f"{bundle.bundle_id}-{case.case_id}-robustness",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "falsification",
            "run-flagship-bundle",
            bundle.bundle_id,
        ],
    )
    target_rows = [
        row for row in robustness_artifacts.table.rows if row.target_id == case.case_id
    ]
    post_row = max(target_rows, key=lambda row: row.noise_level)
    baseline_gpd_str = _metric_with_override(
        case.baseline_metric_overrides.gpd_str
        if case.baseline_metric_overrides
        else None,
        default_reason="gpd_str_not_recorded_for_bounded_flagship_bundle",
    )
    baseline_gpd_stat = (
        case.baseline_metric_overrides.gpd_stat
        if case.baseline_metric_overrides and case.baseline_metric_overrides.gpd_stat
        else _metric_from_statistical_trace(instance=event_package, trace=stat_trace)
    )
    baseline_snapshot = _snapshot_from_quotient(
        quotient_result=quotient_result,
        gpd_str=baseline_gpd_str,
        gpd_stat=baseline_gpd_stat,
    )
    post_snapshot = _snapshot_from_quotient(
        quotient_result=quotient_result,
        gpd_str=baseline_gpd_str,
        gpd_stat=FlagshipMetricValue(
            status=post_row.gpd_stat_status,
            value=post_row.gpd_stat,
            reason=post_row.gpd_stat_reason,
        ),
    )
    return FlagshipControlSummary(
        applicability_status="completed",
        verdict=_robustness_verdict(baseline=baseline_snapshot, post=post_snapshot),
        reason=None,
        pre_control=baseline_snapshot,
        post_control=post_snapshot,
        run_id=robustness_artifacts.run_id,
        artifact_refs={
            "robustness_csv": robustness_artifacts.csv_path,
            "robustness_json": robustness_artifacts.json_path,
            "threshold_crossings": robustness_artifacts.threshold_crossings_path,
            "summary": robustness_artifacts.summary_path,
            "note": robustness_artifacts.note_path,
            "result_note": robustness_artifacts.result_note_path,
            "manifest": robustness_artifacts.manifest_path,
            "stat_trace": stat_trace_rel,
            **({"sec_trace": sec_trace_rel} if sec_trace_rel is not None else {}),
        },
        first_crossings=robustness_artifacts.threshold_crossings["targets"][
            case.case_id
        ],
        notes=[
            "quotient_backed_exact_result_is_held_fixed_under_trace_noise",
            "rm_is_diagnostic_only",
            *(["sec_not_available_for_flagship_case"] if sec_trace_rel is None else []),
        ],
    )


def _case_final_verdict(
    case_result: FlagshipControlCaseResult,
) -> FlagshipControlVerdict:
    verdicts = [
        case_result.hidden_record.verdict,
        case_result.flattening.verdict,
        case_result.robustness.verdict,
    ]
    if "disappeared" in verdicts:
        return "disappeared"
    if "weakened" in verdicts:
        return "weakened"
    if "survived" in verdicts and "inconclusive" not in verdicts:
        return "survived"
    if "inconclusive" in verdicts:
        return "inconclusive"
    return "not_applicable"


def _overall_verdict(case_results: list[FlagshipControlCaseResult]) -> str:
    verdicts = [case.final_verdict for case in case_results]
    applicable = [verdict for verdict in verdicts if verdict != "not_applicable"]
    if not applicable:
        return "mostly_not_applicable"
    if "disappeared" in applicable:
        return "some_disappeared"
    if all(verdict == "survived" for verdict in applicable):
        return "all_applicable_flagships_survived"
    return "mixed_outcomes"


def _build_result_note(
    *,
    run_id: str,
    result: FlagshipControlResult,
    output_paths: dict[str, str],
) -> ResultNote:
    verdict_counts = Counter(case.final_verdict for case in result.cases)
    metrics: dict[str, object] = {
        "case_count": len(result.cases),
        "overall_bundle_verdict": result.overall_bundle_verdict,
    }
    for verdict, count in sorted(verdict_counts.items()):
        metrics[f"case_count_{verdict}"] = count
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[case.case_id for case in result.cases],
        metrics=metrics,
        interpretation=(
            "The flagship control bundle applies the strongest remaining false-positive controls to committed obstruction cases while preserving the quotient-backed theorem object as the decisive backend."
        ),
        caveats=[
            "RM is diagnostic-only when present.",
            "not_applicable and inconclusive statuses are preserved explicitly rather than coerced to survival or failure.",
        ],
        artifact_refs=output_paths,
        metadata={"verdict_rule_version": VERDICT_RULE_VERSION},
    )


def _render_note(
    *,
    bundle: FlagshipControlBundle,
    result: FlagshipControlResult,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Flagship Control Bundle",
        "",
        "## Source flagship cases",
    ]
    for case in result.cases:
        lines.append(f"- `{case.case_id}` ({case.case_type})")
    lines.extend(
        [
            "",
            "## Per-case control verdicts",
        ]
    )
    for case in result.cases:
        lines.extend(
            [
                f"### `{case.case_id}`",
                f"- Hidden-record verdict: `{case.hidden_record.verdict}`",
                f"- Flattening verdict: `{case.flattening.verdict}`",
                f"- Robustness verdict: `{case.robustness.verdict}`",
                f"- Final verdict: `{case.final_verdict}`",
                f"- Pre-control quotient result: exact=`{case.robustness.pre_control.exact_feasible}` survivor_count=`{case.robustness.pre_control.survivor_count}` failure_reason=`{case.robustness.pre_control.failure_reason}`",
                (
                    f"- Post-robustness quotient result: exact=`{case.robustness.post_control.exact_feasible}` survivor_count=`{case.robustness.post_control.survivor_count}` failure_reason=`{case.robustness.post_control.failure_reason}`"
                    if case.robustness.post_control is not None
                    else "- Post-robustness quotient result: `not_applicable`"
                ),
                f"- Pre/post `gpd_str`: `{case.robustness.pre_control.gpd_str.model_dump(mode='json')}` / `{case.robustness.post_control.gpd_str.model_dump(mode='json') if case.robustness.post_control is not None else None}`",
                f"- Pre/post `gpd_stat`: `{case.robustness.pre_control.gpd_stat.model_dump(mode='json')}` / `{case.robustness.post_control.gpd_stat.model_dump(mode='json') if case.robustness.post_control is not None else None}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Overall bundle verdict",
            f"- `{result.overall_bundle_verdict}`",
            "",
            "## Notes",
            "- Post-control decisive evaluation remains quotient-backed.",
            "- hidden-record and flattening are recorded explicitly as not_applicable where no committed same-support intervention exists for the flagship theorem object.",
            "- RM is diagnostic-only.",
            "",
            "## Artifact references",
        ]
    )
    for key, value in output_paths.items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def run_flagship_control_bundle(
    *,
    bundle_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> FlagshipControlBundleArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    source_root = Path.cwd().resolve()
    bundle = load_flagship_control_bundle(bundle_path)
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or bundle.bundle_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]

    case_results: list[FlagshipControlCaseResult] = []
    for case in bundle.flagship_cases:
        family = _load_family(
            _resolve_source_path(
                case.source_refs.discovered_context_family_artifact,
                source_root=source_root,
            )
        )
        event_package = _load_event_package(
            _resolve_source_path(
                case.source_refs.event_package_artifact,
                source_root=source_root,
            )
        )
        candidates = _load_candidates(
            _resolve_source_path(
                case.source_refs.shared_event_candidates_artifact,
                source_root=source_root,
            )
        )
        quotient_result = _load_quotient_result(
            _resolve_source_path(
                case.source_refs.quotient_feasibility_summary_artifact,
                source_root=source_root,
            )
        )
        baseline_snapshot = _snapshot_from_quotient(
            quotient_result=quotient_result,
            gpd_str=_metric_with_override(
                case.baseline_metric_overrides.gpd_str
                if case.baseline_metric_overrides
                else None,
                default_reason="gpd_str_not_recorded_in_committed_flagship_case",
            ),
            gpd_stat=_metric_with_override(
                case.baseline_metric_overrides.gpd_stat
                if case.baseline_metric_overrides
                else None,
                default_reason="gpd_stat_not_recorded_until_control_trace_is_derived",
            ),
        )

        hidden_record = _not_applicable_summary(
            baseline=baseline_snapshot,
            reason=case.hidden_record.reason
            or "hidden_record_control_not_applicable_to_committed_flagship_case",
        )
        flattening = _not_applicable_summary(
            baseline=baseline_snapshot,
            reason=case.flattening.reason
            or "flattening_control_not_applicable_to_committed_flagship_case",
        )
        robustness = _run_robustness_control(
            bundle=bundle,
            case=case,
            baseline=baseline_snapshot,
            event_package=event_package,
            family=family,
            candidates=candidates,
            quotient_result=quotient_result,
            bundle_dir=run_dir,
            source_root=source_root,
            effective_root=effective_root,
            category=category,
            seed=seed,
            timestamp=timestamp,
        )
        case_result = FlagshipControlCaseResult(
            case_id=case.case_id,
            case_type=case.case_type,
            source_refs=case.source_refs,
            hidden_record=hidden_record,
            flattening=flattening,
            robustness=robustness,
            final_verdict="inconclusive",
            artifact_refs={
                **robustness.artifact_refs,
                "quotient_feasibility_summary": case.source_refs.quotient_feasibility_summary_artifact,
            },
            notes=list(case.notes),
        )
        case_result = case_result.model_copy(
            update={"final_verdict": _case_final_verdict(case_result)}
        )
        case_results.append(case_result)

    summary_path = run_dir / "flagship-control-summary.json"
    note_path = run_dir / "flagship-control-note.md"
    table_json_path = run_dir / "flagship-control-table.json"
    table_csv_path = run_dir / "flagship-control-table.csv"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "table_json": repo_relative_path(table_json_path, root=effective_root),
        "table_csv": repo_relative_path(table_csv_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    result = FlagshipControlResult(
        result_format_version="flagship-control-result.v1",
        bundle_id=bundle.bundle_id,
        cases=case_results,
        overall_bundle_verdict=_overall_verdict(case_results),
        artifact_refs=output_paths,
        notes=["quotient_backed_re_evaluation_preserved"],
    )

    table_rows = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "baseline_witness_classification": case.robustness.pre_control.witness_classification,
            "hidden_record_verdict": case.hidden_record.verdict,
            "flattening_verdict": case.flattening.verdict,
            "robustness_verdict": case.robustness.verdict,
            "final_verdict": case.final_verdict,
            "baseline_exact_feasible": case.robustness.pre_control.exact_feasible,
            "baseline_survivor_count": case.robustness.pre_control.survivor_count,
            "post_exact_feasible": (
                case.robustness.post_control.exact_feasible
                if case.robustness.post_control is not None
                else None
            ),
            "post_survivor_count": (
                case.robustness.post_control.survivor_count
                if case.robustness.post_control is not None
                else None
            ),
            "baseline_gpd_str_status": case.robustness.pre_control.gpd_str.status,
            "baseline_gpd_str": case.robustness.pre_control.gpd_str.value,
            "baseline_gpd_stat_status": case.robustness.pre_control.gpd_stat.status,
            "baseline_gpd_stat": case.robustness.pre_control.gpd_stat.value,
            "post_gpd_str_status": (
                case.robustness.post_control.gpd_str.status
                if case.robustness.post_control is not None
                else "not_applicable"
            ),
            "post_gpd_str": (
                case.robustness.post_control.gpd_str.value
                if case.robustness.post_control is not None
                else None
            ),
            "post_gpd_stat_status": (
                case.robustness.post_control.gpd_stat.status
                if case.robustness.post_control is not None
                else "not_applicable"
            ),
            "post_gpd_stat": (
                case.robustness.post_control.gpd_stat.value
                if case.robustness.post_control is not None
                else None
            ),
        }
        for case in case_results
    ]

    summary_path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    table_json_path.write_text(
        json.dumps(
            {
                "bundle_id": bundle.bundle_id,
                "row_count": len(table_rows),
                "rows": table_rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with table_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table_rows[0].keys()))
        writer.writeheader()
        writer.writerows(table_rows)
    note_path.write_text(
        _render_note(bundle=bundle, result=result, output_paths=output_paths),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        result=result,
        output_paths=output_paths,
    )
    result_note_path.write_text(
        json.dumps(result_note.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    config_ref = Path(bundle_path).as_posix()
    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "falsification",
            "run-flagship-bundle",
            config_ref,
        ],
        seed=seed,
        input_artifacts={"bundle": config_ref},
        output_artifacts={
            "summary": output_paths["summary"],
            "table_json": output_paths["table_json"],
            "table_csv": output_paths["table_csv"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "flagship_control_bundle",
            "bundle_id": bundle.bundle_id,
            "case_count": len(case_results),
            "overall_bundle_verdict": result.overall_bundle_verdict,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return FlagshipControlBundleArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        table_json_path=output_paths["table_json"],
        table_csv_path=output_paths["table_csv"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        result=result,
    )
