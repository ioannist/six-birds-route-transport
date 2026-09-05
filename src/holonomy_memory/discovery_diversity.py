from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .benchmarks import REPO_ROOT
from .discovery_multispace import (
    DEFAULT_MULTISPACE_SEARCH_IDS,
    MultiSpaceDiscoverySummary,
    run_multispace_discovery,
)


@dataclass(frozen=True)
class DiscoveryCandidateSignature:
    search_id: str
    candidate_id: str
    support_size: int
    interface_count: int
    carrier_family: str
    route_update_family: str
    observable_family: str
    continuation_catalog_family: str
    primary_interface_id: str
    class_label: str
    primary_current_quotient_size: int
    primary_predictive_quotient_size: int
    primary_max_fiber_size: int
    primary_witness_count: int
    primary_discrepancy_metric_value: Fraction
    primary_current_loop_score: Fraction
    primary_predictive_loop_score: Fraction

    @property
    def qualified_candidate_id(self) -> str:
        return f"{self.search_id}:{self.candidate_id}"

    @property
    def structural_signature(self) -> tuple[object, ...]:
        return (
            self.support_size,
            self.interface_count,
            self.carrier_family,
            self.route_update_family,
            self.observable_family,
            self.continuation_catalog_family,
        )

    @property
    def exact_primary_metric_signature(self) -> tuple[object, ...]:
        return (
            self.class_label,
            self.primary_current_quotient_size,
            self.primary_predictive_quotient_size,
            self.primary_max_fiber_size,
            self.primary_witness_count,
            self.primary_discrepancy_metric_value,
            self.primary_current_loop_score,
            self.primary_predictive_loop_score,
        )

    @property
    def behavior_signature(self) -> tuple[object, ...]:
        return (
            self.class_label,
            self.primary_current_quotient_size,
            self.primary_predictive_quotient_size,
            self.primary_max_fiber_size,
            self.primary_witness_count,
            self.primary_discrepancy_metric_value > 0,
            self.primary_predictive_loop_score > 0,
            self.primary_current_loop_score == 0,
        )


@dataclass(frozen=True)
class DiscoveryDedupCluster:
    cluster_id: str
    match_kind: str
    member_candidate_ids: tuple[str, ...]
    member_search_ids: tuple[str, ...]
    exemplar_candidate_id: str
    exemplar_search_id: str
    cluster_size: int
    shared_structural_signature: tuple[tuple[str, object], ...]
    coarse_metric_summary: tuple[tuple[str, object], ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryDiversitySummary:
    seed: int
    source_search_ids: tuple[str, ...]
    ordered_shortlisted_candidate_ids_audited: tuple[str, ...]
    total_shortlisted_candidate_count: int
    candidate_signatures: tuple[DiscoveryCandidateSignature, ...]
    clusters: tuple[DiscoveryDedupCluster, ...]
    unique_exemplar_count: int
    exact_duplicate_cluster_count: int
    near_duplicate_cluster_count: int
    singleton_count: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryDiversityArtifacts:
    seed: int
    summary_json_path: Path
    summary_csv_path: Path
    summary_note_path: Path
    summary: DiscoveryDiversitySummary


def run_discovery_diversity_audit(
    *,
    seed: int = 0,
    output_root: str | Path | None = None,
    search_ids: tuple[str, ...] = DEFAULT_MULTISPACE_SEARCH_IDS,
) -> DiscoveryDiversityArtifacts:
    multispace_artifacts = run_multispace_discovery(
        seed=seed,
        output_root=output_root,
        search_ids=search_ids,
    )
    candidate_signatures = collect_multispace_shortlisted_candidates(
        multispace_artifacts.summary,
        output_root=output_root,
    )
    clusters = cluster_discovery_candidates(candidate_signatures)
    summary = DiscoveryDiversitySummary(
        seed=seed,
        source_search_ids=multispace_artifacts.summary.search_ids,
        ordered_shortlisted_candidate_ids_audited=tuple(
            signature.qualified_candidate_id for signature in candidate_signatures
        ),
        total_shortlisted_candidate_count=len(candidate_signatures),
        candidate_signatures=candidate_signatures,
        clusters=clusters,
        unique_exemplar_count=len(clusters),
        exact_duplicate_cluster_count=sum(
            1 for cluster in clusters if cluster.match_kind == "exact_duplicate"
        ),
        near_duplicate_cluster_count=sum(
            1 for cluster in clusters if cluster.match_kind == "near_duplicate"
        ),
        singleton_count=sum(1 for cluster in clusters if cluster.match_kind == "singleton"),
        warnings=(),
    )
    return write_discovery_diversity_summary(summary=summary, output_root=output_root)


def collect_multispace_shortlisted_candidates(
    summary: MultiSpaceDiscoverySummary,
    *,
    output_root: str | Path | None = None,
) -> tuple[DiscoveryCandidateSignature, ...]:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    collected: list[DiscoveryCandidateSignature] = []
    for entry in summary.entries:
        if entry.shortlist_count == 0 or entry.shortlist_json_path is None:
            continue
        shortlist_payload = _load_json(_resolve_path(root, entry.shortlist_json_path))
        atlas_payload = _load_json(_resolve_path(root, entry.atlas_json_path))
        atlas_candidates = {
            candidate["candidate_id"]: candidate
            for candidate in atlas_payload["candidates"]
        }
        for shortlist_entry in shortlist_payload["combined_shortlist"]:
            candidate_payload = atlas_candidates[shortlist_entry["candidate_id"]]
            collected.append(_signature_from_candidate_payload(entry.search_id, candidate_payload))
    return tuple(collected)


def cluster_discovery_candidates(
    candidate_signatures: tuple[DiscoveryCandidateSignature, ...],
) -> tuple[DiscoveryDedupCluster, ...]:
    clusters: list[DiscoveryDedupCluster] = []
    assigned: set[int] = set()
    cluster_index = 0

    for index, signature in enumerate(candidate_signatures):
        if index in assigned:
            continue
        member_indices = [
            probe_index
            for probe_index in range(index, len(candidate_signatures))
            if probe_index not in assigned
            and candidate_signatures[probe_index].structural_signature
            == signature.structural_signature
            and candidate_signatures[probe_index].exact_primary_metric_signature
            == signature.exact_primary_metric_signature
        ]
        if len(member_indices) <= 1:
            continue
        clusters.append(
            _build_cluster(
                cluster_index=cluster_index,
                match_kind="exact_duplicate",
                member_indices=member_indices,
                candidate_signatures=candidate_signatures,
            )
        )
        cluster_index += 1
        assigned.update(member_indices)

    for index, signature in enumerate(candidate_signatures):
        if index in assigned:
            continue
        member_indices = [
            probe_index
            for probe_index in range(index, len(candidate_signatures))
            if probe_index not in assigned
            and candidate_signatures[probe_index].structural_signature
            == signature.structural_signature
            and candidate_signatures[probe_index].behavior_signature
            == signature.behavior_signature
        ]
        if len(member_indices) <= 1:
            continue
        clusters.append(
            _build_cluster(
                cluster_index=cluster_index,
                match_kind="near_duplicate",
                member_indices=member_indices,
                candidate_signatures=candidate_signatures,
            )
        )
        cluster_index += 1
        assigned.update(member_indices)

    for index, signature in enumerate(candidate_signatures):
        if index in assigned:
            continue
        clusters.append(
            _build_cluster(
                cluster_index=cluster_index,
                match_kind="singleton",
                member_indices=[index],
                candidate_signatures=candidate_signatures,
            )
        )
        cluster_index += 1
        assigned.add(index)

    return tuple(clusters)


def write_discovery_diversity_summary(
    *,
    summary: DiscoveryDiversitySummary,
    output_root: str | Path | None = None,
) -> DiscoveryDiversityArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    json_path = root / "artifacts" / "results" / "discovery" / "multi_space.dedup.json"
    csv_path = root / "artifacts" / "tables" / "discovery_multi_space_dedup.csv"
    note_path = root / "docs" / "results" / "multi_space.dedup.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(_summary_payload(summary), indent=2) + "\n",
        encoding="utf-8",
    )
    _write_summary_csv(summary, csv_path)
    note_path.write_text(
        _build_summary_note(summary, json_path, csv_path, note_path),
        encoding="utf-8",
    )
    return DiscoveryDiversityArtifacts(
        seed=summary.seed,
        summary_json_path=json_path,
        summary_csv_path=csv_path,
        summary_note_path=note_path,
        summary=summary,
    )


def _build_cluster(
    *,
    cluster_index: int,
    match_kind: str,
    member_indices: list[int],
    candidate_signatures: tuple[DiscoveryCandidateSignature, ...],
) -> DiscoveryDedupCluster:
    members = [candidate_signatures[index] for index in member_indices]
    exemplar = members[0]
    notes: tuple[str, ...]
    if match_kind == "exact_duplicate":
        notes = ("exact structural and primary metric signatures match",)
    elif match_kind == "near_duplicate":
        notes = ("exact structural signature and coarse behavior signature match",)
    else:
        notes = ()
    return DiscoveryDedupCluster(
        cluster_id=f"cluster_{cluster_index:03d}",
        match_kind=match_kind,
        member_candidate_ids=tuple(member.candidate_id for member in members),
        member_search_ids=tuple(member.search_id for member in members),
        exemplar_candidate_id=exemplar.candidate_id,
        exemplar_search_id=exemplar.search_id,
        cluster_size=len(members),
        shared_structural_signature=_structural_signature_pairs(exemplar),
        coarse_metric_summary=_coarse_metric_summary_pairs(exemplar),
        notes=notes,
    )


def _signature_from_candidate_payload(
    search_id: str,
    candidate_payload: dict[str, Any],
) -> DiscoveryCandidateSignature:
    spec = candidate_payload["candidate_spec"]
    primary_metrics = candidate_payload["primary_metrics"]
    return DiscoveryCandidateSignature(
        search_id=search_id,
        candidate_id=candidate_payload["candidate_id"],
        support_size=spec["support_size"],
        interface_count=spec["interface_count"],
        carrier_family=spec["carrier_family"],
        route_update_family=spec["route_update_family"],
        observable_family=spec["observable_family"],
        continuation_catalog_family=spec["continuation_catalog_family"],
        primary_interface_id=candidate_payload["primary_interface_id"],
        class_label=candidate_payload["candidate_label"],
        primary_current_quotient_size=primary_metrics["current_quotient_size"],
        primary_predictive_quotient_size=primary_metrics["predictive_quotient_size"],
        primary_max_fiber_size=primary_metrics["max_fiber_size"],
        primary_witness_count=primary_metrics["witness_count"],
        primary_discrepancy_metric_value=Fraction(
            primary_metrics["discrepancy_metric_value_exact"]
        ),
        primary_current_loop_score=Fraction(primary_metrics["current_loop_score_exact"]),
        primary_predictive_loop_score=Fraction(
            primary_metrics["predictive_loop_score_exact"]
        ),
    )


def _summary_payload(summary: DiscoveryDiversitySummary) -> dict[str, object]:
    return {
        "seed": summary.seed,
        "source_search_ids": list(summary.source_search_ids),
        "ordered_shortlisted_candidate_ids_audited": list(
            summary.ordered_shortlisted_candidate_ids_audited
        ),
        "total_shortlisted_candidate_count": summary.total_shortlisted_candidate_count,
        "unique_exemplar_count": summary.unique_exemplar_count,
        "cluster_counts_by_kind": {
            "exact_duplicate": summary.exact_duplicate_cluster_count,
            "near_duplicate": summary.near_duplicate_cluster_count,
            "singleton": summary.singleton_count,
        },
        "clusters": [
            {
                "cluster_id": cluster.cluster_id,
                "match_kind": cluster.match_kind,
                "exemplar_candidate_id": cluster.exemplar_candidate_id,
                "exemplar_search_id": cluster.exemplar_search_id,
                "member_candidate_ids": list(cluster.member_candidate_ids),
                "member_search_ids": list(cluster.member_search_ids),
                "cluster_size": cluster.cluster_size,
                "shared_structural_signature": {
                    key: value for key, value in cluster.shared_structural_signature
                },
                "coarse_metric_summary": {
                    key: value for key, value in cluster.coarse_metric_summary
                },
                "notes": list(cluster.notes),
            }
            for cluster in summary.clusters
        ],
        "warnings": list(summary.warnings),
    }


def _write_summary_csv(summary: DiscoveryDiversitySummary, csv_path: Path) -> None:
    fieldnames = [
        "search_id",
        "candidate_id",
        "cluster_id",
        "match_kind",
        "is_exemplar",
        "support_size",
        "interface_count",
        "carrier_family",
        "route_update_family",
        "observable_family",
        "continuation_catalog_family",
        "class_label",
        "primary_interface_id",
        "primary_current_quotient_size",
        "primary_predictive_quotient_size",
        "primary_max_fiber_size",
        "primary_witness_count",
        "primary_discrepancy_metric_value",
        "primary_current_loop_score",
        "primary_predictive_loop_score",
    ]
    cluster_lookup: dict[str, DiscoveryDedupCluster] = {}
    exemplar_keys = {
        f"{cluster.exemplar_search_id}:{cluster.exemplar_candidate_id}"
        for cluster in summary.clusters
    }
    for cluster in summary.clusters:
        for search_id, candidate_id in zip(
            cluster.member_search_ids,
            cluster.member_candidate_ids,
            strict=True,
        ):
            cluster_lookup[f"{search_id}:{candidate_id}"] = cluster
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for signature in summary.candidate_signatures:
            cluster = cluster_lookup[signature.qualified_candidate_id]
            writer.writerow(
                {
                    "search_id": signature.search_id,
                    "candidate_id": signature.candidate_id,
                    "cluster_id": cluster.cluster_id,
                    "match_kind": cluster.match_kind,
                    "is_exemplar": str(signature.qualified_candidate_id in exemplar_keys).lower(),
                    "support_size": signature.support_size,
                    "interface_count": signature.interface_count,
                    "carrier_family": signature.carrier_family,
                    "route_update_family": signature.route_update_family,
                    "observable_family": signature.observable_family,
                    "continuation_catalog_family": signature.continuation_catalog_family,
                    "class_label": signature.class_label,
                    "primary_interface_id": signature.primary_interface_id,
                    "primary_current_quotient_size": signature.primary_current_quotient_size,
                    "primary_predictive_quotient_size": signature.primary_predictive_quotient_size,
                    "primary_max_fiber_size": signature.primary_max_fiber_size,
                    "primary_witness_count": signature.primary_witness_count,
                    "primary_discrepancy_metric_value": _fraction_string(
                        signature.primary_discrepancy_metric_value
                    ),
                    "primary_current_loop_score": _fraction_string(
                        signature.primary_current_loop_score
                    ),
                    "primary_predictive_loop_score": _fraction_string(
                        signature.primary_predictive_loop_score
                    ),
                }
            )


def _build_summary_note(
    summary: DiscoveryDiversitySummary,
    json_path: Path,
    csv_path: Path,
    note_path: Path,
) -> str:
    lines = [
        "# Discovery Diversity Audit",
        "",
        f"- seed: {summary.seed}",
        f"- source search ids: {', '.join(summary.source_search_ids)}",
        f"- json path: {_relative_string(json_path)}",
        f"- csv path: {_relative_string(csv_path)}",
        f"- note path: {_relative_string(note_path)}",
        f"- total shortlisted candidate count: {summary.total_shortlisted_candidate_count}",
        f"- unique exemplar count: {summary.unique_exemplar_count}",
        (
            "- cluster counts by kind: "
            f"exact_duplicate={summary.exact_duplicate_cluster_count}, "
            f"near_duplicate={summary.near_duplicate_cluster_count}, "
            f"singleton={summary.singleton_count}"
        ),
        "",
        "| cluster_id | match_kind | exemplar_candidate_id | exemplar_search_id | member_count | member_candidate_ids |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for cluster in summary.clusters:
        lines.append(
            "| "
            f"{cluster.cluster_id} | "
            f"{cluster.match_kind} | "
            f"{cluster.exemplar_candidate_id} | "
            f"{cluster.exemplar_search_id} | "
            f"{cluster.cluster_size} | "
            f"{', '.join(cluster.member_candidate_ids)} |"
        )
    lines.extend(
        [
            "",
            _conclusion_line(summary),
        ]
    )
    return "\n".join(lines) + "\n"


def _conclusion_line(summary: DiscoveryDiversitySummary) -> str:
    if summary.singleton_count == summary.total_shortlisted_candidate_count:
        return (
            "- conclusion: the shortlisted discovery set is fully singleton under the "
            "current structural and behavior signatures, so it is diverse enough to "
            "proceed without dedup pruning."
        )
    return (
        "- conclusion: the shortlisted discovery set includes clustered near-duplicates "
        f"or exact duplicates, leaving {summary.unique_exemplar_count} unique exemplars "
        "for follow-up."
    )


def _structural_signature_pairs(
    signature: DiscoveryCandidateSignature,
) -> tuple[tuple[str, object], ...]:
    return (
        ("support_size", signature.support_size),
        ("interface_count", signature.interface_count),
        ("carrier_family", signature.carrier_family),
        ("route_update_family", signature.route_update_family),
        ("observable_family", signature.observable_family),
        ("continuation_catalog_family", signature.continuation_catalog_family),
    )


def _coarse_metric_summary_pairs(
    signature: DiscoveryCandidateSignature,
) -> tuple[tuple[str, object], ...]:
    return (
        ("class_label", signature.class_label),
        ("primary_interface_id", signature.primary_interface_id),
        ("primary_current_quotient_size", signature.primary_current_quotient_size),
        ("primary_predictive_quotient_size", signature.primary_predictive_quotient_size),
        ("primary_max_fiber_size", signature.primary_max_fiber_size),
        ("primary_witness_count", signature.primary_witness_count),
        ("discrepancy_positive", signature.primary_discrepancy_metric_value > 0),
        ("predictive_loop_positive", signature.primary_predictive_loop_score > 0),
        ("current_loop_zero", signature.primary_current_loop_score == 0),
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(root: Path, path_value: Path) -> Path:
    return path_value if path_value.is_absolute() else root / path_value


def _fraction_string(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _relative_string(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
