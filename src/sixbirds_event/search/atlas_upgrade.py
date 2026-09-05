from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import sys

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
    AtlasUpgradeConfig,
    AtlasUpgradePoint,
    AtlasUpgradeRow,
    AtlasUpgradeTable,
    RegimeLabel,
    TargetedCandidateClassificationThresholds,
    TargetedNonextendabilitySearch,
    TargetedSearchPoint,
    TargetedSearchRow,
    TargetedSearchStopRule,
)
from .targeted_nonextendability import _run_point as _run_targeted_point


ATLAS_RULE_VERSION = "atlas-upgrade-classifier.v1"


@dataclass(slots=True)
class AtlasUpgradeArtifacts:
    run_id: str
    run_dir: str
    table_csv_path: str
    table_json_path: str
    regime_counts_path: str
    threshold_summary_path: str
    figure_regime_counts_csv_path: str
    figure_atlas_points_csv_path: str
    figure_threshold_summary_csv_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    table: AtlasUpgradeTable
    regime_counts: dict[str, int]
    best_candidate_path: str | None
    negative_result_path: str | None
    summary: dict[str, object]


def load_atlas_upgrade_config(path: str | Path) -> AtlasUpgradeConfig:
    model = load_model(path, kind="atlas-upgrade-config")
    assert isinstance(model, AtlasUpgradeConfig)
    return model


def _as_targeted_search(config: AtlasUpgradeConfig) -> TargetedNonextendabilitySearch:
    points = [
        TargetedSearchPoint(
            point_id=point.point_id,
            config_artifact=point.config_artifact,
            preparation_id=point.preparation_id,
            protocol_id=point.protocol_id,
            trajectories=point.trajectories,
            seed=point.seed,
            notes=point.notes,
        )
        for point in config.points
    ]
    return TargetedNonextendabilitySearch(
        search_format_version="targeted-nonextendability-search.v1",
        search_id=config.atlas_id,
        points=points,
        extraction_thresholds=config.extraction_thresholds,
        coarse_event_generation_thresholds=config.coarse_event_generation_thresholds,
        shared_event_inference_thresholds=config.shared_event_inference_thresholds,
        provenance_required=config.provenance_required,
        candidate_classification_thresholds=config.candidate_classification_thresholds,
        stop_rule=TargetedSearchStopRule(),
        metadata=config.metadata,
    )


def _is_nontrivial_extendable_structure(row: TargetedSearchRow) -> bool:
    return (
        row.accepted_context_count >= 2
        and row.event_package_path is not None
        and (
            row.accepted_coarse_event_count > 0
            or row.accepted_coarse_proposal_count > 0
            or row.accepted_shared_event_proposal_count > 0
        )
    )


def _classify_regime(
    *,
    row: TargetedSearchRow,
    thresholds: TargetedCandidateClassificationThresholds,
) -> RegimeLabel:
    if row.event_package_path is None or row.accepted_context_count < 2:
        return "trivial_or_nonrecording"

    candidate_eval = row.all_accepted_proposals
    baseline_eval = row.baseline_hard_only
    provenance_ok = row.provenance_classification == "admissible"

    candidate_gpd_str = candidate_eval.gpd_str or 0.0
    baseline_gpd_str = baseline_eval.gpd_str or 0.0

    if (
        provenance_ok
        and row.accepted_coarse_proposal_count
        >= thresholds.min_accepted_coarse_proposal_count
        and candidate_eval.exact_feasible is False
        and candidate_eval.gpd_str_status == "solved"
        and candidate_gpd_str > thresholds.strong_nonextendable_min_gpd_str
    ):
        return "strongly_nonextendable"

    if (
        candidate_eval.gpd_str_status == "solved" and candidate_gpd_str > 0
    ) or candidate_eval.exact_feasible is False:
        return "weakly_frustrated"

    if (
        provenance_ok
        and baseline_eval.exact_feasible is True
        and candidate_eval.exact_feasible is True
        and baseline_eval.gpd_str_status == "solved"
        and candidate_eval.gpd_str_status == "solved"
        and baseline_gpd_str == 0
        and candidate_gpd_str == 0
    ):
        if _is_nontrivial_extendable_structure(row):
            return "multi_context_but_extendable"
        return "globally_packageable"

    return "trivial_or_nonrecording"


def _figure_group_labels(
    *,
    point: AtlasUpgradePoint,
    row: TargetedSearchRow,
    regime: RegimeLabel,
) -> list[str]:
    config_slug = Path(point.config_artifact).stem
    primary = point.figure_group or config_slug
    return [
        primary,
        regime,
        row.provenance_classification or "no_provenance",
        "coarse_events_present"
        if row.accepted_coarse_event_count > 0
        else "coarse_events_absent",
    ]


def _atlas_row_from_targeted(
    *,
    atlas_id: str,
    point: AtlasUpgradePoint,
    row: TargetedSearchRow,
    thresholds: TargetedCandidateClassificationThresholds,
) -> AtlasUpgradeRow:
    regime = _classify_regime(row=row, thresholds=thresholds)
    return AtlasUpgradeRow(
        row_format_version="atlas-upgrade-row.v1",
        atlas_id=atlas_id,
        point_id=row.point_id,
        config_path=row.config_path,
        preparation_id=row.preparation_id,
        protocol_id=row.protocol_id,
        trajectories=row.trajectories,
        seed=row.seed,
        raw_run_path=row.raw_run_path,
        discovered_context_family_path=row.discovered_context_family_path,
        event_package_path=row.event_package_path,
        provenance_classification=row.provenance_classification,
        accepted_context_count=row.accepted_context_count,
        accepted_singleton_event_count=row.accepted_singleton_event_count,
        accepted_coarse_event_count=row.accepted_coarse_event_count,
        accepted_shared_event_proposal_count=row.accepted_shared_event_proposal_count,
        accepted_coarse_proposal_count=row.accepted_coarse_proposal_count,
        baseline_hard_only=row.baseline_hard_only,
        all_accepted_proposals=row.all_accepted_proposals,
        ccd_status=row.ccd_status,
        ccd_overall=row.ccd_overall,
        sec_status=row.sec_status,
        sec_mean=row.sec_mean,
        rm_status=row.rm_status,
        rm_overall=row.rm_overall,
        regime_classification=regime,
        figure_group_labels=_figure_group_labels(point=point, row=row, regime=regime),
        run_ids=row.run_ids,
        artifact_paths=row.artifact_paths,
        notes=row.notes,
    )


def _row_to_csv_record(row: AtlasUpgradeRow) -> dict[str, object]:
    return {
        "point_id": row.point_id,
        "config_path": row.config_path,
        "preparation_id": row.preparation_id,
        "protocol_id": row.protocol_id,
        "trajectories": row.trajectories,
        "seed": row.seed,
        "raw_run_path": row.raw_run_path,
        "discovered_context_family_path": row.discovered_context_family_path,
        "event_package_path": row.event_package_path,
        "provenance_classification": row.provenance_classification,
        "accepted_context_count": row.accepted_context_count,
        "accepted_singleton_event_count": row.accepted_singleton_event_count,
        "accepted_coarse_event_count": row.accepted_coarse_event_count,
        "accepted_shared_event_proposal_count": row.accepted_shared_event_proposal_count,
        "accepted_coarse_proposal_count": row.accepted_coarse_proposal_count,
        "baseline_exact_structural_status": row.baseline_hard_only.exact_structural_status,
        "baseline_exact_feasible": row.baseline_hard_only.exact_feasible,
        "baseline_exact_respecting_tuple_count": row.baseline_hard_only.exact_respecting_tuple_count,
        "baseline_gpd_str_status": row.baseline_hard_only.gpd_str_status,
        "baseline_gpd_str": row.baseline_hard_only.gpd_str,
        "baseline_gpd_stat_status": row.baseline_hard_only.gpd_stat_status,
        "baseline_gpd_stat": row.baseline_hard_only.gpd_stat,
        "candidate_exact_structural_status": row.all_accepted_proposals.exact_structural_status,
        "candidate_exact_feasible": row.all_accepted_proposals.exact_feasible,
        "candidate_exact_respecting_tuple_count": row.all_accepted_proposals.exact_respecting_tuple_count,
        "candidate_gpd_str_status": row.all_accepted_proposals.gpd_str_status,
        "candidate_gpd_str": row.all_accepted_proposals.gpd_str,
        "candidate_gpd_stat_status": row.all_accepted_proposals.gpd_stat_status,
        "candidate_gpd_stat": row.all_accepted_proposals.gpd_stat,
        "ccd_status": row.ccd_status,
        "ccd_overall": row.ccd_overall,
        "sec_status": row.sec_status,
        "sec_mean": row.sec_mean,
        "rm_status": row.rm_status,
        "rm_overall": row.rm_overall,
        "regime_classification": row.regime_classification,
        "figure_group_labels": "|".join(row.figure_group_labels),
        "substrate_run_id": row.run_ids.get("substrate_run"),
        "context_discovery_run_id": row.run_ids.get("context_discovery"),
        "package_build_run_id": row.run_ids.get("package_build"),
        "provenance_audit_run_id": row.run_ids.get("provenance_audit"),
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _threshold_summary(
    *,
    config: AtlasUpgradeConfig,
    table: AtlasUpgradeTable,
) -> dict[str, object]:
    return {
        "discovery_thresholds": config.extraction_thresholds.model_dump(mode="json"),
        "coarse_event_generation_thresholds": config.coarse_event_generation_thresholds.model_dump(
            mode="json"
        ),
        "shared_event_inference_thresholds": config.shared_event_inference_thresholds.model_dump(
            mode="json"
        ),
        "provenance_required": config.provenance_required,
        "stage_counts": {
            "discovery_success_count": sum(
                row.accepted_context_count >= 2 for row in table.rows
            ),
            "package_build_success_count": sum(
                row.event_package_path is not None for row in table.rows
            ),
            "provenance_admissible_count": sum(
                row.provenance_classification == "admissible" for row in table.rows
            ),
            "accepted_coarse_event_positive_count": sum(
                row.accepted_coarse_event_count > 0 for row in table.rows
            ),
            "accepted_coarse_proposal_positive_count": sum(
                row.accepted_coarse_proposal_count > 0 for row in table.rows
            ),
            "all_accepted_proposals_feasible_count": sum(
                row.all_accepted_proposals.exact_feasible is True for row in table.rows
            ),
            "all_accepted_proposals_infeasible_count": sum(
                row.all_accepted_proposals.exact_feasible is False for row in table.rows
            ),
        },
    }


def _result_note(
    *,
    run_id: str,
    atlas: AtlasUpgradeTable,
    regime_counts: dict[str, int],
    output_paths: dict[str, str],
    no_strong_found: bool,
) -> ResultNote:
    metrics = {
        "total_point_count": atlas.row_count,
        "provenance_admissible_count": sum(
            row.provenance_classification == "admissible" for row in atlas.rows
        ),
        "nontrivial_extendable_count": sum(
            row.regime_classification
            in {"globally_packageable", "multi_context_but_extendable"}
            and row.accepted_context_count >= 2
            for row in atlas.rows
        ),
        "strong_nonextendable_count": regime_counts.get("strongly_nonextendable", 0),
        "no_strong_discovered_obstruction_found": int(no_strong_found),
    }
    for regime, count in sorted(regime_counts.items()):
        metrics[f"regime_count_{regime}"] = count
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"{atlas.atlas_id}_result_note",
        run_id=run_id,
        instance_ids=[atlas.atlas_id],
        metrics=metrics,
        interpretation=(
            "Atlas-upgrade rows preserve separate hard_only and all_accepted_proposals evaluations and record an explicit negative result when no strong discovered obstruction is found."
        ),
        caveats=[
            "RM is diagnostic-only where present.",
            "unsupported metrics preserve unsolved / insufficient_data / not_applicable statuses.",
        ],
        artifact_refs=output_paths,
        metadata={
            "analysis_kind": "atlas_upgrade",
            "classification_rule_version": ATLAS_RULE_VERSION,
        },
    )


def run_atlas_upgrade(
    *,
    config_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> AtlasUpgradeArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    config = load_atlas_upgrade_config(config_path)
    adapter = _as_targeted_search(config)
    bundle_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or config.output_label or config.atlas_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = bundle_dir.parents[2]
    derived_dir = bundle_dir / "derived"
    derived_dir.mkdir()

    rows: list[AtlasUpgradeRow] = []
    for point, targeted_point in zip(config.points, adapter.points, strict=True):
        targeted_row = _run_targeted_point(
            point=targeted_point,
            search=adapter,
            category=category,
            timestamp=timestamp,
            root=effective_root,
            derived_dir=derived_dir,
        )
        rows.append(
            _atlas_row_from_targeted(
                atlas_id=config.atlas_id,
                point=point,
                row=targeted_row,
                thresholds=config.candidate_classification_thresholds,
            )
        )

    table = AtlasUpgradeTable(
        table_format_version="atlas-upgrade-results.v1",
        atlas_id=config.atlas_id,
        row_count=len(rows),
        rows=rows,
        metadata={
            "atlas_artifact": repo_relative_path(config_path, root=effective_root),
            "classification_rule_version": ATLAS_RULE_VERSION,
        },
    )

    regime_counter = Counter(row.regime_classification for row in table.rows)
    regime_counts: dict[str, int] = {
        regime: regime_counter.get(regime, 0)
        for regime in [
            "trivial_or_nonrecording",
            "globally_packageable",
            "multi_context_but_extendable",
            "weakly_frustrated",
            "strongly_nonextendable",
        ]
    }

    strong_candidates = [
        row
        for row in table.rows
        if row.regime_classification == "strongly_nonextendable"
    ]
    strong_candidates.sort(
        key=lambda row: (
            -(row.all_accepted_proposals.gpd_str or 0.0),
            row.all_accepted_proposals.exact_respecting_tuple_count
            if row.all_accepted_proposals.exact_respecting_tuple_count is not None
            else 10**9,
            -row.accepted_coarse_proposal_count,
            row.point_id,
        )
    )
    best_candidate = strong_candidates[0] if strong_candidates else None
    no_strong_found = best_candidate is None

    table_csv_path = bundle_dir / "atlas-upgrade.csv"
    table_json_path = bundle_dir / "atlas-upgrade.json"
    regime_counts_path = bundle_dir / "regime-counts.json"
    threshold_summary_path = bundle_dir / "threshold-summary.json"
    figure_regime_counts_csv_path = bundle_dir / "figure-regime-counts.csv"
    figure_atlas_points_csv_path = bundle_dir / "figure-atlas-points.csv"
    figure_threshold_summary_csv_path = bundle_dir / "figure-threshold-summary.csv"
    summary_path = bundle_dir / "atlas-upgrade-summary.json"
    note_path = bundle_dir / "atlas-upgrade-note.md"
    result_note_path = bundle_dir / "result-note.json"
    manifest_path = bundle_dir / "run-manifest.json"
    best_candidate_path = bundle_dir / "best-candidate.json"
    negative_result_path = bundle_dir / "negative-result.json"

    csv_rows = [_row_to_csv_record(row) for row in table.rows]
    _write_csv(table_csv_path, csv_rows)
    _write_csv(figure_atlas_points_csv_path, csv_rows)
    table_json_path.write_text(
        json.dumps(table.model_dump(mode="json", exclude_none=True), indent=2) + "\n",
        encoding="utf-8",
    )
    regime_counts_path.write_text(
        json.dumps(regime_counts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        figure_regime_counts_csv_path,
        [
            {"regime_label": regime, "count": count}
            for regime, count in regime_counts.items()
        ],
    )

    threshold_summary = _threshold_summary(config=config, table=table)
    threshold_summary_path.write_text(
        json.dumps(threshold_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        figure_threshold_summary_csv_path,
        [
            {"stage": key, "value": value}
            for key, value in threshold_summary["stage_counts"].items()
        ],
    )

    output_paths = {
        "table_csv": repo_relative_path(table_csv_path, root=effective_root),
        "table_json": repo_relative_path(table_json_path, root=effective_root),
        "regime_counts": repo_relative_path(regime_counts_path, root=effective_root),
        "threshold_summary": repo_relative_path(
            threshold_summary_path, root=effective_root
        ),
        "figure_regime_counts_csv": repo_relative_path(
            figure_regime_counts_csv_path, root=effective_root
        ),
        "figure_atlas_points_csv": repo_relative_path(
            figure_atlas_points_csv_path, root=effective_root
        ),
        "figure_threshold_summary_csv": repo_relative_path(
            figure_threshold_summary_csv_path, root=effective_root
        ),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
    }

    if best_candidate is not None:
        best_candidate_path.write_text(
            json.dumps(
                best_candidate.model_dump(mode="json", exclude_none=True), indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        best_candidate_relpath = repo_relative_path(
            best_candidate_path, root=effective_root
        )
        negative_result_relpath = None
        output_paths["best_candidate"] = best_candidate_relpath
    else:
        negative_result_path.write_text(
            json.dumps(
                {
                    "atlas_id": config.atlas_id,
                    "negative_result": True,
                    "reason": "no_strong_discovered_obstruction_found",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        negative_result_relpath = repo_relative_path(
            negative_result_path, root=effective_root
        )
        best_candidate_relpath = None
        output_paths["negative_result"] = negative_result_relpath

    summary: dict[str, object] = {
        "atlas_id": config.atlas_id,
        "config_family": [point.config_artifact for point in config.points],
        "threshold_configs": {
            "discovery": config.extraction_thresholds.model_dump(mode="json"),
            "coarse_event_generation": config.coarse_event_generation_thresholds.model_dump(
                mode="json"
            ),
            "shared_event_inference": config.shared_event_inference_thresholds.model_dump(
                mode="json"
            ),
            "candidate_classification": config.candidate_classification_thresholds.model_dump(
                mode="json"
            ),
        },
        "provenance_required": config.provenance_required,
        "counts_by_regime": regime_counts,
        "provenance_admissible_count": sum(
            row.provenance_classification == "admissible" for row in table.rows
        ),
        "nontrivial_extendable_count": sum(
            row.regime_classification
            in {"globally_packageable", "multi_context_but_extendable"}
            and row.accepted_context_count >= 2
            for row in table.rows
        ),
        "strong_nonextendable_count": regime_counts["strongly_nonextendable"],
        "best_candidate_id": None
        if best_candidate is None
        else best_candidate.point_id,
        "no_strong_discovered_obstruction_found": no_strong_found,
        "artifact_paths": output_paths,
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    note_lines = [
        f"# Atlas Upgrade: {config.atlas_id}",
        "",
        "## Configs covered",
    ]
    for point in config.points:
        note_lines.append(
            f"- `{point.point_id}`: config=`{point.config_artifact}`, preparation=`{point.preparation_id}`, protocol=`{point.protocol_id}`, seed=`{point.seed}`"
        )
    note_lines.extend(
        [
            "",
            "## Thresholds",
            f"- Discovery thresholds: `{config.extraction_thresholds.model_dump(mode='json')}`",
            f"- Coarse-event thresholds: `{config.coarse_event_generation_thresholds.model_dump(mode='json')}`",
            f"- Shared-event inference thresholds: `{config.shared_event_inference_thresholds.model_dump(mode='json')}`",
            f"- Provenance required: `{config.provenance_required}`",
            "",
            "## Evaluation modes",
            "- Baseline hard-only mode is recorded separately from all-accepted-proposals mode.",
            "- All-accepted-proposals mode drives strong-discovered-obstruction assessment.",
            "",
            "## Regime counts",
        ]
    )
    for regime, count in regime_counts.items():
        note_lines.append(f"- `{regime}`: `{count}`")
    note_lines.extend(
        [
            "",
            "## Outcome",
            f"- Strong discovered obstruction found: `{not no_strong_found}`",
        ]
    )
    if no_strong_found:
        note_lines.append(
            "- Negative result: no strong endogenous discovered obstruction was found in the committed upgraded atlas family."
        )
    else:
        note_lines.append(f"- Best candidate: `{best_candidate.point_id}`")
    note_lines.extend(
        [
            "- RM is diagnostic-only.",
            "- Unavailable metrics preserve unsolved / insufficient_data / not_applicable statuses.",
            "",
            "## Artifact references",
        ]
    )
    for key, value in output_paths.items():
        note_lines.append(f"- `{key}`: `{value}`")
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    result_note = _result_note(
        run_id=run_id,
        atlas=table,
        regime_counts=regime_counts,
        output_paths=output_paths,
        no_strong_found=no_strong_found,
    )
    result_note_path.write_text(
        json.dumps(result_note.model_dump(mode="json", exclude_none=True), indent=2)
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
            "search",
            "run-atlas-upgrade",
            str(config_path),
        ],
        seed=seed,
        input_artifacts={
            "config": repo_relative_path(config_path, root=effective_root),
        },
        output_artifacts=output_paths,
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "atlas_upgrade",
            "classification_rule_version": ATLAS_RULE_VERSION,
        },
    )
    write_run_manifest(manifest, run_dir=bundle_dir)

    return AtlasUpgradeArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(bundle_dir, root=effective_root),
        table_csv_path=repo_relative_path(table_csv_path, root=effective_root),
        table_json_path=repo_relative_path(table_json_path, root=effective_root),
        regime_counts_path=repo_relative_path(regime_counts_path, root=effective_root),
        threshold_summary_path=repo_relative_path(
            threshold_summary_path, root=effective_root
        ),
        figure_regime_counts_csv_path=repo_relative_path(
            figure_regime_counts_csv_path, root=effective_root
        ),
        figure_atlas_points_csv_path=repo_relative_path(
            figure_atlas_points_csv_path, root=effective_root
        ),
        figure_threshold_summary_csv_path=repo_relative_path(
            figure_threshold_summary_csv_path, root=effective_root
        ),
        summary_path=repo_relative_path(summary_path, root=effective_root),
        note_path=repo_relative_path(note_path, root=effective_root),
        result_note_path=repo_relative_path(result_note_path, root=effective_root),
        manifest_path=repo_relative_path(manifest_path, root=effective_root),
        table=table,
        regime_counts=regime_counts,
        best_candidate_path=best_candidate_relpath,
        negative_result_path=negative_result_relpath,
        summary=summary,
    )
