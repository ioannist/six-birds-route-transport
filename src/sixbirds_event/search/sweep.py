from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import statistics
import sys

from ..discovery.models import (
    DiscoveredContextFamily,
    SharedEventCandidates,
)
from ..reporting.context_discovery_report import write_context_discovery_report
from ..reporting.package_build_report import write_package_build_report
from ..reporting.statistical_report import write_statistical_summary
from ..reporting.structural_report import generate_structural_report
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.observation_trace import Observation, ObservationTrace
from ..schemas.result_note import ResultNote
from ..search.models import (
    AtlasStatus,
    ClassificationThresholds,
    RegimeLabel,
    SearchAtlas,
    SearchAtlasRow,
    SearchSweep,
    SearchSweepPoint,
)
from ..substrates.engine import load_substrate_config, write_substrate_run
from ..validation import load_model


CLASSIFICATION_RULE_VERSION = "search-classifier.v1"


@dataclass(slots=True)
class SearchSweepArtifacts:
    run_id: str
    run_dir: str
    atlas_csv_path: str
    atlas_json_path: str
    regime_counts_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    atlas: SearchAtlas
    regime_counts: dict[str, int]


def load_search_sweep(path: str | Path) -> SearchSweep:
    model = load_model(path, kind="search-sweep")
    assert isinstance(model, SearchSweep)
    return model


def _load_family(path: str | Path) -> DiscoveredContextFamily:
    model = load_model(path, kind="discovered-context-family")
    assert isinstance(model, DiscoveredContextFamily)
    return model


def _load_candidates(path: str | Path) -> SharedEventCandidates:
    model = load_model(path, kind="shared-event-candidates")
    assert isinstance(model, SharedEventCandidates)
    return model


def _derive_stat_trace(
    *,
    family: DiscoveredContextFamily,
    raw_run,
    instance_id: str,
    instance_artifact: str,
    trace_id: str,
) -> ObservationTrace:
    observations: list[Observation] = []
    for context in family.accepted_contexts:
        label_to_outcome = {
            outcome.observation_label: outcome.outcome_id
            for outcome in context.atomic_outcomes
        }
        counts = Counter()
        for trajectory in raw_run.trajectories:
            if (
                trajectory.preparation_id != context.candidate_key.preparation_id
                or trajectory.protocol_id != context.candidate_key.protocol_id
            ):
                continue
            step = next(
                (
                    step
                    for step in trajectory.steps
                    if step.step_index == context.candidate_key.step_index
                ),
                None,
            )
            if step is None:
                continue
            label = step.observations.get(context.candidate_key.lens_id)
            if label is None:
                continue
            outcome_id = label_to_outcome.get(label)
            if outcome_id is None:
                continue
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
        instance_artifact=instance_artifact,
        observations=observations,
        metadata={
            "derived_from": "substrate_run",
            "derivation_kind": "search_stat_trace",
        },
    )


def _sec_summary(candidates: SharedEventCandidates) -> tuple[AtlasStatus, float | None]:
    scored_rows = [
        row
        for row in candidates.candidate_rows
        if not row.insufficient_data and row.approx_score is not None
    ]
    if not candidates.candidate_rows:
        return ("not_applicable", None)
    if not scored_rows:
        return ("insufficient_data", None)
    accepted_scores = [row.approx_score for row in scored_rows if row.accepted]
    values = accepted_scores or [
        row.approx_score for row in scored_rows if row.approx_score is not None
    ]
    return ("scored", statistics.mean(values))


def _classify_row(
    *,
    row: SearchAtlasRow,
    thresholds: ClassificationThresholds,
) -> RegimeLabel:
    if row.accepted_context_count < 2 or row.event_package_path is None:
        return "trivial_or_nonrecording"
    if row.exact_structural_status == "infeasible" and (
        row.exact_respecting_tuple_count == 0
        or (
            row.gpd_str is not None
            and row.gpd_str >= thresholds.strong_nonextendable_min_gpd_str
        )
    ):
        return "strongly_nonextendable"
    if row.gpd_str is not None and row.gpd_str > 0:
        return "weakly_frustrated"
    if row.exact_structural_status == "infeasible":
        return "weakly_frustrated"
    if (
        row.exact_structural_status == "feasible"
        and row.gpd_str == 0
        and row.gpd_stat_status == "solved"
        and row.gpd_stat is not None
        and row.gpd_stat <= thresholds.near_zero_gpd_stat
    ):
        if row.accepted_shared_event_proposal_count == 0:
            return "globally_packageable"
        return "multi_context_but_extendable"
    return "weakly_frustrated"


def _row_to_csv_record(row: SearchAtlasRow) -> dict[str, object]:
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
        "accepted_context_count": row.accepted_context_count,
        "accepted_shared_event_proposal_count": row.accepted_shared_event_proposal_count,
        "exact_structural_status": row.exact_structural_status,
        "exact_structural_feasible_hard_only": row.exact_structural_feasible_hard_only,
        "exact_respecting_tuple_count": row.exact_respecting_tuple_count,
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
        "regime_classification": row.regime_classification,
        "substrate_run_id": row.run_ids.get("substrate_run"),
        "context_discovery_run_id": row.run_ids.get("context_discovery"),
        "package_build_run_id": row.run_ids.get("package_build"),
        "structural_run_id": row.run_ids.get("structural"),
        "statistical_run_id": row.run_ids.get("statistical"),
        "raw_run_artifact": row.artifact_paths.get("raw_run"),
        "family_artifact": row.artifact_paths.get("family"),
        "package_artifact": row.artifact_paths.get("event_package"),
        "structural_summary_artifact": row.artifact_paths.get("structural_summary"),
        "statistical_summary_artifact": row.artifact_paths.get("statistical_summary"),
        "candidate_artifact": row.artifact_paths.get("shared_event_candidates"),
    }


def _build_result_note(
    *,
    run_id: str,
    atlas: SearchAtlas,
    regime_counts: dict[str, int],
    output_paths: dict[str, str],
) -> ResultNote:
    metrics = {
        "total_point_count": atlas.row_count,
        "nontrivial_point_count": sum(
            1 for row in atlas.rows if row.accepted_context_count >= 2
        ),
        "unsolved_gpd_stat_count": sum(
            1 for row in atlas.rows if row.gpd_stat_status == "unsolved"
        ),
        "sec_insufficient_data_count": sum(
            1 for row in atlas.rows if row.sec_status == "insufficient_data"
        ),
        "rm_not_applicable_count": sum(
            1 for row in atlas.rows if row.rm_status == "not_applicable"
        ),
    }
    for regime, count in sorted(regime_counts.items()):
        metrics[f"regime_count_{regime}"] = count
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[atlas.sweep_id],
        metrics=metrics,
        interpretation=(
            "Search sweep atlas rows preserve explicit solved/unsolved/insufficient_data/not_applicable statuses rather than coercing unsupported metrics to zero."
        ),
        caveats=[
            "RM is diagnostic-only when present.",
            "CCD is marked not_applicable for sweep points that do not provide repeated-read trace structure.",
        ],
        artifact_refs={
            "atlas_csv": output_paths["atlas_csv"],
            "atlas_json": output_paths["atlas_json"],
            "regime_counts": output_paths["regime_counts"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
        },
        metadata={"classification_rule_version": CLASSIFICATION_RULE_VERSION},
    )


def _render_note(
    *,
    sweep: SearchSweep,
    atlas: SearchAtlas,
    regime_counts: dict[str, int],
    summary: dict[str, object],
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Search Sweep Report",
        "",
        "## Sweep ID",
        f"- Sweep ID: `{sweep.sweep_id}`",
        "",
        "## Configs / points covered",
    ]
    for row in atlas.rows:
        lines.append(
            f"- `{row.point_id}`: config=`{row.config_path}`, prep=`{row.preparation_id}`, protocol=`{row.protocol_id}`, seed=`{row.seed}`, regime=`{row.regime_classification}`"
        )
    lines.extend(
        [
            "",
            "## Extraction and inference thresholds",
            f"- extraction: `{sweep.extraction_thresholds.model_dump(mode='json')}`",
            f"- shared-event inference: `{sweep.shared_event_inference_thresholds.model_dump(mode='json')}`",
            f"- classification: `{sweep.classification_thresholds.model_dump(mode='json')}`",
            "",
            "## Regime counts",
        ]
    )
    for regime, count in sorted(regime_counts.items()):
        lines.append(f"- `{regime}`: `{count}`")
    lines.extend(
        [
            "",
            "## Technical interpretation",
            "- This compact atlas preserves per-point provenance and status fields. It does not coerce unsolved, insufficient-data, or not-applicable results into numeric zeros.",
            "",
            "## Notes",
            "- RM is diagnostic-only.",
            "- unsolved / insufficient-data handling is preserved explicitly in atlas row status fields.",
            f"- unsolved / insufficient-data counts: `{summary['status_counts']}`",
            "",
            "## Artifact references",
            f"- Atlas CSV: `{output_paths['atlas_csv']}`",
            f"- Atlas JSON: `{output_paths['atlas_json']}`",
            f"- Regime counts: `{output_paths['regime_counts']}`",
            f"- Search summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _run_point(
    *,
    point: SearchSweepPoint,
    sweep: SearchSweep,
    category: str,
    timestamp: str | None,
    root: Path,
    derived_dir: Path,
) -> SearchAtlasRow:
    config = load_substrate_config(point.config_artifact)
    substrate_artifacts = write_substrate_run(
        config,
        config_path=point.config_artifact,
        preparation_id=point.preparation_id,
        protocol_id=point.protocol_id,
        trajectories=point.trajectories,
        seed=point.seed,
        category=category,
        label=f"{sweep.sweep_id}-{point.point_id}-substrate",
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "run",
            point.config_artifact,
            "--preparation",
            point.preparation_id,
            "--protocol",
            point.protocol_id,
            "--trajectories",
            str(point.trajectories),
            "--seed",
            str(point.seed),
        ],
    )
    discovery_artifacts = write_context_discovery_report(
        run_paths=[root / substrate_artifacts.run_trace_path],
        category=category,
        label=f"{sweep.sweep_id}-{point.point_id}-discover",
        seed=point.seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "discover-contexts",
            substrate_artifacts.run_trace_path,
        ],
        thresholds=sweep.extraction_thresholds,
    )
    family = _load_family(root / discovery_artifacts.family_path)
    notes = list(point.notes)
    run_ids = {
        "substrate_run": substrate_artifacts.run_id,
        "context_discovery": discovery_artifacts.run_id,
    }
    artifact_paths = {
        "raw_run": substrate_artifacts.run_trace_path,
        "family": discovery_artifacts.family_path,
    }

    if family.diagnostics_summary.accepted_context_count < 2:
        notes.append("no_nontrivial_multi_context_structure")
        row = SearchAtlasRow(
            row_format_version="search-atlas-row.v1",
            sweep_id=sweep.sweep_id,
            point_id=point.point_id,
            config_path=point.config_artifact,
            preparation_id=point.preparation_id,
            protocol_id=point.protocol_id,
            trajectories=point.trajectories,
            seed=point.seed,
            raw_run_path=substrate_artifacts.run_trace_path,
            discovered_context_family_path=discovery_artifacts.family_path,
            event_package_path=None,
            accepted_context_count=family.diagnostics_summary.accepted_context_count,
            accepted_shared_event_proposal_count=0,
            exact_structural_status="not_applicable",
            exact_structural_feasible_hard_only=None,
            exact_respecting_tuple_count=None,
            gpd_str=None,
            gpd_stat_status="not_applicable",
            gpd_stat=None,
            gpd_stat_reason=None,
            ccd_status="not_applicable",
            ccd_overall=None,
            sec_status="not_applicable",
            sec_mean=None,
            rm_status="not_applicable",
            rm_overall=None,
            regime_classification="trivial_or_nonrecording",
            run_ids=run_ids,
            artifact_paths=artifact_paths,
            notes=notes,
        )
        return row

    package_artifacts = write_package_build_report(
        family_path=root / discovery_artifacts.family_path,
        run_paths=[root / substrate_artifacts.run_trace_path],
        skeleton_path=(
            None
            if discovery_artifacts.skeleton_path is None
            else root / discovery_artifacts.skeleton_path
        ),
        category=category,
        label=f"{sweep.sweep_id}-{point.point_id}-package",
        seed=point.seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "build-event-package",
            discovery_artifacts.family_path,
            "--raw-run",
            substrate_artifacts.run_trace_path,
        ],
        thresholds=sweep.shared_event_inference_thresholds,
    )
    candidates = _load_candidates(root / package_artifacts.candidates_path)
    run_ids["package_build"] = package_artifacts.run_id
    artifact_paths["shared_event_candidates"] = package_artifacts.candidates_path
    artifact_paths["event_package"] = package_artifacts.event_package_path

    stat_trace = _derive_stat_trace(
        family=family,
        raw_run=substrate_artifacts.run_trace,
        instance_id=package_artifacts.event_package.instance_id,
        instance_artifact=package_artifacts.event_package_path,
        trace_id=f"trace_{sweep.sweep_id}_{point.point_id}_stat",
    )
    stat_trace_path = derived_dir / f"{point.point_id}-stat.json"
    stat_trace_path.write_text(
        json.dumps(stat_trace.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    stat_trace_relpath = repo_relative_path(stat_trace_path, root=root)
    artifact_paths["stat_trace"] = stat_trace_relpath

    structural_artifacts = generate_structural_report(
        package_artifacts.event_package,
        instance_path=package_artifacts.event_package_path,
        category=category,
        label=f"{sweep.sweep_id}-{point.point_id}-structural",
        seed=point.seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "structural",
            "report",
            package_artifacts.event_package_path,
        ],
    )
    statistical_artifacts = write_statistical_summary(
        package_artifacts.event_package,
        [stat_trace],
        instance_path=package_artifacts.event_package_path,
        trace_paths=[stat_trace_relpath],
        category=category,
        label=f"{sweep.sweep_id}-{point.point_id}-statistical",
        seed=point.seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "derived-statistical",
            stat_trace_relpath,
        ],
    )
    run_ids["structural"] = structural_artifacts.run_id
    run_ids["statistical"] = statistical_artifacts.run_id
    artifact_paths["structural_summary"] = structural_artifacts.summary_path
    artifact_paths["statistical_summary"] = statistical_artifacts.summary_path

    sec_status, sec_mean = _sec_summary(candidates)
    row = SearchAtlasRow(
        row_format_version="search-atlas-row.v1",
        sweep_id=sweep.sweep_id,
        point_id=point.point_id,
        config_path=point.config_artifact,
        preparation_id=point.preparation_id,
        protocol_id=point.protocol_id,
        trajectories=point.trajectories,
        seed=point.seed,
        raw_run_path=substrate_artifacts.run_trace_path,
        discovered_context_family_path=discovery_artifacts.family_path,
        event_package_path=package_artifacts.event_package_path,
        accepted_context_count=family.diagnostics_summary.accepted_context_count,
        accepted_shared_event_proposal_count=len(
            package_artifacts.event_package.equality_proposals
        ),
        exact_structural_status=(
            "feasible"
            if structural_artifacts.summary.exact_extendable_hard_only
            else "infeasible"
        ),
        exact_structural_feasible_hard_only=structural_artifacts.summary.exact_extendable_hard_only,
        exact_respecting_tuple_count=structural_artifacts.summary.hard_only_respecting_tuple_count,
        gpd_str=(
            float(structural_artifacts.summary.gpd_str)
            if structural_artifacts.summary.gpd_str is not None
            else None
        ),
        gpd_stat_status=(
            "solved" if statistical_artifacts.result.solved else "unsolved"
        ),
        gpd_stat=statistical_artifacts.result.gpd_stat,
        gpd_stat_reason=statistical_artifacts.result.reason,
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status=sec_status,
        sec_mean=sec_mean,
        rm_status="not_applicable",
        rm_overall=None,
        regime_classification="trivial_or_nonrecording",
        run_ids=run_ids,
        artifact_paths=artifact_paths,
        notes=notes
        + [
            "ccd_not_applicable_without_repeated_read_trace",
            "rm_not_applicable_without_route_observations",
        ],
    )
    return row.model_copy(
        update={
            "regime_classification": _classify_row(
                row=row, thresholds=sweep.classification_thresholds
            )
        }
    )


def run_search_sweep(
    *,
    sweep_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> SearchSweepArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    sweep = load_search_sweep(sweep_path)
    bundle_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or sweep.sweep_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = bundle_dir.parents[2]
    sweep_relpath = repo_relative_path(sweep_path, root=effective_root)
    derived_dir = bundle_dir / "derived"
    derived_dir.mkdir()

    rows = [
        _run_point(
            point=point,
            sweep=sweep,
            category=category,
            timestamp=timestamp,
            root=effective_root,
            derived_dir=derived_dir,
        )
        for point in sweep.points
    ]
    atlas = SearchAtlas(
        atlas_format_version="search-atlas.v1",
        sweep_id=sweep.sweep_id,
        row_count=len(rows),
        rows=rows,
        metadata={
            "classification_rule_version": CLASSIFICATION_RULE_VERSION,
            "sweep_artifact": sweep_relpath,
        },
    )
    regime_counts_counter = Counter(row.regime_classification for row in atlas.rows)
    regime_counts: dict[str, int] = {
        regime: regime_counts_counter.get(regime, 0)
        for regime in [
            "globally_packageable",
            "multi_context_but_extendable",
            "weakly_frustrated",
            "strongly_nonextendable",
            "trivial_or_nonrecording",
        ]
    }
    status_counts = {
        "gpd_stat_unsolved": sum(
            1 for row in atlas.rows if row.gpd_stat_status == "unsolved"
        ),
        "sec_insufficient_data": sum(
            1 for row in atlas.rows if row.sec_status == "insufficient_data"
        ),
        "rm_not_applicable": sum(
            1 for row in atlas.rows if row.rm_status == "not_applicable"
        ),
        "ccd_not_applicable": sum(
            1 for row in atlas.rows if row.ccd_status == "not_applicable"
        ),
    }

    atlas_csv_path = bundle_dir / "atlas.csv"
    atlas_json_path = bundle_dir / "atlas.json"
    regime_counts_path = bundle_dir / "regime-counts.json"
    summary_path = bundle_dir / "search-summary.json"
    note_path = bundle_dir / "search-note.md"
    result_note_path = bundle_dir / "result-note.json"
    manifest_path = bundle_dir / "run-manifest.json"
    output_paths = {
        "atlas_csv": repo_relative_path(atlas_csv_path, root=effective_root),
        "atlas_json": repo_relative_path(atlas_json_path, root=effective_root),
        "regime_counts": repo_relative_path(regime_counts_path, root=effective_root),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    csv_rows = [_row_to_csv_record(row) for row in atlas.rows]
    fieldnames = list(csv_rows[0]) if csv_rows else []
    with atlas_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in csv_rows:
            writer.writerow(record)

    atlas_json_path.write_text(
        json.dumps(atlas.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    regime_counts_path.write_text(
        json.dumps(regime_counts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "sweep_id": sweep.sweep_id,
        "total_point_count": atlas.row_count,
        "regime_counts": regime_counts,
        "extraction_thresholds": sweep.extraction_thresholds.model_dump(mode="json"),
        "shared_event_inference_thresholds": sweep.shared_event_inference_thresholds.model_dump(
            mode="json"
        ),
        "classification_thresholds": sweep.classification_thresholds.model_dump(
            mode="json"
        ),
        "classification_rule_version": CLASSIFICATION_RULE_VERSION,
        "atlas_csv_path": output_paths["atlas_csv"],
        "atlas_json_path": output_paths["atlas_json"],
        "notable_unsolved_or_insufficient_data_counts": status_counts,
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    note_path.write_text(
        _render_note(
            sweep=sweep,
            atlas=atlas,
            regime_counts=regime_counts,
            summary={"status_counts": status_counts},
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        atlas=atlas,
        regime_counts=regime_counts,
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
            "search",
            "run-sweep",
            sweep_relpath,
        ],
        seed=seed,
        input_artifacts={"sweep": sweep_relpath},
        output_artifacts={
            "atlas_csv": output_paths["atlas_csv"],
            "atlas_json": output_paths["atlas_json"],
            "regime_counts": output_paths["regime_counts"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "search_sweep",
            "sweep_id": sweep.sweep_id,
            "point_count": atlas.row_count,
            "classification_rule_version": CLASSIFICATION_RULE_VERSION,
        },
    )
    write_run_manifest(manifest, run_dir=bundle_dir)
    return SearchSweepArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(bundle_dir, root=effective_root),
        atlas_csv_path=output_paths["atlas_csv"],
        atlas_json_path=output_paths["atlas_json"],
        regime_counts_path=output_paths["regime_counts"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        atlas=atlas,
        regime_counts=regime_counts,
    )
