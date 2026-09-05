from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from ..pica_bridge.ingest import load_pica_export_bundle
from ..provenance.audit import audit_package_provenance
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote


@dataclass(slots=True)
class PicaBridgeReportArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    source_index_path: str
    provenance_audit_summary_path: str | None
    result_note_path: str
    manifest_path: str


def write_pica_bridge_report(
    *,
    bundle_path: str | Path,
    package_path: str | Path | None = None,
    provenance_path: str | Path | None = None,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> PicaBridgeReportArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    resolved = load_pica_export_bundle(bundle_path, repo_root=effective_root)

    summary_path = run_dir / "pica-bridge-summary.json"
    source_index_path = run_dir / "pica-source-index.json"
    provenance_summary_path = (
        run_dir / "provenance-audit-summary.json"
        if package_path is not None and provenance_path is not None
        else None
    )
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"

    output_artifacts = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "source_index": repo_relative_path(source_index_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }
    if provenance_summary_path is not None:
        output_artifacts["provenance_audit_summary"] = repo_relative_path(
            provenance_summary_path,
            root=effective_root,
        )

    source_index = resolved.to_source_index_payload()
    source_index_path.write_text(
        json.dumps(source_index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    provenance_result = None
    if provenance_summary_path is not None:
        provenance_result = audit_package_provenance(
            package_path=package_path,
            provenance_path=provenance_path,
            root=effective_root,
        ).model_copy(
            update={
                "artifact_refs": {
                    "summary": output_artifacts["summary"],
                    "source_index": output_artifacts["source_index"],
                    "provenance_audit_summary": output_artifacts[
                        "provenance_audit_summary"
                    ],
                    "result_note": output_artifacts["result_note"],
                    "manifest": output_artifacts["manifest"],
                }
            }
        )
        provenance_summary_path.write_text(
            json.dumps(
                provenance_result.model_dump(mode="json"),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    summary = {
        "bundle_artifact": repo_relative_path(bundle_path, root=effective_root),
        "export_bundle_id": resolved.export_bundle.export_bundle_id,
        "campaign_count": len(resolved.campaigns),
        "point_count": len(resolved.points),
        "run_count": len(resolved.runs),
        "closure_catalog_count": len(resolved.closure_catalogs),
        "observable_ledger_count": len(resolved.observable_ledgers),
        "level_count": len(source_index["level_ids"]),
        "resolution_count": len(source_index["resolution_ids"]),
        "closure_count": len(source_index["closure_ids"]),
        "lens_count": len(source_index["lens_ids"]),
        "protocol_step_count": len(source_index["protocol_step_ids"]),
        "package_artifact": (
            repo_relative_path(package_path, root=effective_root)
            if package_path is not None
            else None
        ),
        "provenance_artifact": (
            repo_relative_path(provenance_path, root=effective_root)
            if provenance_path is not None
            else None
        ),
        "admissibility_classification": (
            provenance_result.admissibility_classification
            if provenance_result is not None
            else None
        ),
        "artifact_refs": output_artifacts,
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[resolved.export_bundle.export_bundle_id],
        metrics={
            "campaign_count": len(resolved.campaigns),
            "point_count": len(resolved.points),
            "run_count": len(resolved.runs),
            "closure_catalog_count": len(resolved.closure_catalogs),
            "observable_ledger_count": len(resolved.observable_ledgers),
            "closure_count": len(source_index["closure_ids"]),
            "lens_count": len(source_index["lens_ids"]),
        },
        interpretation=(
            "PICA bridge inspection resolved a bundle of observable-first artifacts and indexed campaign, run, closure, lens, and protocol-step identifiers."
        ),
        caveats=[
            "The bridge is artifact-based and does not execute PICA or rebuild discovery around PICA in this ticket.",
            "Hidden/internal PICA fields remain optional debug-only bridge inputs.",
        ],
        artifact_refs=output_artifacts,
        metadata={
            "export_bundle_id": resolved.export_bundle.export_bundle_id,
            "admissibility_classification": (
                provenance_result.admissibility_classification
                if provenance_result is not None
                else None
            ),
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
            "pica",
            "inspect-bundle",
            repo_relative_path(bundle_path, root=effective_root),
        ],
        seed=seed,
        input_artifacts={
            "bundle": repo_relative_path(bundle_path, root=effective_root),
            **(
                {
                    "package": repo_relative_path(package_path, root=effective_root),
                    "provenance": repo_relative_path(
                        provenance_path, root=effective_root
                    ),
                }
                if package_path is not None and provenance_path is not None
                else {}
            ),
        },
        output_artifacts=output_artifacts,
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "pica_bridge_inspect",
            "export_bundle_id": resolved.export_bundle.export_bundle_id,
            "admissibility_classification": (
                provenance_result.admissibility_classification
                if provenance_result is not None
                else None
            ),
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return PicaBridgeReportArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        summary_path=output_artifacts["summary"],
        source_index_path=output_artifacts["source_index"],
        provenance_audit_summary_path=output_artifacts.get("provenance_audit_summary"),
        result_note_path=output_artifacts["result_note"],
        manifest_path=repo_relative_path(manifest_path, root=effective_root),
    )
