from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import sys

from ..discovery.models import (
    DiscoveredContextFamily,
    PicaContextDiscoveryConfig,
    SharedEventCandidates,
)
from ..discovery.shared_event_inference import _project_pica_row_label
from ..pica_bridge.ingest import PicaBundleResolved, load_pica_export_bundle
from ..pica_bridge.models import PicaPilotCampaign
from ..pica_bridge.pilot import PicaPilotArtifacts, run_pica_pilot_campaign
from ..provenance.audit import write_provenance_audit_report
from ..reporting.package_build_report import write_package_build_report
from ..reporting.pica_context_discovery_report import (
    write_pica_context_discovery_report,
)
from ..reporting.statistical_report import write_statistical_summary
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.observation_trace import Observation, ObservationTrace
from ..schemas.result_note import ResultNote
from ..solvers.structural_exact import solve_exact_structural_feasibility
from ..validation import load_model
from .models import (
    PicaTargetedObstructionSearch,
    PicaTargetedSearchPoint,
    PicaTargetedSearchRow,
    PicaTargetedSearchTable,
    TargetedCandidateLabel,
    TargetedSearchEvaluation,
)
from .targeted_nonextendability import (
    _baseline_deficit_evaluation,
    _candidate_deficit_evaluation,
    _sec_summary,
)


PICA_TARGETED_CLASSIFIER_VERSION = "pica-targeted-obstruction-classifier.v1"
PICA_TARGETED_ADEQUACY_VERSION = "pica-targeted-adequacy-floor.v1"


@dataclass(slots=True)
class PicaTargetedSearchArtifacts:
    run_id: str
    run_dir: str
    table_csv_path: str
    table_json_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    table: PicaTargetedSearchTable
    classification_counts: dict[str, int]
    outcome_path: str
    outcome_kind: str


def load_pica_targeted_obstruction_search(
    path: str | Path,
) -> PicaTargetedObstructionSearch:
    model = load_model(path, kind="pica-targeted-obstruction-search")
    assert isinstance(model, PicaTargetedObstructionSearch)
    return model


def _load_family(path: str | Path) -> DiscoveredContextFamily:
    model = load_model(path, kind="discovered-context-family")
    assert isinstance(model, DiscoveredContextFamily)
    return model


def _load_candidates(path: str | Path) -> SharedEventCandidates:
    model = load_model(path, kind="shared-event-candidates")
    assert isinstance(model, SharedEventCandidates)
    return model


def _load_pilot_config(path: str | Path) -> PicaPilotCampaign:
    model = load_model(path, kind="pica-pilot-campaign")
    assert isinstance(model, PicaPilotCampaign)
    return model


def _load_pica_discovery_config(path: str | Path) -> PicaContextDiscoveryConfig:
    model = load_model(path, kind="pica-context-discovery")
    assert isinstance(model, PicaContextDiscoveryConfig)
    return model


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _row_to_csv_record(row: PicaTargetedSearchRow) -> dict[str, object]:
    return {
        "point_id": row.point_id,
        "source_pica_campaign_config_path": row.source_pica_campaign_config_path,
        "discovery_config_path": row.discovery_config_path,
        "preparation_id": row.preparation_id,
        "protocol_id": row.protocol_id,
        "trajectories": row.trajectories,
        "seed_list": "|".join(str(seed) for seed in row.seed_list),
        "produced_export_bundle_path": row.produced_export_bundle_path,
        "discovered_context_family_path": row.discovered_context_family_path,
        "event_package_path": row.event_package_path,
        "provenance_classification": row.provenance_classification,
        "accepted_context_count": row.accepted_context_count,
        "accepted_singleton_event_count": row.accepted_singleton_event_count,
        "accepted_proper_coarse_event_count": row.accepted_proper_coarse_event_count,
        "accepted_shared_event_proposal_count": row.accepted_shared_event_proposal_count,
        "accepted_proper_coarse_structural_proposal_count": row.accepted_proper_coarse_structural_proposal_count,
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
        "candidate_classification": row.candidate_classification,
        "wrapper_run_ids": "|".join(
            row.run_ids.get(key, "")
            for key in sorted(
                run_id for run_id in row.run_ids if run_id.startswith("pica_wrapper_")
            )
        ),
        "context_discovery_run_id": row.run_ids.get("context_discovery"),
        "package_build_run_id": row.run_ids.get("package_build"),
        "provenance_audit_run_id": row.run_ids.get("provenance_audit"),
        "baseline_statistical_run_id": row.run_ids.get("baseline_statistical"),
        "candidate_statistical_run_id": row.run_ids.get("candidate_statistical"),
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def _pilot_config_for_seed(
    *,
    base_config: PicaPilotCampaign,
    base_config_path: str,
    seed: int,
) -> dict[str, object]:
    payload = base_config.model_dump(mode="json")
    run_settings = dict(payload["run_settings"])
    run_settings["seed"] = seed
    payload["run_settings"] = run_settings
    payload["source_config_path"] = base_config_path
    return payload


def _merge_pilot_outputs(
    *,
    point: PicaTargetedSearchPoint,
    preparation_id: str,
    protocol_id: str,
    pilot_outputs: list[PicaPilotArtifacts],
    output_dir: Path,
    root: Path,
) -> str:
    merged_dir = output_dir / point.point_id
    merged_dir.mkdir(parents=True, exist_ok=True)

    campaigns = [
        json.loads((root / artifact.campaign_export_path).read_text(encoding="utf-8"))
        for artifact in pilot_outputs
    ]
    runs = [
        json.loads((root / artifact.run_ledger_path).read_text(encoding="utf-8"))
        for artifact in pilot_outputs
    ]
    catalogs = [
        json.loads((root / artifact.closure_catalog_path).read_text(encoding="utf-8"))
        for artifact in pilot_outputs
    ]
    ledgers = [
        json.loads((root / artifact.observable_ledger_path).read_text(encoding="utf-8"))
        for artifact in pilot_outputs
    ]
    commutators = [
        json.loads(
            (root / artifact.commutator_catalog_path).read_text(encoding="utf-8")
        )
        if artifact.commutator_catalog_path is not None
        else None
        for artifact in pilot_outputs
    ]
    packaging_operator_catalogs = [
        json.loads(
            (root / artifact.packaging_operator_catalog_path).read_text(
                encoding="utf-8"
            )
        )
        if artifact.packaging_operator_catalog_path is not None
        else None
        for artifact in pilot_outputs
    ]
    packaging_selection_ledgers = [
        json.loads(
            (root / artifact.packaging_selection_ledger_path).read_text(
                encoding="utf-8"
            )
        )
        if artifact.packaging_selection_ledger_path is not None
        else None
        for artifact in pilot_outputs
    ]

    merged_campaign = dict(campaigns[0])
    merged_campaign["campaign_id"] = f"{point.point_id}_campaign"
    merged_campaign["campaign_label"] = point.point_id
    merged_campaign["point_inventory"] = []
    merged_campaign["run_inventory"] = []

    campaign_path = merged_dir / "pica-campaign-export.json"

    for index, (campaign, run, catalog, ledger, seed) in enumerate(
        zip(campaigns, runs, catalogs, ledgers, point.seed_list, strict=True)
    ):
        point_id = f"{point.point_id}_seed{seed}"
        point_record = dict(campaign["point_inventory"][0])
        point_record["point_id"] = point_id
        point_record["preparation_id"] = preparation_id
        point_record["protocol_id"] = protocol_id
        point_record["run_id"] = run["run_id"]
        point_record["seed"] = seed
        merged_campaign["point_inventory"].append(point_record)

        run_path = merged_dir / f"pica-run-ledger-seed{index}.json"
        catalog_path = merged_dir / f"pica-closure-catalog-seed{index}.json"
        ledger_path = merged_dir / f"pica-observable-ledger-seed{index}.json"
        commutator_path = merged_dir / f"pica-commutator-catalog-seed{index}.json"
        packaging_operator_catalog_path = (
            merged_dir / f"pica-packaging-operator-catalog-seed{index}.json"
        )
        packaging_selection_ledger_path = (
            merged_dir / f"pica-packaging-selection-ledger-seed{index}.json"
        )

        run_inventory = {
            "run_id": run["run_id"],
            "point_id": point_id,
            "run_ledger_path": repo_relative_path(run_path, root=root),
            "closure_catalog_path": repo_relative_path(catalog_path, root=root),
            "observable_ledger_path": repo_relative_path(ledger_path, root=root),
        }
        if commutators[index] is not None:
            run_inventory["commutator_catalog_path"] = repo_relative_path(
                commutator_path,
                root=root,
            )
        if packaging_operator_catalogs[index] is not None:
            run_inventory["packaging_operator_catalog_path"] = repo_relative_path(
                packaging_operator_catalog_path,
                root=root,
            )
        if packaging_selection_ledgers[index] is not None:
            run_inventory["packaging_selection_ledger_path"] = repo_relative_path(
                packaging_selection_ledger_path,
                root=root,
            )
        merged_campaign["run_inventory"].append(run_inventory)

        run["campaign_id"] = merged_campaign["campaign_id"]
        run["point_id"] = point_id
        run["preparation_id"] = preparation_id
        run["protocol_id"] = protocol_id
        run["closure_catalog_path"] = repo_relative_path(catalog_path, root=root)
        run["observable_ledger_path"] = repo_relative_path(ledger_path, root=root)
        if commutators[index] is not None:
            run["commutator_catalog_id"] = commutators[index]["commutator_catalog_id"]
            run["commutator_catalog_path"] = repo_relative_path(
                commutator_path,
                root=root,
            )
        if packaging_operator_catalogs[index] is not None:
            run["packaging_operator_catalog_id"] = packaging_operator_catalogs[index][
                "packaging_operator_catalog_id"
            ]
            run["packaging_operator_catalog_path"] = repo_relative_path(
                packaging_operator_catalog_path,
                root=root,
            )
        if packaging_selection_ledgers[index] is not None:
            run["packaging_selection_ledger_id"] = packaging_selection_ledgers[index][
                "packaging_selection_ledger_id"
            ]
            run["packaging_selection_ledger_path"] = repo_relative_path(
                packaging_selection_ledger_path,
                root=root,
            )

        catalog["campaign_id"] = merged_campaign["campaign_id"]
        catalog["point_id"] = point_id

        ledger["campaign_id"] = merged_campaign["campaign_id"]
        ledger["point_id"] = point_id
        for row in ledger["rows"]:
            row["preparation_id"] = preparation_id
            row["protocol_id"] = protocol_id
        if commutators[index] is not None:
            commutators[index]["campaign_id"] = merged_campaign["campaign_id"]
            commutators[index]["point_id"] = point_id
        if packaging_operator_catalogs[index] is not None:
            packaging_operator_catalogs[index]["campaign_id"] = merged_campaign[
                "campaign_id"
            ]
            packaging_operator_catalogs[index]["point_id"] = point_id
        if packaging_selection_ledgers[index] is not None:
            packaging_selection_ledgers[index]["campaign_id"] = merged_campaign[
                "campaign_id"
            ]
            packaging_selection_ledgers[index]["point_id"] = point_id

        _write_json(run_path, run)
        _write_json(catalog_path, catalog)
        _write_json(ledger_path, ledger)
        if commutators[index] is not None:
            _write_json(commutator_path, commutators[index])
        if packaging_operator_catalogs[index] is not None:
            _write_json(
                packaging_operator_catalog_path,
                packaging_operator_catalogs[index],
            )
        if packaging_selection_ledgers[index] is not None:
            _write_json(
                packaging_selection_ledger_path,
                packaging_selection_ledgers[index],
            )

    _write_json(campaign_path, merged_campaign)

    bundle = {
        "schema_version": "pica-export-bundle.v1",
        "export_bundle_id": f"{point.point_id}_bundle",
        "producer": {
            "name": "pica",
            "version": "targeted-search-merge",
            "build_label": "cargo_runner_release",
        },
        "export_timestamp": "2026-03-27T00:00:00Z",
        "path_policy": "repo_relative",
        "campaign_exports": [
            {
                "campaign_id": merged_campaign["campaign_id"],
                "artifact_path": repo_relative_path(campaign_path, root=root),
            }
        ],
        "run_ledgers": [],
        "closure_catalogs": [],
        "observable_ledgers": [],
        "commutator_catalogs": [],
        "packaging_operator_catalogs": [],
        "packaging_selection_ledgers": [],
        "notes": [
            "Merged multiseed PICA export bundle for targeted obstruction search."
        ],
        "flags": ["adapter_export", "merged_multiseed"],
    }

    for index, (run, catalog, ledger) in enumerate(
        zip(runs, catalogs, ledgers, strict=True)
    ):
        bundle["run_ledgers"].append(
            {
                "run_id": run["run_id"],
                "campaign_id": merged_campaign["campaign_id"],
                "artifact_path": repo_relative_path(
                    merged_dir / f"pica-run-ledger-seed{index}.json",
                    root=root,
                ),
            }
        )
        bundle["closure_catalogs"].append(
            {
                "closure_catalog_id": catalog["closure_catalog_id"],
                "run_id": run["run_id"],
                "artifact_path": repo_relative_path(
                    merged_dir / f"pica-closure-catalog-seed{index}.json",
                    root=root,
                ),
            }
        )
        bundle["observable_ledgers"].append(
            {
                "observable_ledger_id": ledger["observable_ledger_id"],
                "run_id": run["run_id"],
                "artifact_path": repo_relative_path(
                    merged_dir / f"pica-observable-ledger-seed{index}.json",
                    root=root,
                ),
            }
        )
        commutator = commutators[index]
        if commutator is not None:
            bundle["commutator_catalogs"].append(
                {
                    "commutator_catalog_id": commutator["commutator_catalog_id"],
                    "run_id": run["run_id"],
                    "artifact_path": repo_relative_path(
                        merged_dir / f"pica-commutator-catalog-seed{index}.json",
                        root=root,
                    ),
                }
            )
        packaging_operator_catalog = packaging_operator_catalogs[index]
        if packaging_operator_catalog is not None:
            bundle["packaging_operator_catalogs"].append(
                {
                    "packaging_operator_catalog_id": packaging_operator_catalog[
                        "packaging_operator_catalog_id"
                    ],
                    "run_id": run["run_id"],
                    "artifact_path": repo_relative_path(
                        merged_dir
                        / f"pica-packaging-operator-catalog-seed{index}.json",
                        root=root,
                    ),
                }
            )
        packaging_selection_ledger = packaging_selection_ledgers[index]
        if packaging_selection_ledger is not None:
            bundle["packaging_selection_ledgers"].append(
                {
                    "packaging_selection_ledger_id": packaging_selection_ledger[
                        "packaging_selection_ledger_id"
                    ],
                    "run_id": run["run_id"],
                    "artifact_path": repo_relative_path(
                        merged_dir
                        / f"pica-packaging-selection-ledger-seed{index}.json",
                        root=root,
                    ),
                }
            )

    bundle_path = merged_dir / "pica-export-bundle.json"
    _write_json(bundle_path, bundle)
    return repo_relative_path(bundle_path, root=root)


def _derive_pica_stat_trace(
    *,
    family: DiscoveredContextFamily,
    resolved: PicaBundleResolved,
    instance_id: str,
    instance_artifact: str,
    trace_id: str,
) -> ObservationTrace:
    observations: list[Observation] = []
    ledgers_by_run = resolved.observable_ledgers_by_run()
    for context in family.accepted_contexts:
        source_metadata = context.source_metadata
        label_to_outcome = {
            outcome.observation_label: outcome.outcome_id
            for outcome in context.atomic_outcomes
        }
        counts = Counter()
        run_ids = (
            list(source_metadata.run_ids)
            if source_metadata is not None and source_metadata.run_ids
            else sorted(ledgers_by_run)
        )
        for run_id in run_ids:
            ledger = ledgers_by_run.get(run_id)
            if ledger is None:
                continue
            for row in ledger.rows:
                if (
                    row.preparation_id != context.candidate_key.preparation_id
                    or row.protocol_id != context.candidate_key.protocol_id
                    or row.level_id != context.candidate_key.level_id
                    or row.resolution_id != context.candidate_key.resolution_id
                    or row.closure_id != context.candidate_key.closure_id
                    or row.lens_id != context.candidate_key.lens_id
                    or row.protocol_step_id != context.candidate_key.protocol_step_id
                ):
                    continue
                if source_metadata is None:
                    projected = row.observation_label
                else:
                    projected = _project_pica_row_label(row, source_metadata)
                if projected is None:
                    continue
                outcome_id = label_to_outcome.get(projected)
                if outcome_id is not None:
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
            "derived_from": "pica_export_bundle",
            "derivation_kind": "pica_targeted_obstruction_stat_trace",
        },
    )


def _point_has_dual_mode_difference(row: PicaTargetedSearchRow) -> bool:
    baseline = row.baseline_hard_only
    candidate = row.all_accepted_proposals
    if baseline.exact_feasible != candidate.exact_feasible:
        return True
    if baseline.exact_respecting_tuple_count != candidate.exact_respecting_tuple_count:
        return True
    if baseline.gpd_str != candidate.gpd_str:
        return True
    if baseline.gpd_stat != candidate.gpd_stat:
        return True
    return False


def _candidate_classification(
    *,
    row: PicaTargetedSearchRow,
    search: PicaTargetedObstructionSearch,
    blocking_classification: str | None,
) -> TargetedCandidateLabel:
    if row.event_package_path is None or row.accepted_context_count < 2:
        return "trivial_or_nonrecording"

    if row.all_accepted_proposals.gpd_str_status != "solved":
        return "inconclusive"

    provenance_ok = row.provenance_classification == "admissible"
    some_provenance = row.provenance_classification in {
        "admissible",
        "partially_supported",
    }
    candidate_exact_fails = row.all_accepted_proposals.exact_feasible is False
    positive_candidate_deficit = (
        row.all_accepted_proposals.gpd_str is not None
        and row.all_accepted_proposals.gpd_str
        > search.candidate_classification_thresholds.strong_nonextendable_min_gpd_str
    )
    strong_block = (
        row.all_accepted_proposals.exact_respecting_tuple_count == 0
        or blocking_classification == "no_respecting_tuples"
    )

    if (
        provenance_ok
        and row.accepted_proper_coarse_structural_proposal_count
        >= search.candidate_classification_thresholds.min_accepted_coarse_proposal_count
        and candidate_exact_fails
        and positive_candidate_deficit
        and strong_block
    ):
        return "strongly_nonextendable_candidate"

    if (
        provenance_ok
        and row.all_accepted_proposals.exact_feasible is True
        and row.all_accepted_proposals.gpd_str == 0
    ):
        return "extendable_candidate"

    if some_provenance and (
        candidate_exact_fails
        or (
            row.all_accepted_proposals.gpd_str is not None
            and row.all_accepted_proposals.gpd_str > 0
        )
        or (
            row.all_accepted_proposals.gpd_stat_status == "solved"
            and row.all_accepted_proposals.gpd_stat is not None
            and row.all_accepted_proposals.gpd_stat
            > search.candidate_classification_thresholds.near_zero_gpd_stat
        )
    ):
        return "weakly_frustrated_candidate"

    return "inconclusive"


def _evaluate_adequacy(
    *, rows: list[PicaTargetedSearchRow], search: PicaTargetedObstructionSearch
) -> dict[str, object]:
    counts = {
        "total_point_count": len(rows),
        "admissible_built_package_count": sum(
            1
            for row in rows
            if row.event_package_path is not None
            and row.provenance_classification == "admissible"
        ),
        "points_with_proper_coarse_events": sum(
            1 for row in rows if row.accepted_proper_coarse_event_count > 0
        ),
        "points_with_proper_coarse_structural_proposals": sum(
            1
            for row in rows
            if row.accepted_proper_coarse_structural_proposal_count > 0
        ),
        "points_with_dual_mode_difference": sum(
            1 for row in rows if _point_has_dual_mode_difference(row)
        ),
    }
    floor = search.adequacy_floor
    checks = {
        "total_point_count": counts["total_point_count"] >= floor.min_total_point_count,
        "admissible_built_package_count": counts["admissible_built_package_count"]
        >= floor.min_admissible_built_package_count,
        "points_with_proper_coarse_events": counts["points_with_proper_coarse_events"]
        >= floor.min_points_with_proper_coarse_events,
        "points_with_proper_coarse_structural_proposals": counts[
            "points_with_proper_coarse_structural_proposals"
        ]
        >= floor.min_points_with_proper_coarse_structural_proposals,
        "points_with_dual_mode_difference": counts["points_with_dual_mode_difference"]
        >= floor.min_points_with_dual_mode_difference,
    }
    return {
        "adequate": all(checks.values()),
        "counts": counts,
        "checks": checks,
        "thresholds": floor.model_dump(mode="json"),
    }


def _select_best_candidate(
    rows: list[PicaTargetedSearchRow],
) -> PicaTargetedSearchRow | None:
    candidates = [
        row
        for row in rows
        if row.candidate_classification == "strongly_nonextendable_candidate"
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (
            -(row.all_accepted_proposals.gpd_str or 0.0),
            row.all_accepted_proposals.exact_respecting_tuple_count
            if row.all_accepted_proposals.exact_respecting_tuple_count is not None
            else 10**9,
            row.point_id,
        ),
    )[0]


def _render_note(
    *,
    search: PicaTargetedObstructionSearch,
    table: PicaTargetedSearchTable,
    classification_counts: dict[str, int],
    adequacy: dict[str, object],
    best_candidate_id: str | None,
    outcome_kind: str,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# PICA Targeted Obstruction Search",
        "",
        f"- Search ID: `{search.search_id}`",
        "",
        "## PICA family covered",
    ]
    for row in table.rows:
        lines.append(
            f"- `{row.point_id}`: pilot_config=`{row.source_pica_campaign_config_path}`, bundle=`{row.produced_export_bundle_path}`, provenance=`{row.provenance_classification}`, coarse_events=`{row.accepted_proper_coarse_event_count}`, coarse_proposals=`{row.accepted_proper_coarse_structural_proposal_count}`, class=`{row.candidate_classification}`"
        )
    lines.extend(
        [
            "",
            "## Threshold configuration",
            f"- Event algebra: `{search.event_generation_thresholds.model_dump(mode='json')}`",
            f"- Structural inference: `{search.shared_event_inference_thresholds.model_dump(mode='json')}`",
            f"- Candidate classification: `{search.candidate_classification_thresholds.model_dump(mode='json')}`",
            f"- Adequacy floor: `{search.adequacy_floor.model_dump(mode='json')}`",
            "",
            "## Evaluation modes",
            "- Baseline hard-only mode evaluates exact feasibility and deficits using only hard constraints.",
            "- All-accepted-proposals mode evaluates exact feasibility and deficits using all accepted structural proposals.",
            "- Strong endogenous obstruction classification is allowed only in the all-accepted-proposals mode.",
            "",
            "## Candidate classification counts",
        ]
    )
    for label, count in sorted(classification_counts.items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(
        [
            "",
            "## Adequacy floor result",
            f"- Adequate: `{adequacy['adequate']}`",
            f"- Counts: `{adequacy['counts']}`",
            f"- Checks: `{adequacy['checks']}`",
            "",
            "## Outcome",
            f"- Outcome kind: `{outcome_kind}`",
            f"- Best candidate ID: `{best_candidate_id}`",
            "",
            "## Notes",
            "- RM is diagnostic-only.",
            "- unsolved / insufficient_data / not_applicable statuses are preserved explicitly.",
            "- A meaningful negative result is emitted only when the adequacy floor is satisfied.",
            "",
            "## Artifact references",
            f"- Search CSV: `{output_paths['table_csv']}`",
            f"- Search JSON: `{output_paths['table_json']}`",
            f"- Search summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
            f"- Outcome artifact: `{output_paths['outcome']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    table: PicaTargetedSearchTable,
    classification_counts: dict[str, int],
    adequacy: dict[str, object],
    outcome_kind: str,
    best_candidate_id: str | None,
    output_paths: dict[str, str],
) -> ResultNote:
    metrics = {
        "point_count": table.row_count,
        "adequacy_met": adequacy["adequate"],
        "outcome_kind": outcome_kind,
        **adequacy["counts"],
    }
    for label, count in sorted(classification_counts.items()):
        metrics[f"classification_count_{label}"] = count
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[table.search_id],
        metrics=metrics,
        interpretation=(
            "The bounded PICA-targeted campaign preserves baseline hard-only versus all-accepted-proposals evaluation explicitly and only permits a negative obstruction conclusion when the adequacy floor is met."
        ),
        caveats=[
            "A strong discovered candidate must include at least one accepted proper-coarse structural proposal.",
            "When the adequacy floor fails, the honest campaign outcome is inadequate rather than a negative obstruction result.",
        ],
        artifact_refs=output_paths,
        metadata={
            "classifier_version": PICA_TARGETED_CLASSIFIER_VERSION,
            "adequacy_version": PICA_TARGETED_ADEQUACY_VERSION,
            "best_candidate_id": best_candidate_id,
        },
    )


def _run_point(
    *,
    point: PicaTargetedSearchPoint,
    search: PicaTargetedObstructionSearch,
    category: str,
    timestamp: str | None,
    root: Path,
    derived_dir: Path,
) -> PicaTargetedSearchRow:
    pilot_config = _load_pilot_config(root / point.pilot_config_artifact)
    discovery_config = _load_pica_discovery_config(
        root / point.discovery_config_artifact
    )

    pilot_outputs: list[PicaPilotArtifacts] = []
    run_ids: dict[str, str] = {}
    notes = list(point.notes)

    point_tmp_dir = derived_dir / point.point_id / "configs"
    point_tmp_dir.mkdir(parents=True, exist_ok=True)
    for index, seed in enumerate(point.seed_list):
        seeded_payload = _pilot_config_for_seed(
            base_config=pilot_config,
            base_config_path=point.pilot_config_artifact,
            seed=seed,
        )
        seeded_config_path = point_tmp_dir / f"pilot-seed-{seed}.json"
        _write_json(seeded_config_path, seeded_payload)
        pilot_artifacts = run_pica_pilot_campaign(
            config_path=seeded_config_path,
            category=category,
            label=f"{search.search_id}-{point.point_id}-pica-seed{seed}",
            timestamp=timestamp,
            root=root,
            command=[
                sys.executable,
                "-m",
                "sixbirds_event",
                "pica",
                "run-pilot",
                point.pilot_config_artifact,
            ],
        )
        pilot_outputs.append(pilot_artifacts)
        run_ids[f"pica_wrapper_{index}"] = pilot_artifacts.run_id

    merged_bundle_relpath = _merge_pilot_outputs(
        point=point,
        preparation_id=pilot_config.preparation_id,
        protocol_id=pilot_config.protocol_id,
        pilot_outputs=pilot_outputs,
        output_dir=derived_dir / "bundles",
        root=root,
    )
    merged_bundle_path = root / merged_bundle_relpath

    active_discovery_config = discovery_config.model_copy(
        update={"bundle_artifact": merged_bundle_relpath}
    )
    discovery_artifacts = write_pica_context_discovery_report(
        bundle_path=merged_bundle_path,
        category=category,
        label=f"{search.search_id}-{point.point_id}-discover",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "pica",
            "discover-contexts",
            merged_bundle_relpath,
            "--config",
            point.discovery_config_artifact,
        ],
        config=active_discovery_config,
    )
    family = _load_family(root / discovery_artifacts.family_path)
    run_ids["context_discovery"] = discovery_artifacts.run_id

    if family.diagnostics_summary.accepted_context_count < 2:
        notes.append("no_nontrivial_multi_context_structure")
        return PicaTargetedSearchRow(
            row_format_version="pica-targeted-search-row.v1",
            search_id=search.search_id,
            point_id=point.point_id,
            source_pica_campaign_config_path=point.pilot_config_artifact,
            discovery_config_path=point.discovery_config_artifact,
            preparation_id=pilot_config.preparation_id,
            protocol_id=pilot_config.protocol_id,
            trajectories=point.trajectories,
            seed_list=point.seed_list,
            produced_export_bundle_path=merged_bundle_relpath,
            discovered_context_family_path=discovery_artifacts.family_path,
            event_package_path=None,
            provenance_classification=None,
            accepted_context_count=family.diagnostics_summary.accepted_context_count,
            accepted_singleton_event_count=0,
            accepted_proper_coarse_event_count=0,
            accepted_shared_event_proposal_count=0,
            accepted_proper_coarse_structural_proposal_count=0,
            baseline_hard_only=TargetedSearchEvaluation(
                exact_structural_status="not_applicable",
                exact_feasible=None,
                exact_respecting_tuple_count=None,
                gpd_str_status="not_applicable",
                gpd_str=None,
                gpd_str_reason=None,
                gpd_stat_status="not_applicable",
                gpd_stat=None,
                gpd_stat_reason=None,
            ),
            all_accepted_proposals=TargetedSearchEvaluation(
                exact_structural_status="not_applicable",
                exact_feasible=None,
                exact_respecting_tuple_count=None,
                gpd_str_status="not_applicable",
                gpd_str=None,
                gpd_str_reason=None,
                gpd_stat_status="not_applicable",
                gpd_stat=None,
                gpd_stat_reason=None,
            ),
            ccd_status="not_applicable",
            ccd_overall=None,
            sec_status="not_applicable",
            sec_mean=None,
            rm_status="not_applicable",
            rm_overall=None,
            candidate_classification="trivial_or_nonrecording",
            run_ids=run_ids,
            artifact_paths={
                "export_bundle": merged_bundle_relpath,
                "discovered_context_family": discovery_artifacts.family_path,
            },
            notes=notes,
        )

    package_artifacts = write_package_build_report(
        family_path=root / discovery_artifacts.family_path,
        run_paths=[],
        pica_bundle_path=merged_bundle_relpath,
        skeleton_path=(
            None
            if discovery_artifacts.skeleton_path is None
            else root / discovery_artifacts.skeleton_path
        ),
        category=category,
        label=f"{search.search_id}-{point.point_id}-package",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "build-event-package",
            discovery_artifacts.family_path,
            "--pica-bundle",
            merged_bundle_relpath,
            "--event-algebra-mode",
            search.event_generation_thresholds.event_algebra_mode or "auto",
            "--inference-mode",
            search.shared_event_inference_thresholds.inference_mode,
        ],
        thresholds=search.shared_event_inference_thresholds,
        event_thresholds=search.event_generation_thresholds,
    )
    candidates = _load_candidates(root / package_artifacts.candidates_path)
    run_ids["package_build"] = package_artifacts.run_id

    provenance_artifacts = write_provenance_audit_report(
        package_path=root / package_artifacts.event_package_path,
        provenance_path=root / package_artifacts.provenance_path,
        category=category,
        label=f"{search.search_id}-{point.point_id}-provenance",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "provenance",
            package_artifacts.event_package_path,
            "--provenance",
            package_artifacts.provenance_path,
        ],
    )
    run_ids["provenance_audit"] = provenance_artifacts.run_id

    resolved_bundle = load_pica_export_bundle(merged_bundle_path, repo_root=root)
    stat_trace = _derive_pica_stat_trace(
        family=family,
        resolved=resolved_bundle,
        instance_id=package_artifacts.event_package.instance_id,
        instance_artifact=package_artifacts.event_package_path,
        trace_id=f"trace_{search.search_id}_{point.point_id}_stat",
    )
    stat_trace_path = derived_dir / f"{point.point_id}-stat.json"
    _write_json(stat_trace_path, stat_trace.model_dump(mode="json"))
    stat_trace_relpath = repo_relative_path(stat_trace_path, root=root)

    hard_only_exact = solve_exact_structural_feasibility(
        package_artifacts.event_package
    )
    all_proposals_exact = solve_exact_structural_feasibility(
        package_artifacts.event_package,
        include_soft=True,
    )

    baseline_statistical = write_statistical_summary(
        package_artifacts.event_package,
        [stat_trace],
        instance_path=package_artifacts.event_package_path,
        trace_paths=[stat_trace_relpath],
        category=category,
        label=f"{search.search_id}-{point.point_id}-baseline-statistical",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        include_soft=False,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "pica-targeted-baseline-statistical",
            stat_trace_relpath,
        ],
    )
    candidate_statistical = write_statistical_summary(
        package_artifacts.event_package,
        [stat_trace],
        instance_path=package_artifacts.event_package_path,
        trace_paths=[stat_trace_relpath],
        category=category,
        label=f"{search.search_id}-{point.point_id}-candidate-statistical",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        include_soft=True,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "pica-targeted-candidate-statistical",
            stat_trace_relpath,
        ],
    )
    run_ids["baseline_statistical"] = baseline_statistical.run_id
    run_ids["candidate_statistical"] = candidate_statistical.run_id

    baseline_gpd_str_status, baseline_gpd_str, baseline_gpd_str_reason = (
        _baseline_deficit_evaluation(package_artifacts.event_package)
    )
    candidate_gpd_str_status, candidate_gpd_str, candidate_gpd_str_reason = (
        _candidate_deficit_evaluation(package_artifacts.event_package)
    )
    baseline_hard_only = TargetedSearchEvaluation(
        exact_structural_status="feasible"
        if hard_only_exact.feasible
        else "infeasible",
        exact_feasible=hard_only_exact.feasible,
        exact_respecting_tuple_count=hard_only_exact.respecting_tuple_count,
        gpd_str_status=baseline_gpd_str_status,
        gpd_str=baseline_gpd_str,
        gpd_str_reason=baseline_gpd_str_reason,
        gpd_stat_status="solved" if baseline_statistical.result.solved else "unsolved",
        gpd_stat=baseline_statistical.result.gpd_stat,
        gpd_stat_reason=baseline_statistical.result.reason,
    )
    all_accepted_proposals = TargetedSearchEvaluation(
        exact_structural_status=(
            "feasible" if all_proposals_exact.feasible else "infeasible"
        ),
        exact_feasible=all_proposals_exact.feasible,
        exact_respecting_tuple_count=all_proposals_exact.respecting_tuple_count,
        gpd_str_status=candidate_gpd_str_status,
        gpd_str=candidate_gpd_str,
        gpd_str_reason=candidate_gpd_str_reason,
        gpd_stat_status="solved" if candidate_statistical.result.solved else "unsolved",
        gpd_stat=candidate_statistical.result.gpd_stat,
        gpd_stat_reason=candidate_statistical.result.reason,
    )
    sec_status, sec_mean = _sec_summary(candidates)
    accepted_proper_coarse_structural_proposal_count = sum(
        1
        for row in candidates.candidate_rows
        if row.accepted and (row.left_is_proper_coarse or row.right_is_proper_coarse)
    )

    row = PicaTargetedSearchRow(
        row_format_version="pica-targeted-search-row.v1",
        search_id=search.search_id,
        point_id=point.point_id,
        source_pica_campaign_config_path=point.pilot_config_artifact,
        discovery_config_path=point.discovery_config_artifact,
        preparation_id=pilot_config.preparation_id,
        protocol_id=pilot_config.protocol_id,
        trajectories=point.trajectories,
        seed_list=point.seed_list,
        produced_export_bundle_path=merged_bundle_relpath,
        discovered_context_family_path=discovery_artifacts.family_path,
        event_package_path=package_artifacts.event_package_path,
        provenance_classification=provenance_artifacts.result.admissibility_classification,
        accepted_context_count=family.diagnostics_summary.accepted_context_count,
        accepted_singleton_event_count=package_artifacts.discovered_event_family.diagnostics_summary.accepted_singleton_event_count,
        accepted_proper_coarse_event_count=package_artifacts.discovered_event_family.diagnostics_summary.accepted_coarse_event_count,
        accepted_shared_event_proposal_count=len(
            package_artifacts.event_package.equality_proposals
        ),
        accepted_proper_coarse_structural_proposal_count=accepted_proper_coarse_structural_proposal_count,
        baseline_hard_only=baseline_hard_only,
        all_accepted_proposals=all_accepted_proposals,
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status=sec_status,
        sec_mean=sec_mean,
        rm_status="not_applicable",
        rm_overall=None,
        candidate_classification="inconclusive",
        run_ids=run_ids,
        artifact_paths={
            "export_bundle": merged_bundle_relpath,
            "discovered_context_family": discovery_artifacts.family_path,
            "event_package": package_artifacts.event_package_path,
            "package_provenance": package_artifacts.provenance_path,
            "shared_event_candidates": package_artifacts.candidates_path,
            "package_build_summary": package_artifacts.summary_path,
            "provenance_summary": provenance_artifacts.summary_path,
            "baseline_statistical_summary": baseline_statistical.summary_path,
            "candidate_statistical_summary": candidate_statistical.summary_path,
            "stat_trace": stat_trace_relpath,
        },
        notes=notes
        + [
            "ccd_not_applicable_without_repeated_read_trace",
            "rm_not_applicable_without_route_observations",
        ],
    )
    return row.model_copy(
        update={
            "candidate_classification": _candidate_classification(
                row=row,
                search=search,
                blocking_classification=(
                    "no_respecting_tuples"
                    if all_proposals_exact.reason == "no_respecting_tuples"
                    else all_proposals_exact.reason
                ),
            )
        }
    )


def run_pica_targeted_obstruction_search(
    *,
    search_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> PicaTargetedSearchArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    search = load_pica_targeted_obstruction_search(search_path)
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or search.search_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    derived_dir = run_dir / "derived"
    derived_dir.mkdir()

    rows = [
        _run_point(
            point=point,
            search=search,
            category=category,
            timestamp=timestamp,
            root=effective_root,
            derived_dir=derived_dir,
        )
        for point in search.points
    ]
    table = PicaTargetedSearchTable(
        table_format_version="pica-targeted-search-results.v1",
        search_id=search.search_id,
        row_count=len(rows),
        rows=rows,
        metadata={
            "classifier_version": PICA_TARGETED_CLASSIFIER_VERSION,
            "adequacy_version": PICA_TARGETED_ADEQUACY_VERSION,
            "search_artifact": repo_relative_path(search_path, root=effective_root),
        },
    )
    classification_counts = dict(
        Counter(row.candidate_classification for row in table.rows)
    )
    adequacy = _evaluate_adequacy(rows=table.rows, search=search)
    best_candidate = _select_best_candidate(table.rows)

    table_csv_path = run_dir / "pica-targeted-search.csv"
    table_json_path = run_dir / "pica-targeted-search.json"
    summary_path = run_dir / "pica-targeted-search-summary.json"
    note_path = run_dir / "pica-targeted-search-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"

    _write_csv(table_csv_path, [_row_to_csv_record(row) for row in table.rows])
    _write_json(table_json_path, table.model_dump(mode="json"))

    if best_candidate is not None:
        outcome_kind = "best_candidate"
        outcome_path = run_dir / "best-candidate.json"
        outcome_payload = {
            "search_id": search.search_id,
            "best_candidate_id": best_candidate.point_id,
            "candidate_classification": best_candidate.candidate_classification,
            "event_package_path": best_candidate.event_package_path,
            "produced_export_bundle_path": best_candidate.produced_export_bundle_path,
            "accepted_proper_coarse_structural_proposal_count": best_candidate.accepted_proper_coarse_structural_proposal_count,
            "all_accepted_proposals": best_candidate.all_accepted_proposals.model_dump(
                mode="json"
            ),
            "provenance_classification": best_candidate.provenance_classification,
        }
    elif adequacy["adequate"]:
        outcome_kind = "negative_result"
        outcome_path = run_dir / "negative-result.json"
        outcome_payload = {
            "search_id": search.search_id,
            "adequacy_floor_met": True,
            "negative_result": True,
            "best_candidate_id": None,
            "statement": "No provenance-admissible strong endogenous discovered obstruction was found in this committed bounded PICA family.",
            "adequacy": adequacy,
        }
    else:
        outcome_kind = "search_inadequate"
        outcome_path = run_dir / "inadequate-search-result.json"
        outcome_payload = {
            "search_id": search.search_id,
            "adequacy_floor_met": False,
            "outcome": "search_inadequate",
            "best_candidate_id": None,
            "adequacy": adequacy,
            "statement": "The committed bounded PICA campaign did not satisfy the adequacy floor required for a meaningful negative obstruction result.",
        }
    _write_json(outcome_path, outcome_payload)

    output_paths = {
        "table_csv": repo_relative_path(table_csv_path, root=effective_root),
        "table_json": repo_relative_path(table_json_path, root=effective_root),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
        "outcome": repo_relative_path(outcome_path, root=effective_root),
    }
    summary = {
        "search_id": search.search_id,
        "campaign_family": [point.pilot_config_artifact for point in search.points],
        "discovery_configs": [
            point.discovery_config_artifact for point in search.points
        ],
        "event_generation_thresholds": search.event_generation_thresholds.model_dump(
            mode="json"
        ),
        "shared_event_inference_thresholds": search.shared_event_inference_thresholds.model_dump(
            mode="json"
        ),
        "candidate_classification_thresholds": search.candidate_classification_thresholds.model_dump(
            mode="json"
        ),
        "adequacy_floor_thresholds": search.adequacy_floor.model_dump(mode="json"),
        "counts_by_candidate_class": classification_counts,
        "adequacy_floor_result": adequacy,
        "best_candidate_id": None
        if best_candidate is None
        else best_candidate.point_id,
        "negative_result": outcome_kind == "negative_result",
        "outcome_kind": outcome_kind,
        "paths": output_paths,
    }
    _write_json(summary_path, summary)

    note_path.write_text(
        _render_note(
            search=search,
            table=table,
            classification_counts=classification_counts,
            adequacy=adequacy,
            best_candidate_id=None
            if best_candidate is None
            else best_candidate.point_id,
            outcome_kind=outcome_kind,
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        table=table,
        classification_counts=classification_counts,
        adequacy=adequacy,
        outcome_kind=outcome_kind,
        best_candidate_id=None if best_candidate is None else best_candidate.point_id,
        output_paths=output_paths,
    )
    _write_json(result_note_path, result_note.model_dump(mode="json"))

    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-pica-targeted-obstruction",
            repo_relative_path(search_path, root=effective_root),
        ],
        seed=seed,
        input_artifacts={
            "search_config": repo_relative_path(search_path, root=effective_root)
        },
        output_artifacts={
            "table_csv": output_paths["table_csv"],
            "table_json": output_paths["table_json"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
            outcome_kind: output_paths["outcome"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "pica_targeted_obstruction_search",
            "outcome_kind": outcome_kind,
            "adequacy_met": adequacy["adequate"],
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return PicaTargetedSearchArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        table_csv_path=output_paths["table_csv"],
        table_json_path=output_paths["table_json"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        table=table,
        classification_counts=classification_counts,
        outcome_path=output_paths["outcome"],
        outcome_kind=outcome_kind,
    )
