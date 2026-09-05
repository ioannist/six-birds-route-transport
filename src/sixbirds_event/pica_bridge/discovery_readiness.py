from __future__ import annotations

from dataclasses import dataclass
import json
from itertools import combinations
from pathlib import Path
import sys

from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    get_repo_root,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from .ingest import load_pica_export_bundle
from .models import PicaDiscoveryReadinessSummary


@dataclass(slots=True)
class PicaDiscoveryReadinessArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    summary: PicaDiscoveryReadinessSummary


def _bundle_export_mode(summary: PicaDiscoveryReadinessSummary) -> str:
    return summary.pica_export_mode


def analyze_pica_discovery_readiness(
    *,
    bundle_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> PicaDiscoveryReadinessArtifacts:
    repo_root = get_repo_root(root)
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    resolved = load_pica_export_bundle(bundle_path, repo_root=repo_root)

    summary_path = run_dir / "pica-discovery-readiness-summary.json"
    note_path = run_dir / "pica-discovery-readiness-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"

    output_artifacts = {
        "summary": repo_relative_path(summary_path, root=repo_root),
        "note": repo_relative_path(note_path, root=repo_root),
        "result_note": repo_relative_path(result_note_path, root=repo_root),
        "manifest": repo_relative_path(manifest_path, root=repo_root),
    }

    ledgers = list(resolved.observable_ledgers.values())
    distinct_run_trajectories = {
        (ledger.run_id, row.trajectory_id) for ledger in ledgers for row in ledger.rows
    }
    protocol_step_ids = {
        (ledger.run_id, row.protocol_step_id)
        for ledger in ledgers
        for row in ledger.rows
    }
    context_support: dict[
        tuple[str, str, str, str, str, str, str, str, int], set[str]
    ] = {}
    for ledger in ledgers:
        for row in ledger.rows:
            key = (
                ledger.run_id,
                row.preparation_id,
                row.protocol_id,
                row.level_id,
                row.resolution_id,
                row.closure_id,
                row.lens_id,
                row.protocol_step_id,
                row.step_index,
            )
            context_support.setdefault(key, set()).add(row.trajectory_id)

    context_keys = sorted(context_support)
    shared_support_pairs = 0
    probe_pairs = 0
    for left_key, right_key in combinations(context_keys, 2):
        if left_key[0] != right_key[0]:
            continue
        if left_key[1] != right_key[1] or left_key[2] != right_key[2]:
            continue
        common_support = context_support[left_key] & context_support[right_key]
        if not common_support:
            continue
        shared_support_pairs += 1
        for probe_key in context_keys:
            if probe_key in {left_key, right_key}:
                continue
            if probe_key[0] != left_key[0]:
                continue
            if probe_key[1] != left_key[1] or probe_key[2] != left_key[2]:
                continue
            if common_support & context_support[probe_key]:
                probe_pairs += 1
                break

    if ledgers and all(
        ledger.observation_granularity == "per_trajectory" for ledger in ledgers
    ):
        observation_granularity = "per_trajectory"
    else:
        observation_granularity = "aggregate_summary"
    if ledgers and all(
        ledger.cooccurrence_scope == "within_run_and_trajectory" for ledger in ledgers
    ):
        cooccurrence_scope = "within_run_and_trajectory"
    elif ledgers and all(
        ledger.cooccurrence_scope == "within_run" for ledger in ledgers
    ):
        cooccurrence_scope = "within_run"
    else:
        cooccurrence_scope = "none"
    supports_structural_probe_conditioning = bool(ledgers) and all(
        ledger.supports_structural_probe_conditioning for ledger in ledgers
    )
    readiness_classification = (
        "discovery_grade_ready"
        if supports_structural_probe_conditioning
        and shared_support_pairs > 0
        and probe_pairs > 0
        else "discovery_grade_inadequate"
    )
    pica_export_mode = (
        "discovery_grade_per_trajectory"
        if observation_granularity == "per_trajectory"
        else "aggregate_summary"
    )

    summary = PicaDiscoveryReadinessSummary(
        schema_version="pica-discovery-readiness.v1",
        bundle_artifact=repo_relative_path(bundle_path, root=repo_root),
        export_bundle_id=resolved.export_bundle.export_bundle_id,
        pica_export_mode=pica_export_mode,
        observation_granularity=observation_granularity,
        cooccurrence_scope=cooccurrence_scope,
        run_count=len(resolved.runs),
        trajectory_count=len(distinct_run_trajectories),
        closure_count=sum(
            len(catalog.closures) for catalog in resolved.closure_catalogs.values()
        ),
        lens_count=sum(
            len(catalog.lenses) for catalog in resolved.closure_catalogs.values()
        ),
        step_count=len(protocol_step_ids),
        context_key_count=len(context_keys),
        context_pair_count=max(len(context_keys) * (len(context_keys) - 1) // 2, 0),
        context_pairs_with_shared_trajectory_support=shared_support_pairs,
        context_pairs_with_probe_conditioning_potential=probe_pairs,
        supports_structural_probe_conditioning=supports_structural_probe_conditioning,
        readiness_classification=readiness_classification,
        notes=[
            "Readiness is computed from observable-ledger cooccurrence structure only.",
            "Hidden microstate traces are not required for this classification.",
        ],
        flags=[pica_export_mode, readiness_classification],
        artifact_refs=output_artifacts,
    )
    summary_path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    note_path.write_text(
        "\n".join(
            [
                "# PICA Discovery Readiness",
                "",
                f"- Bundle: `{summary.bundle_artifact}`",
                f"- Export bundle ID: `{summary.export_bundle_id}`",
                f"- Export mode: `{_bundle_export_mode(summary)}`",
                f"- Observation granularity: `{summary.observation_granularity}`",
                f"- Cooccurrence scope: `{summary.cooccurrence_scope}`",
                "- Supports structural probe conditioning: "
                f"`{summary.supports_structural_probe_conditioning}`",
                f"- Run count: `{summary.run_count}`",
                f"- Trajectory count: `{summary.trajectory_count}`",
                f"- Closure count: `{summary.closure_count}`",
                f"- Lens count: `{summary.lens_count}`",
                f"- Step count: `{summary.step_count}`",
                f"- Context key count: `{summary.context_key_count}`",
                "- Context pairs with shared trajectory support: "
                f"`{summary.context_pairs_with_shared_trajectory_support}`",
                "- Context pairs with probe-conditioning potential: "
                f"`{summary.context_pairs_with_probe_conditioning_potential}`",
                f"- Readiness classification: `{summary.readiness_classification}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[resolved.export_bundle.export_bundle_id],
        metrics={
            "run_count": summary.run_count,
            "trajectory_count": summary.trajectory_count,
            "context_key_count": summary.context_key_count,
            "context_pairs_with_shared_trajectory_support": (
                summary.context_pairs_with_shared_trajectory_support
            ),
            "context_pairs_with_probe_conditioning_potential": (
                summary.context_pairs_with_probe_conditioning_potential
            ),
        },
        interpretation=(
            "PICA discovery readiness checks whether observable ledgers preserve enough same-trajectory support to allow structural cross-context conditioning."
        ),
        caveats=[
            "Classification is based on observable assignment overlap, not semantic discovery success.",
            "Aggregate-summary bundles are expected to fail readiness even if they remain useful for coarse reporting.",
        ],
        artifact_refs=output_artifacts,
        metadata={
            "analysis_kind": "pica_discovery_readiness",
            "export_bundle_id": resolved.export_bundle.export_bundle_id,
            "readiness_classification": summary.readiness_classification,
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
            "analyze-discovery-readiness",
            repo_relative_path(bundle_path, root=repo_root),
        ],
        seed=seed,
        input_artifacts={
            "bundle": repo_relative_path(bundle_path, root=repo_root),
        },
        output_artifacts=output_artifacts,
        status="succeeded",
        git_commit=detect_git_commit(root=repo_root),
        metadata={
            "analysis_kind": "pica_discovery_readiness",
            "export_bundle_id": resolved.export_bundle.export_bundle_id,
            "readiness_classification": summary.readiness_classification,
            "pica_export_mode": summary.pica_export_mode,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return PicaDiscoveryReadinessArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=repo_root),
        summary_path=output_artifacts["summary"],
        note_path=output_artifacts["note"],
        result_note_path=output_artifacts["result_note"],
        manifest_path=output_artifacts["manifest"],
        summary=summary,
    )
