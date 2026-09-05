from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .benchmarks import REPO_ROOT
from .discovery import DISCOVERY_LABELS
from .discovery_triage import triage_discovery_candidates


DEFAULT_MULTISPACE_SEARCH_IDS = (
    "fixed_support_core_small",
    "cyclic_memory_small",
    "groupoid_probe_small",
)


@dataclass(frozen=True)
class MultiSpaceDiscoveryEntry:
    search_id: str
    atlas_json_path: Path
    atlas_csv_path: Path
    atlas_note_path: Path
    shortlist_json_path: Path | None
    shortlist_csv_path: Path | None
    shortlist_note_path: Path | None
    attempted_candidate_count: int
    realized_candidate_count: int
    evaluated_candidate_count: int
    flat_count: int
    dissipative_count: int
    coherent_candidate_count: int
    nonflat_count: int
    shortlist_count: int
    all_flat: bool
    productive: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MultiSpaceDiscoverySummary:
    seed: int
    search_ids: tuple[str, ...]
    entries: tuple[MultiSpaceDiscoveryEntry, ...]
    aggregate_class_counts: tuple[tuple[str, int], ...]
    aggregate_evaluated_candidate_count: int
    aggregate_nonflat_count: int
    aggregate_shortlist_count: int
    all_flat_space_ids: tuple[str, ...]
    productive_space_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MultiSpaceDiscoveryArtifacts:
    seed: int
    summary_json_path: Path
    summary_csv_path: Path
    summary_note_path: Path
    summary: MultiSpaceDiscoverySummary


def run_multispace_discovery(
    *,
    seed: int = 0,
    output_root: str | Path | None = None,
    search_ids: tuple[str, ...] = DEFAULT_MULTISPACE_SEARCH_IDS,
) -> MultiSpaceDiscoveryArtifacts:
    entries: list[MultiSpaceDiscoveryEntry] = []
    warnings: list[str] = []
    for search_id in search_ids:
        triage_artifacts = triage_discovery_candidates(
            search_id=search_id,
            seed=seed,
            output_root=output_root,
            allow_all_flat=True,
        )
        atlas_obj = triage_artifacts.shortlist.class_counts
        class_count_map = {label: count for label, count in atlas_obj}
        flat_count = class_count_map.get("flat", 0)
        dissipative_count = class_count_map.get("dissipative", 0)
        coherent_candidate_count = class_count_map.get("coherent_candidate", 0)
        evaluated_candidate_count = flat_count + dissipative_count + coherent_candidate_count
        nonflat_count = dissipative_count + coherent_candidate_count
        shortlist_count = len(triage_artifacts.shortlist.combined_shortlist)
        entries.append(
            MultiSpaceDiscoveryEntry(
                search_id=search_id,
                atlas_json_path=triage_artifacts.atlas_json_path,
                atlas_csv_path=triage_artifacts.atlas_csv_path,
                atlas_note_path=triage_artifacts.atlas_note_path,
                shortlist_json_path=triage_artifacts.shortlist_json_path,
                shortlist_csv_path=triage_artifacts.shortlist_csv_path,
                shortlist_note_path=triage_artifacts.shortlist_note_path,
                attempted_candidate_count=_load_atlas_payload(triage_artifacts.atlas_json_path)[
                    "attempted_candidate_count"
                ],
                realized_candidate_count=_load_atlas_payload(triage_artifacts.atlas_json_path)[
                    "realized_candidate_count"
                ],
                evaluated_candidate_count=evaluated_candidate_count,
                flat_count=flat_count,
                dissipative_count=dissipative_count,
                coherent_candidate_count=coherent_candidate_count,
                nonflat_count=nonflat_count,
                shortlist_count=shortlist_count,
                all_flat=evaluated_candidate_count > 0 and nonflat_count == 0,
                productive=nonflat_count > 0,
                warnings=triage_artifacts.shortlist.warnings,
            )
        )

    aggregate_class_counts = tuple(
        (
            label,
            sum(
                getattr(entry, f"{label}_count")
                if label != "coherent_candidate"
                else entry.coherent_candidate_count
                for entry in entries
            ),
        )
        for label in DISCOVERY_LABELS
    )
    summary = MultiSpaceDiscoverySummary(
        seed=seed,
        search_ids=search_ids,
        entries=tuple(entries),
        aggregate_class_counts=aggregate_class_counts,
        aggregate_evaluated_candidate_count=sum(
            entry.evaluated_candidate_count for entry in entries
        ),
        aggregate_nonflat_count=sum(entry.nonflat_count for entry in entries),
        aggregate_shortlist_count=sum(entry.shortlist_count for entry in entries),
        all_flat_space_ids=tuple(entry.search_id for entry in entries if entry.all_flat),
        productive_space_ids=tuple(entry.search_id for entry in entries if entry.productive),
        warnings=tuple(warnings),
    )
    return write_multispace_discovery_summary(summary=summary, output_root=output_root)


def write_multispace_discovery_summary(
    *,
    summary: MultiSpaceDiscoverySummary,
    output_root: str | Path | None = None,
) -> MultiSpaceDiscoveryArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    json_path = root / "artifacts" / "results" / "discovery" / "multi_space.discovery.json"
    csv_path = root / "artifacts" / "tables" / "discovery_multi_space_summary.csv"
    note_path = root / "docs" / "results" / "multi_space.discovery.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(_summary_payload(summary), indent=2) + "\n", encoding="utf-8")
    _write_summary_csv(summary, csv_path)
    note_path.write_text(_build_summary_note(summary, json_path, csv_path, note_path), encoding="utf-8")
    return MultiSpaceDiscoveryArtifacts(
        seed=summary.seed,
        summary_json_path=json_path,
        summary_csv_path=csv_path,
        summary_note_path=note_path,
        summary=summary,
    )


def _load_atlas_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _summary_payload(summary: MultiSpaceDiscoverySummary) -> dict[str, object]:
    return {
        "seed": summary.seed,
        "search_ids": list(summary.search_ids),
        "entries": [
            {
                "search_id": entry.search_id,
                "atlas_json_path": _relative_string(entry.atlas_json_path),
                "atlas_csv_path": _relative_string(entry.atlas_csv_path),
                "atlas_note_path": _relative_string(entry.atlas_note_path),
                "shortlist_json_path": (
                    _relative_string(entry.shortlist_json_path)
                    if entry.shortlist_json_path is not None
                    else None
                ),
                "shortlist_csv_path": (
                    _relative_string(entry.shortlist_csv_path)
                    if entry.shortlist_csv_path is not None
                    else None
                ),
                "shortlist_note_path": (
                    _relative_string(entry.shortlist_note_path)
                    if entry.shortlist_note_path is not None
                    else None
                ),
                "attempted_candidate_count": entry.attempted_candidate_count,
                "realized_candidate_count": entry.realized_candidate_count,
                "evaluated_candidate_count": entry.evaluated_candidate_count,
                "flat_count": entry.flat_count,
                "dissipative_count": entry.dissipative_count,
                "coherent_candidate_count": entry.coherent_candidate_count,
                "nonflat_count": entry.nonflat_count,
                "shortlist_count": entry.shortlist_count,
                "all_flat": entry.all_flat,
                "productive": entry.productive,
                "warnings": list(entry.warnings),
            }
            for entry in summary.entries
        ],
        "aggregate_class_counts": {
            label: count for label, count in summary.aggregate_class_counts
        },
        "aggregate_evaluated_candidate_count": summary.aggregate_evaluated_candidate_count,
        "aggregate_nonflat_count": summary.aggregate_nonflat_count,
        "aggregate_shortlist_count": summary.aggregate_shortlist_count,
        "all_flat_space_ids": list(summary.all_flat_space_ids),
        "productive_space_ids": list(summary.productive_space_ids),
        "warnings": list(summary.warnings),
    }


def _write_summary_csv(summary: MultiSpaceDiscoverySummary, csv_path: Path) -> None:
    fieldnames = [
        "search_id",
        "attempted_candidate_count",
        "realized_candidate_count",
        "evaluated_candidate_count",
        "flat_count",
        "dissipative_count",
        "coherent_candidate_count",
        "nonflat_count",
        "shortlist_count",
        "all_flat",
        "productive",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in summary.entries:
            writer.writerow(
                {
                    "search_id": entry.search_id,
                    "attempted_candidate_count": entry.attempted_candidate_count,
                    "realized_candidate_count": entry.realized_candidate_count,
                    "evaluated_candidate_count": entry.evaluated_candidate_count,
                    "flat_count": entry.flat_count,
                    "dissipative_count": entry.dissipative_count,
                    "coherent_candidate_count": entry.coherent_candidate_count,
                    "nonflat_count": entry.nonflat_count,
                    "shortlist_count": entry.shortlist_count,
                    "all_flat": str(entry.all_flat).lower(),
                    "productive": str(entry.productive).lower(),
                }
            )


def _build_summary_note(
    summary: MultiSpaceDiscoverySummary,
    json_path: Path,
    csv_path: Path,
    note_path: Path,
) -> str:
    lines = [
        "# Multi-Space Discovery Summary",
        "",
        f"- seed: {summary.seed}",
        f"- search_ids: {', '.join(summary.search_ids)}",
        f"- summary_json_path: {_relative_string(json_path)}",
        f"- summary_csv_path: {_relative_string(csv_path)}",
        f"- summary_note_path: {_relative_string(note_path)}",
        "",
        "## Per Space",
        "",
    ]
    for entry in summary.entries:
        lines.append(
            (
                f"- {entry.search_id}: "
                f"flat={entry.flat_count}, "
                f"dissipative={entry.dissipative_count}, "
                f"coherent_candidate={entry.coherent_candidate_count}, "
                f"nonflat={entry.nonflat_count}, "
                f"shortlist={entry.shortlist_count}, "
                f"all_flat={str(entry.all_flat).lower()}, "
                f"productive={str(entry.productive).lower()}"
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- flat: {dict(summary.aggregate_class_counts).get('flat', 0)}",
            f"- dissipative: {dict(summary.aggregate_class_counts).get('dissipative', 0)}",
            f"- coherent_candidate: {dict(summary.aggregate_class_counts).get('coherent_candidate', 0)}",
            f"- aggregate_evaluated_candidate_count: {summary.aggregate_evaluated_candidate_count}",
            f"- aggregate_nonflat_count: {summary.aggregate_nonflat_count}",
            f"- aggregate_shortlist_count: {summary.aggregate_shortlist_count}",
            f"- all_flat_space_ids: {', '.join(summary.all_flat_space_ids) if summary.all_flat_space_ids else 'none'}",
            f"- productive_space_ids: {', '.join(summary.productive_space_ids) if summary.productive_space_ids else 'none'}",
            "",
            "## Conclusion",
            "",
        ]
    )
    if len(summary.productive_space_ids) > 1:
        lines.append("- Discovery signal persists beyond one smoke search space.")
    else:
        lines.append("- Discovery signal remains concentrated in one productive search space.")
    return "\n".join(lines) + "\n"


def _relative_string(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
