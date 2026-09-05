from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys

from ..audits.context_closure import (
    ContextClosureDefectResult,
    compute_context_closure_defect,
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
class CCDReportArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    result: ContextClosureDefectResult


def load_observation_trace_file(
    path: str | Path,
) -> ObservationTrace:
    model = load_model(path, kind="observation-trace")
    assert isinstance(model, ObservationTrace)
    return model


def _render_ccd_note(
    *,
    result: ContextClosureDefectResult,
    trace_path: str,
    instance_path: str | None,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Context Closure Defect Report",
        "",
        "## Trace / instance",
        f"- Trace ID: `{result.trace_id}`",
        f"- Trace path: `{trace_path}`",
        f"- Instance ID: `{result.instance_id}`",
        f"- Instance path: `{instance_path}`",
        "",
        "## Contexts analyzed",
        f"- Context count: `{len(result.context_results)}`",
        f"- Insufficient-data contexts: `{result.insufficient_data_contexts}`",
        "",
        "## Per-context defect components",
    ]
    for context_result in result.context_results:
        lines.extend(
            [
                f"- `{context_result.context_id}`: ccd=`{context_result.ccd}`, exclusivity=`{context_result.exclusivity_defect}`, exhaustivity=`{context_result.exhaustivity_defect}`, reread_instability=`{context_result.reread_instability}`, closure_defect=`{context_result.closure_defect}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Overall CCD",
            f"- Overall CCD: `{result.overall_ccd}`",
            "",
            "## Short technical interpretation",
            (
                "- The audit summarizes repeated-read failure modes by separating exclusivity, exhaustivity, reread instability, and closure-idempotence effects."
            ),
            "",
            "## Caveats / insufficient-data flags",
            "- Reread instability and closure defect are omitted for contexts with no singleton-to-singleton transitions.",
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
    result: ContextClosureDefectResult,
    output_paths: dict[str, str],
) -> ResultNote:
    max_context_ccd = max(
        (
            context_result.ccd
            for context_result in result.context_results
            if context_result.ccd is not None
        ),
        default=0.0,
    )
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[result.instance_id or "unlinked_trace"],
        metrics={
            "overall_ccd": result.overall_ccd
            if result.overall_ccd is not None
            else -1.0,
            "contexts_analyzed": len(result.context_results),
            "insufficient_data_contexts": len(result.insufficient_data_contexts),
            "max_context_ccd": max_context_ccd,
        },
        interpretation=(
            "Repeated-read data are closure-stable with low defect components."
            if (result.overall_ccd or 0.0) <= 1e-9
            else "Repeated-read data show measurable closure-related defects across one or more contexts."
        ),
        caveats=[
            "CCD is estimated from repeated-read traces only.",
            "Closure defect is derived from the empirical reread kernel and may be omitted when transition data are insufficient.",
        ],
        artifact_refs={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
        },
        metadata={
            "trace_id": result.trace_id,
        },
    )


def write_ccd_report(
    trace: ObservationTrace,
    *,
    trace_path: str | Path,
    category: str,
    label: str | None = None,
    instance: EventPackageInstance | None = None,
    instance_path: str | Path | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> CCDReportArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    trace_relpath = repo_relative_path(trace_path, root=effective_root)
    instance_relpath = (
        repo_relative_path(instance_path, root=effective_root)
        if instance_path is not None
        else None
    )
    result = compute_context_closure_defect(trace, instance=instance)

    summary_path = run_dir / "ccd-summary.json"
    note_path = run_dir / "ccd-note.md"
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
        "trace_id": result.trace_id,
        "trace_path": trace_relpath,
        "instance_id": result.instance_id,
        "instance_path": instance_relpath,
        "overall_ccd": result.overall_ccd,
        "component_weights": result.component_weights,
        "insufficient_data_contexts": result.insufficient_data_contexts,
        "context_results": [
            asdict(context_result) for context_result in result.context_results
        ],
        "output_paths": output_paths,
    }
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(
        _render_ccd_note(
            result=result,
            trace_path=trace_relpath,
            instance_path=instance_relpath,
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

    input_artifacts = {"trace": trace_relpath}
    if instance_relpath is not None:
        input_artifacts["instance"] = instance_relpath
    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "ccd",
            trace_relpath,
        ],
        seed=seed,
        input_artifacts=input_artifacts,
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "context_closure_defect",
            "trace_id": result.trace_id,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return CCDReportArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=output_paths["manifest"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        result=result,
    )
