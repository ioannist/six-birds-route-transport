from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from ..discovery.context_discovery import DEFAULT_THRESHOLDS, discover_context_family
from ..discovery.models import DiscoveredContextFamily, ExtractionThresholds
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from ..substrates.engine import load_substrate_run


@dataclass(slots=True)
class ContextDiscoveryReportArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    family_path: str
    note_path: str
    result_note_path: str
    skeleton_path: str | None
    family: DiscoveredContextFamily


def load_substrate_run_files(paths: list[str | Path]):
    return [load_substrate_run(path) for path in paths]


def _render_note(
    *,
    family: DiscoveredContextFamily,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Context Discovery Report",
        "",
        "## Source substrate-run files",
    ]
    for path in family.source_run_artifacts:
        lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "## Threshold configuration used",
            f"- `min_trajectory_count`: `{family.thresholds.min_trajectory_count}`",
            f"- `min_atom_count`: `{family.thresholds.min_atom_count}`",
            f"- `min_atom_support_count`: `{family.thresholds.min_atom_support_count}`",
            f"- `min_atom_support_fraction`: `{family.thresholds.min_atom_support_fraction}`",
            f"- `min_coverage`: `{family.thresholds.min_coverage}`",
            f"- `max_batch_tv`: `{family.thresholds.max_batch_tv}`",
            f"- `max_persistence_flip_rate`: `{family.thresholds.max_persistence_flip_rate}`",
            f"- `batch_count`: `{family.thresholds.batch_count}`",
            "",
            "## Accepted context count",
            f"- Accepted contexts: `{family.diagnostics_summary.accepted_context_count}`",
            "",
            "## Rejected candidate count",
            f"- Rejected candidates: `{family.diagnostics_summary.rejected_candidate_count}`",
            f"- Rejection summary: `{family.diagnostics_summary.rejection_reason_counts}`",
            "",
            "## Per-context diagnostics summary",
        ]
    )
    for context in family.accepted_contexts:
        lines.append(
            f"- `{context.context_id}`: retained_atom_count=`{context.diagnostics.retained_atom_count}`, "
            f"coverage_fraction=`{context.diagnostics.coverage_fraction}`, empirical_entropy=`{context.diagnostics.empirical_entropy}`, "
            f"batch_tv_max=`{context.diagnostics.batch_tv_max}`, persistence_flip_rate=`{context.diagnostics.persistence_flip_rate}`"
        )
    lines.extend(
        [
            "",
            "## Skeleton emission",
            f"- Event-package skeleton emitted: `{family.event_package_skeleton_artifact is not None}`",
            "",
            "## Artifact references",
            f"- Discovered context family: `{output_paths['family']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
        ]
    )
    if family.event_package_skeleton_artifact is not None:
        lines.append(
            f"- Event-package skeleton: `{family.event_package_skeleton_artifact}`"
        )
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    family: DiscoveredContextFamily,
    output_paths: dict[str, str],
) -> ResultNote:
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[family.family_id],
        metrics={
            "accepted_context_count": family.diagnostics_summary.accepted_context_count,
            "rejected_candidate_count": family.diagnostics_summary.rejected_candidate_count,
            "candidate_count": family.diagnostics_summary.candidate_count,
            "skeleton_emitted": family.event_package_skeleton_artifact is not None,
        },
        interpretation=(
            "Candidate contexts were extracted from observable substrate-run records using preparation/protocol/lens/step keys only; hidden-state IDs were not used in acceptance logic."
        ),
        caveats=[
            "Diagnostics are extraction-time stability proxies, not full CCD/SEC/RM audits.",
            "Shared-event inference is deferred to later discovery stages.",
        ],
        artifact_refs={
            "family": output_paths["family"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
            **(
                {"event_package_skeleton": family.event_package_skeleton_artifact}
                if family.event_package_skeleton_artifact is not None
                else {}
            ),
        },
        metadata={"observable_only": True},
    )


def write_context_discovery_report(
    *,
    run_paths: list[str | Path],
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
    thresholds: ExtractionThresholds | None = None,
) -> ContextDiscoveryReportArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    run_relpaths = [repo_relative_path(path, root=effective_root) for path in run_paths]
    runs = load_substrate_run_files(run_paths)
    discovery = discover_context_family(
        runs,
        source_run_artifacts=run_relpaths,
        family_id=f"family_{run_id}",
        thresholds=thresholds or DEFAULT_THRESHOLDS,
        created_at=manifest_timestamp,
    )

    family_path = run_dir / "discovered-context-family.json"
    note_path = run_dir / "context-discovery-note.md"
    result_note_path = run_dir / "result-note.json"
    skeleton_path = (
        run_dir / "event-package-skeleton.json"
        if discovery.event_package_skeleton is not None
        else None
    )
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "family": repo_relative_path(family_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }
    family = discovery.family.model_copy(
        update={
            "event_package_skeleton_artifact": (
                repo_relative_path(skeleton_path, root=effective_root)
                if skeleton_path is not None
                else None
            )
        }
    )
    family_path.write_text(
        json.dumps(family.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if skeleton_path is not None and discovery.event_package_skeleton is not None:
        skeleton_path.write_text(
            json.dumps(
                discovery.event_package_skeleton.model_dump(mode="json"),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    note_path.write_text(
        _render_note(family=family, output_paths=output_paths), encoding="utf-8"
    )
    result_note = _build_result_note(
        run_id=run_id, family=family, output_paths=output_paths
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
            "discover-contexts",
            *run_relpaths,
        ],
        seed=seed,
        input_artifacts={
            f"substrate_run_{index}": path
            for index, path in enumerate(run_relpaths, start=1)
        },
        output_artifacts={
            "discovered_context_family": output_paths["family"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
            **(
                {"event_package_skeleton": family.event_package_skeleton_artifact}
                if family.event_package_skeleton_artifact is not None
                else {}
            ),
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "context_discovery",
            "accepted_context_count": family.diagnostics_summary.accepted_context_count,
            "rejected_candidate_count": family.diagnostics_summary.rejected_candidate_count,
            "observable_only": True,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return ContextDiscoveryReportArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=output_paths["manifest"],
        family_path=output_paths["family"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        skeleton_path=family.event_package_skeleton_artifact,
        family=family,
    )
