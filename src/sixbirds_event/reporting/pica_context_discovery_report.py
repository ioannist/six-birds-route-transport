from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from ..discovery.pica_context_discovery import (
    DEFAULT_PICA_CONTEXT_DISCOVERY,
    discover_pica_context_family,
)
from ..discovery.models import DiscoveredContextFamily, PicaContextDiscoveryConfig
from ..pica_bridge.ingest import load_pica_export_bundle
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote


@dataclass(slots=True)
class PicaContextDiscoveryReportArtifacts:
    run_id: str
    run_dir: str
    family_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    skeleton_path: str | None
    family: DiscoveredContextFamily


def _render_note(
    *,
    family: DiscoveredContextFamily,
    config: PicaContextDiscoveryConfig,
    output_paths: dict[str, str],
) -> str:
    level_count = family.metadata.get("distinct_level_count", 0)
    resolution_count = family.metadata.get("distinct_resolution_count", 0)
    closure_count = family.metadata.get("distinct_closure_count", 0)
    lines = [
        "# PICA Context Discovery Report",
        "",
        f"- Source mode: `{family.source_mode}`",
        f"- Source bundle: `{family.source_bundle_artifact}`",
        f"- Projection mode: `{config.projection.projection_mode}`",
        f"- Projection field: `{config.projection.payload_key or config.projection.projection_mode}`",
        f"- Projection bins: `{config.projection.bin_edges}`",
        f"- Accepted context count: `{family.diagnostics_summary.accepted_context_count}`",
        f"- Rejected candidate count: `{family.diagnostics_summary.rejected_candidate_count}`",
        f"- Distinct level count: `{level_count}`",
        f"- Distinct resolution count: `{resolution_count}`",
        f"- Distinct closure count: `{closure_count}`",
        f"- Rejection summary: `{family.diagnostics_summary.rejection_reason_counts}`",
        "",
        "## Accepted contexts",
    ]
    for context in family.accepted_contexts:
        diagnostics = context.diagnostics
        lines.append(
            f"- `{context.context_id}`: row_count=`{diagnostics.row_count}`, retained_atom_count=`{diagnostics.retained_atom_count}`, "
            f"coverage_fraction=`{diagnostics.coverage_fraction}`, empirical_entropy=`{diagnostics.empirical_entropy}`, "
            f"batch_tv_max=`{diagnostics.batch_tv_max}`, support_by_retained_atom=`{diagnostics.support_by_retained_atom}`"
        )
    lines.extend(
        [
            "",
            "## Artifact references",
            f"- Discovered context family: `{output_paths['family']}`",
            f"- Context discovery note: `{output_paths['note']}`",
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
            "distinct_level_count": int(family.metadata.get("distinct_level_count", 0)),
            "distinct_resolution_count": int(
                family.metadata.get("distinct_resolution_count", 0)
            ),
            "distinct_closure_count": int(
                family.metadata.get("distinct_closure_count", 0)
            ),
        },
        interpretation=(
            "PICA-native context extraction grouped observable-ledger rows by preparation/protocol/level/resolution/closure/lens/protocol-step keys and projected observable labels without using hidden-state identifiers."
        ),
        caveats=[
            "The committed multiseed export remains single-level in this ticket; the multilayer signal comes from resolutions and closures rather than multiple levels.",
            "Projection is explicit and deterministic; changing the projection config may change which contexts are nontrivial.",
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
        metadata={"observable_only": True, "source_mode": family.source_mode},
    )


def write_pica_context_discovery_report(
    *,
    bundle_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
    config: PicaContextDiscoveryConfig | None = None,
) -> PicaContextDiscoveryReportArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    active_config = (
        config.model_copy(
            update={
                "bundle_artifact": repo_relative_path(bundle_path, root=effective_root)
            }
        )
        if config is not None
        else DEFAULT_PICA_CONTEXT_DISCOVERY.model_copy(
            update={
                "bundle_artifact": repo_relative_path(bundle_path, root=effective_root)
            }
        )
    )
    resolved = load_pica_export_bundle(bundle_path, repo_root=effective_root)
    discovery = discover_pica_context_family(
        resolved,
        config=active_config,
        family_id=f"family_{run_id}",
        bundle_artifact=repo_relative_path(bundle_path, root=effective_root),
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
        _render_note(family=family, config=active_config, output_paths=output_paths),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        family=family,
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
            "pica",
            "discover-contexts",
            repo_relative_path(bundle_path, root=effective_root),
        ],
        seed=seed,
        input_artifacts={
            "pica_export_bundle": repo_relative_path(bundle_path, root=effective_root)
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
            "analysis_kind": "pica_context_discovery",
            "accepted_context_count": family.diagnostics_summary.accepted_context_count,
            "rejected_candidate_count": family.diagnostics_summary.rejected_candidate_count,
            "distinct_closure_count": int(
                family.metadata.get("distinct_closure_count", 0)
            ),
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return PicaContextDiscoveryReportArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        family_path=output_paths["family"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        skeleton_path=family.event_package_skeleton_artifact,
        family=family,
    )
