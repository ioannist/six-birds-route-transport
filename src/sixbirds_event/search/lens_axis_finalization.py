from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    get_repo_root,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from ..validation import load_model
from .models import (
    LensAxisFinalOutcome,
    LensAxisFinalizationConfig,
    LensAxisFinalizationRegime,
    LensAxisSearch,
    LensAxisTable,
)


@dataclass(slots=True)
class LensAxisFinalizationArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    note_path: str
    regime_table_path: str
    result_note_path: str
    manifest_path: str
    outcome_path: str
    final_outcome: LensAxisFinalOutcome


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _resolve_repo_artifact(path: str | Path, *, root: Path) -> Path:
    candidate = root / path
    if candidate.exists():
        return candidate
    canonical_root = get_repo_root()
    fallback = canonical_root / path
    if fallback.exists():
        return fallback
    return candidate


def load_lens_axis_finalization_config(
    path: str | Path,
) -> LensAxisFinalizationConfig:
    model = load_model(path, kind="lens-axis-finalization")
    assert isinstance(model, LensAxisFinalizationConfig)
    return model


def _load_json(path: str | Path, *, root: Path) -> dict[str, Any]:
    resolved = _resolve_repo_artifact(path, root=root)
    return json.loads(resolved.read_text(encoding="utf-8"))


def _artifact_ref(path: str | Path) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return repo_relative_path(candidate, root=get_repo_root())
    return candidate.as_posix()


def _same_step_row(
    *,
    table: LensAxisTable,
    point_id: str,
):
    for row in table.rows:
        if row.point_id == point_id:
            return row
    raise ValueError(f"same-step flagship point_id '{point_id}' not found in table")


def _build_note(
    *,
    config: LensAxisFinalizationConfig,
    same_step_row,
    same_step_summary: dict[str, Any],
    cross_search: LensAxisSearch,
    cross_package_summary: dict[str, Any],
    cross_provenance_summary: dict[str, Any],
    cross_quotient_summary: dict[str, Any],
    output_paths: dict[str, str],
) -> str:
    accepted_result = cross_quotient_summary["accepted_proposal_set_result"]
    natural_result = cross_quotient_summary["natural_pairing_result"]
    lines = [
        "# Lens-axis finalization",
        "",
        f"- Lens-axis ID: `{config.lens_axis_id}`",
        f"- Canonical flagship case: `{config.canonical_flagship_case_id}`",
        f"- Final claim level: `{config.final_claim_level}`",
        "",
        "## Fixed structure",
        f"- Fixed mechanism/configuration: `{cross_search.fixed_mechanism_label}`",
        f"- Fixed packaging family: `{cross_search.fixed_packaging_family_label}`",
        "- Same support object is preserved across both subregimes.",
        "- Shared-event admissibility remains unchanged; only previously accepted proposals count toward admitted obstruction.",
        "",
        "## Same-step bounded-negative subregime",
        f"- Flagship point: `{same_step_row.point_id}`",
        f"- Candidate class: `{same_step_row.candidate_classification}`",
        f"- Quotient witness status: `{same_step_row.quotient_witness_status}`",
        f"- Accepted-only survivor count: `{same_step_row.quotient_accepted_only_survivor_count}`",
        f"- Natural-pairing survivor count: `{same_step_row.quotient_natural_pairing_survivor_count}`",
        f"- Same-slice non-nested lens pair count: `{same_step_row.same_slice_non_nested_lens_pair_count}`",
        f"- Campaign outcome: `{'negative_result' if same_step_summary.get('negative_result') else 'non_negative'}`",
        "",
        "## Cross-resolution strict-extension flagship",
        f"- Search ID: `{cross_search.search_id}`",
        f"- Cross-resolution comparisons allowed: `{cross_search.allow_cross_resolution_pairs}`",
        f"- Event basis mode: `{cross_package_summary['event_basis_mode']}`",
        f"- Event algebra mode: `{cross_package_summary['event_algebra_mode']}`",
        f"- Accepted context count: `{cross_package_summary['accepted_context_count']}`",
        f"- Accepted shared-event proposal count: `{cross_package_summary['accepted_shared_event_proposal_count']}`",
        f"- Provenance classification: `{cross_provenance_summary['admissibility_classification']}`",
        f"- Accepted-only exact feasible: `{accepted_result['exact_feasible']}`",
        f"- Accepted-only survivor count: `{accepted_result['survivor_count']}`",
        f"- Accepted-only failure reason: `{accepted_result['exact_failure_reason']}`",
        f"- Natural-pairing exact feasible: `{natural_result['exact_feasible']}`",
        f"- Natural-pairing survivor count: `{natural_result['survivor_count']}`",
        f"- Quotient witness classification: `{cross_quotient_summary['witness_classification']}`",
        "",
        "## Regime closure",
        "- The earlier same-step run remains the bounded-negative subregime.",
        "- The official lens-axis flagship is the accepted cross-resolution strict-extension obstruction on the same fixed mechanism and support.",
        "- Parameter sensitivity is treated as regime structure, not as a contradiction between runs.",
        "- RM remains diagnostic-only where referenced by the underlying runs.",
        "",
        "## Artifacts",
    ]
    for key, value in sorted(output_paths.items()):
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def run_lens_axis_finalization(
    *,
    config_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> LensAxisFinalizationArtifacts:
    repo_root = get_repo_root(root)
    config = load_lens_axis_finalization_config(config_path)

    same_step_table = load_model(
        _resolve_repo_artifact(config.same_step_table_artifact, root=repo_root),
        kind="lens-axis-results",
    )
    assert isinstance(same_step_table, LensAxisTable)
    same_step_row = _same_step_row(
        table=same_step_table, point_id=config.same_step_flagship_point_id
    )
    same_step_summary = _load_json(
        config.same_step_negative_summary_artifact, root=repo_root
    )
    same_step_outcome = _load_json(
        config.same_step_negative_outcome_artifact, root=repo_root
    )
    same_step_support = _load_json(
        config.same_step_support_relation_artifact, root=repo_root
    )
    same_step_quotient = _load_json(
        config.same_step_quotient_diagnostics_artifact, root=repo_root
    )
    cross_search = load_model(
        _resolve_repo_artifact(
            config.cross_resolution_search_config_artifact, root=repo_root
        ),
        kind="lens-axis-search",
    )
    assert isinstance(cross_search, LensAxisSearch)
    cross_package_summary = _load_json(
        config.cross_resolution_package_build_summary_artifact,
        root=repo_root,
    )
    cross_provenance_summary = _load_json(
        config.cross_resolution_provenance_summary_artifact,
        root=repo_root,
    )
    cross_quotient_summary = _load_json(
        config.cross_resolution_quotient_summary_artifact,
        root=repo_root,
    )

    accepted_result = cross_quotient_summary["accepted_proposal_set_result"]
    natural_result = cross_quotient_summary["natural_pairing_result"]
    witness_classification = cross_quotient_summary["witness_classification"]

    if cross_provenance_summary.get("admissibility_classification") != "admissible":
        raise ValueError(
            "final lens-axis flagship requires admissible provenance classification"
        )
    if witness_classification != "accepted_proposal_obstruction":
        raise ValueError(
            "final lens-axis flagship requires witness_classification=accepted_proposal_obstruction"
        )
    if accepted_result.get("exact_feasible") is not False:
        raise ValueError(
            "final lens-axis flagship requires accepted_proposal_set_result.exact_feasible=false"
        )
    if natural_result is None or natural_result.get("exact_feasible") is not True:
        raise ValueError(
            "final lens-axis flagship requires a feasible natural-pairing control"
        )

    same_step_regime = LensAxisFinalizationRegime(
        regime_label="same_step_bounded_negative",
        varies="same-step lens/projection family on a fixed step_1 / resolution_k_4 support slice",
        fixed=(
            f"mechanism={same_step_row.fixed_mechanism_label}; "
            f"packaging_family={same_step_row.fixed_packaging_family_label}; "
            "single frozen slice and same support object"
        ),
        candidate_class=same_step_row.candidate_classification,
        quotient_witness_status=same_step_row.quotient_witness_status,
        flagship_artifact=same_step_row.quotient_feasibility_summary_path,
        control_artifact=config.same_step_negative_outcome_artifact,
        notes=[
            "Accepted proposals stayed quotient-feasible in the bounded same-step family.",
            "Candidate-subset witnesses remained present without becoming admitted obstruction.",
        ],
        flags=["same_step", "bounded_negative", "subregime_preserved"],
    )
    cross_resolution_regime = LensAxisFinalizationRegime(
        regime_label="cross_resolution_strict_extension",
        varies="cross-resolution obs_primary record algebra on the same support across k2/k4/k8/k14/k20",
        fixed=(
            f"mechanism={cross_search.fixed_mechanism_label}; "
            f"packaging_family={cross_search.fixed_packaging_family_label}; "
            "same run, same support object, same evaluation regime"
        ),
        candidate_class="strongly_nonextendable_candidate",
        quotient_witness_status="accepted_proposal_obstruction",
        flagship_artifact=config.cross_resolution_quotient_summary_artifact,
        control_artifact=config.cross_resolution_quotient_summary_artifact,
        notes=[
            "Natural-pairing control remains feasible inside the same quotient audit artifact.",
            "No admissibility relaxation was introduced for this flagship witness.",
        ],
        flags=["cross_resolution", "strict_extension", "canonical_flagship"],
    )

    final_outcome = LensAxisFinalOutcome(
        final_outcome_format_version="lens-axis-final-outcome.v1",
        lens_axis_id=config.lens_axis_id,
        final_axis_status="closed_with_cross_resolution_accepted_obstruction",
        canonical_flagship_case_id=config.canonical_flagship_case_id,
        same_step_table_artifact=config.same_step_table_artifact,
        same_step_negative_summary_artifact=config.same_step_negative_summary_artifact,
        same_step_negative_outcome_artifact=config.same_step_negative_outcome_artifact,
        cross_resolution_search_config_artifact=config.cross_resolution_search_config_artifact,
        cross_resolution_package_build_summary_artifact=config.cross_resolution_package_build_summary_artifact,
        cross_resolution_provenance_summary_artifact=config.cross_resolution_provenance_summary_artifact,
        cross_resolution_quotient_summary_artifact=config.cross_resolution_quotient_summary_artifact,
        accepted_only_survivor_count=accepted_result["survivor_count"],
        natural_pairing_survivor_count=natural_result["survivor_count"],
        accepted_only_failure_reason=accepted_result["exact_failure_reason"],
        accepted_proposal_obstruction=True,
        final_claim_level=config.final_claim_level,
        regimes=[same_step_regime, cross_resolution_regime],
        notes=[
            "Same-step bounded negative and cross-resolution accepted obstruction are treated as two lens-axis subregimes on the same fixed mechanism/support family.",
            "The cross-resolution strict-extension case is the canonical lens-axis flagship.",
            "The accepted obstruction remains quotient-backed and provenance-admissible.",
        ],
        flags=[
            "lens_axis_finalized",
            "same_step_negative_preserved",
            "cross_resolution_flagship",
        ],
        metadata={
            "same_step_flagship_point_id": config.same_step_flagship_point_id,
            "same_step_campaign_outcome_kind": same_step_outcome.get("outcome_kind"),
            "same_step_candidate_count_weakly_frustrated_candidate": (
                same_step_summary.get("counts_by_candidate_class", {}).get(
                    "weakly_frustrated_candidate", 0
                )
            ),
            "same_step_quotient_count_candidate_subset_quotient_witness": (
                same_step_summary.get("counts_by_quotient_witness_status", {}).get(
                    "candidate_subset_quotient_witness", 0
                )
            ),
            "cross_resolution_search_id": cross_search.search_id,
            "cross_resolution_accepted_context_count": cross_package_summary[
                "accepted_context_count"
            ],
            "cross_resolution_accepted_shared_event_proposal_count": cross_package_summary[
                "accepted_shared_event_proposal_count"
            ],
            "cross_resolution_provenance_classification": cross_provenance_summary[
                "admissibility_classification"
            ],
            "cross_resolution_witness_classification": witness_classification,
        },
    )

    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or config.output_label or config.lens_axis_id,
        timestamp=timestamp,
        root=repo_root,
    )
    summary_path = run_dir / "lens-axis-final-summary.json"
    note_path = run_dir / "lens-axis-final-note.md"
    regime_table_path = run_dir / "lens-axis-regime-table.json"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    outcome_path = run_dir / "th4-finalized.json"

    _write_json(summary_path, final_outcome.model_dump(mode="json"))
    _write_json(
        regime_table_path,
        {
            "lens_axis_id": config.lens_axis_id,
            "canonical_flagship_case_id": config.canonical_flagship_case_id,
            "regimes": [
                {
                    "regime_label": same_step_regime.regime_label,
                    "what_varies": same_step_regime.varies,
                    "what_is_fixed": same_step_regime.fixed,
                    "candidate_class": same_step_regime.candidate_class,
                    "quotient_witness_status": same_step_regime.quotient_witness_status,
                    "flagship_artifact": same_step_regime.flagship_artifact,
                    "control_artifact": same_step_regime.control_artifact,
                    "accepted_only_survivor_count": same_step_row.quotient_accepted_only_survivor_count,
                    "natural_pairing_survivor_count": same_step_row.quotient_natural_pairing_survivor_count,
                    "claim_level": same_step_row.claim_level_supported,
                },
                {
                    "regime_label": cross_resolution_regime.regime_label,
                    "what_varies": cross_resolution_regime.varies,
                    "what_is_fixed": cross_resolution_regime.fixed,
                    "candidate_class": cross_resolution_regime.candidate_class,
                    "quotient_witness_status": cross_resolution_regime.quotient_witness_status,
                    "flagship_artifact": cross_resolution_regime.flagship_artifact,
                    "control_artifact": cross_resolution_regime.control_artifact,
                    "accepted_only_survivor_count": accepted_result["survivor_count"],
                    "natural_pairing_survivor_count": natural_result["survivor_count"],
                    "claim_level": config.final_claim_level,
                },
            ],
            "support_relation_source": config.same_step_support_relation_artifact,
            "quotient_diagnostics_source": config.same_step_quotient_diagnostics_artifact,
            "same_step_support_relation_rows": len(same_step_support.get("rows", [])),
            "same_step_quotient_diagnostic_rows": len(
                same_step_quotient.get("rows", [])
            ),
        },
    )
    output_paths = {
        "summary": repo_relative_path(summary_path, root=repo_root),
        "note": repo_relative_path(note_path, root=repo_root),
        "regime_table": repo_relative_path(regime_table_path, root=repo_root),
        "result_note": repo_relative_path(result_note_path, root=repo_root),
        "manifest": repo_relative_path(manifest_path, root=repo_root),
        "th4_finalized": repo_relative_path(outcome_path, root=repo_root),
    }
    note_path.write_text(
        _build_note(
            config=config,
            same_step_row=same_step_row,
            same_step_summary=same_step_summary,
            cross_search=cross_search,
            cross_package_summary=cross_package_summary,
            cross_provenance_summary=cross_provenance_summary,
            cross_quotient_summary=cross_quotient_summary,
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )
    _write_json(outcome_path, final_outcome.model_dump(mode="json"))

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[config.lens_axis_id, config.canonical_flagship_case_id],
        metrics={
            "accepted_proposal_obstruction": True,
            "accepted_only_survivor_count": accepted_result["survivor_count"],
            "natural_pairing_survivor_count": natural_result["survivor_count"],
            "same_step_negative_preserved": True,
            "same_step_nontrivial_regime_count": len(
                same_step_summary.get("counts_by_candidate_class", {})
            ),
            "cross_resolution_accepted_context_count": cross_package_summary[
                "accepted_context_count"
            ],
            "cross_resolution_accepted_shared_event_proposal_count": cross_package_summary[
                "accepted_shared_event_proposal_count"
            ],
        },
        interpretation=(
            "The lens axis is closed as a two-regime result: a bounded same-step negative subregime and a canonical cross-resolution strict-extension regime whose accepted proposal set is quotient-infeasible on fixed mechanism and support."
        ),
        caveats=[
            "The canonical flagship remains a lens-axis result and does not by itself close the packaging axis.",
            "The same-step bounded-negative run remains part of the final record and is not overwritten.",
        ],
        artifact_refs=output_paths,
        metadata={
            "final_claim_level": config.final_claim_level,
            "same_step_flagship_point_id": config.same_step_flagship_point_id,
            "canonical_flagship_case_id": config.canonical_flagship_case_id,
        },
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
            "finalize-lens-axis",
            str(config_path),
        ],
        seed=seed,
        input_artifacts={
            "finalization_config": _artifact_ref(config_path),
            "same_step_table": config.same_step_table_artifact,
            "same_step_negative_summary": config.same_step_negative_summary_artifact,
            "same_step_negative_outcome": config.same_step_negative_outcome_artifact,
            "cross_resolution_search_config": config.cross_resolution_search_config_artifact,
            "cross_resolution_package_build_summary": config.cross_resolution_package_build_summary_artifact,
            "cross_resolution_provenance_summary": config.cross_resolution_provenance_summary_artifact,
            "cross_resolution_quotient_summary": config.cross_resolution_quotient_summary_artifact,
        },
        output_artifacts=output_paths,
        status="succeeded",
        git_commit=detect_git_commit(root=repo_root),
        metadata={
            "lens_axis_id": config.lens_axis_id,
            "canonical_flagship_case_id": config.canonical_flagship_case_id,
            "final_axis_status": final_outcome.final_axis_status,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return LensAxisFinalizationArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=repo_root),
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        regime_table_path=output_paths["regime_table"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        outcome_path=output_paths["th4_finalized"],
        final_outcome=final_outcome,
    )
