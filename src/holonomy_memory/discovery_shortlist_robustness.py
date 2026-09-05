from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .benchmarks import REPO_ROOT
from .discovery import DiscoveryCandidateRecord, run_discovery_search
from .discovery_triage import (
    DEFAULT_DISCOVERY_TRIAGE_SEARCH_ID,
    DiscoveryShortlistEntry,
    compute_discovery_robustness_proxy,
    triage_discovery_candidates,
)
from .search_spaces import load_search_space, load_search_space_for_id


DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT = 8


@dataclass(frozen=True)
class ShortlistedCandidateRobustnessEntry:
    search_id: str
    candidate_id: str
    class_label: str
    primary_interface_id: str
    threshold: Fraction
    trial_count: int
    pass_count: int
    survival_fraction: Fraction
    meets_threshold: bool
    primary_witness_count: int
    primary_discrepancy_metric_value: Fraction
    primary_predictive_loop_score: Fraction
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryShortlistRobustnessSummary:
    search_id: str
    seed: int
    atlas_path: Path
    shortlist_path: Path
    ordered_shortlisted_candidate_ids: tuple[str, ...]
    entries: tuple[ShortlistedCandidateRobustnessEntry, ...]
    overall_pass: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryShortlistRobustnessArtifacts:
    search_id: str
    seed: int
    summary_json_path: Path
    summary_csv_path: Path
    summary_note_path: Path
    summary: DiscoveryShortlistRobustnessSummary


def run_discovery_shortlist_robustness(
    *,
    search_id: str | None = None,
    search_path: str | Path | None = None,
    seed: int = 0,
    output_root: str | Path | None = None,
    trial_count: int = DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT,
) -> DiscoveryShortlistRobustnessArtifacts:
    resolved_search_id = search_id or DEFAULT_DISCOVERY_TRIAGE_SEARCH_ID
    triage_artifacts = triage_discovery_candidates(
        search_id=resolved_search_id if search_path is None else None,
        search_path=search_path,
        seed=seed,
        output_root=output_root,
    )
    discovery_artifacts = run_discovery_search(
        search_id=resolved_search_id if search_path is None else None,
        search_path=search_path,
        seed=seed,
        output_root=output_root,
    )
    if search_path is not None:
        search_space = load_search_space(search_path)
    else:
        search_space = load_search_space_for_id(resolved_search_id)

    records_by_id = {
        record.candidate_spec.candidate_id: record
        for record in discovery_artifacts.atlas.candidate_records
    }
    ordered_entries: list[ShortlistedCandidateRobustnessEntry] = []
    warnings: list[str] = []
    for shortlist_entry in triage_artifacts.shortlist.combined_shortlist:
        candidate_record = records_by_id.get(shortlist_entry.candidate_id)
        if candidate_record is None:
            ordered_entries.append(
                ShortlistedCandidateRobustnessEntry(
                    search_id=triage_artifacts.search_id,
                    candidate_id=shortlist_entry.candidate_id,
                    class_label=shortlist_entry.class_label,
                    primary_interface_id=shortlist_entry.primary_interface_id,
                    threshold=_threshold_for_class_label(shortlist_entry.class_label),
                    trial_count=trial_count,
                    pass_count=0,
                    survival_fraction=Fraction(0, 1),
                    meets_threshold=False,
                    primary_witness_count=shortlist_entry.primary_witness_count,
                    primary_discrepancy_metric_value=shortlist_entry.primary_discrepancy_metric_value,
                    primary_predictive_loop_score=shortlist_entry.primary_predictive_loop_score,
                    warnings=("candidate missing from rerun atlas",),
                )
            )
            warnings.append(
                f"{shortlist_entry.candidate_id}: candidate missing from rerun atlas"
            )
            continue
        ordered_entries.append(
            evaluate_shortlisted_candidate_robustness(
                shortlist_entry=shortlist_entry,
                candidate_record=candidate_record,
                search_space=search_space,
                seed=seed,
                trial_count=trial_count,
            )
        )

    summary = DiscoveryShortlistRobustnessSummary(
        search_id=triage_artifacts.search_id,
        seed=seed,
        atlas_path=triage_artifacts.atlas_json_path,
        shortlist_path=triage_artifacts.shortlist_json_path,
        ordered_shortlisted_candidate_ids=tuple(
            entry.candidate_id for entry in triage_artifacts.shortlist.combined_shortlist
        ),
        entries=tuple(ordered_entries),
        overall_pass=any(entry.meets_threshold for entry in ordered_entries),
        warnings=tuple(warnings),
    )
    return write_discovery_shortlist_robustness(
        summary=summary,
        output_root=output_root,
    )


def evaluate_shortlisted_candidate_robustness(
    *,
    shortlist_entry: DiscoveryShortlistEntry,
    candidate_record: DiscoveryCandidateRecord,
    search_space: object,
    seed: int,
    trial_count: int,
) -> ShortlistedCandidateRobustnessEntry:
    survival_fraction = compute_discovery_robustness_proxy(
        record=candidate_record,
        search_space=search_space,
        seed=seed,
        proxy_trial_count=trial_count,
    )
    threshold = _threshold_for_class_label(shortlist_entry.class_label)
    pass_count = int(survival_fraction * trial_count)
    return ShortlistedCandidateRobustnessEntry(
        search_id=shortlist_entry.search_id,
        candidate_id=shortlist_entry.candidate_id,
        class_label=shortlist_entry.class_label,
        primary_interface_id=shortlist_entry.primary_interface_id,
        threshold=threshold,
        trial_count=trial_count,
        pass_count=pass_count,
        survival_fraction=survival_fraction,
        meets_threshold=survival_fraction >= threshold,
        primary_witness_count=shortlist_entry.primary_witness_count,
        primary_discrepancy_metric_value=shortlist_entry.primary_discrepancy_metric_value,
        primary_predictive_loop_score=shortlist_entry.primary_predictive_loop_score,
        warnings=(),
    )


def write_discovery_shortlist_robustness(
    *,
    summary: DiscoveryShortlistRobustnessSummary,
    output_root: str | Path | None = None,
) -> DiscoveryShortlistRobustnessArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    json_path = (
        root
        / "artifacts"
        / "results"
        / "discovery"
        / f"{summary.search_id}.shortlist_robustness.json"
    )
    csv_path = (
        root
        / "artifacts"
        / "tables"
        / f"discovery_{summary.search_id}_shortlist_robustness.csv"
    )
    note_path = (
        root / "docs" / "results" / f"{summary.search_id}.shortlist_robustness.md"
    )
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
    return DiscoveryShortlistRobustnessArtifacts(
        search_id=summary.search_id,
        seed=summary.seed,
        summary_json_path=json_path,
        summary_csv_path=csv_path,
        summary_note_path=note_path,
        summary=summary,
    )


def _threshold_for_class_label(class_label: str) -> Fraction:
    # HM-020A currently operates on an all-coherent shortlist, but keep the
    # threshold table explicit so future shortlist classes do not need a redesign.
    return {
        "coherent_candidate": Fraction(1, 2),
        "dissipative": Fraction(1, 2),
        "flat": Fraction(4, 5),
    }[class_label]


def _summary_payload(
    summary: DiscoveryShortlistRobustnessSummary,
) -> dict[str, object]:
    return {
        "search_id": summary.search_id,
        "seed": summary.seed,
        "atlas_path": _relative_string(summary.atlas_path),
        "shortlist_path": _relative_string(summary.shortlist_path),
        "ordered_shortlisted_candidate_ids": list(summary.ordered_shortlisted_candidate_ids),
        "entries": [_entry_payload(entry) for entry in summary.entries],
        "overall_pass": summary.overall_pass,
        "warnings": list(summary.warnings),
    }


def _entry_payload(entry: ShortlistedCandidateRobustnessEntry) -> dict[str, object]:
    return {
        "search_id": entry.search_id,
        "candidate_id": entry.candidate_id,
        "class_label": entry.class_label,
        "primary_interface_id": entry.primary_interface_id,
        "threshold": float(entry.threshold),
        "threshold_exact": _fraction_string(entry.threshold),
        "trial_count": entry.trial_count,
        "pass_count": entry.pass_count,
        "survival_fraction": float(entry.survival_fraction),
        "survival_fraction_exact": _fraction_string(entry.survival_fraction),
        "meets_threshold": entry.meets_threshold,
        "primary_witness_count": entry.primary_witness_count,
        "primary_discrepancy_metric_value": float(entry.primary_discrepancy_metric_value),
        "primary_discrepancy_metric_value_exact": _fraction_string(
            entry.primary_discrepancy_metric_value
        ),
        "primary_predictive_loop_score": float(entry.primary_predictive_loop_score),
        "primary_predictive_loop_score_exact": _fraction_string(
            entry.primary_predictive_loop_score
        ),
        "warnings": list(entry.warnings),
    }


def _write_summary_csv(
    summary: DiscoveryShortlistRobustnessSummary,
    csv_path: Path,
) -> None:
    fieldnames = [
        "search_id",
        "candidate_id",
        "class_label",
        "primary_interface_id",
        "threshold",
        "trial_count",
        "pass_count",
        "survival_fraction",
        "meets_threshold",
        "primary_witness_count",
        "primary_discrepancy_metric_value",
        "primary_predictive_loop_score",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in summary.entries:
            writer.writerow(
                {
                    "search_id": entry.search_id,
                    "candidate_id": entry.candidate_id,
                    "class_label": entry.class_label,
                    "primary_interface_id": entry.primary_interface_id,
                    "threshold": float(entry.threshold),
                    "trial_count": entry.trial_count,
                    "pass_count": entry.pass_count,
                    "survival_fraction": float(entry.survival_fraction),
                    "meets_threshold": str(entry.meets_threshold).lower(),
                    "primary_witness_count": entry.primary_witness_count,
                    "primary_discrepancy_metric_value": float(
                        entry.primary_discrepancy_metric_value
                    ),
                    "primary_predictive_loop_score": float(
                        entry.primary_predictive_loop_score
                    ),
                }
            )


def _build_summary_note(
    summary: DiscoveryShortlistRobustnessSummary,
    json_path: Path,
    csv_path: Path,
    note_path: Path,
) -> str:
    lines = [
        f"# Shortlist Robustness: {summary.search_id}",
        "",
        f"- search_id: {summary.search_id}",
        f"- seed: {summary.seed}",
        f"- atlas_path: {_relative_string(summary.atlas_path)}",
        f"- shortlist_path: {_relative_string(summary.shortlist_path)}",
        f"- robustness_json_path: {_relative_string(json_path)}",
        f"- robustness_csv_path: {_relative_string(csv_path)}",
        f"- robustness_note_path: {_relative_string(note_path)}",
        f"- ordered_shortlisted_candidate_ids: {', '.join(summary.ordered_shortlisted_candidate_ids)}",
        "",
        "## Summary",
        "",
    ]
    for entry in summary.entries:
        lines.append(
            (
                f"- {entry.candidate_id}: {entry.class_label}, "
                f"threshold={_fraction_string(entry.threshold)}, "
                f"trial_count={entry.trial_count}, "
                f"pass_count={entry.pass_count}, "
                f"survival_fraction={_fraction_string(entry.survival_fraction)}, "
                f"meets_threshold={str(entry.meets_threshold).lower()}"
            )
        )
    lines.extend(["", "## Conclusion", ""])
    if any(entry.meets_threshold for entry in summary.entries):
        lines.append("- At least one shortlisted candidate survived above threshold.")
    else:
        lines.append("- No shortlisted candidate survived above threshold.")
    if summary.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in summary.warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def _fraction_string(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _relative_string(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
