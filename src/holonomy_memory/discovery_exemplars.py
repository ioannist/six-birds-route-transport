from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .benchmarks import REPO_ROOT
from .discovery import DiscoveryCandidateRecord, run_discovery_search
from .discovery_diversity import (
    DiscoveryCandidateSignature,
    DiscoveryDiversityArtifacts,
    DiscoveryDiversitySummary,
    run_discovery_diversity_audit,
)
from .discovery_shortlist_robustness import (
    DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT,
    run_discovery_shortlist_robustness,
)
from .discovery_triage import compute_discovery_robustness_proxy
from .search_spaces import load_search_space_for_id


@dataclass(frozen=True)
class PromotedDiscoveryExemplar:
    qualified_id: str
    search_id: str
    candidate_id: str
    cluster_id: str
    class_label: str
    primary_interface_id: str
    primary_discrepancy_metric_value: Fraction
    primary_predictive_loop_score: Fraction
    survival_fraction: Fraction
    threshold: Fraction
    meets_threshold: bool
    distinctness_kind: str
    selection_reasons: tuple[str, ...]
    atlas_json_path: Path
    atlas_csv_path: Path
    atlas_note_path: Path
    shortlist_json_path: Path
    shortlist_csv_path: Path
    shortlist_note_path: Path
    robustness_json_path: Path
    robustness_csv_path: Path
    robustness_note_path: Path
    dedup_json_path: Path
    dedup_csv_path: Path
    dedup_note_path: Path


@dataclass(frozen=True)
class DiscoveryExemplarPromotionSummary:
    seed: int
    ordered_promoted_qualified_ids: tuple[str, ...]
    promoted_exemplars: tuple[PromotedDiscoveryExemplar, ...]
    promotion_rule_description: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryExemplarPromotionArtifacts:
    seed: int
    summary_json_path: Path
    summary_csv_path: Path
    index_note_path: Path
    individual_exemplar_note_paths: tuple[Path, ...]
    summary: DiscoveryExemplarPromotionSummary


@dataclass(frozen=True)
class _RobustnessEvidence:
    qualified_id: str
    search_id: str
    candidate_id: str
    class_label: str
    primary_interface_id: str
    primary_witness_count: int
    primary_discrepancy_metric_value: Fraction
    primary_predictive_loop_score: Fraction
    trial_count: int
    pass_count: int
    survival_fraction: Fraction
    threshold: Fraction
    meets_threshold: bool
    json_path: Path
    csv_path: Path
    note_path: Path


def promote_discovery_exemplars(
    *,
    seed: int = 0,
    output_root: str | Path | None = None,
    max_exemplars: int = 2,
) -> DiscoveryExemplarPromotionArtifacts:
    if max_exemplars < 1 or max_exemplars > 2:
        raise ValueError("max_exemplars must be 1 or 2")

    root = Path(output_root) if output_root is not None else REPO_ROOT
    diversity_artifacts = run_discovery_diversity_audit(seed=seed, output_root=root)
    audit_candidates = _build_audit_candidates(diversity_artifacts.summary)
    robustness_by_qualified_id = complete_exemplar_robustness_evidence(
        audit_candidates=audit_candidates,
        seed=seed,
        output_root=root,
    )
    promoted = _select_promoted_exemplars(
        audit_candidates=audit_candidates,
        robustness_by_qualified_id=robustness_by_qualified_id,
        diversity_artifacts=diversity_artifacts,
        max_exemplars=max_exemplars,
        output_root=root,
    )
    summary = DiscoveryExemplarPromotionSummary(
        seed=seed,
        ordered_promoted_qualified_ids=tuple(
            exemplar.qualified_id for exemplar in promoted
        ),
        promoted_exemplars=tuple(promoted),
        promotion_rule_description=(
            "rank by meets_threshold, survival_fraction, discrepancy, predictive_loop_score, "
            "then audit-order tie-break; always keep the top candidate and add a second only "
            "if it also meets threshold and is non-redundant by search_id or exact structure"
        ),
        warnings=(),
    )
    return write_discovery_exemplar_artifacts(summary=summary, output_root=root)


def complete_exemplar_robustness_evidence(
    *,
    audit_candidates: tuple["_AuditCandidate", ...],
    seed: int,
    output_root: str | Path | None = None,
) -> dict[str, _RobustnessEvidence]:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    evidence_by_qualified_id: dict[str, _RobustnessEvidence] = {}

    cyclic_artifacts = run_discovery_shortlist_robustness(
        search_id="cyclic_memory_small",
        seed=seed,
        output_root=root,
    )
    for entry in cyclic_artifacts.summary.entries:
        qualified_id = f"{entry.search_id}:{entry.candidate_id}"
        evidence_by_qualified_id[qualified_id] = _RobustnessEvidence(
            qualified_id=qualified_id,
            search_id=entry.search_id,
            candidate_id=entry.candidate_id,
            class_label=entry.class_label,
            primary_interface_id=entry.primary_interface_id,
            primary_witness_count=entry.primary_witness_count,
            primary_discrepancy_metric_value=entry.primary_discrepancy_metric_value,
            primary_predictive_loop_score=entry.primary_predictive_loop_score,
            trial_count=entry.trial_count,
            pass_count=entry.pass_count,
            survival_fraction=entry.survival_fraction,
            threshold=entry.threshold,
            meets_threshold=entry.meets_threshold,
            json_path=cyclic_artifacts.summary_json_path,
            csv_path=cyclic_artifacts.summary_csv_path,
            note_path=cyclic_artifacts.summary_note_path,
        )

    missing_candidates = [
        candidate
        for candidate in audit_candidates
        if candidate.qualified_id not in evidence_by_qualified_id
    ]
    if not missing_candidates:
        return evidence_by_qualified_id

    candidate_records_by_search: dict[str, dict[str, DiscoveryCandidateRecord]] = {}
    for search_id in sorted({candidate.search_id for candidate in missing_candidates}):
        atlas_artifacts = run_discovery_search(
            search_id=search_id,
            seed=seed,
            output_root=root,
        )
        candidate_records_by_search[search_id] = {
            record.candidate_spec.candidate_id: record
            for record in atlas_artifacts.atlas.candidate_records
        }

    for candidate in missing_candidates:
        candidate_record = candidate_records_by_search[candidate.search_id][candidate.candidate_id]
        evidence_by_qualified_id[candidate.qualified_id] = _run_single_candidate_promotion_robustness(
            candidate=candidate,
            candidate_record=candidate_record,
            seed=seed,
            output_root=root,
        )
    return evidence_by_qualified_id


def write_discovery_exemplar_artifacts(
    *,
    summary: DiscoveryExemplarPromotionSummary,
    output_root: str | Path | None = None,
) -> DiscoveryExemplarPromotionArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    summary_json_path = root / "artifacts" / "results" / "discovery" / "promoted_exemplars.json"
    summary_csv_path = root / "artifacts" / "tables" / "discovery_promoted_exemplars.csv"
    index_note_path = root / "docs" / "results" / "discovery_exemplars.md"
    summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_csv_path.parent.mkdir(parents=True, exist_ok=True)
    index_note_path.parent.mkdir(parents=True, exist_ok=True)

    summary_json_path.write_text(
        json.dumps(_summary_payload(summary), indent=2) + "\n",
        encoding="utf-8",
    )
    _write_summary_csv(summary, summary_csv_path)
    index_note_path.write_text(
        _build_index_note(summary, summary_json_path, summary_csv_path, index_note_path),
        encoding="utf-8",
    )

    individual_note_paths: list[Path] = []
    for exemplar in summary.promoted_exemplars:
        note_path = (
            root
            / "docs"
            / "results"
            / f"exemplar.{exemplar.search_id}.{exemplar.candidate_id}.md"
        )
        note_path.write_text(_build_exemplar_note(exemplar, note_path), encoding="utf-8")
        individual_note_paths.append(note_path)

    return DiscoveryExemplarPromotionArtifacts(
        seed=summary.seed,
        summary_json_path=summary_json_path,
        summary_csv_path=summary_csv_path,
        index_note_path=index_note_path,
        individual_exemplar_note_paths=tuple(individual_note_paths),
        summary=summary,
    )


@dataclass(frozen=True)
class _AuditCandidate:
    qualified_id: str
    search_id: str
    candidate_id: str
    cluster_id: str
    distinctness_kind: str
    signature: DiscoveryCandidateSignature
    audit_order: int


def _build_audit_candidates(
    summary: DiscoveryDiversitySummary,
) -> tuple[_AuditCandidate, ...]:
    signature_by_qualified_id = {
        signature.qualified_candidate_id: signature
        for signature in summary.candidate_signatures
    }
    candidates: list[_AuditCandidate] = []
    for audit_order, cluster in enumerate(summary.clusters):
        qualified_id = f"{cluster.exemplar_search_id}:{cluster.exemplar_candidate_id}"
        candidates.append(
            _AuditCandidate(
                qualified_id=qualified_id,
                search_id=cluster.exemplar_search_id,
                candidate_id=cluster.exemplar_candidate_id,
                cluster_id=cluster.cluster_id,
                distinctness_kind=cluster.match_kind,
                signature=signature_by_qualified_id[qualified_id],
                audit_order=audit_order,
            )
        )
    return tuple(candidates)


def _run_single_candidate_promotion_robustness(
    *,
    candidate: _AuditCandidate,
    candidate_record: DiscoveryCandidateRecord,
    seed: int,
    output_root: str | Path,
) -> _RobustnessEvidence:
    root = Path(output_root)
    search_space = load_search_space_for_id(candidate.search_id)
    survival_fraction = compute_discovery_robustness_proxy(
        record=candidate_record,
        search_space=search_space,
        seed=seed,
        proxy_trial_count=DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT,
    )
    threshold = _threshold_for_class_label(candidate.signature.class_label)
    pass_count = int(survival_fraction * DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT)
    meets_threshold = survival_fraction >= threshold
    json_path = (
        root
        / "artifacts"
        / "results"
        / "discovery"
        / f"{candidate.search_id}.{candidate.candidate_id}.promotion_robustness.json"
    )
    csv_path = (
        root
        / "artifacts"
        / "tables"
        / f"discovery_{candidate.search_id}_{candidate.candidate_id}_promotion_robustness.csv"
    )
    note_path = (
        root
        / "docs"
        / "results"
        / f"{candidate.search_id}.{candidate.candidate_id}.promotion_robustness.md"
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "qualified_id": candidate.qualified_id,
        "search_id": candidate.search_id,
        "candidate_id": candidate.candidate_id,
        "class_label": candidate.signature.class_label,
        "primary_interface_id": candidate.signature.primary_interface_id,
        "trial_count": DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT,
        "pass_count": pass_count,
        "survival_fraction": float(survival_fraction),
        "survival_fraction_exact": _fraction_string(survival_fraction),
        "threshold": float(threshold),
        "threshold_exact": _fraction_string(threshold),
        "meets_threshold": meets_threshold,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "qualified_id",
                "search_id",
                "candidate_id",
                "class_label",
                "primary_interface_id",
                "trial_count",
                "pass_count",
                "survival_fraction",
                "threshold",
                "meets_threshold",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "qualified_id": candidate.qualified_id,
                "search_id": candidate.search_id,
                "candidate_id": candidate.candidate_id,
                "class_label": candidate.signature.class_label,
                "primary_interface_id": candidate.signature.primary_interface_id,
                "trial_count": DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT,
                "pass_count": pass_count,
                "survival_fraction": _fraction_string(survival_fraction),
                "threshold": _fraction_string(threshold),
                "meets_threshold": str(meets_threshold).lower(),
            }
        )
    note_path.write_text(
        "\n".join(
            [
                f"# Promotion Robustness: {candidate.qualified_id}",
                "",
                f"- qualified id: {candidate.qualified_id}",
                f"- class label: {candidate.signature.class_label}",
                f"- primary interface id: {candidate.signature.primary_interface_id}",
                f"- trial count: {DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT}",
                f"- pass count: {pass_count}",
                f"- survival fraction: {_fraction_string(survival_fraction)}",
                f"- threshold: {_fraction_string(threshold)}",
                f"- meets threshold: {str(meets_threshold).lower()}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return _RobustnessEvidence(
        qualified_id=candidate.qualified_id,
        search_id=candidate.search_id,
        candidate_id=candidate.candidate_id,
        class_label=candidate.signature.class_label,
        primary_interface_id=candidate.signature.primary_interface_id,
        primary_witness_count=candidate.signature.primary_witness_count,
        primary_discrepancy_metric_value=candidate.signature.primary_discrepancy_metric_value,
        primary_predictive_loop_score=candidate.signature.primary_predictive_loop_score,
        trial_count=DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT,
        pass_count=pass_count,
        survival_fraction=survival_fraction,
        threshold=threshold,
        meets_threshold=meets_threshold,
        json_path=json_path,
        csv_path=csv_path,
        note_path=note_path,
    )


def _select_promoted_exemplars(
    *,
    audit_candidates: tuple[_AuditCandidate, ...],
    robustness_by_qualified_id: dict[str, _RobustnessEvidence],
    diversity_artifacts: DiscoveryDiversityArtifacts,
    max_exemplars: int,
    output_root: str | Path,
) -> list[PromotedDiscoveryExemplar]:
    root = Path(output_root)
    ranked_candidates = sorted(
        audit_candidates,
        key=lambda candidate: (
            not robustness_by_qualified_id[candidate.qualified_id].meets_threshold,
            -float(robustness_by_qualified_id[candidate.qualified_id].survival_fraction),
            -float(candidate.signature.primary_discrepancy_metric_value),
            -float(candidate.signature.primary_predictive_loop_score),
            candidate.audit_order,
        ),
    )
    promoted_candidates: list[_AuditCandidate] = [ranked_candidates[0]]
    if max_exemplars > 1:
        first = promoted_candidates[0]
        for candidate in ranked_candidates[1:]:
            evidence = robustness_by_qualified_id[candidate.qualified_id]
            if not evidence.meets_threshold:
                continue
            if candidate.search_id != first.search_id:
                promoted_candidates.append(candidate)
                break
        if len(promoted_candidates) == 1:
            for candidate in ranked_candidates[1:]:
                evidence = robustness_by_qualified_id[candidate.qualified_id]
                if not evidence.meets_threshold:
                    continue
                if candidate.signature.structural_signature != first.signature.structural_signature:
                    promoted_candidates.append(candidate)
                    break

    return [
        _build_promoted_exemplar(
            candidate=candidate,
            robustness=robustness_by_qualified_id[candidate.qualified_id],
            diversity_artifacts=diversity_artifacts,
            output_root=root,
            first_promoted=promoted_candidates[0],
        )
        for candidate in promoted_candidates
    ]


def _build_promoted_exemplar(
    *,
    candidate: _AuditCandidate,
    robustness: _RobustnessEvidence,
    diversity_artifacts: DiscoveryDiversityArtifacts,
    output_root: Path,
    first_promoted: _AuditCandidate,
) -> PromotedDiscoveryExemplar:
    atlas_json_path = output_root / "artifacts" / "results" / "discovery" / f"{candidate.search_id}.atlas.json"
    atlas_csv_path = output_root / "artifacts" / "tables" / f"discovery_{candidate.search_id}.csv"
    atlas_note_path = output_root / "docs" / "results" / f"{candidate.search_id}.atlas.md"
    shortlist_json_path = output_root / "artifacts" / "results" / "discovery" / f"{candidate.search_id}.shortlist.json"
    shortlist_csv_path = output_root / "artifacts" / "tables" / f"discovery_{candidate.search_id}_shortlist.csv"
    shortlist_note_path = output_root / "docs" / "results" / f"{candidate.search_id}.shortlist.md"
    selection_reasons = _selection_reasons(
        candidate=candidate,
        robustness=robustness,
        first_promoted=first_promoted,
    )
    return PromotedDiscoveryExemplar(
        qualified_id=candidate.qualified_id,
        search_id=candidate.search_id,
        candidate_id=candidate.candidate_id,
        cluster_id=candidate.cluster_id,
        class_label=candidate.signature.class_label,
        primary_interface_id=candidate.signature.primary_interface_id,
        primary_discrepancy_metric_value=candidate.signature.primary_discrepancy_metric_value,
        primary_predictive_loop_score=candidate.signature.primary_predictive_loop_score,
        survival_fraction=robustness.survival_fraction,
        threshold=robustness.threshold,
        meets_threshold=robustness.meets_threshold,
        distinctness_kind=candidate.distinctness_kind,
        selection_reasons=selection_reasons,
        atlas_json_path=atlas_json_path,
        atlas_csv_path=atlas_csv_path,
        atlas_note_path=atlas_note_path,
        shortlist_json_path=shortlist_json_path,
        shortlist_csv_path=shortlist_csv_path,
        shortlist_note_path=shortlist_note_path,
        robustness_json_path=robustness.json_path,
        robustness_csv_path=robustness.csv_path,
        robustness_note_path=robustness.note_path,
        dedup_json_path=diversity_artifacts.summary_json_path,
        dedup_csv_path=diversity_artifacts.summary_csv_path,
        dedup_note_path=diversity_artifacts.summary_note_path,
    )


def _selection_reasons(
    *,
    candidate: _AuditCandidate,
    robustness: _RobustnessEvidence,
    first_promoted: _AuditCandidate,
) -> tuple[str, ...]:
    reasons = [
        "high_discrepancy",
        "predictive_loop_positive"
        if candidate.signature.primary_predictive_loop_score > 0
        else "predictive_loop_zero",
        "robustness_above_threshold"
        if robustness.meets_threshold
        else "robustness_below_threshold",
    ]
    if candidate.distinctness_kind == "singleton":
        reasons.append("singleton_cluster")
    else:
        reasons.append(candidate.distinctness_kind)
    if candidate.qualified_id != first_promoted.qualified_id:
        if candidate.search_id != first_promoted.search_id:
            reasons.append("cross_space_distinct")
        elif (
            candidate.signature.structural_signature
            != first_promoted.signature.structural_signature
        ):
            reasons.append("distinct_structural_signature")
    return tuple(reasons)


def _summary_payload(summary: DiscoveryExemplarPromotionSummary) -> dict[str, object]:
    return {
        "seed": summary.seed,
        "ordered_promoted_qualified_ids": list(summary.ordered_promoted_qualified_ids),
        "promotion_rule_description": summary.promotion_rule_description,
        "promoted_exemplars": [
            {
                "qualified_id": exemplar.qualified_id,
                "search_id": exemplar.search_id,
                "candidate_id": exemplar.candidate_id,
                "cluster_id": exemplar.cluster_id,
                "class_label": exemplar.class_label,
                "primary_interface_id": exemplar.primary_interface_id,
                "primary_discrepancy_metric_value": float(
                    exemplar.primary_discrepancy_metric_value
                ),
                "primary_discrepancy_metric_value_exact": _fraction_string(
                    exemplar.primary_discrepancy_metric_value
                ),
                "primary_predictive_loop_score": float(exemplar.primary_predictive_loop_score),
                "primary_predictive_loop_score_exact": _fraction_string(
                    exemplar.primary_predictive_loop_score
                ),
                "survival_fraction": float(exemplar.survival_fraction),
                "survival_fraction_exact": _fraction_string(exemplar.survival_fraction),
                "threshold": float(exemplar.threshold),
                "threshold_exact": _fraction_string(exemplar.threshold),
                "meets_threshold": exemplar.meets_threshold,
                "distinctness_kind": exemplar.distinctness_kind,
                "selection_reasons": list(exemplar.selection_reasons),
                "traceability_paths": {
                    "atlas_json_path": _relative_string(exemplar.atlas_json_path),
                    "atlas_csv_path": _relative_string(exemplar.atlas_csv_path),
                    "atlas_note_path": _relative_string(exemplar.atlas_note_path),
                    "shortlist_json_path": _relative_string(exemplar.shortlist_json_path),
                    "shortlist_csv_path": _relative_string(exemplar.shortlist_csv_path),
                    "shortlist_note_path": _relative_string(exemplar.shortlist_note_path),
                    "robustness_json_path": _relative_string(exemplar.robustness_json_path),
                    "robustness_csv_path": _relative_string(exemplar.robustness_csv_path),
                    "robustness_note_path": _relative_string(exemplar.robustness_note_path),
                    "dedup_json_path": _relative_string(exemplar.dedup_json_path),
                    "dedup_csv_path": _relative_string(exemplar.dedup_csv_path),
                    "dedup_note_path": _relative_string(exemplar.dedup_note_path),
                },
            }
            for exemplar in summary.promoted_exemplars
        ],
        "warnings": list(summary.warnings),
    }


def _write_summary_csv(
    summary: DiscoveryExemplarPromotionSummary,
    csv_path: Path,
) -> None:
    fieldnames = [
        "qualified_id",
        "search_id",
        "candidate_id",
        "cluster_id",
        "class_label",
        "primary_interface_id",
        "primary_discrepancy_metric_value",
        "primary_predictive_loop_score",
        "survival_fraction",
        "threshold",
        "meets_threshold",
        "distinctness_kind",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for exemplar in summary.promoted_exemplars:
            writer.writerow(
                {
                    "qualified_id": exemplar.qualified_id,
                    "search_id": exemplar.search_id,
                    "candidate_id": exemplar.candidate_id,
                    "cluster_id": exemplar.cluster_id,
                    "class_label": exemplar.class_label,
                    "primary_interface_id": exemplar.primary_interface_id,
                    "primary_discrepancy_metric_value": _fraction_string(
                        exemplar.primary_discrepancy_metric_value
                    ),
                    "primary_predictive_loop_score": _fraction_string(
                        exemplar.primary_predictive_loop_score
                    ),
                    "survival_fraction": _fraction_string(exemplar.survival_fraction),
                    "threshold": _fraction_string(exemplar.threshold),
                    "meets_threshold": str(exemplar.meets_threshold).lower(),
                    "distinctness_kind": exemplar.distinctness_kind,
                }
            )


def _build_index_note(
    summary: DiscoveryExemplarPromotionSummary,
    summary_json_path: Path,
    summary_csv_path: Path,
    index_note_path: Path,
) -> str:
    lines = [
        "# Discovery Exemplars",
        "",
        f"- seed: {summary.seed}",
        f"- promoted qualified ids: {', '.join(summary.ordered_promoted_qualified_ids)}",
        f"- summary json path: {_relative_string(summary_json_path)}",
        f"- summary csv path: {_relative_string(summary_csv_path)}",
        f"- index note path: {_relative_string(index_note_path)}",
        "",
        "| qualified_id | class_label | discrepancy | predictive_loop_score | survival_fraction | threshold | meets_threshold | distinctness_kind |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for exemplar in summary.promoted_exemplars:
        lines.append(
            "| "
            f"{exemplar.qualified_id} | "
            f"{exemplar.class_label} | "
            f"{_fraction_string(exemplar.primary_discrepancy_metric_value)} | "
            f"{_fraction_string(exemplar.primary_predictive_loop_score)} | "
            f"{_fraction_string(exemplar.survival_fraction)} | "
            f"{_fraction_string(exemplar.threshold)} | "
            f"{str(exemplar.meets_threshold).lower()} | "
            f"{exemplar.distinctness_kind} |"
        )
    lines.extend(
        [
            "",
            "- conclusion: these exemplars were promoted because they combine the strongest bounded robustness with nontrivial discrepancy, loop-signal evidence, and explicit dedup distinctness.",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_exemplar_note(
    exemplar: PromotedDiscoveryExemplar,
    note_path: Path,
) -> str:
    return (
        "\n".join(
            [
                f"# Exemplar {exemplar.qualified_id}",
                "",
                f"- qualified id: {exemplar.qualified_id}",
                f"- search id: {exemplar.search_id}",
                f"- candidate id: {exemplar.candidate_id}",
                f"- cluster id: {exemplar.cluster_id}",
                f"- class label: {exemplar.class_label}",
                f"- primary interface id: {exemplar.primary_interface_id}",
                f"- discrepancy: {_fraction_string(exemplar.primary_discrepancy_metric_value)}",
                f"- predictive loop score: {_fraction_string(exemplar.primary_predictive_loop_score)}",
                f"- survival fraction: {_fraction_string(exemplar.survival_fraction)}",
                f"- threshold: {_fraction_string(exemplar.threshold)}",
                f"- meets threshold: {str(exemplar.meets_threshold).lower()}",
                f"- distinctness kind: {exemplar.distinctness_kind}",
                f"- note path: {_relative_string(note_path)}",
                "",
                "## Selection Reasons",
                "",
                *[f"- {reason}" for reason in exemplar.selection_reasons],
                "",
                "## Traceability",
                "",
                f"- atlas json path: {_relative_string(exemplar.atlas_json_path)}",
                f"- atlas csv path: {_relative_string(exemplar.atlas_csv_path)}",
                f"- atlas note path: {_relative_string(exemplar.atlas_note_path)}",
                f"- shortlist json path: {_relative_string(exemplar.shortlist_json_path)}",
                f"- shortlist csv path: {_relative_string(exemplar.shortlist_csv_path)}",
                f"- shortlist note path: {_relative_string(exemplar.shortlist_note_path)}",
                f"- robustness json path: {_relative_string(exemplar.robustness_json_path)}",
                f"- robustness csv path: {_relative_string(exemplar.robustness_csv_path)}",
                f"- robustness note path: {_relative_string(exemplar.robustness_note_path)}",
                f"- dedup json path: {_relative_string(exemplar.dedup_json_path)}",
                f"- dedup csv path: {_relative_string(exemplar.dedup_csv_path)}",
                f"- dedup note path: {_relative_string(exemplar.dedup_note_path)}",
                "",
                "- conclusion: this exemplar is worth follow-up because it survived bounded robustness at a competitive rate and remained distinct in the HM-020C dedup audit.",
            ]
        )
        + "\n"
    )


def _threshold_for_class_label(class_label: str) -> Fraction:
    return {
        "coherent_candidate": Fraction(1, 2),
        "dissipative": Fraction(1, 2),
        "flat": Fraction(4, 5),
    }[class_label]


def _fraction_string(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _relative_string(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
