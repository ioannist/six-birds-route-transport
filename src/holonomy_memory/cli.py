from __future__ import annotations

from argparse import ArgumentParser

from . import __version__
from .aggregate_outputs import aggregate_outputs
from .discovery_exemplars import promote_discovery_exemplars
from .discovery_diversity import run_discovery_diversity_audit
from .discovery import run_discovery_search
from .discovery_multispace import run_multispace_discovery
from .discovery_shortlist_robustness import run_discovery_shortlist_robustness
from .discovery_triage import triage_discovery_candidates
from .repro import run_benchmark_suite, run_discovery_smoke
from .runner import run_benchmark
from .robustness import run_core_robustness_suite, run_robustness_sweep


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="holonomy-memory",
        description="Holonomy-with-memory scaffold CLI.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run-benchmark",
        help="Run one benchmark manifest and write stable result artifacts.",
    )
    selection_group = run_parser.add_mutually_exclusive_group(required=True)
    selection_group.add_argument(
        "--benchmark-id",
        help="Benchmark inventory id to run.",
    )
    selection_group.add_argument(
        "--manifest-path",
        help="Explicit path to a benchmark manifest JSON file.",
    )
    run_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed to record with the run.",
    )
    run_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which artifacts/results, artifacts/tables, and docs/results are written.",
    )

    robustness_parser = subparsers.add_parser(
        "run-robustness",
        help="Run one benchmark perturbation sweep and write stable robustness artifacts.",
    )
    robustness_selection_group = robustness_parser.add_mutually_exclusive_group(
        required=True
    )
    robustness_selection_group.add_argument(
        "--benchmark-id",
        help="Benchmark inventory id to run.",
    )
    robustness_selection_group.add_argument(
        "--manifest-path",
        help="Explicit path to a benchmark manifest JSON file.",
    )
    robustness_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic base seed for the robustness sweep.",
    )
    robustness_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which robustness artifacts are written.",
    )

    core_suite_parser = subparsers.add_parser(
        "run-robustness-core-suite",
        help="Run the core robustness benchmark suite and write stable aggregate artifacts.",
    )
    core_suite_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic base seed for the core robustness suite.",
    )
    core_suite_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which robustness artifacts are written.",
    )

    discovery_parser = subparsers.add_parser(
        "run-discovery",
        help="Run one deterministic discovery search and write stable atlas artifacts.",
    )
    discovery_selection_group = discovery_parser.add_mutually_exclusive_group(required=True)
    discovery_selection_group.add_argument(
        "--search-id",
        help="Search-space inventory id to run.",
    )
    discovery_selection_group.add_argument(
        "--search-path",
        help="Explicit path to a search-space JSON file.",
    )
    discovery_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed to record with the discovery run.",
    )
    discovery_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which discovery atlas artifacts are written.",
    )

    triage_parser = subparsers.add_parser(
        "triage-discovery",
        help="Run the deterministic smoke discovery search and build a shortlist.",
    )
    triage_selection_group = triage_parser.add_mutually_exclusive_group(required=True)
    triage_selection_group.add_argument(
        "--search-id",
        help="Search-space inventory id to run and triage.",
    )
    triage_selection_group.add_argument(
        "--search-path",
        help="Explicit path to a search-space JSON file.",
    )
    triage_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed to record with the discovery triage run.",
    )
    triage_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which atlas and shortlist artifacts are written.",
    )
    triage_parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Shortlist size per ranking category.",
    )

    shortlist_robustness_parser = subparsers.add_parser(
        "run-discovery-shortlist-robustness",
        help="Run bounded robustness sweeps on the discovery shortlist.",
    )
    shortlist_robustness_selection_group = (
        shortlist_robustness_parser.add_mutually_exclusive_group(required=True)
    )
    shortlist_robustness_selection_group.add_argument(
        "--search-id",
        help="Search-space inventory id whose shortlist should be robustness-checked.",
    )
    shortlist_robustness_selection_group.add_argument(
        "--search-path",
        help="Explicit path to a search-space JSON file.",
    )
    shortlist_robustness_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed to record with the shortlisted robustness run.",
    )
    shortlist_robustness_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which shortlist-robustness artifacts are written.",
    )
    shortlist_robustness_parser.add_argument(
        "--trial-count",
        type=int,
        default=8,
        help="Deterministic trial count per shortlisted candidate.",
    )

    multispace_parser = subparsers.add_parser(
        "run-discovery-multispace",
        help="Run discovery and triage over the fixed multi-space smoke set.",
    )
    multispace_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed to record with the multi-space discovery run.",
    )
    multispace_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which multi-space discovery artifacts are written.",
    )

    diversity_parser = subparsers.add_parser(
        "audit-discovery-diversity",
        help="Audit dedup and diversity across the fixed multi-space shortlist union.",
    )
    diversity_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed to record with the diversity audit.",
    )
    diversity_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which diversity audit artifacts are written.",
    )

    exemplar_parser = subparsers.add_parser(
        "promote-discovery-exemplars",
        help="Promote one or two discovered exemplars into tracked artifacts.",
    )
    exemplar_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed to record with exemplar promotion.",
    )
    exemplar_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which exemplar promotion artifacts are written.",
    )
    exemplar_parser.add_argument(
        "--max-exemplars",
        type=int,
        default=2,
        help="Maximum number of exemplars to promote.",
    )

    aggregate_parser = subparsers.add_parser(
        "aggregate-outputs",
        help="Aggregate benchmark and discovery artifacts into combined tables and figures.",
    )
    aggregate_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which aggregate outputs and figures are written.",
    )

    benchmark_suite_parser = subparsers.add_parser(
        "run-benchmark-suite",
        help="Run the fixed benchmark suite and write stable aggregate artifacts.",
    )
    benchmark_suite_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed to record with the benchmark suite run.",
    )
    benchmark_suite_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which benchmark suite artifacts are written.",
    )

    discovery_smoke_parser = subparsers.add_parser(
        "run-discovery-smoke",
        help="Run the fixed discovery smoke orchestration and write stable summary artifacts.",
    )
    discovery_smoke_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed to record with the discovery smoke run.",
    )
    discovery_smoke_parser.add_argument(
        "--output-root",
        default=None,
        help="Root directory under which discovery smoke artifacts are written.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run-benchmark":
        artifacts = run_benchmark(
            benchmark_id=args.benchmark_id,
            manifest_path=args.manifest_path,
            seed=args.seed,
            output_root=args.output_root,
        )
        print(f"JSON: {artifacts.json_artifact_path}")
        print(f"CSV: {artifacts.csv_artifact_path}")
        print(f"Ops: {artifacts.ops_note_path}")
    if args.command == "run-robustness":
        artifacts = run_robustness_sweep(
            benchmark_id=args.benchmark_id,
            manifest_path=args.manifest_path,
            seed=args.seed,
            output_root=args.output_root,
        )
        summary = artifacts.benchmark_summary
        if summary is None:
            raise RuntimeError("benchmark robustness run did not produce a summary")
        print(f"JSON: {summary.json_artifact_path}")
        print(f"CSV: {summary.csv_artifact_path}")
        print(f"Ops: {summary.ops_note_path}")
        print(
            "Survival: "
            f"{float(summary.survival_fraction):.3f} "
            f"(threshold {float(summary.required_threshold):.3f})"
        )
    if args.command == "run-robustness-core-suite":
        artifacts = run_core_robustness_suite(
            seed=args.seed,
            output_root=args.output_root,
        )
        summary = artifacts.suite_summary
        if summary is None:
            raise RuntimeError("core robustness suite did not produce a summary")
        print(f"JSON: {summary.json_artifact_path}")
        print(f"CSV: {summary.csv_artifact_path}")
        print(f"Ops: {summary.ops_note_path}")
        print(f"Overall pass: {str(summary.overall_pass).lower()}")
    if args.command == "run-discovery":
        artifacts = run_discovery_search(
            search_id=args.search_id,
            search_path=args.search_path,
            seed=args.seed,
            output_root=args.output_root,
        )
        atlas = artifacts.atlas
        print(f"JSON: {artifacts.json_atlas_path}")
        print(f"CSV: {artifacts.csv_summary_path}")
        print(f"Ops: {artifacts.summary_note_path}")
        print(
            "Counts: "
            f"attempted={atlas.attempted_candidate_count} "
            f"realized={atlas.realized_candidate_count} "
            f"evaluated={atlas.evaluated_candidate_count}"
        )
    if args.command == "triage-discovery":
        artifacts = triage_discovery_candidates(
            search_id=args.search_id,
            search_path=args.search_path,
            seed=args.seed,
            output_root=args.output_root,
            top_k=args.top_k,
        )
        shortlist = artifacts.shortlist
        print(f"Atlas JSON: {artifacts.atlas_json_path}")
        print(f"Atlas CSV: {artifacts.atlas_csv_path}")
        print(f"Atlas Ops: {artifacts.atlas_note_path}")
        print(f"Shortlist JSON: {artifacts.shortlist_json_path}")
        print(f"Shortlist CSV: {artifacts.shortlist_csv_path}")
        print(f"Shortlist Ops: {artifacts.shortlist_note_path}")
        print(
            "Shortlist counts: "
            f"discrepancy={len(shortlist.top_by_discrepancy)} "
            f"predictive_loop={len(shortlist.top_by_predictive_loop)} "
            f"robustness_proxy={len(shortlist.top_by_robustness_proxy)} "
            f"combined={len(shortlist.combined_shortlist)}"
        )
    if args.command == "run-discovery-shortlist-robustness":
        artifacts = run_discovery_shortlist_robustness(
            search_id=args.search_id,
            search_path=args.search_path,
            seed=args.seed,
            output_root=args.output_root,
            trial_count=args.trial_count,
        )
        summary = artifacts.summary
        print(f"JSON: {artifacts.summary_json_path}")
        print(f"CSV: {artifacts.summary_csv_path}")
        print(f"Ops: {artifacts.summary_note_path}")
        print(
            "Overall pass: "
            f"{str(summary.overall_pass).lower()} "
            f"({sum(1 for entry in summary.entries if entry.meets_threshold)}/"
            f"{len(summary.entries)} above threshold)"
        )
    if args.command == "run-discovery-multispace":
        artifacts = run_multispace_discovery(
            seed=args.seed,
            output_root=args.output_root,
        )
        summary = artifacts.summary
        print(f"JSON: {artifacts.summary_json_path}")
        print(f"CSV: {artifacts.summary_csv_path}")
        print(f"Ops: {artifacts.summary_note_path}")
        print(
            "Spaces: "
            f"all_flat={','.join(summary.all_flat_space_ids) or 'none'} "
            f"productive={','.join(summary.productive_space_ids) or 'none'}"
        )
    if args.command == "audit-discovery-diversity":
        artifacts = run_discovery_diversity_audit(
            seed=args.seed,
            output_root=args.output_root,
        )
        summary = artifacts.summary
        print(f"JSON: {artifacts.summary_json_path}")
        print(f"CSV: {artifacts.summary_csv_path}")
        print(f"Ops: {artifacts.summary_note_path}")
        print(
            "Audit: "
            f"shortlisted={summary.total_shortlisted_candidate_count} "
            f"clusters={len(summary.clusters)} "
            f"unique_exemplars={summary.unique_exemplar_count}"
        )
    if args.command == "promote-discovery-exemplars":
        artifacts = promote_discovery_exemplars(
            seed=args.seed,
            output_root=args.output_root,
            max_exemplars=args.max_exemplars,
        )
        summary = artifacts.summary
        print(f"JSON: {artifacts.summary_json_path}")
        print(f"CSV: {artifacts.summary_csv_path}")
        print(f"Ops: {artifacts.index_note_path}")
        print(
            "Promoted: "
            + (",".join(summary.ordered_promoted_qualified_ids) or "none")
        )
    if args.command == "aggregate-outputs":
        artifacts = aggregate_outputs(output_root=args.output_root)
        print(f"JSON: {artifacts.combined_json_path}")
        print(f"CSV: {artifacts.combined_csv_path}")
        print(f"Figures: {artifacts.figure_manifest_path}")
        print(f"Ops: {artifacts.tracked_note_path}")
    if args.command == "run-benchmark-suite":
        artifacts = run_benchmark_suite(
            seed=args.seed,
            output_root=args.output_root,
        )
        print(f"JSON: {artifacts.summary_json_path}")
        print(f"CSV: {artifacts.summary_csv_path}")
        print(f"Ops: {artifacts.summary_note_path}")
    if args.command == "run-discovery-smoke":
        artifacts = run_discovery_smoke(
            seed=args.seed,
            output_root=args.output_root,
        )
        print(f"JSON: {artifacts.summary_json_path}")
        print(f"Ops: {artifacts.summary_note_path}")
    return 0
