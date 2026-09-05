from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys

from ..audits.shared_event_consistency import (
    SharedEventConsistencyResult,
    compute_shared_event_consistency,
)
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import ObservationTrace
from ..schemas.result_note import ResultNote
from ..validation import load_model


@dataclass(slots=True)
class SECReportArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    result: SharedEventConsistencyResult


def load_observation_trace_files(paths: list[str | Path]) -> list[ObservationTrace]:
    traces: list[ObservationTrace] = []
    for path in paths:
        model = load_model(path, kind="observation-trace")
        assert isinstance(model, ObservationTrace)
        traces.append(model)
    return traces


def _render_sec_note(
    *,
    result: SharedEventConsistencyResult,
    instance_path: str,
    trace_paths: list[str],
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Shared Event Consistency Report",
        "",
        "## Instance / traces",
        f"- Instance ID: `{result.instance_id}`",
        f"- Instance path: `{instance_path}`",
        f"- Trace IDs: `{result.trace_ids}`",
        f"- Trace paths: `{trace_paths}`",
        "",
        "## Event-pair SEC results",
    ]
    for pair in result.event_pair_results:
        lines.append(
            f"- `{pair.proposal_id}` ({pair.left_event_id} ~ {pair.right_event_id}): approx_score=`{pair.approx_score}`, exact_consistent=`{pair.exact_consistent}`, insufficient_data=`{pair.insufficient_data}`, probes=`{pair.common_probe_ids}`"
        )
    lines.extend(["", "## Context-pair SEC summary"])
    for context_pair in result.context_pair_results:
        lines.append(
            f"- `{context_pair.left_context_id}` / `{context_pair.right_context_id}`: scored_pairs=`{context_pair.scored_pair_count}`, insufficient=`{context_pair.insufficient_data_pair_count}`, mean_approx=`{context_pair.mean_approx_score}`, max_approx=`{context_pair.max_approx_score}`, exact_pass_fraction=`{context_pair.exact_pass_fraction}`"
        )
    lines.extend(
        [
            "",
            "## Exact tolerance used",
            f"- Exact tolerance: `{result.exact_tolerance}`",
            "",
            "## Short technical interpretation",
            "- SEC compares instance-defined shared-event proposals by total-variation distance over common downstream probes and reports both approximate scores and tolerance-based exact consistency.",
            "",
            "## Caveats / insufficient-data flags",
            "- Event pairs with no common probes are marked insufficient-data and do not receive fabricated distances.",
            "",
            "## Artifact references",
            f"- Summary JSON: `{output_paths['summary']}`",
            f"- Result note JSON: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    result: SharedEventConsistencyResult,
    output_paths: dict[str, str],
) -> ResultNote:
    scored_pairs = [
        pair for pair in result.event_pair_results if not pair.insufficient_data
    ]
    approx_scores = [
        pair.approx_score for pair in scored_pairs if pair.approx_score is not None
    ]
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[result.instance_id],
        metrics={
            "event_pair_count": len(result.event_pair_results),
            "scored_event_pair_count": len(scored_pairs),
            "insufficient_data_pair_count": sum(
                1 for pair in result.event_pair_results if pair.insufficient_data
            ),
            "mean_approx_sec": sum(approx_scores) / len(approx_scores)
            if approx_scores
            else -1.0,
            "exact_tolerance": result.exact_tolerance,
        },
        interpretation=(
            "Shared-event proposals are operationally consistent across the available common probes."
            if approx_scores and max(approx_scores) <= result.exact_tolerance
            else "At least one shared-event proposal is operationally distinguishable or lacks common probe coverage."
        ),
        caveats=[
            "SEC uses total variation distance over event-linked downstream probe signatures.",
            "Pairs with no common probes are reported as insufficient-data.",
        ],
        artifact_refs={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
        },
        metadata={
            "trace_count": len(result.trace_ids),
        },
    )


def write_sec_report(
    instance: EventPackageInstance,
    traces: list[ObservationTrace],
    *,
    instance_path: str | Path,
    trace_paths: list[str | Path],
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
    exact_tolerance: float = 1e-6,
) -> SECReportArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    instance_relpath = repo_relative_path(instance_path, root=effective_root)
    trace_relpaths = [
        repo_relative_path(path, root=effective_root) for path in trace_paths
    ]
    result = compute_shared_event_consistency(
        instance,
        traces,
        exact_tolerance=exact_tolerance,
    )

    summary_path = run_dir / "sec-summary.json"
    note_path = run_dir / "sec-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    summary_payload = {
        "run_id": run_id,
        "instance_id": result.instance_id,
        "instance_path": instance_relpath,
        "trace_ids": result.trace_ids,
        "trace_paths": trace_relpaths,
        "exact_tolerance": result.exact_tolerance,
        "aggregation_policy": result.aggregation_policy,
        "event_pair_results": [asdict(item) for item in result.event_pair_results],
        "context_pair_results": [asdict(item) for item in result.context_pair_results],
        "output_paths": output_paths,
    }
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(
        _render_sec_note(
            result=result,
            instance_path=instance_relpath,
            trace_paths=trace_relpaths,
            output_paths=output_paths,
        ),
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
    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "sec",
            *trace_relpaths,
        ],
        seed=seed,
        input_artifacts={
            "instance": instance_relpath,
            **{
                f"trace_{index}": path
                for index, path in enumerate(trace_relpaths, start=1)
            },
        },
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "shared_event_consistency",
            "trace_count": len(trace_relpaths),
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return SECReportArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=output_paths["manifest"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        result=result,
    )
