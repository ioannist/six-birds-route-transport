from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from ..provenance.audit import audit_package_provenance
from ..provenance.models import ProvenanceAuditResult
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote


@dataclass(slots=True)
class PicaProvenanceRefreshArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    audited_packages: list[dict[str, object]]


@dataclass(slots=True)
class _PackageAuditEntry:
    package_id: str
    package_path: str
    provenance_path: str | None
    audit_result: ProvenanceAuditResult
    audit_artifacts_path: str | None


def _render_note(
    *,
    audited_packages: list[dict[str, object]],
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# PICA Provenance Refresh Report",
        "",
        "## Audited packages",
    ]
    for entry in audited_packages:
        lines.append(
            f"- `{entry['package_id']}`: classification=`{entry['admissibility_classification']}`, "
            f"unsupported_events=`{entry['unsupported_event_count']}`, "
            f"unresolved_source_refs=`{entry['unresolved_source_ref_count']}`, "
            f"unknown_row_filter_fields=`{entry['unknown_row_filter_field_count']}`"
        )
    lines.extend(
        [
            "",
            "## Artifact references",
            f"- Summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Manifest: `{output_paths['manifest']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_pica_provenance_refresh_report(
    *,
    package_provenance_pairs: list[tuple[str | Path, str | Path | None]],
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> PicaProvenanceRefreshArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or "pica-provenance-refresh",
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]

    summary_path = run_dir / "pica-provenance-refresh-summary.json"
    note_path = run_dir / "pica-provenance-refresh-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    audited_packages: list[dict[str, object]] = []
    for package_path, provenance_path in package_provenance_pairs:
        result = audit_package_provenance(
            package_path=package_path,
            provenance_path=provenance_path,
            root=effective_root,
        )
        audited_packages.append(
            {
                "package_id": result.package_id,
                "package_artifact": result.package_artifact,
                "provenance_artifact": repo_relative_path(
                    provenance_path, root=effective_root
                )
                if provenance_path is not None
                else None,
                "admissibility_classification": result.admissibility_classification,
                "event_total_count": result.event_total_count,
                "event_covered_count": result.event_covered_count,
                "unsupported_event_count": result.unsupported_event_count,
                "unresolved_source_ref_count": result.unresolved_source_ref_count,
                "unknown_row_filter_field_count": result.unknown_row_filter_field_count,
                "context_total_count": result.context_total_count,
                "context_covered_count": result.context_covered_count,
                "proposal_total_count": result.proposal_total_count,
                "proposal_covered_count": result.proposal_covered_count,
            }
        )

    admissible_count = sum(
        1
        for entry in audited_packages
        if entry["admissibility_classification"] == "admissible"
    )
    total_unknown_row_filter_fields = sum(
        entry["unknown_row_filter_field_count"]  # type: ignore[arg-type]
        for entry in audited_packages
    )

    summary_payload = {
        "refresh_id": run_id,
        "audited_package_count": len(audited_packages),
        "admissible_count": admissible_count,
        "total_unknown_row_filter_field_count": total_unknown_row_filter_fields,
        "systematic_failure_mode_present": total_unknown_row_filter_fields > 0,
        "audited_packages": audited_packages,
        "paths": output_paths,
    }
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(
        _render_note(audited_packages=audited_packages, output_paths=output_paths),
        encoding="utf-8",
    )

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[str(entry["package_id"]) for entry in audited_packages]
        or ["none"],
        metrics={
            "audited_package_count": len(audited_packages),
            "admissible_count": admissible_count,
            "total_unknown_row_filter_field_count": total_unknown_row_filter_fields,
            "systematic_failure_mode_present": total_unknown_row_filter_fields > 0,
        },
        interpretation=(
            "PICA provenance refresh audited committed PICA-derived packages "
            "after the row-filter repair. "
            f"admissible={admissible_count}/{len(audited_packages)}, "
            f"unknown_row_filter_fields={total_unknown_row_filter_fields}."
        ),
        caveats=[
            "This refresh does not rerun the full targeted obstruction campaign.",
            "It only re-audits existing packages against the repaired provenance layer.",
        ],
        artifact_refs={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
        },
        metadata={
            "analysis_kind": "pica_provenance_refresh",
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
            "audits",
            "pica-provenance-refresh",
        ],
        seed=seed,
        input_artifacts={
            f"package_{i}": str(entry["package_artifact"])
            for i, entry in enumerate(audited_packages)
        },
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "pica_provenance_refresh",
            "audited_package_count": len(audited_packages),
            "admissible_count": admissible_count,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return PicaProvenanceRefreshArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        audited_packages=audited_packages,
    )
