from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .benchmarks import REPO_ROOT


BENCHMARK_RESULT_PATHS = (
    "artifacts/results/flat_control.result.json",
    "artifacts/results/protocol_trap_naive.result.json",
    "artifacts/results/protocol_trap_honest.result.json",
    "artifacts/results/flattenable_raw.result.json",
    "artifacts/results/flattenable_completed.result.json",
    "artifacts/results/latent_memory_base.result.json",
    "artifacts/results/latent_memory_refined.result.json",
    "artifacts/results/dissipative_memory.result.json",
    "artifacts/results/memory_wheel.result.json",
)

BENCHMARK_ROBUSTNESS_PATHS = (
    "artifacts/results/robustness/flat_control.robustness.json",
    "artifacts/results/robustness/protocol_trap_honest.robustness.json",
    "artifacts/results/robustness/flattenable_completed.robustness.json",
    "artifacts/results/robustness/latent_memory_base.robustness.json",
    "artifacts/results/robustness/latent_memory_refined.robustness.json",
    "artifacts/results/robustness/dissipative_memory.robustness.json",
    "artifacts/results/robustness/memory_wheel.robustness.json",
    "artifacts/results/robustness/core_suite.robustness.json",
)

DISCOVERY_ATLAS_PATHS = (
    "artifacts/results/discovery/fixed_support_core_small.atlas.json",
    "artifacts/results/discovery/cyclic_memory_small.atlas.json",
    "artifacts/results/discovery/groupoid_probe_small.atlas.json",
)

DISCOVERY_REQUIRED_PATHS = (
    "artifacts/results/discovery/cyclic_memory_small.shortlist_robustness.json",
    "artifacts/results/discovery/multi_space.discovery.json",
    "artifacts/results/discovery/multi_space.dedup.json",
    "artifacts/results/discovery/promoted_exemplars.json",
)

DISCOVERY_SHORTLIST_GLOB = "artifacts/results/discovery/*.shortlist.json"
DISCOVERY_PROMOTION_ROBUSTNESS_GLOB = "artifacts/results/discovery/*.promotion_robustness.json"
DEDUP_MEMBER_CSV_PATH = "artifacts/tables/discovery_multi_space_dedup.csv"


@dataclass(frozen=True)
class SourceArtifactRecord:
    category: str
    path: Path
    required: bool


@dataclass(frozen=True)
class AggregateRow:
    record_type: str
    source_artifact_path: str
    source_id: str
    benchmark_id: str | None = None
    search_id: str | None = None
    candidate_id: str | None = None
    qualified_id: str | None = None
    interface_id: str | None = None
    class_label: str | None = None
    current_quotient_size: int | None = None
    predictive_quotient_size: int | None = None
    max_fiber_size: int | None = None
    witness_count: int | None = None
    discrepancy_metric_value: float | None = None
    loop_action_score_current_quotient: float | None = None
    loop_action_score_predictive_quotient: float | None = None
    survival_fraction: float | None = None
    threshold: float | None = None
    meets_threshold: bool | None = None
    support_size: int | None = None
    interface_count: int | None = None
    carrier_family: str | None = None
    route_update_family: str | None = None
    observable_family: str | None = None
    continuation_catalog_family: str | None = None
    flat_count: int | None = None
    dissipative_count: int | None = None
    coherent_candidate_count: int | None = None
    nonflat_count: int | None = None
    shortlist_count: int | None = None
    cluster_id: str | None = None
    distinctness_kind: str | None = None


@dataclass(frozen=True)
class AggregateFigureRecord:
    figure_id: str
    figure_path: Path
    figure_kind: str
    source_artifact_paths: tuple[Path, ...]
    source_record_types: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class AggregateSummary:
    source_artifact_inventory: tuple[SourceArtifactRecord, ...]
    aggregate_rows: tuple[AggregateRow, ...]
    row_counts_by_record_type: tuple[tuple[str, int], ...]
    figure_records: tuple[AggregateFigureRecord, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AggregateArtifacts:
    combined_json_path: Path
    combined_csv_path: Path
    figure_manifest_path: Path
    tracked_note_path: Path
    ordered_figure_paths: tuple[Path, ...]
    summary: AggregateSummary


def aggregate_outputs(
    *,
    output_root: str | Path | None = None,
    source_root: str | Path | None = None,
) -> AggregateArtifacts:
    resolved_source_root = Path(source_root) if source_root is not None else REPO_ROOT
    inventory, warnings = collect_source_artifacts(source_root=resolved_source_root)
    rows = build_aggregate_rows(inventory)
    figure_records = generate_aggregate_figures(
        rows=rows,
        output_root=output_root,
    )
    row_counts = tuple(
        (record_type, sum(1 for row in rows if row.record_type == record_type))
        for record_type in (
            "benchmark_interface",
            "benchmark_robustness",
            "discovery_space",
            "discovery_candidate",
            "discovery_shortlist_candidate",
            "discovery_shortlist_robustness",
            "discovery_dedup_member",
            "discovery_promoted_exemplar",
            "discovery_promotion_robustness",
        )
        if any(row.record_type == record_type for row in rows)
    )
    summary = AggregateSummary(
        source_artifact_inventory=inventory,
        aggregate_rows=rows,
        row_counts_by_record_type=row_counts,
        figure_records=figure_records,
        warnings=tuple(warnings),
    )
    return write_aggregate_outputs(summary=summary, output_root=output_root)


def write_aggregate_outputs(
    *,
    summary: AggregateSummary,
    output_root: str | Path | None = None,
) -> AggregateArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    portable_root = REPO_ROOT if output_root is None else None
    combined_json_path = root / "artifacts" / "results" / "aggregate_outputs.json"
    combined_csv_path = root / "artifacts" / "tables" / "aggregate_outputs.csv"
    figure_manifest_path = root / "artifacts" / "results" / "aggregate_figures.json"
    tracked_note_path = root / "docs" / "results" / "aggregate_outputs.md"
    combined_json_path.parent.mkdir(parents=True, exist_ok=True)
    combined_csv_path.parent.mkdir(parents=True, exist_ok=True)
    figure_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    tracked_note_path.parent.mkdir(parents=True, exist_ok=True)

    combined_json_path.write_text(
        json.dumps(_summary_payload(summary, portable_root=portable_root), indent=2)
        + "\n",
        encoding="utf-8",
    )
    _write_rows_csv(
        summary.aggregate_rows,
        combined_csv_path,
        portable_root=portable_root,
    )
    figure_manifest_path.write_text(
        json.dumps(
            _figure_manifest_payload(
                summary.figure_records,
                portable_root=portable_root,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    tracked_note_path.write_text(
        _build_note(summary, combined_json_path, combined_csv_path, figure_manifest_path),
        encoding="utf-8",
    )
    return AggregateArtifacts(
        combined_json_path=combined_json_path,
        combined_csv_path=combined_csv_path,
        figure_manifest_path=figure_manifest_path,
        tracked_note_path=tracked_note_path,
        ordered_figure_paths=tuple(record.figure_path for record in summary.figure_records),
        summary=summary,
    )


def collect_source_artifacts(
    *,
    source_root: Path,
) -> tuple[tuple[SourceArtifactRecord, ...], tuple[str, ...]]:
    inventory: list[SourceArtifactRecord] = []
    warnings: list[str] = []

    for relative_path in BENCHMARK_RESULT_PATHS:
        inventory.append(
            _require_source_artifact(
                source_root=source_root,
                relative_path=relative_path,
                category="benchmark_result",
            )
        )
    for relative_path in BENCHMARK_ROBUSTNESS_PATHS:
        inventory.append(
            _require_source_artifact(
                source_root=source_root,
                relative_path=relative_path,
                category="benchmark_robustness",
            )
        )
    for relative_path in DISCOVERY_ATLAS_PATHS:
        inventory.append(
            _require_source_artifact(
                source_root=source_root,
                relative_path=relative_path,
                category="discovery_atlas",
            )
        )

    shortlist_paths = sorted(source_root.glob(DISCOVERY_SHORTLIST_GLOB))
    if not shortlist_paths:
        raise FileNotFoundError("no discovery shortlist artifacts found for aggregation")
    for path in shortlist_paths:
        inventory.append(
            SourceArtifactRecord(
                category="discovery_shortlist",
                path=path.resolve(),
                required=True,
            )
        )

    for relative_path in DISCOVERY_REQUIRED_PATHS:
        inventory.append(
            _require_source_artifact(
                source_root=source_root,
                relative_path=relative_path,
                category="discovery_summary",
            )
        )

    inventory.append(
        _require_source_artifact(
            source_root=source_root,
            relative_path=DEDUP_MEMBER_CSV_PATH,
            category="discovery_dedup_csv",
        )
    )

    promotion_paths = sorted(source_root.glob(DISCOVERY_PROMOTION_ROBUSTNESS_GLOB))
    if not promotion_paths:
        warnings.append("optional discovery promotion-robustness artifacts are absent")
    for path in promotion_paths:
        inventory.append(
            SourceArtifactRecord(
                category="discovery_promotion_robustness",
                path=path.resolve(),
                required=False,
            )
        )
    return tuple(inventory), tuple(warnings)


def build_aggregate_rows(
    inventory: tuple[SourceArtifactRecord, ...],
) -> tuple[AggregateRow, ...]:
    rows: list[AggregateRow] = []
    for artifact in inventory:
        if artifact.category == "benchmark_result":
            rows.extend(_rows_from_benchmark_result(artifact.path))
        elif artifact.category == "benchmark_robustness":
            rows.extend(_rows_from_benchmark_robustness(artifact.path))
        elif artifact.category == "discovery_atlas":
            rows.extend(_rows_from_discovery_atlas(artifact.path))
        elif artifact.category == "discovery_shortlist":
            rows.extend(_rows_from_discovery_shortlist(artifact.path))
        elif artifact.category == "discovery_summary":
            if artifact.path.name == "multi_space.discovery.json":
                rows.extend(_rows_from_discovery_multispace(artifact.path))
            elif artifact.path.name == "promoted_exemplars.json":
                rows.extend(_rows_from_promoted_exemplars(artifact.path))
            elif artifact.path.name == "cyclic_memory_small.shortlist_robustness.json":
                rows.extend(_rows_from_shortlist_robustness(artifact.path))
        elif artifact.category == "discovery_dedup_csv":
            rows.extend(_rows_from_dedup_csv(artifact.path))
        elif artifact.category == "discovery_promotion_robustness":
            rows.extend(_rows_from_promotion_robustness(artifact.path))
    return tuple(rows)


def generate_aggregate_figures(
    *,
    rows: tuple[AggregateRow, ...],
    output_root: str | Path | None = None,
) -> tuple[AggregateFigureRecord, ...]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    root = Path(output_root) if output_root is not None else REPO_ROOT
    figure_dir = root / "artifacts" / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    figure_records = [
        _plot_q_vs_m(rows, figure_dir, plt),
        _plot_witness_counts(rows, figure_dir, plt),
        _plot_loop_action_scores(rows, figure_dir, plt),
        _plot_robustness_fractions(rows, figure_dir, plt),
        _plot_class_distributions(rows, figure_dir, plt),
    ]
    return tuple(figure_records)


def _require_source_artifact(
    *,
    source_root: Path,
    relative_path: str,
    category: str,
) -> SourceArtifactRecord:
    path = (source_root / relative_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"required aggregation source artifact is missing: {relative_path}"
        )
    return SourceArtifactRecord(category=category, path=path, required=True)


def _rows_from_benchmark_result(path: Path) -> list[AggregateRow]:
    payload = _load_json(path)
    rows: list[AggregateRow] = []
    for record in payload["records"]:
        rows.append(
            AggregateRow(
                record_type="benchmark_interface",
                source_artifact_path=str(path),
                source_id=f"{record['benchmark_id']}:{record['interface_id']}",
                benchmark_id=record["benchmark_id"],
                interface_id=record["interface_id"],
                class_label=record["class_label"],
                current_quotient_size=record["current_quotient_size"],
                predictive_quotient_size=record["predictive_quotient_size"],
                max_fiber_size=record["max_fiber_size"],
                witness_count=record["witness_count"],
                discrepancy_metric_value=record["discrepancy_metric_value"],
                loop_action_score_current_quotient=record["loop_action_score_current_quotient"],
                loop_action_score_predictive_quotient=record["loop_action_score_predictive_quotient"],
            )
        )
    return rows


def _rows_from_benchmark_robustness(path: Path) -> list[AggregateRow]:
    payload = _load_json(path)
    if "benchmark_id" in payload:
        benchmark_id = payload["benchmark_id"]
        return [
            AggregateRow(
                record_type="benchmark_robustness",
                source_artifact_path=str(path),
                source_id=benchmark_id,
                benchmark_id=benchmark_id,
                survival_fraction=payload["survival_fraction"],
                threshold=payload["threshold"],
                meets_threshold=payload["meets_threshold"],
            )
        ]
    if payload.get("suite_id") == "core_suite":
        return [
            AggregateRow(
                record_type="benchmark_robustness",
                source_artifact_path=str(path),
                source_id="core_suite",
                benchmark_id="core_suite",
                survival_fraction=1.0 if payload["overall_pass"] else 0.0,
                threshold=1.0,
                meets_threshold=payload["overall_pass"],
            )
        ]
    return []


def _rows_from_discovery_atlas(path: Path) -> list[AggregateRow]:
    payload = _load_json(path)
    rows: list[AggregateRow] = []
    for candidate in payload["candidates"]:
        spec = candidate["candidate_spec"]
        primary_metrics = candidate["primary_metrics"]
        search_id = payload["search_id"]
        candidate_id = candidate["candidate_id"]
        rows.append(
            AggregateRow(
                record_type="discovery_candidate",
                source_artifact_path=str(path),
                source_id=f"{search_id}:{candidate_id}",
                search_id=search_id,
                candidate_id=candidate_id,
                qualified_id=f"{search_id}:{candidate_id}",
                interface_id=candidate["primary_interface_id"],
                class_label=candidate["candidate_label"],
                current_quotient_size=primary_metrics["current_quotient_size"],
                predictive_quotient_size=primary_metrics["predictive_quotient_size"],
                max_fiber_size=primary_metrics["max_fiber_size"],
                witness_count=primary_metrics["witness_count"],
                discrepancy_metric_value=primary_metrics["discrepancy_metric_value"],
                loop_action_score_current_quotient=primary_metrics["current_loop_score"],
                loop_action_score_predictive_quotient=primary_metrics["predictive_loop_score"],
                support_size=spec["support_size"],
                interface_count=spec["interface_count"],
                carrier_family=spec["carrier_family"],
                route_update_family=spec["route_update_family"],
                observable_family=spec["observable_family"],
                continuation_catalog_family=spec["continuation_catalog_family"],
            )
        )
    return rows


def _rows_from_discovery_shortlist(path: Path) -> list[AggregateRow]:
    payload = _load_json(path)
    search_id = payload["search_id"]
    rows: list[AggregateRow] = []
    for entry in payload["combined_shortlist"]:
        candidate_id = entry["candidate_id"]
        rows.append(
            AggregateRow(
                record_type="discovery_shortlist_candidate",
                source_artifact_path=str(path),
                source_id=f"{search_id}:{candidate_id}",
                search_id=search_id,
                candidate_id=candidate_id,
                qualified_id=f"{search_id}:{candidate_id}",
                interface_id=entry["primary_interface_id"],
                class_label=entry["class_label"],
                witness_count=entry["primary_witness_count"],
                discrepancy_metric_value=entry["primary_discrepancy_metric_value"],
                loop_action_score_predictive_quotient=entry["primary_predictive_loop_score"],
            )
        )
    return rows


def _rows_from_shortlist_robustness(path: Path) -> list[AggregateRow]:
    payload = _load_json(path)
    search_id = payload["search_id"]
    rows: list[AggregateRow] = []
    for entry in payload["entries"]:
        candidate_id = entry["candidate_id"]
        rows.append(
            AggregateRow(
                record_type="discovery_shortlist_robustness",
                source_artifact_path=str(path),
                source_id=f"{search_id}:{candidate_id}",
                search_id=search_id,
                candidate_id=candidate_id,
                qualified_id=f"{search_id}:{candidate_id}",
                interface_id=entry["primary_interface_id"],
                class_label=entry["class_label"],
                witness_count=entry["primary_witness_count"],
                discrepancy_metric_value=entry["primary_discrepancy_metric_value"],
                loop_action_score_predictive_quotient=entry["primary_predictive_loop_score"],
                survival_fraction=entry["survival_fraction"],
                threshold=entry["threshold"],
                meets_threshold=entry["meets_threshold"],
            )
        )
    return rows


def _rows_from_discovery_multispace(path: Path) -> list[AggregateRow]:
    payload = _load_json(path)
    rows: list[AggregateRow] = []
    for entry in payload["entries"]:
        rows.append(
            AggregateRow(
                record_type="discovery_space",
                source_artifact_path=str(path),
                source_id=entry["search_id"],
                search_id=entry["search_id"],
                flat_count=entry["flat_count"],
                dissipative_count=entry["dissipative_count"],
                coherent_candidate_count=entry["coherent_candidate_count"],
                nonflat_count=entry["nonflat_count"],
                shortlist_count=entry["shortlist_count"],
            )
        )
    return rows


def _rows_from_dedup_csv(path: Path) -> list[AggregateRow]:
    rows: list[AggregateRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for item in reader:
            search_id = item["search_id"]
            candidate_id = item["candidate_id"]
            rows.append(
                AggregateRow(
                    record_type="discovery_dedup_member",
                    source_artifact_path=str(path),
                    source_id=f"{search_id}:{candidate_id}",
                    search_id=search_id,
                    candidate_id=candidate_id,
                    qualified_id=f"{search_id}:{candidate_id}",
                    interface_id=item["primary_interface_id"],
                    class_label=item["class_label"],
                    current_quotient_size=_maybe_int(item["primary_current_quotient_size"]),
                    predictive_quotient_size=_maybe_int(item["primary_predictive_quotient_size"]),
                    max_fiber_size=_maybe_int(item["primary_max_fiber_size"]),
                    witness_count=_maybe_int(item["primary_witness_count"]),
                    discrepancy_metric_value=_maybe_float(item["primary_discrepancy_metric_value"]),
                    loop_action_score_current_quotient=_maybe_float(item["primary_current_loop_score"]),
                    loop_action_score_predictive_quotient=_maybe_float(item["primary_predictive_loop_score"]),
                    support_size=_maybe_int(item["support_size"]),
                    interface_count=_maybe_int(item["interface_count"]),
                    carrier_family=item["carrier_family"],
                    route_update_family=item["route_update_family"],
                    observable_family=item["observable_family"],
                    continuation_catalog_family=item["continuation_catalog_family"],
                    cluster_id=item["cluster_id"],
                    distinctness_kind=item["match_kind"],
                )
            )
    return rows


def _rows_from_promoted_exemplars(path: Path) -> list[AggregateRow]:
    payload = _load_json(path)
    rows: list[AggregateRow] = []
    for entry in payload["promoted_exemplars"]:
        rows.append(
            AggregateRow(
                record_type="discovery_promoted_exemplar",
                source_artifact_path=str(path),
                source_id=entry["qualified_id"],
                search_id=entry["search_id"],
                candidate_id=entry["candidate_id"],
                qualified_id=entry["qualified_id"],
                interface_id=entry["primary_interface_id"],
                class_label=entry["class_label"],
                discrepancy_metric_value=entry["primary_discrepancy_metric_value"],
                loop_action_score_predictive_quotient=entry["primary_predictive_loop_score"],
                survival_fraction=entry["survival_fraction"],
                threshold=entry["threshold"],
                meets_threshold=entry["meets_threshold"],
                cluster_id=entry["cluster_id"],
                distinctness_kind=entry["distinctness_kind"],
            )
        )
    return rows


def _rows_from_promotion_robustness(path: Path) -> list[AggregateRow]:
    payload = _load_json(path)
    return [
        AggregateRow(
            record_type="discovery_promotion_robustness",
            source_artifact_path=str(path),
            source_id=payload["qualified_id"],
            search_id=payload["search_id"],
            candidate_id=payload["candidate_id"],
            qualified_id=payload["qualified_id"],
            interface_id=payload["primary_interface_id"],
            class_label=payload["class_label"],
            survival_fraction=payload["survival_fraction"],
            threshold=payload["threshold"],
            meets_threshold=payload["meets_threshold"],
        )
    ]


def _plot_q_vs_m(rows: tuple[AggregateRow, ...], figure_dir: Path, plt: Any) -> AggregateFigureRecord:
    selected = [
        row
        for row in rows
        if row.record_type in {"benchmark_interface", "discovery_candidate"}
        and row.current_quotient_size is not None
        and row.predictive_quotient_size is not None
    ]
    figure_path = figure_dir / "q_vs_m.png"
    fig, ax = plt.subplots(figsize=(6, 4))
    benchmark_rows = [row for row in selected if row.record_type == "benchmark_interface"]
    discovery_rows = [row for row in selected if row.record_type == "discovery_candidate"]
    if benchmark_rows:
        ax.scatter(
            [row.current_quotient_size for row in benchmark_rows],
            [row.predictive_quotient_size for row in benchmark_rows],
            label="benchmark",
        )
    if discovery_rows:
        ax.scatter(
            [row.current_quotient_size for row in discovery_rows],
            [row.predictive_quotient_size for row in discovery_rows],
            label="discovery",
        )
    ax.set_xlabel("|Q|")
    ax.set_ylabel("|M|")
    ax.set_title("|Q| vs |M|")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_path)
    plt.close(fig)
    return _figure_record(
        figure_id="q_vs_m",
        figure_path=figure_path,
        figure_kind="scatter",
        rows=selected,
        description="Current versus predictive quotient sizes for benchmark interfaces and discovery candidates.",
    )


def _plot_witness_counts(rows: tuple[AggregateRow, ...], figure_dir: Path, plt: Any) -> AggregateFigureRecord:
    selected = [
        row
        for row in rows
        if row.record_type in {"benchmark_interface", "discovery_promoted_exemplar"}
        and row.witness_count is not None
    ]
    figure_path = figure_dir / "witness_counts.png"
    fig, ax = plt.subplots(figsize=(8, 4))
    labels = [row.source_id for row in selected]
    values = [row.witness_count for row in selected]
    ax.bar(range(len(selected)), values)
    ax.set_xticks(range(len(selected)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("witness_count")
    ax.set_title("Witness Counts")
    fig.tight_layout()
    fig.savefig(figure_path)
    plt.close(fig)
    return _figure_record(
        figure_id="witness_counts",
        figure_path=figure_path,
        figure_kind="bar",
        rows=selected,
        description="Witness counts across benchmark interfaces and promoted discovery exemplars.",
    )


def _plot_loop_action_scores(rows: tuple[AggregateRow, ...], figure_dir: Path, plt: Any) -> AggregateFigureRecord:
    selected = [
        row
        for row in rows
        if row.record_type in {"benchmark_interface", "discovery_promoted_exemplar"}
        and row.loop_action_score_predictive_quotient is not None
    ]
    figure_path = figure_dir / "loop_action_scores.png"
    fig, ax = plt.subplots(figsize=(8, 4))
    x_positions = list(range(len(selected)))
    current_scores = [row.loop_action_score_current_quotient or 0.0 for row in selected]
    predictive_scores = [row.loop_action_score_predictive_quotient or 0.0 for row in selected]
    ax.bar([position - 0.2 for position in x_positions], current_scores, width=0.4, label="current")
    ax.bar([position + 0.2 for position in x_positions], predictive_scores, width=0.4, label="predictive")
    ax.set_xticks(x_positions)
    ax.set_xticklabels([row.source_id for row in selected], rotation=45, ha="right")
    ax.set_ylabel("loop action score")
    ax.set_title("Loop-Action Scores")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_path)
    plt.close(fig)
    return _figure_record(
        figure_id="loop_action_scores",
        figure_path=figure_path,
        figure_kind="grouped_bar",
        rows=selected,
        description="Current versus predictive loop-action scores for benchmark interfaces and promoted exemplars.",
    )


def _plot_robustness_fractions(rows: tuple[AggregateRow, ...], figure_dir: Path, plt: Any) -> AggregateFigureRecord:
    selected = [
        row
        for row in rows
        if row.record_type
        in {
            "benchmark_robustness",
            "discovery_shortlist_robustness",
            "discovery_promotion_robustness",
            "discovery_promoted_exemplar",
        }
        and row.survival_fraction is not None
    ]
    figure_path = figure_dir / "robustness_fractions.png"
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(range(len(selected)), [row.survival_fraction for row in selected])
    ax.set_xticks(range(len(selected)))
    ax.set_xticklabels([row.source_id for row in selected], rotation=45, ha="right")
    ax.set_ylabel("survival_fraction")
    ax.set_title("Robustness Fractions")
    fig.tight_layout()
    fig.savefig(figure_path)
    plt.close(fig)
    return _figure_record(
        figure_id="robustness_fractions",
        figure_path=figure_path,
        figure_kind="bar",
        rows=selected,
        description="Benchmark and discovery robustness fractions from robustness summaries and promoted exemplars.",
    )


def _plot_class_distributions(rows: tuple[AggregateRow, ...], figure_dir: Path, plt: Any) -> AggregateFigureRecord:
    selected = [row for row in rows if row.record_type == "discovery_space"]
    figure_path = figure_dir / "class_distributions.png"
    fig, ax = plt.subplots(figsize=(7, 4))
    x_positions = list(range(len(selected)))
    ax.bar([position - 0.25 for position in x_positions], [row.flat_count or 0 for row in selected], width=0.25, label="flat")
    ax.bar([position for position in x_positions], [row.dissipative_count or 0 for row in selected], width=0.25, label="dissipative")
    ax.bar([position + 0.25 for position in x_positions], [row.coherent_candidate_count or 0 for row in selected], width=0.25, label="coherent_candidate")
    ax.set_xticks(x_positions)
    ax.set_xticklabels([row.search_id for row in selected], rotation=20, ha="right")
    ax.set_ylabel("candidate count")
    ax.set_title("Discovery Class Distributions")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_path)
    plt.close(fig)
    return _figure_record(
        figure_id="class_distributions",
        figure_path=figure_path,
        figure_kind="grouped_bar",
        rows=selected,
        description="Discovery class distributions by search space, including the all-flat control space.",
    )


def _figure_record(
    *,
    figure_id: str,
    figure_path: Path,
    figure_kind: str,
    rows: list[AggregateRow],
    description: str,
) -> AggregateFigureRecord:
    return AggregateFigureRecord(
        figure_id=figure_id,
        figure_path=figure_path.resolve(),
        figure_kind=figure_kind,
        source_artifact_paths=tuple(
            Path(path).resolve()
            for path in sorted({row.source_artifact_path for row in rows})
        ),
        source_record_types=tuple(sorted({row.record_type for row in rows})),
        description=description,
    )


def _summary_payload(
    summary: AggregateSummary,
    *,
    portable_root: Path | None,
) -> dict[str, object]:
    return {
        "source_artifact_inventory": [
            {
                "category": artifact.category,
                "path": _serialized_path(artifact.path, portable_root),
                "required": artifact.required,
            }
            for artifact in summary.source_artifact_inventory
        ],
        "row_counts_by_record_type": {
            record_type: count for record_type, count in summary.row_counts_by_record_type
        },
        "aggregate_rows": [
            {
                **asdict(row),
                "source_artifact_path": _serialized_path(
                    row.source_artifact_path,
                    portable_root,
                ),
            }
            for row in summary.aggregate_rows
        ],
        "figure_records": [
            {
                "figure_id": record.figure_id,
                "figure_path": _serialized_path(record.figure_path, portable_root),
                "figure_kind": record.figure_kind,
                "source_artifact_paths": [
                    _serialized_path(path, portable_root)
                    for path in record.source_artifact_paths
                ],
                "source_record_types": list(record.source_record_types),
                "description": record.description,
            }
            for record in summary.figure_records
        ],
        "warnings": list(summary.warnings),
    }


def _figure_manifest_payload(
    figure_records: tuple[AggregateFigureRecord, ...],
    *,
    portable_root: Path | None,
) -> dict[str, object]:
    return {
        "figures": [
            {
                "figure_id": record.figure_id,
                "figure_path": _serialized_path(record.figure_path, portable_root),
                "figure_kind": record.figure_kind,
                "source_artifact_paths": [
                    _serialized_path(path, portable_root)
                    for path in record.source_artifact_paths
                ],
                "source_record_types": list(record.source_record_types),
                "description": record.description,
            }
            for record in figure_records
        ]
    }


def _write_rows_csv(
    rows: tuple[AggregateRow, ...],
    csv_path: Path,
    *,
    portable_root: Path | None,
) -> None:
    fieldnames = [
        "record_type",
        "source_artifact_path",
        "source_id",
        "benchmark_id",
        "search_id",
        "candidate_id",
        "qualified_id",
        "interface_id",
        "class_label",
        "current_quotient_size",
        "predictive_quotient_size",
        "max_fiber_size",
        "witness_count",
        "discrepancy_metric_value",
        "loop_action_score_current_quotient",
        "loop_action_score_predictive_quotient",
        "survival_fraction",
        "threshold",
        "meets_threshold",
        "support_size",
        "interface_count",
        "carrier_family",
        "route_update_family",
        "observable_family",
        "continuation_catalog_family",
        "flat_count",
        "dissipative_count",
        "coherent_candidate_count",
        "nonflat_count",
        "shortlist_count",
        "cluster_id",
        "distinctness_kind",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            payload["source_artifact_path"] = _serialized_path(
                row.source_artifact_path,
                portable_root,
            )
            writer.writerow(payload)


def _build_note(
    summary: AggregateSummary,
    combined_json_path: Path,
    combined_csv_path: Path,
    figure_manifest_path: Path,
) -> str:
    benchmark_source_count = sum(
        1 for artifact in summary.source_artifact_inventory if artifact.category.startswith("benchmark")
    )
    discovery_source_count = sum(
        1 for artifact in summary.source_artifact_inventory if artifact.category.startswith("discovery")
    )
    lines = [
        "# Aggregate Outputs",
        "",
        f"- combined json path: {_relative_string(combined_json_path)}",
        f"- combined csv path: {_relative_string(combined_csv_path)}",
        f"- figure manifest path: {_relative_string(figure_manifest_path)}",
        "- row counts by record type:",
    ]
    for record_type, count in summary.row_counts_by_record_type:
        lines.append(f"  - {record_type}: {count}")
    lines.extend(
        [
            "- generated figures:",
            *[f"  - {_relative_string(record.figure_path)}" for record in summary.figure_records],
            (
                "- source coverage summary: "
                f"benchmark sources={benchmark_source_count}, "
                f"discovery sources={discovery_source_count}"
            ),
            "- conclusion: the implementation-facing aggregate is ready for follow-up writing work.",
        ]
    )
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _maybe_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _maybe_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return float(int(numerator) / int(denominator))
    return float(value)


def _relative_string(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _serialized_path(path: str | Path, portable_root: Path | None) -> str:
    resolved = Path(path).resolve()
    if portable_root is not None:
        try:
            return resolved.relative_to(portable_root.resolve()).as_posix()
        except ValueError:
            pass
    return str(resolved)
