from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import sys

from ..reporting.hidden_record_report import write_hidden_record_intervention_report
from ..reporting.flattening_report import write_flattening_intervention_report
from ..reporting.sec_report import (
    load_observation_trace_files,
    write_sec_report,
)
from ..reporting.structural_report import (
    generate_structural_report,
    load_event_package_instance,
)
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from ..validation import load_model
from .models import (
    FrameworkResponse,
    MetricStatus,
    RedteamCaseConfig,
    RedteamCaseResult,
    RedteamResultsTable,
    RedteamSuite,
)


@dataclass(slots=True)
class RedteamSuiteArtifacts:
    run_id: str
    run_dir: str
    json_path: str
    csv_path: str
    response_counts_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    summary: dict[str, object]


def load_redteam_suite(path: str | Path) -> RedteamSuite:
    model = load_model(path, kind="redteam-suite")
    assert isinstance(model, RedteamSuite)
    return model


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _structural_status(feasible: bool | None) -> str:
    if feasible is None:
        return "not_applicable"
    return "feasible" if feasible else "infeasible"


def _stat_status(solved: bool | None) -> MetricStatus:
    if solved is None:
        return "not_applicable"
    return "solved" if solved else "unsolved"


def _rm_status(rm_summary: dict[str, object] | None) -> MetricStatus:
    if rm_summary is None:
        return "not_applicable"
    if rm_summary.get("overall_rm") is not None:
        return "scored"
    return "insufficient_data"


def _mean_scored_sec(result) -> float | None:
    scores = [
        pair.approx_score
        for pair in result.event_pair_results
        if not pair.insufficient_data and pair.approx_score is not None
    ]
    return sum(scores) / len(scores) if scores else None


def _write_case_note(
    *,
    note_path: Path,
    case: RedteamCaseConfig,
    row: RedteamCaseResult,
) -> None:
    lines = [
        f"# Red-Team Case: {case.case_id}",
        "",
        "## Adversarial type",
        f"- Adversarial type: `{case.adversarial_type}`",
        f"- Runner mode: `{case.runner_mode}`",
        f"- Expected issue type: `{case.expected_issue_type}`",
        f"- Expected framework response: `{case.expected_framework_response}`",
        "",
        "## Input assets",
    ]
    for key, value in row.input_asset_refs.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Attempted metrics",
            f"- Attempted metrics: `{row.attempted_metrics}`",
            "",
            "## Observed outputs",
            f"- Exact structural status: `{row.exact_structural_status}`",
            f"- Exact structural feasible hard only: `{row.exact_structural_feasible_hard_only}`",
            f"- `gpd_str`: `{row.gpd_str}`",
            f"- `gpd_stat` status/value/reason: `{row.gpd_stat_status}` / `{row.gpd_stat}` / `{row.gpd_stat_reason}`",
            f"- CCD status/value: `{row.ccd_status}` / `{row.ccd_overall}`",
            f"- SEC status/value: `{row.sec_status}` / `{row.sec_mean}`",
            f"- RM status/value: `{row.rm_status}` / `{row.rm_overall}`",
            f"- Intervention conclusion: `{row.intervention_conclusion}`",
            "",
            "## Framework response",
            f"- Framework response classification: `{row.framework_response}`",
            f"- Explanatory flags: `{row.explanatory_flags}`",
            "",
            "## Artifact references",
        ]
    )
    for key, value in row.artifact_paths.items():
        lines.append(f"- `{key}`: `{value}`")
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_hidden_label_smuggling_case(
    *,
    case: RedteamCaseConfig,
    category: str,
    timestamp: str | None,
    root: Path,
    note_path: str,
) -> tuple[RedteamCaseResult, list[str]]:
    instance_path = case.asset_refs["instance"]
    instance = load_event_package_instance(instance_path)
    structural = generate_structural_report(
        instance,
        instance_path=instance_path,
        category=category,
        label=f"{case.case_id}-structural",
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "structural",
            "report",
            instance_path,
        ],
    )
    flags = [
        "source_provenance_not_checked_by_structural_runner",
        "unsupported_hidden_label_split_not_automatically_flagged",
    ]
    response: FrameworkResponse
    if structural.summary.exact_extendable_hard_only and (
        structural.summary.gpd_str is not None
        and abs(structural.summary.gpd_str) <= 1e-9
    ):
        response = "not_flagged"
    else:
        response = "partially_flagged"
    row = RedteamCaseResult(
        row_format_version="redteam-case-result.v1",
        suite_id="pending_suite",
        case_id=case.case_id,
        adversarial_type=case.adversarial_type,
        input_asset_refs=case.asset_refs,
        attempted_metrics=["structural"],
        exact_structural_status=_structural_status(
            structural.summary.exact_extendable_hard_only
        ),
        exact_structural_feasible_hard_only=structural.summary.exact_extendable_hard_only,
        gpd_str=structural.summary.gpd_str,
        gpd_stat_status="not_applicable",
        gpd_stat=None,
        gpd_stat_reason=None,
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status="not_applicable",
        sec_mean=None,
        rm_status="not_applicable",
        rm_overall=None,
        intervention_conclusion=None,
        framework_response=response,
        explanatory_flags=flags,
        run_ids={"structural": structural.run_id},
        artifact_paths={
            "structural_summary": structural.summary_path,
            "structural_note": structural.note_path,
            "structural_result_note": structural.result_note_path,
            "structural_manifest": structural.manifest_path,
        },
        note_path=note_path,
    )
    return row, flags


def _run_hidden_record_case(
    *,
    case: RedteamCaseConfig,
    category: str,
    timestamp: str | None,
    root: Path,
    note_path: str,
) -> tuple[RedteamCaseResult, list[str]]:
    intervention_path = case.asset_refs["intervention"]
    artifact = write_hidden_record_intervention_report(
        intervention_path=intervention_path,
        category=category,
        label=case.case_id,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "interventions",
            "hidden-record",
            intervention_path,
        ],
    )
    before = artifact.summary["before"]
    after = artifact.summary["after"]
    conclusion = artifact.conclusion
    flags = [f"after_gpd_str={after['gpd_str']}", f"after_gpd_stat={after['gpd_stat']}"]
    response: FrameworkResponse = {
        "disappeared": "corrected",
        "weakened": "partially_corrected",
        "survived": "partially_flagged",
    }[conclusion]
    row = RedteamCaseResult(
        row_format_version="redteam-case-result.v1",
        suite_id="pending_suite",
        case_id=case.case_id,
        adversarial_type=case.adversarial_type,
        input_asset_refs=case.asset_refs,
        attempted_metrics=["structural", "statistical", "rm", "intervention"],
        exact_structural_status=_structural_status(
            before["exact_structural_feasible_hard_only"]
        ),
        exact_structural_feasible_hard_only=before[
            "exact_structural_feasible_hard_only"
        ],
        gpd_str=before["gpd_str"],
        gpd_stat_status=_stat_status(before["statistical_solved"]),
        gpd_stat=before["gpd_stat"],
        gpd_stat_reason=before["statistical_reason"],
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status="not_applicable",
        sec_mean=None,
        rm_status=_rm_status(before["rm"]),
        rm_overall=before["rm"]["overall_rm"] if before["rm"] is not None else None,
        intervention_conclusion=conclusion,
        framework_response=response,
        explanatory_flags=flags,
        run_ids={"intervention": artifact.run_id},
        artifact_paths={
            "comparison_summary": artifact.summary_path,
            "comparison_note": artifact.note_path,
            "result_note": artifact.result_note_path,
            "manifest": artifact.manifest_path,
            "augmented_instance": artifact.augmented_instance_path,
            "before_stat": artifact.before_stat_path,
            "after_stat": artifact.after_stat_path,
        },
        note_path=note_path,
    )
    return row, flags


def _run_flattening_case(
    *,
    case: RedteamCaseConfig,
    category: str,
    timestamp: str | None,
    root: Path,
    note_path: str,
) -> tuple[RedteamCaseResult, list[str]]:
    intervention_path = case.asset_refs["intervention"]
    artifact = write_flattening_intervention_report(
        intervention_path=intervention_path,
        category=category,
        label=case.case_id,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "interventions",
            "flattening",
            intervention_path,
        ],
    )
    before = artifact.summary["before"]
    after = artifact.summary["after"]
    conclusion = artifact.conclusion
    flags = [
        f"after_rm_status={after['rm_status']}",
        f"after_overall_rm={after['overall_rm']}",
    ]
    response: FrameworkResponse = {
        "repairable": "corrected",
        "weakened": "partially_corrected",
        "robust": "partially_flagged",
    }[conclusion]
    row = RedteamCaseResult(
        row_format_version="redteam-case-result.v1",
        suite_id="pending_suite",
        case_id=case.case_id,
        adversarial_type=case.adversarial_type,
        input_asset_refs=case.asset_refs,
        attempted_metrics=["structural", "statistical", "rm", "intervention"],
        exact_structural_status=before["exact_structural_status"],
        exact_structural_feasible_hard_only=before[
            "exact_structural_feasible_hard_only"
        ],
        gpd_str=before["gpd_str"],
        gpd_stat_status=before["gpd_stat_status"],
        gpd_stat=before["gpd_stat"],
        gpd_stat_reason=before["gpd_stat_reason"],
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status="not_applicable",
        sec_mean=None,
        rm_status=before["rm_status"],
        rm_overall=before["overall_rm"],
        intervention_conclusion=conclusion,
        framework_response=response,
        explanatory_flags=flags,
        run_ids={"intervention": artifact.run_id},
        artifact_paths={
            "comparison_summary": artifact.summary_path,
            "comparison_note": artifact.note_path,
            "result_note": artifact.result_note_path,
            "manifest": artifact.manifest_path,
            "before_route_trace": artifact.before_route_trace_path,
            "after_route_trace": artifact.after_route_trace_path,
        },
        note_path=note_path,
    )
    return row, flags


def _run_bad_shared_event_case(
    *,
    case: RedteamCaseConfig,
    category: str,
    timestamp: str | None,
    root: Path,
    note_path: str,
) -> tuple[RedteamCaseResult, list[str]]:
    instance_path = case.asset_refs["instance"]
    trace_path = case.asset_refs["trace"]
    instance = load_event_package_instance(instance_path)
    traces = load_observation_trace_files([trace_path])
    structural = generate_structural_report(
        instance,
        instance_path=instance_path,
        category=category,
        label=f"{case.case_id}-structural",
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "structural",
            "report",
            instance_path,
        ],
    )
    sec = write_sec_report(
        instance,
        traces,
        instance_path=instance_path,
        trace_paths=[trace_path],
        category=category,
        label=f"{case.case_id}-sec",
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "sec",
            trace_path,
            "--instance",
            instance_path,
        ],
    )
    sec_threshold = float(
        case.classification_thresholds.get("sec_flag_threshold", 0.15)
    )
    sec_mean = _mean_scored_sec(sec.result)
    scored_pairs = [
        pair for pair in sec.result.event_pair_results if not pair.insufficient_data
    ]
    exact_failures = sum(1 for pair in scored_pairs if pair.exact_consistent is False)
    if scored_pairs and (
        (sec_mean is not None and sec_mean > sec_threshold) or exact_failures > 0
    ):
        response: FrameworkResponse = "flagged"
    elif scored_pairs:
        response = "partially_flagged"
    else:
        response = "not_flagged"
    flags = [
        f"sec_flag_threshold={sec_threshold}",
        f"scored_pair_count={len(scored_pairs)}",
        f"exact_failure_count={exact_failures}",
    ]
    row = RedteamCaseResult(
        row_format_version="redteam-case-result.v1",
        suite_id="pending_suite",
        case_id=case.case_id,
        adversarial_type=case.adversarial_type,
        input_asset_refs=case.asset_refs,
        attempted_metrics=["structural", "sec"],
        exact_structural_status=_structural_status(
            structural.summary.exact_extendable_hard_only
        ),
        exact_structural_feasible_hard_only=structural.summary.exact_extendable_hard_only,
        gpd_str=structural.summary.gpd_str,
        gpd_stat_status="not_applicable",
        gpd_stat=None,
        gpd_stat_reason=None,
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status="scored" if sec_mean is not None else "insufficient_data",
        sec_mean=sec_mean,
        rm_status="not_applicable",
        rm_overall=None,
        intervention_conclusion=None,
        framework_response=response,
        explanatory_flags=flags,
        run_ids={"structural": structural.run_id, "sec": sec.run_id},
        artifact_paths={
            "structural_summary": structural.summary_path,
            "structural_note": structural.note_path,
            "structural_manifest": structural.manifest_path,
            "sec_summary": sec.summary_path,
            "sec_note": sec.note_path,
            "sec_result_note": sec.result_note_path,
            "sec_manifest": sec.manifest_path,
        },
        note_path=note_path,
    )
    return row, flags


def _run_case(
    *,
    case: RedteamCaseConfig,
    suite_id: str,
    category: str,
    timestamp: str | None,
    root: Path,
    run_dir: Path,
    effective_root: Path,
) -> RedteamCaseResult:
    note_file_path = run_dir / f"case-{case.case_id}.md"
    note_relpath = repo_relative_path(note_file_path, root=effective_root)
    if case.runner_mode == "structural_only":
        row, _ = _run_hidden_label_smuggling_case(
            case=case,
            category=category,
            timestamp=timestamp,
            root=root,
            note_path=note_relpath,
        )
    elif case.runner_mode == "hidden_record_intervention":
        row, _ = _run_hidden_record_case(
            case=case,
            category=category,
            timestamp=timestamp,
            root=root,
            note_path=note_relpath,
        )
    elif case.runner_mode == "flattening_intervention":
        row, _ = _run_flattening_case(
            case=case,
            category=category,
            timestamp=timestamp,
            root=root,
            note_path=note_relpath,
        )
    elif case.runner_mode == "sec_audit":
        row, _ = _run_bad_shared_event_case(
            case=case,
            category=category,
            timestamp=timestamp,
            root=root,
            note_path=note_relpath,
        )
    else:
        raise ValueError(f"unsupported runner_mode '{case.runner_mode}'")

    row = row.model_copy(update={"suite_id": suite_id})
    _write_case_note(
        note_path=note_file_path,
        case=case,
        row=row,
    )
    return row


def _row_to_csv_record(row: RedteamCaseResult) -> dict[str, object]:
    return {
        "case_id": row.case_id,
        "adversarial_type": row.adversarial_type,
        "attempted_metrics": json.dumps(row.attempted_metrics, sort_keys=True),
        "exact_structural_status": row.exact_structural_status,
        "exact_structural_feasible_hard_only": row.exact_structural_feasible_hard_only,
        "gpd_str": row.gpd_str,
        "gpd_stat_status": row.gpd_stat_status,
        "gpd_stat": row.gpd_stat,
        "gpd_stat_reason": row.gpd_stat_reason,
        "ccd_status": row.ccd_status,
        "ccd_overall": row.ccd_overall,
        "sec_status": row.sec_status,
        "sec_mean": row.sec_mean,
        "rm_status": row.rm_status,
        "rm_overall": row.rm_overall,
        "intervention_conclusion": row.intervention_conclusion,
        "framework_response": row.framework_response,
        "input_asset_refs": json.dumps(row.input_asset_refs, sort_keys=True),
        "run_ids": json.dumps(row.run_ids, sort_keys=True),
        "artifact_paths": json.dumps(row.artifact_paths, sort_keys=True),
        "explanatory_flags": json.dumps(row.explanatory_flags, sort_keys=True),
        "note_path": row.note_path,
    }


def run_redteam_suite(
    *,
    suite_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> RedteamSuiteArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    suite = load_redteam_suite(suite_path)
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or suite.suite_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    suite_relpath = repo_relative_path(suite_path, root=effective_root)

    rows = [
        _run_case(
            case=case,
            suite_id=suite.suite_id,
            category=category,
            timestamp=timestamp,
            root=effective_root,
            run_dir=run_dir,
            effective_root=effective_root,
        )
        for case in suite.cases
    ]
    table = RedteamResultsTable(
        table_format_version="redteam-results.v1",
        suite_id=suite.suite_id,
        row_count=len(rows),
        rows=rows,
        metadata={"suite_artifact": suite_relpath},
    )

    response_counts_counter = Counter(row.framework_response for row in rows)
    response_counts = {
        response: response_counts_counter.get(response, 0)
        for response in [
            "flagged",
            "corrected",
            "partially_flagged",
            "partially_corrected",
            "not_flagged",
        ]
    }
    type_counts = {
        case_type: sum(1 for row in rows if row.adversarial_type == case_type)
        for case_type in [
            "hidden_label_smuggling",
            "schedule_protocol_residue_artifact",
            "flattenable_route_mismatch",
            "bad_shared_event_proposals",
        ]
    }
    notable_vulnerabilities = [
        row.case_id for row in rows if row.framework_response == "not_flagged"
    ]
    notable_corrections = [
        row.case_id
        for row in rows
        if row.framework_response in {"corrected", "partially_corrected"}
    ]
    status_counts = {
        "gpd_stat_status:not_applicable": sum(
            1 for row in rows if row.gpd_stat_status == "not_applicable"
        ),
        "rm_status:not_applicable": sum(
            1 for row in rows if row.rm_status == "not_applicable"
        ),
        "sec_status:not_applicable": sum(
            1 for row in rows if row.sec_status == "not_applicable"
        ),
    }

    json_path = run_dir / "redteam-results.json"
    csv_path = run_dir / "redteam-results.csv"
    response_counts_path = run_dir / "response-counts.json"
    summary_path = run_dir / "redteam-summary.json"
    note_path = run_dir / "redteam-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "results_json": repo_relative_path(json_path, root=effective_root),
        "results_csv": repo_relative_path(csv_path, root=effective_root),
        "response_counts": repo_relative_path(
            response_counts_path, root=effective_root
        ),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    json_path.write_text(
        json.dumps(table.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    csv_rows = [_row_to_csv_record(row) for row in table.rows]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        for record in csv_rows:
            writer.writerow(record)
    response_counts_path.write_text(
        json.dumps(response_counts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "suite_id": suite.suite_id,
        "total_case_count": len(rows),
        "counts_by_adversarial_type": type_counts,
        "counts_by_framework_response": response_counts,
        "notable_vulnerabilities": notable_vulnerabilities,
        "notable_successful_corrections": notable_corrections,
        "results_json_path": output_paths["results_json"],
        "results_csv_path": output_paths["results_csv"],
        "status_counts": status_counts,
    }
    _write_json(summary_path, summary)

    note_lines = [
        "# Red-Team Suite",
        "",
        "## Suite ID",
        f"- Suite ID: `{suite.suite_id}`",
        "",
        "## Cases covered",
    ]
    for row in table.rows:
        note_lines.extend(
            [
                f"- `{row.case_id}` ({row.adversarial_type}): response=`{row.framework_response}`, intervention=`{row.intervention_conclusion}`",
                f"  metrics=`{{'exact_structural_status': '{row.exact_structural_status}', 'gpd_str': {row.gpd_str}, 'gpd_stat_status': '{row.gpd_stat_status}', 'sec_status': '{row.sec_status}', 'sec_mean': {row.sec_mean}, 'rm_status': '{row.rm_status}', 'rm_overall': {row.rm_overall}}}`",
            ]
        )
    note_lines.extend(
        [
            "",
            "## Notable vulnerabilities / limitations",
            f"- Cases not automatically flagged: `{notable_vulnerabilities}`",
            "",
            "## Successful correction mechanisms",
            f"- Cases corrected or partially corrected: `{notable_corrections}`",
            "",
            "## Caveats",
            "- RM is diagnostic-only where present.",
            "- unsolved / insufficient_data / not_applicable statuses are preserved explicitly rather than coerced to numeric zero.",
            "",
            "## Artifact references",
            f"- Results JSON: `{output_paths['results_json']}`",
            f"- Results CSV: `{output_paths['results_csv']}`",
            f"- Response counts: `{output_paths['response_counts']}`",
            f"- Summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Manifest: `{output_paths['manifest']}`",
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[row.case_id for row in rows],
        metrics={
            "case_count": len(rows),
            "flagged_count": response_counts["flagged"],
            "corrected_count": response_counts["corrected"],
            "partially_flagged_count": response_counts["partially_flagged"],
            "partially_corrected_count": response_counts["partially_corrected"],
            "not_flagged_count": response_counts["not_flagged"],
        },
        interpretation=(
            "Red-team suite reran existing structural, SEC, and intervention reporters on adversarial cases and recorded whether the current framework flagged, corrected, partially flagged, partially corrected, or failed to flag each issue."
        ),
        caveats=[
            "A not_flagged result is preserved explicitly when the current automated framework does not mark the adversarial issue.",
            "RM is diagnostic-only where present.",
        ],
        artifact_refs=output_paths,
        metadata={
            "suite_id": suite.suite_id,
            "notable_vulnerabilities": notable_vulnerabilities,
            "notable_successful_corrections": notable_corrections,
        },
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
            "redteam",
            "run-suite",
            suite_relpath,
        ],
        seed=seed,
        input_artifacts={"suite": suite_relpath},
        output_artifacts={
            "results_json": output_paths["results_json"],
            "results_csv": output_paths["results_csv"],
            "response_counts": output_paths["response_counts"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "redteam_suite",
            "suite_id": suite.suite_id,
            "case_count": len(rows),
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return RedteamSuiteArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        json_path=output_paths["results_json"],
        csv_path=output_paths["results_csv"],
        response_counts_path=output_paths["response_counts"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        summary=summary,
    )
