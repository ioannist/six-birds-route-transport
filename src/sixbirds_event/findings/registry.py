from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import sys
from typing import Any

from ..crosscheck.exact import run_exact_crosscheck
from ..falsification.discovered_case import run_discovered_case_falsification
from ..pipeline.end_to_end import (
    run_benchmark_suite,
    run_intervention_suite,
    run_lean_build,
    run_search_suite,
)
from ..provenance.audit import write_provenance_audit_report
from ..redteam.suite import run_redteam_suite
from ..robustness.noise_runner import run_noise_robustness_sweep
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from ..search.atlas_upgrade import run_atlas_upgrade
from ..search.targeted_nonextendability import run_targeted_nonextendability_search
from ..validation import load_json_file
from .models import (
    ClaimEvidenceLink,
    ClaimEvidenceMap,
    FindingEntry,
    FindingsRegistry,
    FindingsRegistryConfig,
)


@dataclass(slots=True)
class FindingsRegistryArtifacts:
    run_id: str
    run_dir: str
    registry_path: str
    registry_csv_path: str
    claim_evidence_map_path: str
    flagship_examples_path: str
    figure_candidates_path: str
    table_candidates_path: str
    theorem_experiment_links_path: str
    best_evidence_paths_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    registry: FindingsRegistry


CLAIM_LABELS: dict[str, str] = {
    "C1": "Fixed-context Booleanity",
    "C2": "Explicit finite nonextendability exists",
    "C3": "Hidden bookkeeping can dissolve apparent obstruction",
    "C4": "Some route dependence is repairable by explicit completion/flattening",
    "C5": "Endogenous discovered multi-context extendable regimes exist",
    "C6": "No strong endogenous discovered obstruction was found in the committed search family",
    "C7": "Hidden-label smuggling is a real limitation unless provenance is required",
    "C8": "Provenance-backed coarse-event package building from substrate data is possible",
}


def load_findings_registry_config(path: str | Path) -> FindingsRegistryConfig:
    payload = load_json_file(path)
    return FindingsRegistryConfig.model_validate(payload)


def _write_json(path: Path, payload: dict[str, object] | list[object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_result_note(path: Path, note: ResultNote) -> None:
    path.write_text(
        json.dumps(note.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(root: Path, relpath: str) -> dict[str, Any]:
    return json.loads((root / relpath).read_text(encoding="utf-8"))


def _finding(
    *,
    finding_id: str,
    category: str,
    title: str,
    status: str,
    key_claim_tags: list[str],
    primary_artifact_refs: dict[str, str],
    supporting_artifact_refs: dict[str, str] | None = None,
    key_metrics: dict[str, object] | None = None,
    provenance_classification: str | None = None,
    figure_table_candidate_labels: list[str] | None = None,
    theorem_link_ids: list[str] | None = None,
    best_evidence_flag: bool = False,
    best_evidence_score: float | None = None,
    notes: list[str] | None = None,
    flags: list[str] | None = None,
) -> FindingEntry:
    return FindingEntry(
        finding_format_version="finding-entry.v1",
        finding_id=finding_id,
        category=category,  # type: ignore[arg-type]
        title=title,
        status=status,
        key_claim_tags=key_claim_tags,
        primary_artifact_refs=primary_artifact_refs,
        supporting_artifact_refs=supporting_artifact_refs or {},
        key_metrics=key_metrics or {},
        provenance_classification=provenance_classification,  # type: ignore[arg-type]
        figure_table_candidate_labels=figure_table_candidate_labels or [],
        theorem_link_ids=theorem_link_ids or [],
        best_evidence_flag=best_evidence_flag,
        best_evidence_score=best_evidence_score,
        notes=notes or [],
        flags=flags or [],
    )


def _entry_csv_record(entry: FindingEntry) -> dict[str, object]:
    return {
        "finding_id": entry.finding_id,
        "category": entry.category,
        "title": entry.title,
        "status": entry.status,
        "key_claim_tags": "|".join(entry.key_claim_tags),
        "primary_artifact_refs": json.dumps(
            entry.primary_artifact_refs, sort_keys=True
        ),
        "supporting_artifact_refs": json.dumps(
            entry.supporting_artifact_refs, sort_keys=True
        ),
        "key_metrics": json.dumps(entry.key_metrics, sort_keys=True),
        "provenance_classification": entry.provenance_classification,
        "figure_table_candidate_labels": "|".join(entry.figure_table_candidate_labels),
        "theorem_link_ids": "|".join(entry.theorem_link_ids),
        "best_evidence_flag": entry.best_evidence_flag,
        "best_evidence_score": entry.best_evidence_score,
        "flags": "|".join(entry.flags),
        "notes": "|".join(entry.notes),
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _relative(root: Path, path: str | Path) -> str:
    return repo_relative_path(path, root=root)


def _claim_evidence_map(config: FindingsRegistryConfig) -> ClaimEvidenceMap:
    return ClaimEvidenceMap(
        claim_map_format_version="claim-evidence-map.v1",
        claim_count=len(config.claim_ids),
        claims=[
            ClaimEvidenceLink(
                claim_id="C1",
                claim_label=CLAIM_LABELS["C1"],
                evidence_entry_ids=[
                    "lean_fixed_context_booleanity",
                    "benchmark_classical_master_test",
                ],
                best_evidence_entry_id="lean_fixed_context_booleanity",
                theorem_linkage_ids=[
                    "T23_fixed_context_booleanity_to_fixed_context_event_layer"
                ],
            ),
            ClaimEvidenceLink(
                claim_id="C2",
                claim_label=CLAIM_LABELS["C2"],
                evidence_entry_ids=[
                    "benchmark_parity_context_witness",
                    "exact_crosscheck_parity_context_witness",
                    "lean_small_finite_obstruction_witness",
                ],
                best_evidence_entry_id="exact_crosscheck_parity_context_witness",
                theorem_linkage_ids=[
                    "T25_small_finite_obstruction_to_python_exact_feasibility"
                ],
                caveat_flags=["lean_witness_is_smaller_than_parity_benchmark"],
            ),
            ClaimEvidenceLink(
                claim_id="C3",
                claim_label=CLAIM_LABELS["C3"],
                evidence_entry_ids=["intervention_hidden_record_route_split"],
                best_evidence_entry_id="intervention_hidden_record_route_split",
            ),
            ClaimEvidenceLink(
                claim_id="C4",
                claim_label=CLAIM_LABELS["C4"],
                evidence_entry_ids=["intervention_flattening_completion_branch"],
                best_evidence_entry_id="intervention_flattening_completion_branch",
            ),
            ClaimEvidenceLink(
                claim_id="C5",
                claim_label=CLAIM_LABELS["C5"],
                evidence_entry_ids=[
                    "discovered_triadic_branch_flagship_package",
                    "atlas_upgrade_negative_result",
                ],
                best_evidence_entry_id="discovered_triadic_branch_flagship_package",
                caveat_flags=["selected_discovered_case_has_no_baseline_obstruction"],
            ),
            ClaimEvidenceLink(
                claim_id="C6",
                claim_label=CLAIM_LABELS["C6"],
                evidence_entry_ids=[
                    "targeted_search_negative_result",
                    "atlas_upgrade_negative_result",
                    "no_baseline_obstruction",
                ],
                best_evidence_entry_id="atlas_upgrade_negative_result",
                caveat_flags=["no_strong_discovered_obstruction_found"],
            ),
            ClaimEvidenceLink(
                claim_id="C7",
                claim_label=CLAIM_LABELS["C7"],
                evidence_entry_ids=[
                    "hidden_label_smuggling_not_flagged_without_provenance_audit",
                    "redteam_suite",
                ],
                best_evidence_entry_id="hidden_label_smuggling_not_flagged_without_provenance_audit",
                caveat_flags=["provenance_required_to_close_smuggling_gap"],
            ),
            ClaimEvidenceLink(
                claim_id="C8",
                claim_label=CLAIM_LABELS["C8"],
                evidence_entry_ids=[
                    "coarse_event_discovery_with_provenance",
                    "discovered_triadic_branch_flagship_package",
                    "atlas_upgrade_negative_result",
                ],
                best_evidence_entry_id="coarse_event_discovery_with_provenance",
            ),
        ],
        metadata={"registry_id": config.registry_id},
    )


def build_findings_registry(
    *,
    config_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> FindingsRegistryArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    config = load_findings_registry_config(config_path)
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or config.registry_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    label_prefix = label or config.registry_id

    benchmark_suite = (
        run_benchmark_suite(
            category=category,
            label=f"{label_prefix}-benchmark-suite",
            seed=seed,
            timestamp=timestamp,
            root=effective_root,
        )
        if config.evidence_refresh.run_benchmark_suite
        else None
    )
    intervention_suite = (
        run_intervention_suite(
            category=category,
            label=f"{label_prefix}-intervention-suite",
            seed=seed,
            timestamp=timestamp,
            root=effective_root,
        )
        if config.evidence_refresh.run_intervention_suite
        else None
    )
    search_suite = (
        run_search_suite(
            category=category,
            label=f"{label_prefix}-search-suite",
            seed=seed,
            timestamp=timestamp,
            root=effective_root,
        )
        if config.evidence_refresh.run_search_suite
        else None
    )
    lean_suite = (
        run_lean_build(
            category=category,
            label=f"{label_prefix}-lean-build",
            seed=seed,
            timestamp=timestamp,
            root=effective_root,
        )
        if config.evidence_refresh.run_lean_build_suite
        else None
    )
    robustness = run_noise_robustness_sweep(
        sweep_path=config.evidence_refresh.robustness_sweep_artifact,
        category=category,
        label=f"{label_prefix}-robustness",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
    )
    redteam = run_redteam_suite(
        suite_path=config.evidence_refresh.redteam_suite_artifact,
        category=category,
        label=f"{label_prefix}-redteam",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
    )
    crosscheck = run_exact_crosscheck(
        config_path=config.evidence_refresh.exact_crosscheck_artifact,
        category=category,
        label=f"{label_prefix}-crosscheck",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
    )
    falsification = run_discovered_case_falsification(
        falsification_path=config.evidence_refresh.discovered_case_falsification_artifact,
        category=category,
        label=f"{label_prefix}-falsification",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
    )
    targeted = run_targeted_nonextendability_search(
        search_path=config.evidence_refresh.targeted_search_artifact,
        category=category,
        label=f"{label_prefix}-targeted-search",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
    )
    atlas = run_atlas_upgrade(
        config_path=config.evidence_refresh.atlas_upgrade_artifact,
        category=category,
        label=f"{label_prefix}-atlas-upgrade",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
    )
    provenance_audits = {
        audit.audit_id: write_provenance_audit_report(
            package_path=audit.package_artifact,
            provenance_path=audit.provenance_artifact,
            category=category,
            label=f"{label_prefix}-{audit.audit_id}",
            seed=seed,
            timestamp=timestamp,
            root=effective_root,
        )
        for audit in config.evidence_refresh.provenance_audits
    }

    benchmark_summary = benchmark_suite.summary if benchmark_suite else {}
    intervention_summary = intervention_suite.summary if intervention_suite else {}
    search_summary = search_suite.summary if search_suite else {}
    lean_summary = lean_suite.summary if lean_suite else {}
    redteam_summary = redteam.summary
    robustness_summary = robustness.summary
    crosscheck_results = _load_json(effective_root, crosscheck.results_path)
    falsification_summary = _load_json(effective_root, falsification.summary_path)
    targeted_summary = _load_json(effective_root, targeted.summary_path)
    regime_counts = _load_json(effective_root, atlas.regime_counts_path)

    benchmark_entries = {
        entry["benchmark_id"]: entry
        for entry in benchmark_summary.get("benchmarks", [])
    }
    intervention_entries = {
        entry["intervention_id"]: entry
        for entry in intervention_summary.get("interventions", [])
    }
    redteam_rows = {
        row["case_id"]: row
        for row in _load_json(effective_root, redteam.json_path)["rows"]
    }
    crosscheck_rows = {row["target_id"]: row for row in crosscheck_results["rows"]}

    entries: list[FindingEntry] = []

    if benchmark_suite is not None:
        entries.append(
            _finding(
                finding_id="suite_benchmark_suite_refresh",
                category="suite",
                title="Benchmark suite refresh",
                status="succeeded",
                key_claim_tags=["C1", "C2"],
                primary_artifact_refs={
                    "summary": benchmark_suite.summary_path,
                    "note": benchmark_suite.note_path,
                },
                supporting_artifact_refs={
                    "result_note": benchmark_suite.result_note_path,
                    "manifest": benchmark_suite.manifest_path,
                },
                key_metrics={
                    "benchmark_count": len(benchmark_summary.get("benchmarks", []))
                },
                figure_table_candidate_labels=["table:benchmark_results"],
                notes=["fresh_repo_local_suite_refresh"],
            )
        )
    if intervention_suite is not None:
        entries.append(
            _finding(
                finding_id="suite_intervention_suite_refresh",
                category="suite",
                title="Intervention suite refresh",
                status="succeeded",
                key_claim_tags=["C3", "C4"],
                primary_artifact_refs={
                    "summary": intervention_suite.summary_path,
                    "note": intervention_suite.note_path,
                },
                supporting_artifact_refs={
                    "result_note": intervention_suite.result_note_path,
                    "manifest": intervention_suite.manifest_path,
                },
                key_metrics={
                    "intervention_count": len(
                        intervention_summary.get("interventions", [])
                    )
                },
                figure_table_candidate_labels=["table:interventions"],
                notes=["fresh_repo_local_suite_refresh"],
            )
        )
    if search_suite is not None:
        entries.append(
            _finding(
                finding_id="suite_search_suite_refresh",
                category="suite",
                title="Search suite refresh",
                status="succeeded",
                key_claim_tags=["C5"],
                primary_artifact_refs={
                    "summary": search_suite.summary_path,
                    "note": search_suite.note_path,
                },
                supporting_artifact_refs={
                    "result_note": search_suite.result_note_path,
                    "manifest": search_suite.manifest_path,
                },
                key_metrics=search_summary.get("regime_counts", {}),
                figure_table_candidate_labels=["figure:benchmark_suite_search_control"],
                notes=["fresh_repo_local_suite_refresh"],
            )
        )
    if lean_suite is not None:
        entries.append(
            _finding(
                finding_id="suite_lean_build_refresh",
                category="suite",
                title="Lean build suite refresh",
                status=(
                    "skipped"
                    if lean_summary.get("skipped")
                    else ("succeeded" if lean_summary.get("success") else "failed")
                ),
                key_claim_tags=["C1", "C2"],
                primary_artifact_refs={
                    "summary": lean_suite.summary_path,
                    "note": lean_suite.note_path,
                },
                supporting_artifact_refs={
                    "result_note": lean_suite.result_note_path,
                    "manifest": lean_suite.manifest_path,
                },
                key_metrics={
                    "success": lean_summary.get("success"),
                    "skipped": lean_summary.get("skipped"),
                    "return_code": lean_summary.get("return_code"),
                },
                notes=["fresh_repo_local_suite_refresh"],
            )
        )

    classical = benchmark_entries["classical-master-test"]
    epistemic = benchmark_entries["epistemic-six-state"]
    parity = benchmark_entries["parity-context-witness"]
    hidden = intervention_entries["hidden_record_route_split"]
    flattening = intervention_entries["flattening_completion_branch"]
    smuggling_audit = provenance_audits["hidden_label_smuggling_provenance"]

    entries.extend(
        [
            _finding(
                finding_id="benchmark_classical_master_test",
                category="benchmark",
                title="Classical master-test benchmark",
                status="extendable_control",
                key_claim_tags=["C1"],
                primary_artifact_refs={
                    "instance": config.static_artifact_refs[
                        "classical_master_test_instance"
                    ],
                    "suite_summary": benchmark_suite.summary_path,
                },
                supporting_artifact_refs={
                    "bundle_index": classical["index_path"],
                    "note": classical["note_path"],
                    "result_note": classical["result_note_path"],
                },
                key_metrics=classical["metrics"],
                figure_table_candidate_labels=[
                    "figure:benchmark_trilogy",
                    "table:benchmark_results",
                ],
                notes=["fixed_context_control"],
            ),
            _finding(
                finding_id="benchmark_epistemic_six_state",
                category="benchmark",
                title="Epistemic six-state benchmark",
                status="extendable_boundary_case",
                key_claim_tags=["C1", "C5"],
                primary_artifact_refs={
                    "instance": config.static_artifact_refs[
                        "epistemic_six_state_instance"
                    ],
                    "suite_summary": benchmark_suite.summary_path,
                },
                supporting_artifact_refs={
                    "bundle_index": epistemic["index_path"],
                    "note": epistemic["note_path"],
                    "result_note": epistemic["result_note_path"],
                },
                key_metrics=epistemic["metrics"],
                figure_table_candidate_labels=["figure:benchmark_trilogy"],
                notes=["nontrivial_but_extendable_benchmark"],
            ),
            _finding(
                finding_id="benchmark_parity_context_witness",
                category="benchmark",
                title="Parity/context witness benchmark",
                status="explicit_computational_obstruction",
                key_claim_tags=["C2"],
                primary_artifact_refs={
                    "instance": config.static_artifact_refs[
                        "parity_context_witness_instance"
                    ],
                    "suite_summary": benchmark_suite.summary_path,
                },
                supporting_artifact_refs={
                    "bundle_index": parity["index_path"],
                    "crosscheck_summary": crosscheck.summary_path,
                    "crosscheck_model": crosscheck.model_path
                    or crosscheck.summary_path,
                },
                key_metrics=parity["metrics"],
                theorem_link_ids=[
                    "T25_small_finite_obstruction_to_python_exact_feasibility"
                ],
                figure_table_candidate_labels=[
                    "figure:benchmark_trilogy",
                    "figure:parity_crosscheck",
                    "table:benchmark_results",
                ],
                best_evidence_flag=True,
                best_evidence_score=10.0,
                notes=["flagship_explicit_finite_obstruction"],
            ),
            _finding(
                finding_id="intervention_hidden_record_route_split",
                category="intervention",
                title="Hidden-record intervention",
                status=hidden["conclusion"],
                key_claim_tags=["C3"],
                primary_artifact_refs={
                    "summary": hidden["summary_path"],
                    "suite_summary": intervention_suite.summary_path,
                },
                supporting_artifact_refs={
                    "note": hidden["note_path"],
                    "result_note": hidden["result_note_path"],
                },
                key_metrics={"conclusion": hidden["conclusion"]},
                figure_table_candidate_labels=[
                    "figure:hidden_record_intervention",
                    "table:interventions",
                ],
                best_evidence_flag=True,
                best_evidence_score=9.5,
                notes=[
                    "apparent_obstruction_disappears_when_bookkeeping_is_admissible"
                ],
            ),
            _finding(
                finding_id="intervention_flattening_completion_branch",
                category="intervention",
                title="Flattening/completion intervention",
                status=flattening["conclusion"],
                key_claim_tags=["C4"],
                primary_artifact_refs={
                    "summary": flattening["summary_path"],
                    "suite_summary": intervention_suite.summary_path,
                },
                supporting_artifact_refs={
                    "note": flattening["note_path"],
                    "result_note": flattening["result_note_path"],
                },
                key_metrics={"conclusion": flattening["conclusion"]},
                figure_table_candidate_labels=[
                    "figure:flattening_intervention",
                    "table:interventions",
                ],
                best_evidence_flag=True,
                best_evidence_score=9.4,
                notes=["route_dependence_is_repairable_in_this_intervention_family"],
            ),
            _finding(
                finding_id="robustness_small_noise_sweep",
                category="robustness",
                title="Small noise robustness sweep",
                status="completed",
                key_claim_tags=["C2", "C5"],
                primary_artifact_refs={
                    "summary": robustness.summary_path,
                    "threshold_crossings": robustness.threshold_crossings_path,
                },
                supporting_artifact_refs={
                    "table_json": robustness.json_path,
                    "table_csv": robustness.csv_path,
                    "note": robustness.note_path,
                },
                key_metrics={
                    "target_count": robustness_summary["target_count"],
                    "row_count": robustness_summary["row_count"],
                },
                figure_table_candidate_labels=[
                    "figure:robustness_threshold_summary",
                    "table:robustness",
                ],
                notes=["explicit_status_preservation"],
            ),
            _finding(
                finding_id="redteam_suite",
                category="redteam",
                title="Adversarial red-team suite",
                status="completed",
                key_claim_tags=["C7"],
                primary_artifact_refs={
                    "summary": redteam.summary_path,
                    "results_json": redteam.json_path,
                },
                supporting_artifact_refs={
                    "results_csv": redteam.csv_path,
                    "response_counts": redteam.response_counts_path,
                    "note": redteam.note_path,
                },
                key_metrics=redteam_summary["counts_by_framework_response"],
                figure_table_candidate_labels=[
                    "figure:redteam_response_counts",
                    "table:redteam_cases",
                ],
                notes=["strengths_and_limits_are_reported_together"],
            ),
            _finding(
                finding_id="hidden_label_smuggling_not_flagged_without_provenance_audit",
                category="redteam",
                title="Hidden-label smuggling limitation",
                status="not_flagged",
                key_claim_tags=["C7"],
                primary_artifact_refs={
                    "redteam_results": redteam.json_path,
                    "smuggling_audit_summary": smuggling_audit.summary_path,
                },
                supporting_artifact_refs={
                    "redteam_summary": redteam.summary_path,
                    "smuggling_audit_note": smuggling_audit.note_path,
                },
                key_metrics={
                    "framework_response": redteam_rows["hidden_label_smuggling"][
                        "framework_response"
                    ],
                    "admissibility_classification": smuggling_audit.result.admissibility_classification,
                },
                provenance_classification=smuggling_audit.result.admissibility_classification,
                figure_table_candidate_labels=[
                    "table:redteam_cases",
                    "table:key_claims",
                ],
                best_evidence_flag=True,
                best_evidence_score=8.8,
                notes=["limitation_is_real_without_provenance_requirement"],
                flags=["limitation", "negative_result"],
            ),
            _finding(
                finding_id="lean_fixed_context_booleanity",
                category="lean",
                title="Lean fixed-context Booleanity layer",
                status="formalized",
                key_claim_tags=["C1"],
                primary_artifact_refs={
                    "finite_test": config.static_artifact_refs["t23_finite_test"],
                    "fixed_context_booleanity": config.static_artifact_refs[
                        "t23_fixed_context_booleanity"
                    ],
                },
                supporting_artifact_refs={
                    "lean_build_summary": lean_suite.summary_path
                },
                theorem_link_ids=[
                    "T23_fixed_context_booleanity_to_fixed_context_event_layer"
                ],
                figure_table_candidate_labels=["table:lean_artifacts"],
                best_evidence_flag=True,
                best_evidence_score=9.0,
                notes=["stable_importable_lean_api"],
            ),
            _finding(
                finding_id="lean_small_finite_obstruction_witness",
                category="lean",
                title="Lean explicit finite obstruction witness",
                status="formalized",
                key_claim_tags=["C2"],
                primary_artifact_refs={
                    "global_realization": config.static_artifact_refs[
                        "t25_global_realization"
                    ],
                    "finite_obstruction_witness": config.static_artifact_refs[
                        "t25_finite_obstruction_witness"
                    ],
                },
                supporting_artifact_refs={
                    "runbook": config.static_artifact_refs["t25_runbook"],
                    "lean_build_summary": lean_suite.summary_path,
                },
                theorem_link_ids=[
                    "T25_small_finite_obstruction_to_python_exact_feasibility"
                ],
                figure_table_candidate_labels=["table:lean_artifacts"],
                best_evidence_flag=True,
                best_evidence_score=8.7,
                notes=["smaller_witness_than_parity_benchmark_but_semantics_aligned"],
            ),
            _finding(
                finding_id="discovered_triadic_branch_flagship_package",
                category="discovered_package",
                title="Selected discovered flagship package",
                status=falsification_summary["final_verdict"],
                key_claim_tags=["C5", "C8"],
                primary_artifact_refs={
                    "event_package": config.static_artifact_refs[
                        "triadic_branch_flagship_event_package"
                    ],
                    "package_provenance": config.static_artifact_refs[
                        "triadic_branch_flagship_package_provenance"
                    ],
                },
                supporting_artifact_refs={
                    "falsification_summary": falsification.summary_path,
                    "shared_event_candidates": config.static_artifact_refs[
                        "triadic_branch_flagship_shared_event_candidates"
                    ],
                    "selection": config.static_artifact_refs[
                        "triadic_branch_flagship_selection"
                    ],
                },
                key_metrics={
                    "accepted_coarse_proposal_count": 45,
                    "baseline_candidate_exact_feasible": falsification_summary[
                        "baseline_all_accepted_proposals"
                    ]["exact_feasible"],
                },
                provenance_classification=falsification_summary[
                    "provenance_classification"
                ],
                figure_table_candidate_labels=[
                    "figure:discovered_case_falsification",
                    "table:discovered_flagship",
                ],
                best_evidence_flag=True,
                best_evidence_score=9.1,
                notes=["best_nontrivial_provenance_admissible_discovered_case"],
            ),
            _finding(
                finding_id="no_baseline_obstruction",
                category="claim_support",
                title="Selected discovered case has no baseline obstruction",
                status="no_baseline_obstruction",
                key_claim_tags=["C5", "C6"],
                primary_artifact_refs={
                    "falsification_summary": falsification.summary_path,
                    "falsification_note": falsification.note_path,
                },
                supporting_artifact_refs={
                    "selection": config.static_artifact_refs[
                        "triadic_branch_flagship_selection"
                    ],
                },
                key_metrics={
                    "baseline_hard_only_exact_feasible": falsification_summary[
                        "baseline_hard_only"
                    ]["exact_feasible"],
                    "baseline_all_accepted_exact_feasible": falsification_summary[
                        "baseline_all_accepted_proposals"
                    ]["exact_feasible"],
                    "baseline_all_accepted_gpd_str": falsification_summary[
                        "baseline_all_accepted_proposals"
                    ]["gpd_str"],
                },
                flags=["negative_result"],
                notes=["selected_discovered_case_is_extendable_in_both_modes"],
            ),
            _finding(
                finding_id="exact_crosscheck_parity_context_witness",
                category="claim_support",
                title="Independent exact cross-check for parity/context witness",
                status="infeasible_certified_by_independent_backend",
                key_claim_tags=["C2"],
                primary_artifact_refs={
                    "summary": crosscheck.summary_path,
                    "results": crosscheck.results_path,
                    "model": crosscheck.model_path or crosscheck.summary_path,
                },
                supporting_artifact_refs={
                    "note": crosscheck.note_path,
                },
                key_metrics={
                    "exact_respecting_tuple_count": crosscheck_rows[
                        "parity_context_witness_hard_only"
                    ]["exact_respecting_tuple_count"],
                    "blocking_proposal_count": len(
                        crosscheck_rows["parity_context_witness_hard_only"][
                            "blocking_proxy"
                        ]["blocking_proposal_ids"]
                    ),
                },
                theorem_link_ids=[
                    "T25_small_finite_obstruction_to_python_exact_feasibility"
                ],
                figure_table_candidate_labels=["figure:parity_crosscheck"],
                best_evidence_flag=True,
                best_evidence_score=9.6,
                notes=["solver_independent_milp_crosscheck"],
            ),
            _finding(
                finding_id="targeted_search_negative_result",
                category="claim_support",
                title="Targeted nonextendability search negative result",
                status="no_strong_discovered_obstruction_found",
                key_claim_tags=["C6"],
                primary_artifact_refs={
                    "summary": targeted.summary_path,
                    "table_json": targeted.table_json_path,
                    "negative_result": targeted.negative_result_path
                    or targeted.summary_path,
                },
                supporting_artifact_refs={
                    "table_csv": targeted.table_csv_path,
                    "note": targeted.note_path,
                },
                key_metrics=targeted_summary["classification_counts"],
                figure_table_candidate_labels=["table:key_claims"],
                best_evidence_flag=True,
                best_evidence_score=8.9,
                notes=["bounded_targeted_family_exhausted_without_strong_candidate"],
                flags=["negative_result"],
            ),
            _finding(
                finding_id="atlas_upgrade_negative_result",
                category="claim_support",
                title="Upgraded atlas negative result",
                status="no_strong_discovered_obstruction_found",
                key_claim_tags=["C5", "C6", "C8"],
                primary_artifact_refs={
                    "summary": atlas.summary_path,
                    "table_json": atlas.table_json_path,
                    "negative_result": atlas.negative_result_path or atlas.summary_path,
                },
                supporting_artifact_refs={
                    "regime_counts": atlas.regime_counts_path,
                    "threshold_summary": atlas.threshold_summary_path,
                    "figure_atlas_points_csv": atlas.figure_atlas_points_csv_path,
                },
                key_metrics={
                    "multi_context_but_extendable": regime_counts[
                        "multi_context_but_extendable"
                    ],
                    "strongly_nonextendable": regime_counts["strongly_nonextendable"],
                    "provenance_admissible_count": atlas.summary[
                        "provenance_admissible_count"
                    ],
                },
                figure_table_candidate_labels=[
                    "figure:atlas_regime_counts",
                    "figure:atlas_points",
                    "table:key_claims",
                ],
                best_evidence_flag=True,
                best_evidence_score=9.2,
                notes=["compact_intentional_atlas_with_explicit_dual_evaluation_modes"],
                flags=["negative_result"],
            ),
            _finding(
                finding_id="coarse_event_discovery_with_provenance",
                category="claim_support",
                title="Provenance-backed coarse-event discovery",
                status="admissible_coarse_event_package_built",
                key_claim_tags=["C8"],
                primary_artifact_refs={
                    "event_package": config.static_artifact_refs[
                        "triadic_branch_flagship_event_package"
                    ],
                    "package_provenance": config.static_artifact_refs[
                        "triadic_branch_flagship_package_provenance"
                    ],
                },
                supporting_artifact_refs={
                    "shared_event_candidates": config.static_artifact_refs[
                        "triadic_branch_flagship_shared_event_candidates"
                    ],
                    "discovered_event_family": config.static_artifact_refs[
                        "triadic_branch_flagship_discovered_event_family"
                    ],
                    "falsification_summary": falsification.summary_path,
                },
                key_metrics={
                    "accepted_coarse_proposal_count": 45,
                    "provenance_classification": falsification_summary[
                        "provenance_classification"
                    ],
                },
                provenance_classification=falsification_summary[
                    "provenance_classification"
                ],
                figure_table_candidate_labels=["table:discovered_flagship"],
                best_evidence_flag=True,
                best_evidence_score=9.0,
                notes=["coarse_events_are_not_free_floating_labels"],
            ),
        ]
    )

    claim_map = _claim_evidence_map(config)
    claim_map.claims = [
        claim for claim in claim_map.claims if claim.claim_id in set(config.claim_ids)
    ]
    claim_map.claim_count = len(claim_map.claims)
    entries_by_id = {entry.finding_id: entry for entry in entries}

    theorem_experiment_links = [
        {
            "theorem_link_id": "T23_fixed_context_booleanity_to_fixed_context_event_layer",
            "title": "T23 fixed-context Booleanity to experiment-side fixed-context event layer",
            "theorem_artifacts": [
                config.static_artifact_refs["t23_finite_test"],
                config.static_artifact_refs["t23_fixed_context_booleanity"],
            ],
            "experiment_artifacts": [
                config.static_artifact_refs["classical_master_test_instance"],
                benchmark_suite.summary_path,
            ],
            "notes": [
                "links the Lean fixed-context Boolean layer to the benchmark-side event-package layer"
            ],
        },
        {
            "theorem_link_id": "T25_small_finite_obstruction_to_python_exact_feasibility",
            "title": "T25 small finite obstruction witness to Python exact-feasibility semantics",
            "theorem_artifacts": [
                config.static_artifact_refs["t25_global_realization"],
                config.static_artifact_refs["t25_finite_obstruction_witness"],
                config.static_artifact_refs["t25_runbook"],
            ],
            "experiment_artifacts": [
                config.static_artifact_refs["parity_context_witness_instance"],
                crosscheck.summary_path,
            ],
            "notes": [
                "the Lean theorem is a smaller witness, not the parity benchmark itself",
                "the linkage is semantic alignment through global-atom and coverage semantics",
            ],
        },
    ]
    flagship_examples = {
        "explicit_finite_obstruction": {
            "finding_id": "benchmark_parity_context_witness",
            "title": entries_by_id["benchmark_parity_context_witness"].title,
            "primary_artifact_refs": entries_by_id[
                "benchmark_parity_context_witness"
            ].primary_artifact_refs,
        },
        "discovered_flagship": {
            "finding_id": "discovered_triadic_branch_flagship_package",
            "title": entries_by_id["discovered_triadic_branch_flagship_package"].title,
            "primary_artifact_refs": entries_by_id[
                "discovered_triadic_branch_flagship_package"
            ].primary_artifact_refs,
        },
        "interventions": [
            {
                "finding_id": "intervention_hidden_record_route_split",
                "title": entries_by_id["intervention_hidden_record_route_split"].title,
                "primary_artifact_refs": entries_by_id[
                    "intervention_hidden_record_route_split"
                ].primary_artifact_refs,
            },
            {
                "finding_id": "intervention_flattening_completion_branch",
                "title": entries_by_id[
                    "intervention_flattening_completion_branch"
                ].title,
                "primary_artifact_refs": entries_by_id[
                    "intervention_flattening_completion_branch"
                ].primary_artifact_refs,
            },
        ],
    }
    figure_candidates = [
        {
            "figure_id": "benchmark_trilogy_summary",
            "label": "Benchmark trilogy summary",
            "artifact_refs": {"benchmark_suite_summary": benchmark_suite.summary_path},
            "finding_ids": [
                "benchmark_classical_master_test",
                "benchmark_epistemic_six_state",
                "benchmark_parity_context_witness",
            ],
        },
        {
            "figure_id": "atlas_regime_counts",
            "label": "Upgraded atlas regime counts",
            "artifact_refs": {
                "regime_counts": atlas.regime_counts_path,
                "figure_regime_counts_csv": atlas.figure_regime_counts_csv_path,
                "figure_atlas_points_csv": atlas.figure_atlas_points_csv_path,
            },
            "finding_ids": ["atlas_upgrade_negative_result"],
        },
        {
            "figure_id": "robustness_threshold_summary",
            "label": "Robustness threshold summary",
            "artifact_refs": {
                "summary": robustness.summary_path,
                "threshold_crossings": robustness.threshold_crossings_path,
            },
            "finding_ids": ["robustness_small_noise_sweep"],
        },
        {
            "figure_id": "redteam_response_counts",
            "label": "Red-team response counts",
            "artifact_refs": {
                "summary": redteam.summary_path,
                "response_counts": redteam.response_counts_path,
            },
            "finding_ids": ["redteam_suite"],
        },
        {
            "figure_id": "parity_context_crosscheck",
            "label": "Parity/context crosscheck summary",
            "artifact_refs": {
                "summary": crosscheck.summary_path,
                "model": crosscheck.model_path or crosscheck.summary_path,
            },
            "finding_ids": ["exact_crosscheck_parity_context_witness"],
        },
        {
            "figure_id": "discovered_case_falsification",
            "label": "Discovered-case falsification summary",
            "artifact_refs": {
                "summary": falsification.summary_path,
                "note": falsification.note_path,
            },
            "finding_ids": [
                "discovered_triadic_branch_flagship_package",
                "no_baseline_obstruction",
            ],
        },
    ]
    table_candidates = [
        {
            "table_id": "benchmark_results_table",
            "label": "Benchmark results table",
            "artifact_refs": {"benchmark_suite_summary": benchmark_suite.summary_path},
            "finding_ids": [
                "benchmark_classical_master_test",
                "benchmark_epistemic_six_state",
                "benchmark_parity_context_witness",
            ],
        },
        {
            "table_id": "intervention_before_after_table",
            "label": "Intervention before/after table",
            "artifact_refs": {
                "intervention_suite_summary": intervention_suite.summary_path
            },
            "finding_ids": [
                "intervention_hidden_record_route_split",
                "intervention_flattening_completion_branch",
            ],
        },
        {
            "table_id": "redteam_cases_table",
            "label": "Red-team cases table",
            "artifact_refs": {
                "redteam_results_json": redteam.json_path,
                "redteam_results_csv": redteam.csv_path,
            },
            "finding_ids": [
                "redteam_suite",
                "hidden_label_smuggling_not_flagged_without_provenance_audit",
            ],
        },
        {
            "table_id": "lean_theorem_artifacts_table",
            "label": "Lean theorem artifact table",
            "artifact_refs": {
                "t23_fixed_context_booleanity": config.static_artifact_refs[
                    "t23_fixed_context_booleanity"
                ],
                "t25_finite_obstruction_witness": config.static_artifact_refs[
                    "t25_finite_obstruction_witness"
                ],
                "t25_runbook": config.static_artifact_refs["t25_runbook"],
            },
            "finding_ids": [
                "lean_fixed_context_booleanity",
                "lean_small_finite_obstruction_witness",
            ],
        },
        {
            "table_id": "key_claims_and_best_evidence",
            "label": "Key claims and best evidence table",
            "artifact_refs": {},
            "finding_ids": [claim.best_evidence_entry_id for claim in claim_map.claims],
        },
    ]
    best_evidence_paths = {
        claim.claim_id: {
            "claim_label": claim.claim_label,
            "best_evidence_entry_id": claim.best_evidence_entry_id,
            "primary_artifact_paths": list(
                entries_by_id[
                    claim.best_evidence_entry_id
                ].primary_artifact_refs.values()
            ),
            "supporting_artifact_paths": list(
                entries_by_id[
                    claim.best_evidence_entry_id
                ].supporting_artifact_refs.values()
            ),
            "caveat_flags": claim.caveat_flags,
        }
        for claim in claim_map.claims
    }

    evidence_refresh_runs = {
        key: value
        for key, value in {
            "benchmark_suite": benchmark_suite.run_id if benchmark_suite else None,
            "intervention_suite": intervention_suite.run_id
            if intervention_suite
            else None,
            "search_suite": search_suite.run_id if search_suite else None,
            "lean_build_suite": lean_suite.run_id if lean_suite else None,
            "robustness": robustness.run_id,
            "redteam": redteam.run_id,
            "crosscheck": crosscheck.run_id,
            "falsification": falsification.run_id,
            "targeted_search": targeted.run_id,
            "atlas_upgrade": atlas.run_id,
            **{
                f"provenance_audit:{audit_id}": artifacts.run_id
                for audit_id, artifacts in provenance_audits.items()
            },
        }.items()
        if value is not None
    }
    evidence_refresh_summary_paths = {
        key: value
        for key, value in {
            "benchmark_suite": benchmark_suite.summary_path
            if benchmark_suite
            else None,
            "intervention_suite": intervention_suite.summary_path
            if intervention_suite
            else None,
            "search_suite": search_suite.summary_path if search_suite else None,
            "lean_build_suite": lean_suite.summary_path if lean_suite else None,
            "robustness": robustness.summary_path,
            "redteam": redteam.summary_path,
            "crosscheck": crosscheck.summary_path,
            "falsification": falsification.summary_path,
            "targeted_search": targeted.summary_path,
            "atlas_upgrade": atlas.summary_path,
            **{
                f"provenance_audit:{audit_id}": artifacts.summary_path
                for audit_id, artifacts in provenance_audits.items()
            },
        }.items()
        if value is not None
    }

    registry_path = run_dir / "findings-registry.json"
    registry_csv_path = run_dir / "findings-registry.csv"
    claim_map_path = run_dir / "claim-evidence-map.json"
    flagship_examples_path = run_dir / "flagship-examples.json"
    figure_candidates_path = run_dir / "figure-candidates.json"
    table_candidates_path = run_dir / "table-candidates.json"
    theorem_links_path = run_dir / "theorem-experiment-links.json"
    best_evidence_paths_path = run_dir / "best-evidence-paths.json"
    summary_path = run_dir / "findings-summary.json"
    note_path = run_dir / "findings-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"

    _write_json(claim_map_path, claim_map.model_dump(mode="json"))
    _write_json(flagship_examples_path, flagship_examples)
    _write_json(figure_candidates_path, figure_candidates)
    _write_json(table_candidates_path, table_candidates)
    _write_json(theorem_links_path, theorem_experiment_links)
    _write_json(best_evidence_paths_path, best_evidence_paths)

    registry = FindingsRegistry(
        registry_format_version="findings-registry.v1",
        registry_id=config.registry_id,
        evidence_refresh_run_ids=evidence_refresh_runs,
        evidence_refresh_summary_paths=evidence_refresh_summary_paths,
        entry_count=len(entries),
        entries=entries,
        claim_evidence_map_path=_relative(effective_root, claim_map_path),
        flagship_examples_path=_relative(effective_root, flagship_examples_path),
        figure_candidates_path=_relative(effective_root, figure_candidates_path),
        table_candidates_path=_relative(effective_root, table_candidates_path),
        theorem_experiment_links_path=_relative(effective_root, theorem_links_path),
        best_evidence_paths_path=_relative(effective_root, best_evidence_paths_path),
        summary_counts={
            "entry_count": len(entries),
            "claim_count": claim_map.claim_count,
            "flagship_count": 4,
            "negative_or_limitation_count": sum(
                1
                for entry in entries
                if "negative_result" in entry.flags or "limitation" in entry.flags
            ),
            **{
                f"category_count:{category_name}": count
                for category_name, count in Counter(
                    entry.category for entry in entries
                ).items()
            },
        },
        status_flags=[
            "no_strong_discovered_obstruction_found",
            "no_baseline_obstruction",
            "hidden_label_smuggling_not_flagged_without_provenance_audit",
        ],
        metadata=config.metadata,
    )
    _write_json(registry_path, registry.model_dump(mode="json"))
    _write_csv(registry_csv_path, [_entry_csv_record(entry) for entry in entries])

    findings_summary = {
        "registry_id": config.registry_id,
        "evidence_refresh_run_ids": evidence_refresh_runs,
        "entry_counts_by_category": dict(Counter(entry.category for entry in entries)),
        "claim_count": claim_map.claim_count,
        "flagship_count": 4,
        "negative_or_limitation_count": registry.summary_counts[
            "negative_or_limitation_count"
        ],
        "paths": {
            "registry_json": _relative(effective_root, registry_path),
            "registry_csv": _relative(effective_root, registry_csv_path),
            "claim_evidence_map": _relative(effective_root, claim_map_path),
            "flagship_examples": _relative(effective_root, flagship_examples_path),
            "figure_candidates": _relative(effective_root, figure_candidates_path),
            "table_candidates": _relative(effective_root, table_candidates_path),
            "theorem_experiment_links": _relative(effective_root, theorem_links_path),
            "best_evidence_paths": _relative(effective_root, best_evidence_paths_path),
        },
    }
    _write_json(summary_path, findings_summary)

    note_lines = [
        f"# Findings Registry: {config.registry_id}",
        "",
        "## Scope",
        "- Registry-oriented final evidence base over benchmarks, discovered packages, interventions, robustness, red-team, Lean, and suite refresh outputs.",
        "",
        "## Evidence refresh components run",
    ]
    for key, run_value in evidence_refresh_runs.items():
        note_lines.append(
            f"- `{key}`: run_id=`{run_value}`, summary=`{evidence_refresh_summary_paths[key]}`"
        )
    note_lines.extend(
        [
            "",
            "## Claims included",
        ]
    )
    for claim in claim_map.claims:
        note_lines.append(
            f"- `{claim.claim_id}` `{claim.claim_label}`: best_evidence=`{claim.best_evidence_entry_id}`, caveats=`{claim.caveat_flags}`"
        )
    note_lines.extend(
        [
            "",
            "## Flagship examples",
            "- Explicit finite obstruction: `benchmark_parity_context_witness`",
            "- Discovered flagship: `discovered_triadic_branch_flagship_package`",
            "- Intervention flagships: `intervention_hidden_record_route_split`, `intervention_flattening_completion_branch`",
            "",
            "## Notable negative results / limitations",
            "- `no_strong_discovered_obstruction_found` is preserved explicitly from targeted-search and atlas outputs.",
            "- `no_baseline_obstruction` is preserved explicitly for the selected discovered flagship case.",
            "- `hidden_label_smuggling_not_flagged_without_provenance_audit` is preserved explicitly as a framework limitation.",
            "",
            "## Theorem-to-experiment linkage note",
            "- T23 fixed-context Booleanity is linked to the benchmark/event-family layer, not to a manuscript theorem export.",
            "- T25 small finite obstruction theorem is linked honestly to the Python exact-feasibility semantics and parity witness crosscheck without claiming theorem identity.",
            "",
            "## Artifact references",
            f"- Registry JSON: `{_relative(effective_root, registry_path)}`",
            f"- Claim-evidence map: `{_relative(effective_root, claim_map_path)}`",
            f"- Flagship examples: `{_relative(effective_root, flagship_examples_path)}`",
            f"- Figure candidates: `{_relative(effective_root, figure_candidates_path)}`",
            f"- Table candidates: `{_relative(effective_root, table_candidates_path)}`",
            f"- Theorem-experiment links: `{_relative(effective_root, theorem_links_path)}`",
            f"- Best evidence paths: `{_relative(effective_root, best_evidence_paths_path)}`",
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[entry.finding_id for entry in entries],
        metrics={
            "entry_count": len(entries),
            "claim_count": claim_map.claim_count,
            "flagship_count": 4,
            "negative_or_limitation_count": registry.summary_counts[
                "negative_or_limitation_count"
            ],
        },
        interpretation=(
            "Final findings registry aggregated a fresh stable repo-local evidence refresh with committed static artifacts into claim-oriented findings, flagships, theorem-to-experiment links, and best-evidence paths."
        ),
        caveats=[
            "Negative and limitation findings are preserved explicitly rather than curated away.",
            "The registry points only at committed repo assets or stable repo-local run outputs created during this build.",
        ],
        artifact_refs={
            "registry": _relative(effective_root, registry_path),
            "claim_evidence_map": _relative(effective_root, claim_map_path),
            "flagship_examples": _relative(effective_root, flagship_examples_path),
            "figure_candidates": _relative(effective_root, figure_candidates_path),
            "table_candidates": _relative(effective_root, table_candidates_path),
            "theorem_experiment_links": _relative(effective_root, theorem_links_path),
            "best_evidence_paths": _relative(effective_root, best_evidence_paths_path),
            "summary": _relative(effective_root, summary_path),
            "note": _relative(effective_root, note_path),
        },
        metadata={"registry_id": config.registry_id},
    )
    _write_result_note(result_note_path, result_note)

    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "findings",
            "build-registry",
            str(config_path),
        ],
        seed=seed,
        input_artifacts={"config": _relative(effective_root, config_path)},
        output_artifacts={
            "registry": _relative(effective_root, registry_path),
            "registry_csv": _relative(effective_root, registry_csv_path),
            "claim_evidence_map": _relative(effective_root, claim_map_path),
            "flagship_examples": _relative(effective_root, flagship_examples_path),
            "figure_candidates": _relative(effective_root, figure_candidates_path),
            "table_candidates": _relative(effective_root, table_candidates_path),
            "theorem_experiment_links": _relative(effective_root, theorem_links_path),
            "best_evidence_paths": _relative(effective_root, best_evidence_paths_path),
            "summary": _relative(effective_root, summary_path),
            "note": _relative(effective_root, note_path),
            "result_note": _relative(effective_root, result_note_path),
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "findings_registry",
            "registry_id": config.registry_id,
            "entry_count": len(entries),
            "claim_count": claim_map.claim_count,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return FindingsRegistryArtifacts(
        run_id=run_id,
        run_dir=_relative(effective_root, run_dir),
        registry_path=_relative(effective_root, registry_path),
        registry_csv_path=_relative(effective_root, registry_csv_path),
        claim_evidence_map_path=_relative(effective_root, claim_map_path),
        flagship_examples_path=_relative(effective_root, flagship_examples_path),
        figure_candidates_path=_relative(effective_root, figure_candidates_path),
        table_candidates_path=_relative(effective_root, table_candidates_path),
        theorem_experiment_links_path=_relative(effective_root, theorem_links_path),
        best_evidence_paths_path=_relative(effective_root, best_evidence_paths_path),
        summary_path=_relative(effective_root, summary_path),
        note_path=_relative(effective_root, note_path),
        result_note_path=_relative(effective_root, result_note_path),
        manifest_path=_relative(effective_root, manifest_path),
        registry=registry,
    )
