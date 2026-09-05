from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .benchmarks import REPO_ROOT
from .discovery import run_discovery_search
from .discovery_diversity import run_discovery_diversity_audit
from .discovery_exemplars import promote_discovery_exemplars
from .discovery_multispace import DEFAULT_MULTISPACE_SEARCH_IDS, run_multispace_discovery
from .discovery_shortlist_robustness import (
    DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT,
    run_discovery_shortlist_robustness,
)
from .discovery_triage import DEFAULT_DISCOVERY_TRIAGE_SEARCH_ID, triage_discovery_candidates
from .runner import BenchmarkRunArtifacts, run_benchmark
from .validation import load_benchmark_result_manifest


BENCHMARK_SUITE_IDS = (
    "flat_control",
    "protocol_trap_naive",
    "protocol_trap_honest",
    "flattenable_raw",
    "flattenable_completed",
    "latent_memory_base",
    "latent_memory_refined",
    "dissipative_memory",
    "memory_wheel",
)

FROZEN_REPRO_COMMANDS = (
    "make test",
    "make benchmark-suite",
    "make discovery-smoke",
    "make lean-build",
)


@dataclass(frozen=True)
class BenchmarkSuiteEntry:
    benchmark_id: str
    measured_interfaces: tuple[str, ...]
    class_labels: tuple[str, ...]
    witness_counts: tuple[int, ...]
    discrepancy_values: tuple[float, ...]
    current_loop_scores: tuple[float, ...]
    predictive_loop_scores: tuple[float, ...]
    support_fixation_statuses: tuple[str, ...]
    currentization_statuses: tuple[str, ...]
    flattening_statuses: tuple[str, ...]
    json_artifact_path: Path
    csv_artifact_path: Path
    ops_note_path: Path


@dataclass(frozen=True)
class BenchmarkSuiteSummary:
    seed: int
    benchmark_ids: tuple[str, ...]
    entries: tuple[BenchmarkSuiteEntry, ...]
    command: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BenchmarkSuiteArtifacts:
    seed: int
    summary_json_path: Path
    summary_csv_path: Path
    summary_note_path: Path
    summary: BenchmarkSuiteSummary


@dataclass(frozen=True)
class DiscoverySmokeSummary:
    seed: int
    command: str
    primary_search_id: str
    search_ids: tuple[str, ...]
    atlas_json_path: Path
    atlas_csv_path: Path
    atlas_note_path: Path
    shortlist_json_path: Path
    shortlist_csv_path: Path
    shortlist_note_path: Path
    shortlist_robustness_json_path: Path
    shortlist_robustness_csv_path: Path
    shortlist_robustness_note_path: Path
    multispace_json_path: Path
    multispace_csv_path: Path
    multispace_note_path: Path
    dedup_json_path: Path
    dedup_csv_path: Path
    dedup_note_path: Path
    promoted_exemplars_json_path: Path
    promoted_exemplars_csv_path: Path
    promoted_exemplars_note_path: Path
    class_counts: tuple[tuple[str, int], ...]
    combined_shortlist_ids: tuple[str, ...]
    shortlisted_robustness: tuple[tuple[str, float, bool], ...]
    multispace_all_flat_space_ids: tuple[str, ...]
    multispace_productive_space_ids: tuple[str, ...]
    promoted_exemplar_qualified_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoverySmokeArtifacts:
    seed: int
    summary_json_path: Path
    summary_note_path: Path
    summary: DiscoverySmokeSummary


@dataclass(frozen=True)
class ReproCommandStatus:
    command: str
    passed: bool


@dataclass(frozen=True)
class ReproFreezeSummary:
    seed: int
    commands: tuple[str, ...]
    verified_from_temporary_clean_copy: bool
    command_statuses: tuple[ReproCommandStatus, ...]
    benchmark_suite_semantics_match: bool
    discovery_smoke_semantics_match: bool
    benchmark_suite_artifact_paths: tuple[str, ...]
    discovery_smoke_artifact_paths: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReproFreezeArtifacts:
    summary_json_path: Path
    summary: ReproFreezeSummary


def run_benchmark_suite(
    *,
    seed: int = 0,
    output_root: str | Path | None = None,
) -> BenchmarkSuiteArtifacts:
    entries: list[BenchmarkSuiteEntry] = []
    warnings: list[str] = []
    for benchmark_id in BENCHMARK_SUITE_IDS:
        artifacts = run_benchmark(
            benchmark_id=benchmark_id,
            seed=seed,
            output_root=output_root,
        )
        load_benchmark_result_manifest(artifacts.json_artifact_path)
        entries.append(_benchmark_suite_entry(artifacts))
        warnings.extend(artifacts.warnings)
    summary = BenchmarkSuiteSummary(
        seed=seed,
        benchmark_ids=BENCHMARK_SUITE_IDS,
        entries=tuple(entries),
        command=f"python -m holonomy_memory run-benchmark-suite --seed {seed}",
        warnings=tuple(warnings),
    )
    return write_benchmark_suite_summary(summary=summary, output_root=output_root)


def write_benchmark_suite_summary(
    *,
    summary: BenchmarkSuiteSummary,
    output_root: str | Path | None = None,
) -> BenchmarkSuiteArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    json_path = root / "artifacts" / "results" / "benchmark_suite.json"
    csv_path = root / "artifacts" / "tables" / "benchmark_suite.csv"
    note_path = root / "docs" / "results" / "benchmark_suite.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(_benchmark_suite_payload(summary, root), indent=2) + "\n",
        encoding="utf-8",
    )
    _write_benchmark_suite_csv(summary, csv_path, root)
    note_path.write_text(
        _build_benchmark_suite_note(summary, json_path, csv_path, note_path, root),
        encoding="utf-8",
    )
    return BenchmarkSuiteArtifacts(
        seed=summary.seed,
        summary_json_path=json_path,
        summary_csv_path=csv_path,
        summary_note_path=note_path,
        summary=summary,
    )


def run_discovery_smoke(
    *,
    seed: int = 0,
    output_root: str | Path | None = None,
) -> DiscoverySmokeArtifacts:
    atlas_artifacts = run_discovery_search(
        search_id=DEFAULT_DISCOVERY_TRIAGE_SEARCH_ID,
        seed=seed,
        output_root=output_root,
    )
    triage_artifacts = triage_discovery_candidates(
        search_id=DEFAULT_DISCOVERY_TRIAGE_SEARCH_ID,
        seed=seed,
        output_root=output_root,
    )
    shortlist_robustness_artifacts = run_discovery_shortlist_robustness(
        search_id=DEFAULT_DISCOVERY_TRIAGE_SEARCH_ID,
        seed=seed,
        output_root=output_root,
        trial_count=DEFAULT_SHORTLIST_ROBUSTNESS_TRIAL_COUNT,
    )
    multispace_artifacts = run_multispace_discovery(seed=seed, output_root=output_root)
    diversity_artifacts = run_discovery_diversity_audit(seed=seed, output_root=output_root)
    exemplar_artifacts = promote_discovery_exemplars(seed=seed, output_root=output_root)
    summary = DiscoverySmokeSummary(
        seed=seed,
        command=f"python -m holonomy_memory run-discovery-smoke --seed {seed}",
        primary_search_id=DEFAULT_DISCOVERY_TRIAGE_SEARCH_ID,
        search_ids=DEFAULT_MULTISPACE_SEARCH_IDS,
        atlas_json_path=atlas_artifacts.json_atlas_path,
        atlas_csv_path=atlas_artifacts.csv_summary_path,
        atlas_note_path=atlas_artifacts.summary_note_path,
        shortlist_json_path=triage_artifacts.shortlist_json_path,
        shortlist_csv_path=triage_artifacts.shortlist_csv_path,
        shortlist_note_path=triage_artifacts.shortlist_note_path,
        shortlist_robustness_json_path=shortlist_robustness_artifacts.summary_json_path,
        shortlist_robustness_csv_path=shortlist_robustness_artifacts.summary_csv_path,
        shortlist_robustness_note_path=shortlist_robustness_artifacts.summary_note_path,
        multispace_json_path=multispace_artifacts.summary_json_path,
        multispace_csv_path=multispace_artifacts.summary_csv_path,
        multispace_note_path=multispace_artifacts.summary_note_path,
        dedup_json_path=diversity_artifacts.summary_json_path,
        dedup_csv_path=diversity_artifacts.summary_csv_path,
        dedup_note_path=diversity_artifacts.summary_note_path,
        promoted_exemplars_json_path=exemplar_artifacts.summary_json_path,
        promoted_exemplars_csv_path=exemplar_artifacts.summary_csv_path,
        promoted_exemplars_note_path=exemplar_artifacts.index_note_path,
        class_counts=triage_artifacts.shortlist.class_counts,
        combined_shortlist_ids=tuple(
            entry.candidate_id for entry in triage_artifacts.shortlist.combined_shortlist
        ),
        shortlisted_robustness=tuple(
            (
                entry.candidate_id,
                float(entry.survival_fraction),
                entry.meets_threshold,
            )
            for entry in shortlist_robustness_artifacts.summary.entries
        ),
        multispace_all_flat_space_ids=multispace_artifacts.summary.all_flat_space_ids,
        multispace_productive_space_ids=multispace_artifacts.summary.productive_space_ids,
        promoted_exemplar_qualified_ids=exemplar_artifacts.summary.ordered_promoted_qualified_ids,
        warnings=tuple(
            atlas_artifacts.atlas.warnings
            + triage_artifacts.shortlist.warnings
            + shortlist_robustness_artifacts.summary.warnings
            + multispace_artifacts.summary.warnings
            + diversity_artifacts.summary.warnings
            + exemplar_artifacts.summary.warnings
        ),
    )
    return write_discovery_smoke_summary(summary=summary, output_root=output_root)


def write_discovery_smoke_summary(
    *,
    summary: DiscoverySmokeSummary,
    output_root: str | Path | None = None,
) -> DiscoverySmokeArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    json_path = root / "artifacts" / "results" / "discovery" / "discovery_smoke.json"
    note_path = root / "docs" / "results" / "discovery_smoke.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(_discovery_smoke_payload(summary, root), indent=2) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(
        _build_discovery_smoke_note(summary, json_path, note_path, root),
        encoding="utf-8",
    )
    return DiscoverySmokeArtifacts(
        seed=summary.seed,
        summary_json_path=json_path,
        summary_note_path=note_path,
        summary=summary,
    )


def verify_repro_freeze(
    *,
    seed: int = 0,
    output_root: str | Path | None = None,
) -> ReproFreezeArtifacts:
    run_benchmark_suite(seed=seed, output_root=output_root)
    run_discovery_smoke(seed=seed, output_root=output_root)
    benchmark_suite_paths = (
        "artifacts/results/benchmark_suite.json",
        "artifacts/tables/benchmark_suite.csv",
        "docs/results/benchmark_suite.md",
    )
    discovery_smoke_paths = (
        "artifacts/results/discovery/discovery_smoke.json",
        "docs/results/discovery_smoke.md",
    )
    warnings: list[str] = []
    with tempfile.TemporaryDirectory(prefix="hm030_clean_") as tmp_dir:
        clean_root = Path(tmp_dir) / REPO_ROOT.name
        _copy_clean_repo(REPO_ROOT, clean_root)

        command_statuses: list[ReproCommandStatus] = []

        test_ok = _run_make_target(clean_root, "test")
        command_statuses.append(ReproCommandStatus(command="make test", passed=test_ok))

        benchmark_first_ok = _run_make_target(clean_root, "benchmark-suite")
        benchmark_first_summary = _load_json(
            clean_root / "artifacts" / "results" / "benchmark_suite.json"
        ) if benchmark_first_ok else None
        benchmark_second_ok = _run_make_target(clean_root, "benchmark-suite")
        benchmark_second_summary = _load_json(
            clean_root / "artifacts" / "results" / "benchmark_suite.json"
        ) if benchmark_second_ok else None
        benchmark_ok = benchmark_first_ok and benchmark_second_ok
        benchmark_match = benchmark_ok and _benchmark_suite_stable_fields(
            benchmark_first_summary
        ) == _benchmark_suite_stable_fields(benchmark_second_summary)
        if not benchmark_match:
            warnings.append("benchmark-suite seeded reruns diverged on stable semantic fields")
        command_statuses.append(
            ReproCommandStatus(command="make benchmark-suite", passed=benchmark_ok)
        )

        discovery_first_ok = _run_make_target(clean_root, "discovery-smoke")
        discovery_first_summary = _load_json(
            clean_root / "artifacts" / "results" / "discovery" / "discovery_smoke.json"
        ) if discovery_first_ok else None
        discovery_second_ok = _run_make_target(clean_root, "discovery-smoke")
        discovery_second_summary = _load_json(
            clean_root / "artifacts" / "results" / "discovery" / "discovery_smoke.json"
        ) if discovery_second_ok else None
        discovery_ok = discovery_first_ok and discovery_second_ok
        discovery_match = discovery_ok and _discovery_smoke_stable_fields(
            discovery_first_summary
        ) == _discovery_smoke_stable_fields(discovery_second_summary)
        if not discovery_match:
            warnings.append("discovery-smoke seeded reruns diverged on stable semantic fields")
        command_statuses.append(
            ReproCommandStatus(command="make discovery-smoke", passed=discovery_ok)
        )

        lean_ok = _run_make_target(clean_root, "lean-build")
        command_statuses.append(ReproCommandStatus(command="make lean-build", passed=lean_ok))

    summary = ReproFreezeSummary(
        seed=seed,
        commands=FROZEN_REPRO_COMMANDS,
        verified_from_temporary_clean_copy=True,
        command_statuses=tuple(command_statuses),
        benchmark_suite_semantics_match=benchmark_match,
        discovery_smoke_semantics_match=discovery_match,
        benchmark_suite_artifact_paths=benchmark_suite_paths,
        discovery_smoke_artifact_paths=discovery_smoke_paths,
        warnings=tuple(warnings),
    )
    return write_repro_freeze_summary(summary=summary, output_root=output_root)


def write_repro_freeze_summary(
    *,
    summary: ReproFreezeSummary,
    output_root: str | Path | None = None,
) -> ReproFreezeArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    json_path = root / "artifacts" / "results" / "repro_freeze.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(_repro_freeze_payload(summary), indent=2) + "\n",
        encoding="utf-8",
    )
    return ReproFreezeArtifacts(
        summary_json_path=json_path,
        summary=summary,
    )


def _benchmark_suite_entry(artifacts: BenchmarkRunArtifacts) -> BenchmarkSuiteEntry:
    records = artifacts.result_manifest.records
    return BenchmarkSuiteEntry(
        benchmark_id=artifacts.benchmark_id,
        measured_interfaces=tuple(record.interface_id for record in records),
        class_labels=tuple(record.class_label.value for record in records),
        witness_counts=tuple(record.witness_count for record in records),
        discrepancy_values=tuple(record.discrepancy_metric_value for record in records),
        current_loop_scores=tuple(
            record.loop_action_score_current_quotient for record in records
        ),
        predictive_loop_scores=tuple(
            record.loop_action_score_predictive_quotient for record in records
        ),
        support_fixation_statuses=tuple(
            record.support_fixation_status.value for record in records
        ),
        currentization_statuses=tuple(
            record.currentization_status.value for record in records
        ),
        flattening_statuses=tuple(record.flattening_status.value for record in records),
        json_artifact_path=artifacts.json_artifact_path,
        csv_artifact_path=artifacts.csv_artifact_path,
        ops_note_path=artifacts.ops_note_path,
    )


def _benchmark_suite_payload(
    summary: BenchmarkSuiteSummary,
    root: Path,
) -> dict[str, object]:
    return {
        "seed": summary.seed,
        "command": summary.command,
        "benchmark_ids": list(summary.benchmark_ids),
        "entries": [
            {
                "benchmark_id": entry.benchmark_id,
                "measured_interfaces": list(entry.measured_interfaces),
                "class_labels": list(entry.class_labels),
                "witness_counts": list(entry.witness_counts),
                "discrepancy_values": list(entry.discrepancy_values),
                "current_loop_scores": list(entry.current_loop_scores),
                "predictive_loop_scores": list(entry.predictive_loop_scores),
                "support_fixation_statuses": list(entry.support_fixation_statuses),
                "currentization_statuses": list(entry.currentization_statuses),
                "flattening_statuses": list(entry.flattening_statuses),
                "json_artifact_path": _path_string(root, entry.json_artifact_path),
                "csv_artifact_path": _path_string(root, entry.csv_artifact_path),
                "ops_note_path": _path_string(root, entry.ops_note_path),
            }
            for entry in summary.entries
        ],
        "warnings": list(summary.warnings),
    }


def _write_benchmark_suite_csv(
    summary: BenchmarkSuiteSummary,
    csv_path: Path,
    root: Path,
) -> None:
    fieldnames = [
        "benchmark_id",
        "measured_interfaces",
        "class_labels",
        "witness_counts",
        "discrepancy_values",
        "current_loop_scores",
        "predictive_loop_scores",
        "support_fixation_statuses",
        "currentization_statuses",
        "flattening_statuses",
        "json_artifact_path",
        "csv_artifact_path",
        "ops_note_path",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in summary.entries:
            writer.writerow(
                {
                    "benchmark_id": entry.benchmark_id,
                    "measured_interfaces": ";".join(entry.measured_interfaces),
                    "class_labels": ";".join(entry.class_labels),
                    "witness_counts": ";".join(str(value) for value in entry.witness_counts),
                    "discrepancy_values": ";".join(
                        _format_float(value) for value in entry.discrepancy_values
                    ),
                    "current_loop_scores": ";".join(
                        _format_float(value) for value in entry.current_loop_scores
                    ),
                    "predictive_loop_scores": ";".join(
                        _format_float(value) for value in entry.predictive_loop_scores
                    ),
                    "support_fixation_statuses": ";".join(entry.support_fixation_statuses),
                    "currentization_statuses": ";".join(entry.currentization_statuses),
                    "flattening_statuses": ";".join(entry.flattening_statuses),
                    "json_artifact_path": _path_string(root, entry.json_artifact_path),
                    "csv_artifact_path": _path_string(root, entry.csv_artifact_path),
                    "ops_note_path": _path_string(root, entry.ops_note_path),
                }
            )


def _build_benchmark_suite_note(
    summary: BenchmarkSuiteSummary,
    json_path: Path,
    csv_path: Path,
    note_path: Path,
    root: Path,
) -> str:
    lines = [
        "# Benchmark Suite",
        "",
        f"- command: `{summary.command}`",
        f"- seed: `{summary.seed}`",
        f"- benchmark_ids: {', '.join(summary.benchmark_ids)}",
        f"- json: `{_path_string(root, json_path)}`",
        f"- csv: `{_path_string(root, csv_path)}`",
        f"- note: `{_path_string(root, note_path)}`",
        "",
        "| benchmark_id | interfaces | class_labels | witness_counts | discrepancy_values | predictive_loop_scores |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in summary.entries:
        lines.append(
            "| "
            f"`{entry.benchmark_id}` | "
            f"`{', '.join(entry.measured_interfaces)}` | "
            f"`{', '.join(entry.class_labels)}` | "
            f"`{', '.join(str(value) for value in entry.witness_counts)}` | "
            f"`{', '.join(_format_float(value) for value in entry.discrepancy_values)}` | "
            f"`{', '.join(_format_float(value) for value in entry.predictive_loop_scores)}` |"
        )
    if summary.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in summary.warnings)
    lines.append("")
    return "\n".join(lines)


def _discovery_smoke_payload(
    summary: DiscoverySmokeSummary,
    root: Path,
) -> dict[str, object]:
    return {
        "seed": summary.seed,
        "command": summary.command,
        "primary_search_id": summary.primary_search_id,
        "search_ids": list(summary.search_ids),
        "atlas_json_path": _path_string(root, summary.atlas_json_path),
        "atlas_csv_path": _path_string(root, summary.atlas_csv_path),
        "atlas_note_path": _path_string(root, summary.atlas_note_path),
        "shortlist_json_path": _path_string(root, summary.shortlist_json_path),
        "shortlist_csv_path": _path_string(root, summary.shortlist_csv_path),
        "shortlist_note_path": _path_string(root, summary.shortlist_note_path),
        "shortlist_robustness_json_path": _path_string(
            root, summary.shortlist_robustness_json_path
        ),
        "shortlist_robustness_csv_path": _path_string(
            root, summary.shortlist_robustness_csv_path
        ),
        "shortlist_robustness_note_path": _path_string(
            root, summary.shortlist_robustness_note_path
        ),
        "multispace_json_path": _path_string(root, summary.multispace_json_path),
        "multispace_csv_path": _path_string(root, summary.multispace_csv_path),
        "multispace_note_path": _path_string(root, summary.multispace_note_path),
        "dedup_json_path": _path_string(root, summary.dedup_json_path),
        "dedup_csv_path": _path_string(root, summary.dedup_csv_path),
        "dedup_note_path": _path_string(root, summary.dedup_note_path),
        "promoted_exemplars_json_path": _path_string(
            root, summary.promoted_exemplars_json_path
        ),
        "promoted_exemplars_csv_path": _path_string(
            root, summary.promoted_exemplars_csv_path
        ),
        "promoted_exemplars_note_path": _path_string(
            root, summary.promoted_exemplars_note_path
        ),
        "class_counts": {label: count for label, count in summary.class_counts},
        "combined_shortlist_ids": list(summary.combined_shortlist_ids),
        "shortlisted_robustness": [
            {
                "candidate_id": candidate_id,
                "survival_fraction": survival_fraction,
                "meets_threshold": meets_threshold,
            }
            for candidate_id, survival_fraction, meets_threshold in summary.shortlisted_robustness
        ],
        "multispace_all_flat_space_ids": list(summary.multispace_all_flat_space_ids),
        "multispace_productive_space_ids": list(summary.multispace_productive_space_ids),
        "promoted_exemplar_qualified_ids": list(summary.promoted_exemplar_qualified_ids),
        "warnings": list(summary.warnings),
    }


def _build_discovery_smoke_note(
    summary: DiscoverySmokeSummary,
    json_path: Path,
    note_path: Path,
    root: Path,
) -> str:
    class_counts = ", ".join(f"{label}={count}" for label, count in summary.class_counts)
    robustness_lines = ", ".join(
        f"{candidate_id}:{_format_float(survival_fraction)}:{str(meets_threshold).lower()}"
        for candidate_id, survival_fraction, meets_threshold in summary.shortlisted_robustness
    )
    lines = [
        "# Discovery Smoke",
        "",
        f"- command: `{summary.command}`",
        f"- seed: `{summary.seed}`",
        f"- primary_search_id: `{summary.primary_search_id}`",
        f"- json: `{_path_string(root, json_path)}`",
        f"- note: `{_path_string(root, note_path)}`",
        f"- atlas: `{_path_string(root, summary.atlas_json_path)}`",
        f"- shortlist: `{_path_string(root, summary.shortlist_json_path)}`",
        f"- shortlist_robustness: `{_path_string(root, summary.shortlist_robustness_json_path)}`",
        f"- multispace: `{_path_string(root, summary.multispace_json_path)}`",
        f"- dedup: `{_path_string(root, summary.dedup_json_path)}`",
        f"- promoted_exemplars: `{_path_string(root, summary.promoted_exemplars_json_path)}`",
        "",
        f"- class_counts[{summary.primary_search_id}]: {class_counts}",
        f"- combined_shortlist_ids: {', '.join(summary.combined_shortlist_ids) or 'none'}",
        f"- shortlisted_robustness: {robustness_lines or 'none'}",
        f"- multispace_all_flat: {', '.join(summary.multispace_all_flat_space_ids) or 'none'}",
        f"- multispace_productive: {', '.join(summary.multispace_productive_space_ids) or 'none'}",
        f"- promoted_exemplars: {', '.join(summary.promoted_exemplar_qualified_ids) or 'none'}",
    ]
    if summary.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in summary.warnings)
    lines.append("")
    return "\n".join(lines)


def _path_string(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _format_float(value: float) -> str:
    return f"{value:.3f}"


def _repro_freeze_payload(summary: ReproFreezeSummary) -> dict[str, object]:
    return {
        "commands": list(summary.commands),
        "seed": summary.seed,
        "verified_from_temporary_clean_copy": summary.verified_from_temporary_clean_copy,
        "command_statuses": [
            {"command": status.command, "passed": status.passed}
            for status in summary.command_statuses
        ],
        "benchmark_suite_semantics_match": summary.benchmark_suite_semantics_match,
        "discovery_smoke_semantics_match": summary.discovery_smoke_semantics_match,
        "benchmark_suite_artifact_paths": list(summary.benchmark_suite_artifact_paths),
        "discovery_smoke_artifact_paths": list(summary.discovery_smoke_artifact_paths),
        "warnings": list(summary.warnings),
    }


def _copy_clean_repo(source_root: Path, destination_root: Path) -> None:
    cache_names = {
        ".git",
        ".lake",
        "build",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
    }

    def ignore(path: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in cache_names}
        return ignored

    shutil.copytree(source_root, destination_root, ignore=ignore)


def _run_make_target(repo_root: Path, target: str) -> bool:
    env = os.environ.copy()
    env["PYTHON"] = sys.executable
    try:
        subprocess.run(
            ["make", target],
            cwd=repo_root,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return False
    return True


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _benchmark_suite_stable_fields(payload: dict[str, object] | None) -> tuple[object, ...]:
    if payload is None:
        return ()
    return (
        tuple(payload["benchmark_ids"]),
        tuple(
            (
                entry["benchmark_id"],
                tuple(entry["measured_interfaces"]),
                tuple(entry["class_labels"]),
                tuple(entry["witness_counts"]),
                tuple(entry["discrepancy_values"]),
                tuple(entry["current_loop_scores"]),
                tuple(entry["predictive_loop_scores"]),
                entry["json_artifact_path"],
                entry["csv_artifact_path"],
                entry["ops_note_path"],
            )
            for entry in payload["entries"]
        ),
    )


def _discovery_smoke_stable_fields(payload: dict[str, object] | None) -> tuple[object, ...]:
    if payload is None:
        return ()
    return (
        payload["primary_search_id"],
        tuple(payload["search_ids"]),
        tuple(sorted(payload["class_counts"].items())),
        tuple(payload["combined_shortlist_ids"]),
        tuple(
            (
                entry["candidate_id"],
                entry["survival_fraction"],
                entry["meets_threshold"],
            )
            for entry in payload["shortlisted_robustness"]
        ),
        tuple(payload["multispace_all_flat_space_ids"]),
        tuple(payload["multispace_productive_space_ids"]),
        tuple(payload["promoted_exemplar_qualified_ids"]),
        payload["atlas_json_path"],
        payload["shortlist_json_path"],
        payload["shortlist_robustness_json_path"],
        payload["multispace_json_path"],
        payload["dedup_json_path"],
        payload["promoted_exemplars_json_path"],
    )
