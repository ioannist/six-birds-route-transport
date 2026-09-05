from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .benchmarks.classical_master_test import run_classical_master_test_benchmark
from .benchmarks.epistemic_six_state import run_epistemic_six_state_benchmark
from .benchmarks.parity_context_witness import run_parity_context_witness_benchmark
from .crosscheck.exact import run_exact_crosscheck
from .evidence.pack import build_paper_evidence_pack
from .findings.registry import build_findings_registry
from .hierarchy.atlas import build_three_axis_hierarchy
from .reporting.ccd_report import load_observation_trace_file, write_ccd_report
from .reporting.context_discovery_report import write_context_discovery_report
from .reporting.pica_context_discovery_report import (
    write_pica_context_discovery_report,
)
from .reporting.pica_provenance_refresh_report import (
    write_pica_provenance_refresh_report,
)
from .reporting.flattening_report import write_flattening_intervention_report
from .reporting.hidden_record_report import write_hidden_record_intervention_report
from .reporting.package_build_report import write_package_build_report
from .reporting.pica_bridge_report import write_pica_bridge_report
from .reporting.pica_packaging_surface_report import (
    write_pica_packaging_surface_report,
)
from .pica_bridge.discovery_readiness import analyze_pica_discovery_readiness
from .pica_bridge.pilot import run_pica_pilot_campaign
from .reporting.rm_report import load_observation_trace_files as load_rm_trace_files
from .reporting.rm_report import write_rm_report
from .reporting.sec_report import load_observation_trace_files, write_sec_report
from .audits.quotient_feasibility import run_quotient_feasibility_audit
from .provenance.audit import write_provenance_audit_report
from .pipeline.end_to_end import (
    run_benchmark_suite,
    run_intervention_suite,
    run_lean_build,
    run_search_suite,
)
from .redteam.suite import run_redteam_suite
from .discovery.models import (
    DiscoveredEventGenerationThresholds,
    SharedEventInferenceThresholds,
)
from .discovery.pica_context_discovery import DEFAULT_PICA_CONTEXT_DISCOVERY
from .falsification.discovered_case import run_discovered_case_falsification
from .falsification.flagship_bundle import run_flagship_control_bundle
from .robustness.noise_runner import run_noise_robustness_sweep
from .reporting.structural_report import (
    generate_structural_report,
    load_event_package_instance,
)
from .run_registry import DEFAULT_RESULTS_CATEGORIES, create_dummy_run, list_runs
from .search.pica_closure_diverse_search import (
    run_pica_closure_diverse_search,
)
from .search.pica_frozen_slice_obstruction import run_pica_frozen_slice_search
from .search.pica_packaging_conflict import run_pica_packaging_conflict_search
from .search.lens_axis import run_lens_axis_search
from .search.lens_axis_cross_resolution import (
    run_lens_axis_cross_resolution_closure,
)
from .search.lens_axis_finalization import run_lens_axis_finalization
from .search.mechanism_axis import run_mechanism_axis_search
from .search.packaging_axis import run_packaging_axis_search
from .search.atlas_upgrade import run_atlas_upgrade
from .search.pica_targeted_obstruction import run_pica_targeted_obstruction_search
from .search.targeted_nonextendability import run_targeted_nonextendability_search
from .search.sweep import run_search_sweep
from .schemas.common import SchemaKind
from .substrates.engine import load_substrate_config, write_substrate_run
from .validation import load_model, validate_file

PIPELINE_RESULTS_CATEGORIES = [*DEFAULT_RESULTS_CATEGORIES, "results"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sixbirds_event")
    parser.add_argument(
        "--version", action="version", version=f"sixbirds-event {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser(
        "validate",
        help="validate a JSON file against one of the supported schemas",
    )
    validate_parser.add_argument("file", help="path to a JSON file")
    validate_parser.add_argument(
        "--kind",
        default="auto",
        choices=[
            "auto",
            *[kind.value for kind in SchemaKind],
        ],
        help="schema kind to validate or auto-detect from the version field",
    )

    runs_parser = subparsers.add_parser(
        "runs",
        help="create and list schema-valid run registry entries",
    )
    runs_subparsers = runs_parser.add_subparsers(dest="runs_command")

    create_dummy_parser = runs_subparsers.add_parser(
        "create-dummy",
        help="create a dummy run directory with a valid manifest",
    )
    create_dummy_parser.add_argument(
        "--category",
        default="benchmarks",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the run directory",
    )
    create_dummy_parser.add_argument("--label", default=None, help="optional run label")
    create_dummy_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="deterministic seed recorded in the manifest",
    )
    create_dummy_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    create_dummy_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    list_parser = runs_subparsers.add_parser(
        "list",
        help="list registered runs by scanning manifest files",
    )
    list_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    hierarchy_parser = subparsers.add_parser(
        "hierarchy",
        help="build hierarchy aggregation and comparison artifacts",
    )
    hierarchy_subparsers = hierarchy_parser.add_subparsers(dest="hierarchy_command")
    build_three_axis_parser = hierarchy_subparsers.add_parser(
        "build-three-axis",
        help="build the cross-axis comparative hierarchy atlas",
    )
    build_three_axis_parser.add_argument(
        "file",
        help="path to a three-axis-hierarchy-config JSON file",
    )
    build_three_axis_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the hierarchy bundle",
    )
    build_three_axis_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    build_three_axis_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    build_three_axis_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-30T00:00:00Z",
    )
    build_three_axis_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    evidence_parser = subparsers.add_parser(
        "evidence",
        help="build stable paper-facing evidence-pack artifacts",
    )
    evidence_subparsers = evidence_parser.add_subparsers(dest="evidence_command")
    build_pack_parser = evidence_subparsers.add_parser(
        "build-pack",
        help="build the stable paper-facing evidence pack",
    )
    build_pack_parser.add_argument(
        "file",
        help="path to a paper-evidence-pack JSON file",
    )
    build_pack_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the evidence-pack bundle",
    )
    build_pack_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    build_pack_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    build_pack_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-31T00:00:00Z",
    )
    build_pack_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    structural_parser = subparsers.add_parser(
        "structural",
        help="run structural analysis and emit report artifacts",
    )
    structural_subparsers = structural_parser.add_subparsers(dest="structural_command")

    report_parser = structural_subparsers.add_parser(
        "report",
        help="generate a structural report bundle for an event-package instance",
    )
    report_parser.add_argument(
        "file", help="path to an event-package instance JSON file"
    )
    report_parser.add_argument(
        "--category",
        default="benchmarks",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the report run",
    )
    report_parser.add_argument("--label", default=None, help="optional run label")
    report_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    report_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    report_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    substrates_parser = subparsers.add_parser(
        "substrates",
        help="run finite substrate configs and emit raw substrate-run artifacts",
    )
    substrates_subparsers = substrates_parser.add_subparsers(dest="substrates_command")
    substrate_run_parser = substrates_subparsers.add_parser(
        "run",
        help="run a substrate config and emit raw substrate-run artifacts",
    )
    substrate_run_parser.add_argument(
        "file", help="path to a substrate-config JSON file"
    )
    substrate_run_parser.add_argument(
        "--preparation",
        required=True,
        help="preparation_id to sample initial states from",
    )
    substrate_run_parser.add_argument(
        "--protocol",
        required=True,
        help="protocol_id to execute",
    )
    substrate_run_parser.add_argument(
        "--trajectories",
        type=int,
        default=None,
        help="number of trajectories to simulate; defaults to config defaults or 1",
    )
    substrate_run_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="seed override; defaults to config defaults or 0",
    )
    substrate_run_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the substrate run",
    )
    substrate_run_parser.add_argument(
        "--label", default=None, help="optional run label"
    )
    substrate_run_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    substrate_run_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    substrate_discover_parser = substrates_subparsers.add_parser(
        "discover-contexts",
        help="extract observable candidate contexts from raw substrate-run files",
    )
    substrate_discover_parser.add_argument(
        "files",
        nargs="+",
        help="one or more substrate-run JSON files",
    )
    substrate_discover_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the discovery run",
    )
    substrate_discover_parser.add_argument(
        "--label", default=None, help="optional run label"
    )
    substrate_discover_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    substrate_discover_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    substrate_discover_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    substrate_build_parser = substrates_subparsers.add_parser(
        "build-event-package",
        help="infer shared events from discovered contexts and build a final event package",
    )
    substrate_build_parser.add_argument(
        "file",
        help="path to a discovered-context-family JSON file",
    )
    substrate_build_parser.add_argument(
        "--raw-run",
        dest="raw_runs",
        action="append",
        help="path to a source substrate-run JSON file; may be repeated",
    )
    substrate_build_parser.add_argument(
        "--pica-bundle",
        default=None,
        help="optional path to a source pica-export-bundle JSON file for PICA-native package building",
    )
    substrate_build_parser.add_argument(
        "--skeleton",
        default=None,
        help="optional path to a discovered event-package skeleton JSON file",
    )
    substrate_build_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the package-build run",
    )
    substrate_build_parser.add_argument(
        "--label", default=None, help="optional run label"
    )
    substrate_build_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    substrate_build_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    substrate_build_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    substrate_build_parser.add_argument(
        "--event-basis",
        default="singleton_only",
        choices=["singleton_only", "singleton_plus_small_unions"],
        help="event basis used for package building",
    )
    substrate_build_parser.add_argument(
        "--max-union-size",
        type=int,
        default=2,
        help="maximum atom-count allowed for generated coarse-event unions",
    )
    substrate_build_parser.add_argument(
        "--min-event-support-count",
        type=int,
        default=3,
        help="minimum conditioning support count for generated coarse events",
    )
    substrate_build_parser.add_argument(
        "--min-event-support-fraction",
        type=float,
        default=0.1,
        help="minimum conditioning support fraction for generated coarse events",
    )
    substrate_build_parser.add_argument(
        "--event-algebra-mode",
        default=None,
        choices=["full_powerset", "conservative_truncation", "auto"],
        help="optional event algebra generation mode; when omitted, the legacy event-basis path is used",
    )
    substrate_build_parser.add_argument(
        "--max-full-powerset-atom-count",
        type=int,
        default=6,
        help="maximum atom count for full powerset generation when event-algebra-mode=auto",
    )
    substrate_build_parser.add_argument(
        "--inference-mode",
        default="structural_primary",
        choices=["structural_primary", "legacy_statistical_primary"],
        help="shared-event inference mode; structural_primary is the default",
    )

    audits_parser = subparsers.add_parser(
        "audits",
        help="run audit analyses and emit report artifacts",
    )
    audits_subparsers = audits_parser.add_subparsers(dest="audits_command")

    ccd_parser = audits_subparsers.add_parser(
        "ccd",
        help="compute context closure defect from a repeated-read observation trace",
    )
    ccd_parser.add_argument("file", help="path to an observation-trace JSON file")
    ccd_parser.add_argument(
        "--instance",
        default=None,
        help="optional path to a linked event-package instance JSON file",
    )
    ccd_parser.add_argument(
        "--category",
        default="benchmarks",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the report run",
    )
    ccd_parser.add_argument("--label", default=None, help="optional run label")
    ccd_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    ccd_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    ccd_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    sec_parser = audits_subparsers.add_parser(
        "sec",
        help="compute shared-event consistency from downstream probe traces",
    )
    sec_parser.add_argument(
        "files",
        nargs="+",
        help="one or more observation-trace JSON files",
    )
    sec_parser.add_argument(
        "--instance",
        required=True,
        help="path to a linked event-package instance JSON file",
    )
    sec_parser.add_argument(
        "--category",
        default="benchmarks",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the report run",
    )
    sec_parser.add_argument("--label", default=None, help="optional run label")
    sec_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    sec_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    sec_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    sec_parser.add_argument(
        "--exact-tolerance",
        type=float,
        default=1e-6,
        help="maximum per-probe TV distance allowed for exact consistency",
    )

    rm_parser = audits_subparsers.add_parser(
        "rm",
        help="compute route mismatch from explicit route observations",
    )
    rm_parser.add_argument(
        "files",
        nargs="+",
        help="one or more observation-trace JSON files",
    )
    rm_parser.add_argument(
        "--instance",
        default=None,
        help="optional linked event-package instance JSON file",
    )
    rm_parser.add_argument(
        "--category",
        default="benchmarks",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the report run",
    )
    rm_parser.add_argument("--label", default=None, help="optional run label")
    rm_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    rm_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    rm_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    rm_parser.add_argument(
        "--exact-tolerance",
        type=float,
        default=1e-6,
        help="maximum route-pair TV distance allowed for exact agreement",
    )
    provenance_parser = audits_subparsers.add_parser(
        "provenance",
        help="audit package admissibility against an explicit provenance manifest",
    )
    provenance_parser.add_argument(
        "file",
        help="path to an event-package instance JSON file",
    )
    provenance_parser.add_argument(
        "--provenance",
        default=None,
        help="optional path to a package-provenance JSON sidecar",
    )
    provenance_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the audit run",
    )
    provenance_parser.add_argument("--label", default=None, help="optional run label")
    provenance_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    provenance_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-26T00:00:00Z",
    )
    provenance_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    pica_refresh_parser = audits_subparsers.add_parser(
        "pica-provenance-refresh",
        help="re-audit committed PICA-derived packages after provenance repair",
    )
    pica_refresh_parser.add_argument(
        "files",
        nargs="+",
        help="one or more package:provenance pairs as package_path:provenance_path",
    )
    pica_refresh_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the refresh run",
    )
    pica_refresh_parser.add_argument("--label", default=None, help="optional run label")
    pica_refresh_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    pica_refresh_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override",
    )
    pica_refresh_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    quotient_parser = audits_subparsers.add_parser(
        "quotient-feasibility",
        help="compute quotient-backed global feasibility on a committed same-slice case",
    )
    quotient_parser.add_argument(
        "file", help="path to a quotient-feasibility-audit JSON file"
    )
    quotient_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the audit run",
    )
    quotient_parser.add_argument("--label", default=None, help="optional run label")
    quotient_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    quotient_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override",
    )
    quotient_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    pica_parser = subparsers.add_parser(
        "pica",
        help="inspect and index artifact exports from vendor/six-birds-pica",
    )
    pica_subparsers = pica_parser.add_subparsers(dest="pica_command")
    pica_inspect_parser = pica_subparsers.add_parser(
        "inspect-bundle",
        help="validate, resolve, and index a PICA export bundle",
    )
    pica_inspect_parser.add_argument(
        "file",
        help="path to a pica-export-bundle JSON file",
    )
    pica_inspect_parser.add_argument(
        "--package",
        default=None,
        help="optional path to an event-package instance JSON file",
    )
    pica_inspect_parser.add_argument(
        "--provenance",
        default=None,
        help="optional path to a package-provenance JSON sidecar",
    )
    pica_inspect_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the bridge inspection run",
    )
    pica_inspect_parser.add_argument("--label", default=None, help="optional run label")
    pica_inspect_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    pica_inspect_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-26T00:00:00Z",
    )
    pica_inspect_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    pica_run_pilot_parser = pica_subparsers.add_parser(
        "run-pilot",
        help="run a bounded subprocess-backed PICA pilot and normalize bridge artifacts",
    )
    pica_run_pilot_parser.add_argument(
        "file",
        help="path to a pica-pilot-campaign JSON file",
    )
    pica_run_pilot_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the pilot wrapper run",
    )
    pica_run_pilot_parser.add_argument(
        "--label", default=None, help="optional run label"
    )
    pica_run_pilot_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    pica_run_pilot_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-26T00:00:00Z",
    )
    pica_run_pilot_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    pica_packaging_parser = pica_subparsers.add_parser(
        "inspect-packaging-surface",
        help="validate, resolve, and index packaging operator/family/source surface from a PICA export bundle",
    )
    pica_packaging_parser.add_argument(
        "file",
        help="path to a pica-export-bundle JSON file",
    )
    pica_packaging_parser.add_argument(
        "--package",
        default=None,
        help="optional path to an event-package instance JSON file",
    )
    pica_packaging_parser.add_argument(
        "--provenance",
        default=None,
        help="optional path to a package-provenance JSON sidecar",
    )
    pica_packaging_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the packaging-surface inspection run",
    )
    pica_packaging_parser.add_argument(
        "--label", default=None, help="optional run label"
    )
    pica_packaging_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    pica_packaging_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-28T00:00:00Z",
    )
    pica_packaging_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    pica_readiness_parser = pica_subparsers.add_parser(
        "analyze-discovery-readiness",
        help="classify whether a PICA export bundle preserves enough same-support structure for structural discovery",
    )
    pica_readiness_parser.add_argument(
        "file",
        help="path to a pica-export-bundle JSON file",
    )
    pica_readiness_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the discovery-readiness run",
    )
    pica_readiness_parser.add_argument(
        "--label", default=None, help="optional run label"
    )
    pica_readiness_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    pica_readiness_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-28T00:00:00Z",
    )
    pica_readiness_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    pica_discover_parser = pica_subparsers.add_parser(
        "discover-contexts",
        help="run PICA-native multilayer context extraction from a resolved export bundle",
    )
    pica_discover_parser.add_argument(
        "file",
        help="path to a pica-export-bundle JSON file",
    )
    pica_discover_parser.add_argument(
        "--config",
        default=None,
        help="optional path to a pica-context-discovery JSON config",
    )
    pica_discover_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the PICA-native context discovery run",
    )
    pica_discover_parser.add_argument(
        "--label", default=None, help="optional run label"
    )
    pica_discover_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    pica_discover_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-27T00:00:00Z",
    )
    pica_discover_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    benchmarks_parser = subparsers.add_parser(
        "benchmarks",
        help="run benchmark bundles",
    )
    benchmark_subparsers = benchmarks_parser.add_subparsers(dest="benchmark_name")
    classical_parser = benchmark_subparsers.add_parser(
        "classical-master-test",
        help="run the classical master-test benchmark bundle",
    )
    classical_subparsers = classical_parser.add_subparsers(dest="benchmark_command")
    classical_run_parser = classical_subparsers.add_parser(
        "run",
        help="run the full classical master-test benchmark bundle",
    )
    classical_run_parser.add_argument(
        "--category",
        default="benchmarks",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the benchmark bundle",
    )
    classical_run_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    classical_run_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="seed recorded in bundle and sub-run manifests",
    )
    classical_run_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    classical_run_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    epistemic_parser = benchmark_subparsers.add_parser(
        "epistemic-six-state",
        help="run the epistemic six-state benchmark bundle",
    )
    epistemic_subparsers = epistemic_parser.add_subparsers(dest="benchmark_command")
    epistemic_run_parser = epistemic_subparsers.add_parser(
        "run",
        help="run the full epistemic six-state benchmark bundle",
    )
    epistemic_run_parser.add_argument(
        "--category",
        default="benchmarks",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the benchmark bundle",
    )
    epistemic_run_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    epistemic_run_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="seed recorded in bundle and sub-run manifests",
    )
    epistemic_run_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    epistemic_run_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    parity_parser = benchmark_subparsers.add_parser(
        "parity-context-witness",
        help="run the parity/context witness benchmark bundle",
    )
    parity_subparsers = parity_parser.add_subparsers(dest="benchmark_command")
    parity_run_parser = parity_subparsers.add_parser(
        "run",
        help="run the full parity/context witness benchmark bundle",
    )
    parity_run_parser.add_argument(
        "--category",
        default="benchmarks",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the benchmark bundle",
    )
    parity_run_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    parity_run_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="seed recorded in bundle and sub-run manifests",
    )
    parity_run_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    parity_run_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    interventions_parser = subparsers.add_parser(
        "interventions",
        help="run intervention comparisons and emit report artifacts",
    )
    interventions_subparsers = interventions_parser.add_subparsers(
        dest="interventions_command"
    )
    hidden_record_parser = interventions_subparsers.add_parser(
        "hidden-record",
        help="expose a hidden residue field as explicit record structure and compare before/after metrics",
    )
    hidden_record_parser.add_argument(
        "file", help="path to a hidden-record-intervention JSON file"
    )
    hidden_record_parser.add_argument(
        "--category",
        default="interventions",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the intervention bundle",
    )
    hidden_record_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    hidden_record_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    hidden_record_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    hidden_record_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    flattening_parser = interventions_subparsers.add_parser(
        "flattening",
        help="append an explicit completion policy to a substrate protocol and compare before/after metrics",
    )
    flattening_parser.add_argument(
        "file", help="path to a flattening-intervention JSON file"
    )
    flattening_parser.add_argument(
        "--category",
        default="interventions",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the intervention bundle",
    )
    flattening_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    flattening_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the manifest"
    )
    flattening_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    flattening_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    search_parser = subparsers.add_parser(
        "search",
        help="run compact discovery sweeps and emit atlas artifacts",
    )
    search_subparsers = search_parser.add_subparsers(dest="search_command")
    run_sweep_parser = search_subparsers.add_parser(
        "run-sweep",
        help="run a compact search sweep and build atlas outputs",
    )
    run_sweep_parser.add_argument("file", help="path to a search-sweep JSON file")
    run_sweep_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the sweep bundle",
    )
    run_sweep_parser.add_argument("--label", default=None, help="optional bundle label")
    run_sweep_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    run_sweep_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    run_sweep_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    run_targeted_parser = search_subparsers.add_parser(
        "run-targeted-nonextendability",
        help="run a compact targeted search for endogenous discovered-package nonextendability",
    )
    run_targeted_parser.add_argument(
        "file",
        help="path to a targeted-nonextendability-search JSON file",
    )
    run_targeted_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the search bundle",
    )
    run_targeted_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    run_targeted_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    run_targeted_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-26T00:00:00Z",
    )
    run_targeted_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    run_atlas_upgrade_parser = search_subparsers.add_parser(
        "run-atlas-upgrade",
        help="run a compact upgraded atlas over the committed substrate family",
    )
    run_atlas_upgrade_parser.add_argument(
        "file",
        help="path to an atlas-upgrade-config JSON file",
    )
    run_atlas_upgrade_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the atlas bundle",
    )
    run_atlas_upgrade_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    run_atlas_upgrade_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    run_atlas_upgrade_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-26T00:00:00Z",
    )
    run_atlas_upgrade_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    run_pica_targeted_parser = search_subparsers.add_parser(
        "run-pica-targeted-obstruction",
        help="run a bounded PICA-targeted endogenous-obstruction campaign",
    )
    run_pica_targeted_parser.add_argument(
        "file",
        help="path to a pica-targeted-obstruction-search JSON file",
    )
    run_pica_targeted_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the search bundle",
    )
    run_pica_targeted_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    run_pica_targeted_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    run_pica_targeted_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-27T00:00:00Z",
    )
    run_pica_targeted_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    run_pica_closure_diverse_parser = search_subparsers.add_parser(
        "run-pica-closure-diverse",
        help="run a closure-diverse PICA endogenous-obstruction campaign",
    )
    run_pica_closure_diverse_parser.add_argument(
        "file",
        help="path to a pica-closure-diverse-search JSON file",
    )
    run_pica_closure_diverse_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the search bundle",
    )
    run_pica_closure_diverse_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    run_pica_closure_diverse_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    run_pica_closure_diverse_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-27T00:00:00Z",
    )
    run_pica_closure_diverse_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    run_frozen_slice_parser = search_subparsers.add_parser(
        "run-frozen-slice-obstruction",
        help="run a frozen-slice PICA endogenous-obstruction campaign",
    )
    run_frozen_slice_parser.add_argument(
        "file",
        help="path to a pica-frozen-slice-search JSON file",
    )
    run_frozen_slice_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the search bundle",
    )
    run_frozen_slice_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    run_frozen_slice_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    run_frozen_slice_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-28T00:00:00Z",
    )
    run_frozen_slice_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    run_packaging_conflict_parser = search_subparsers.add_parser(
        "run-packaging-conflict",
        help="run a commutator-guided PICA packaging-conflict campaign",
    )
    run_packaging_conflict_parser.add_argument(
        "file",
        help="path to a pica-packaging-conflict-search JSON file",
    )
    run_packaging_conflict_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the search bundle",
    )
    run_packaging_conflict_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    run_packaging_conflict_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    run_packaging_conflict_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-28T00:00:00Z",
    )
    run_packaging_conflict_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    run_packaging_conflict_parser.add_argument(
        "--commutator-admissibility-mode",
        default="p5_only",
        choices=["p5_only", "p5_p6_combined", "both"],
        help="package-conflict commutator surface to evaluate",
    )
    run_mechanism_axis_parser = search_subparsers.add_parser(
        "run-mechanism-axis",
        help="run a bounded mechanism-axis campaign with fixed lens/projection settings",
    )
    run_mechanism_axis_parser.add_argument(
        "file",
        help="path to a mechanism-axis-search JSON file",
    )
    run_mechanism_axis_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the search bundle",
    )
    run_mechanism_axis_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    run_mechanism_axis_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    run_mechanism_axis_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-28T00:00:00Z",
    )
    run_mechanism_axis_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    run_lens_axis_parser = search_subparsers.add_parser(
        "run-lens-axis",
        help="run a bounded lens-axis campaign with quotient-backed feasibility",
    )
    run_lens_axis_parser.add_argument(
        "file",
        help="path to a lens-axis-search JSON file",
    )
    run_lens_axis_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the search bundle",
    )
    run_lens_axis_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    run_lens_axis_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    run_lens_axis_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-29T00:00:00Z",
    )
    run_lens_axis_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    run_packaging_axis_parser = search_subparsers.add_parser(
        "run-packaging-axis",
        help="run a bounded packaging-axis campaign with quotient-backed feasibility",
    )
    run_packaging_axis_parser.add_argument(
        "file",
        help="path to a packaging-axis-search JSON file",
    )
    run_packaging_axis_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the search bundle",
    )
    run_packaging_axis_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    run_packaging_axis_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    run_packaging_axis_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-30T00:00:00Z",
    )
    run_packaging_axis_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    close_lens_cross_resolution_parser = search_subparsers.add_parser(
        "close-lens-cross-resolution",
        help="reconcile and close a committed cross-resolution lens-axis witness",
    )
    close_lens_cross_resolution_parser.add_argument(
        "file",
        help="path to a quotient-feasibility-audit JSON file for the committed witness",
    )
    close_lens_cross_resolution_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the closure bundle",
    )
    close_lens_cross_resolution_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    close_lens_cross_resolution_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    close_lens_cross_resolution_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-29T00:00:00Z",
    )
    close_lens_cross_resolution_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    finalize_lens_axis_parser = search_subparsers.add_parser(
        "finalize-lens-axis",
        help="finalize the lens axis into one canonical regime-closure result",
    )
    finalize_lens_axis_parser.add_argument(
        "file",
        help="path to a lens-axis-finalization JSON file",
    )
    finalize_lens_axis_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the finalization bundle",
    )
    finalize_lens_axis_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    finalize_lens_axis_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    finalize_lens_axis_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-30T00:00:00Z",
    )
    finalize_lens_axis_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    robustness_parser = subparsers.add_parser(
        "robustness",
        help="run compact noise robustness sweeps and emit summary artifacts",
    )
    robustness_subparsers = robustness_parser.add_subparsers(dest="robustness_command")
    robustness_run_parser = robustness_subparsers.add_parser(
        "run-sweep",
        help="run a compact noise robustness sweep",
    )
    robustness_run_parser.add_argument(
        "file", help="path to a noise-robustness-sweep JSON file"
    )
    robustness_run_parser.add_argument(
        "--category",
        default="search",
        choices=list(DEFAULT_RESULTS_CATEGORIES),
        help="results category for the sweep bundle",
    )
    robustness_run_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    robustness_run_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    robustness_run_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    robustness_run_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    redteam_parser = subparsers.add_parser(
        "redteam",
        help="run compact adversarial suites and collect framework responses",
    )
    redteam_subparsers = redteam_parser.add_subparsers(dest="redteam_command")
    redteam_run_parser = redteam_subparsers.add_parser(
        "run-suite",
        help="run a committed red-team suite",
    )
    redteam_run_parser.add_argument("file", help="path to a redteam-suite JSON file")
    redteam_run_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the suite bundle",
    )
    redteam_run_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    redteam_run_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    redteam_run_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-26T00:00:00Z",
    )
    redteam_run_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    falsification_parser = subparsers.add_parser(
        "falsification",
        help="run discovered-case falsification bundles",
    )
    falsification_subparsers = falsification_parser.add_subparsers(
        dest="falsification_command"
    )
    falsification_run_parser = falsification_subparsers.add_parser(
        "run-discovered-case",
        help="run the committed discovered-case falsification bundle",
    )
    falsification_run_parser.add_argument(
        "file",
        help="path to a discovered-case-falsification JSON file",
    )
    falsification_run_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the falsification bundle",
    )
    falsification_run_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    falsification_run_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    falsification_run_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-26T00:00:00Z",
    )
    falsification_run_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    falsification_bundle_parser = falsification_subparsers.add_parser(
        "run-flagship-bundle",
        help="run the committed flagship false-positive control bundle",
    )
    falsification_bundle_parser.add_argument(
        "file",
        help="path to a flagship-control-bundle JSON file",
    )
    falsification_bundle_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the flagship control bundle",
    )
    falsification_bundle_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    falsification_bundle_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    falsification_bundle_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-31T00:00:00Z",
    )
    falsification_bundle_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    crosscheck_parser = subparsers.add_parser(
        "crosscheck",
        help="run independent exact cross-check bundles",
    )
    crosscheck_subparsers = crosscheck_parser.add_subparsers(dest="crosscheck_command")
    crosscheck_run_parser = crosscheck_subparsers.add_parser(
        "run",
        help="run an exact-crosscheck config",
    )
    crosscheck_run_parser.add_argument(
        "file",
        help="path to an exact-crosscheck JSON file",
    )
    crosscheck_run_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the cross-check bundle",
    )
    crosscheck_run_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    crosscheck_run_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    crosscheck_run_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-26T00:00:00Z",
    )
    crosscheck_run_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    findings_parser = subparsers.add_parser(
        "findings",
        help="build the final findings registry over refreshed evidence and committed artifacts",
    )
    findings_subparsers = findings_parser.add_subparsers(dest="findings_command")
    findings_build_parser = findings_subparsers.add_parser(
        "build-registry",
        help="run the committed findings registry build",
    )
    findings_build_parser.add_argument(
        "file",
        help="path to a findings-registry-config JSON file",
    )
    findings_build_parser.add_argument(
        "--category",
        default="findings",
        help="results category for the findings registry bundle",
    )
    findings_build_parser.add_argument(
        "--label", default=None, help="optional bundle label"
    )
    findings_build_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the bundle manifest"
    )
    findings_build_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-26T00:00:00Z",
    )
    findings_build_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="run thin end-to-end suite wrappers over the committed benchmark, intervention, search, and Lean commands",
    )
    pipeline_subparsers = pipeline_parser.add_subparsers(dest="pipeline_command")

    pipeline_benchmarks_parser = pipeline_subparsers.add_parser(
        "run-benchmarks",
        help="run the committed benchmark suite wrapper",
    )
    pipeline_benchmarks_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the suite-level run directory",
    )
    pipeline_benchmarks_parser.add_argument(
        "--label", default=None, help="optional suite label"
    )
    pipeline_benchmarks_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the suite manifest"
    )
    pipeline_benchmarks_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    pipeline_benchmarks_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    pipeline_interventions_parser = pipeline_subparsers.add_parser(
        "run-interventions",
        help="run the committed intervention suite wrapper",
    )
    pipeline_interventions_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the suite-level run directory",
    )
    pipeline_interventions_parser.add_argument(
        "--label", default=None, help="optional suite label"
    )
    pipeline_interventions_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the suite manifest"
    )
    pipeline_interventions_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    pipeline_interventions_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    pipeline_search_parser = pipeline_subparsers.add_parser(
        "run-search",
        help="run the committed search suite wrapper",
    )
    pipeline_search_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the suite-level run directory",
    )
    pipeline_search_parser.add_argument(
        "--label", default=None, help="optional suite label"
    )
    pipeline_search_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the suite manifest"
    )
    pipeline_search_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    pipeline_search_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )

    pipeline_lean_parser = pipeline_subparsers.add_parser(
        "run-lean",
        help="run the Lean build suite wrapper",
    )
    pipeline_lean_parser.add_argument(
        "--category",
        default="results",
        choices=PIPELINE_RESULTS_CATEGORIES,
        help="results category for the suite-level run directory",
    )
    pipeline_lean_parser.add_argument(
        "--label", default=None, help="optional suite label"
    )
    pipeline_lean_parser.add_argument(
        "--seed", type=int, default=0, help="seed recorded in the suite manifest"
    )
    pipeline_lean_parser.add_argument(
        "--timestamp",
        default=None,
        help="explicit UTC timestamp override, for example 2026-03-25T00:00:00Z",
    )
    pipeline_lean_parser.add_argument(
        "--root",
        default=None,
        help="override repo root for testing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        result = validate_file(args.file, kind=args.kind)
        if result.ok:
            print(f"valid {result.kind.value}: {args.file}")
            return 0
        print(f"invalid {args.kind}: {args.file}", file=sys.stderr)
        for issue in result.issues:
            prefix = f"{issue.path}: " if issue.path else ""
            print(f"{prefix}{issue.message}", file=sys.stderr)
        return 1
    if args.command == "runs" and args.runs_command == "create-dummy":
        manifest = create_dummy_run(
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        output_path = manifest.output_artifacts["dummy_output"]
        print(f"created {manifest.run_id}: {output_path}")
        return 0
    if args.command == "runs" and args.runs_command == "list":
        runs = list_runs(root=args.root)
        if not runs:
            print("no runs found")
            return 0
        for run in runs:
            print(f"{run.run_id}\t{run.timestamp}\t{run.category}\t{run.status}")
        return 0
    if args.command == "hierarchy" and args.hierarchy_command == "build-three-axis":
        artifacts = build_three_axis_hierarchy(
            config_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"strongest_axis={artifacts.strongest_axis}")
        for row in artifacts.results.rows:
            print(f"{row.axis}_campaign_outcome={row.axis_campaign_outcome_label}")
            print(f"{row.axis}_claim_level={row.claim_level_supported}")
        print(f"summary={artifacts.summary_path}")
        print(f"three_axis_hierarchy_csv={artifacts.table_csv_path}")
        print(f"claim_strength_registry={artifacts.claim_strength_registry_path}")
        print(f"best_evidence_by_axis={artifacts.best_evidence_by_axis_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        return 0
    if args.command == "evidence" and args.evidence_command == "build-pack":
        artifacts = build_paper_evidence_pack(
            index_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"theorem_experiment_map={artifacts.theorem_experiment_map_path}")
        print(f"flagship_witnesses={artifacts.flagship_witnesses_path}")
        print(f"best_evidence_by_axis={artifacts.best_evidence_by_axis_path}")
        print(f"caveat_registry={artifacts.caveat_registry_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        return 0
    if args.command == "structural" and args.structural_command == "report":
        instance = load_event_package_instance(args.file)
        report = generate_structural_report(
            instance,
            instance_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={report.run_id}")
        print(f"summary={report.summary_path}")
        print(f"note={report.note_path}")
        print(f"result_note={report.result_note_path}")
        print(f"manifest={report.manifest_path}")
        return 0
    if args.command == "substrates" and args.substrates_command == "run":
        config = load_substrate_config(args.file)
        artifacts = write_substrate_run(
            config,
            config_path=args.file,
            preparation_id=args.preparation,
            protocol_id=args.protocol,
            trajectories=args.trajectories,
            seed=args.seed,
            category=args.category,
            label=args.label,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"substrate_run={artifacts.run_trace_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"manifest={artifacts.manifest_path}")
        return 0
    if args.command == "substrates" and args.substrates_command == "discover-contexts":
        artifacts = write_context_discovery_report(
            run_paths=args.files,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"family={artifacts.family_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        if artifacts.skeleton_path is not None:
            print(f"event_package_skeleton={artifacts.skeleton_path}")
        print(
            f"accepted_context_count={artifacts.family.diagnostics_summary.accepted_context_count}"
        )
        return 0
    if (
        args.command == "substrates"
        and args.substrates_command == "build-event-package"
    ):
        artifacts = write_package_build_report(
            family_path=args.file,
            run_paths=args.raw_runs,
            pica_bundle_path=args.pica_bundle,
            skeleton_path=args.skeleton,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
            thresholds=SharedEventInferenceThresholds(
                inference_mode=args.inference_mode,
                min_common_probes=1,
                min_conditioning_count=3,
                min_probe_atom_support_count=1,
                max_mean_tv=0.15,
                exact_tolerance=1e-6,
                proposal_constraint_kind="soft",
            ),
            event_thresholds=DiscoveredEventGenerationThresholds(
                event_basis_mode=args.event_basis,
                event_algebra_mode=args.event_algebra_mode,
                max_full_powerset_atom_count=args.max_full_powerset_atom_count,
                max_union_size=args.max_union_size,
                min_event_support_count=args.min_event_support_count,
                min_event_support_fraction=args.min_event_support_fraction,
            ),
        )
        print(f"run_id={artifacts.run_id}")
        print(f"discovered_event_family={artifacts.discovered_event_family_path}")
        print(f"event_algebra_coverage={artifacts.event_algebra_coverage_path}")
        print(f"probe_indistinguishability_signatures={artifacts.signatures_path}")
        print(f"shared_event_candidates={artifacts.candidates_path}")
        print(f"event_package={artifacts.event_package_path}")
        print(f"package_provenance={artifacts.provenance_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        print(f"accepted_context_count={len(artifacts.event_package.contexts)}")
        print(
            "total_generated_event_count="
            f"{artifacts.discovered_event_family.diagnostics_summary.total_event_count}"
        )
        print(
            "generated_proper_coarse_event_count="
            f"{artifacts.discovered_event_family.diagnostics_summary.generated_proper_coarse_event_count}"
        )
        print(
            "event_algebra_complete="
            f"{all(bool(context.event_algebra_complete) for context in artifacts.discovered_event_family.contexts)}"
        )
        print(
            "structurally_valid_candidate_count="
            f"{artifacts.candidates.diagnostics_summary.structurally_valid_candidate_pair_count}"
        )
        print(
            f"accepted_shared_event_proposal_count={len(artifacts.event_package.equality_proposals)}"
        )
        print(
            "accepted_coarse_proposal_count="
            f"{sum(1 for row in artifacts.candidates.candidate_rows if row.accepted and (row.left_is_proper_coarse or row.right_is_proper_coarse))}"
        )
        return 0
    if args.command == "audits" and args.audits_command == "ccd":
        trace = load_observation_trace_file(args.file)
        instance = (
            load_event_package_instance(args.instance)
            if args.instance is not None
            else None
        )
        report = write_ccd_report(
            trace,
            trace_path=args.file,
            category=args.category,
            label=args.label,
            instance=instance,
            instance_path=args.instance,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={report.run_id}")
        print(f"summary={report.summary_path}")
        print(f"note={report.note_path}")
        print(f"result_note={report.result_note_path}")
        print(f"manifest={report.manifest_path}")
        return 0
    if args.command == "audits" and args.audits_command == "sec":
        instance = load_event_package_instance(args.instance)
        traces = load_observation_trace_files(args.files)
        report = write_sec_report(
            instance,
            traces,
            instance_path=args.instance,
            trace_paths=args.files,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
            exact_tolerance=args.exact_tolerance,
        )
        print(f"run_id={report.run_id}")
        print(f"summary={report.summary_path}")
        print(f"note={report.note_path}")
        print(f"result_note={report.result_note_path}")
        print(f"manifest={report.manifest_path}")
        return 0
    if args.command == "audits" and args.audits_command == "rm":
        traces = load_rm_trace_files(args.files)
        instance = (
            load_event_package_instance(args.instance)
            if args.instance is not None
            else None
        )
        report = write_rm_report(
            traces,
            trace_paths=args.files,
            category=args.category,
            label=args.label,
            instance=instance,
            instance_path=args.instance,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
            exact_tolerance=args.exact_tolerance,
        )
        print(f"run_id={report.run_id}")
        print(f"summary={report.summary_path}")
        print(f"note={report.note_path}")
        print(f"result_note={report.result_note_path}")
        print(f"manifest={report.manifest_path}")
        return 0
    if args.command == "audits" and args.audits_command == "provenance":
        report = write_provenance_audit_report(
            package_path=args.file,
            provenance_path=args.provenance,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={report.run_id}")
        print(f"summary={report.summary_path}")
        print(f"note={report.note_path}")
        print(f"result_note={report.result_note_path}")
        print(f"manifest={report.manifest_path}")
        print(
            f"admissibility_classification={report.result.admissibility_classification}"
        )
        return 0
    if args.command == "audits" and args.audits_command == "pica-provenance-refresh":
        pairs: list[tuple[str, str | None]] = []
        for spec in args.files:
            if ":" in spec:
                pkg, prov = spec.split(":", maxsplit=1)
                pairs.append((pkg, prov if prov else None))
            else:
                pairs.append((spec, None))
        report = write_pica_provenance_refresh_report(
            package_provenance_pairs=pairs,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={report.run_id}")
        print(f"summary={report.summary_path}")
        print(f"note={report.note_path}")
        print(f"result_note={report.result_note_path}")
        print(f"manifest={report.manifest_path}")
        for entry in report.audited_packages:
            print(
                f"package={entry['package_id']}"
                f" classification={entry['admissibility_classification']}"
                f" unknown_row_filter_fields={entry['unknown_row_filter_field_count']}"
            )
        return 0
    if args.command == "audits" and args.audits_command == "quotient-feasibility":
        artifacts = run_quotient_feasibility_audit(
            audit_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"quotient_class_ledger={artifacts.quotient_class_ledger_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        if artifacts.witness_search_table_path is not None:
            print(f"witness_search_table={artifacts.witness_search_table_path}")
        print(
            f"quotient_class_count={artifacts.result.quotient_summary.quotient_class_count}"
        )
        print(
            "accepted_only_survivor_count="
            f"{artifacts.result.accepted_proposal_set_result.survivor_count}"
        )
        if artifacts.result.natural_pairing_result is not None:
            print(
                "natural_pairing_survivor_count="
                f"{artifacts.result.natural_pairing_result.survivor_count}"
            )
        print(
            "candidate_subset_witness_found="
            f"{artifacts.result.candidate_subset_witness_result.witness_found}"
        )
        print(f"witness_classification={artifacts.result.witness_classification}")
        return 0
    if args.command == "pica" and args.pica_command == "inspect-bundle":
        if (args.package is None) != (args.provenance is None):
            parser.error("--package and --provenance must be provided together")
        report = write_pica_bridge_report(
            bundle_path=args.file,
            package_path=args.package,
            provenance_path=args.provenance,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={report.run_id}")
        print(f"summary={report.summary_path}")
        print(f"source_index={report.source_index_path}")
        print(f"result_note={report.result_note_path}")
        print(f"manifest={report.manifest_path}")
        if report.provenance_audit_summary_path is not None:
            print(f"provenance_audit_summary={report.provenance_audit_summary_path}")
            audit_payload = validate_file(
                Path(args.root).resolve() / report.provenance_audit_summary_path
                if args.root is not None
                else report.provenance_audit_summary_path,
                kind=SchemaKind.PROVENANCE_AUDIT_RESULT,
            ).model
            assert audit_payload is not None
            print(
                "admissibility_classification="
                f"{audit_payload.admissibility_classification}"
            )
        summary_file = (
            Path(args.root).resolve() / report.summary_path
            if args.root is not None
            else Path(report.summary_path)
        )
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        print(f"campaign_count={summary['campaign_count']}")
        print(f"run_count={summary['run_count']}")
        print(f"closure_count={summary['closure_count']}")
        print(f"lens_count={summary['lens_count']}")
        print(f"observable_ledger_count={summary['observable_ledger_count']}")
        return 0
    if args.command == "pica" and args.pica_command == "run-pilot":
        artifacts = run_pica_pilot_campaign(
            config_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        result = artifacts.result
        print(f"run_id={artifacts.run_id}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        print(f"export_bundle={artifacts.export_bundle_path}")
        print(f"campaign_export={artifacts.campaign_export_path}")
        print(f"run_ledger={artifacts.run_ledger_path}")
        print(f"closure_catalog={artifacts.closure_catalog_path}")
        print(f"observable_ledger={artifacts.observable_ledger_path}")
        print(f"pica_export_mode={result.pica_export_mode}")
        print(f"observation_granularity={result.observation_granularity}")
        print(f"cooccurrence_scope={result.cooccurrence_scope}")
        print(
            "supports_structural_probe_conditioning="
            f"{result.supports_structural_probe_conditioning}"
        )
        print(f"campaign_count={result.summary_counts.campaign_count}")
        print(f"run_count={result.summary_counts.run_count}")
        print(f"closure_count={result.summary_counts.closure_count}")
        print(f"lens_count={result.summary_counts.lens_count}")
        print(
            f"observable_ledger_count={result.summary_counts.observable_ledger_count}"
        )
        return 0
    if args.command == "pica" and args.pica_command == "inspect-packaging-surface":
        if (args.package is None) != (args.provenance is None):
            parser.error("--package and --provenance must be provided together")
        report = write_pica_packaging_surface_report(
            bundle_path=args.file,
            package_path=args.package,
            provenance_path=args.provenance,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={report.run_id}")
        print(f"summary={report.summary_path}")
        print(f"source_index={report.source_index_path}")
        print(f"result_note={report.result_note_path}")
        print(f"manifest={report.manifest_path}")
        if report.provenance_audit_summary_path is not None:
            print(f"provenance_audit_summary={report.provenance_audit_summary_path}")
            audit_payload = validate_file(
                Path(args.root).resolve() / report.provenance_audit_summary_path
                if args.root is not None
                else report.provenance_audit_summary_path,
                kind=SchemaKind.PROVENANCE_AUDIT_RESULT,
            ).model
            assert audit_payload is not None
            print(
                "admissibility_classification="
                f"{audit_payload.admissibility_classification}"
            )
        summary_file = (
            Path(args.root).resolve() / report.summary_path
            if args.root is not None
            else Path(report.summary_path)
        )
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        print(
            "distinct_packaging_operator_count="
            f"{summary['distinct_packaging_operator_count']}"
        )
        print(
            "distinct_packaging_family_count="
            f"{summary['distinct_packaging_family_count']}"
        )
        print(f"support_slice_count={summary['support_slice_count']}")
        print(f"packaging_source_count={len(summary['source_counts'])}")
        print(f"source_counts={json.dumps(summary['source_counts'], sort_keys=True)}")
        print(
            "selected_operator_counts="
            f"{json.dumps(summary['selected_operator_counts'], sort_keys=True)}"
        )
        print(
            "selected_family_counts="
            f"{json.dumps(summary['selected_family_counts'], sort_keys=True)}"
        )
        return 0
    if args.command == "pica" and args.pica_command == "analyze-discovery-readiness":
        artifacts = analyze_pica_discovery_readiness(
            bundle_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        print(f"readiness_classification={artifacts.summary.readiness_classification}")
        print(f"run_count={artifacts.summary.run_count}")
        print(f"trajectory_count={artifacts.summary.trajectory_count}")
        print(
            "context_pairs_with_shared_trajectory_support="
            f"{artifacts.summary.context_pairs_with_shared_trajectory_support}"
        )
        print(
            "context_pairs_with_probe_conditioning_potential="
            f"{artifacts.summary.context_pairs_with_probe_conditioning_potential}"
        )
        return 0
    if args.command == "pica" and args.pica_command == "discover-contexts":
        config = (
            load_model(args.config, kind=SchemaKind.PICA_CONTEXT_DISCOVERY)
            if args.config is not None
            else DEFAULT_PICA_CONTEXT_DISCOVERY
        )
        artifacts = write_pica_context_discovery_report(
            bundle_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
            config=config.model_copy(update={"bundle_artifact": args.file}),
        )
        family = artifacts.family
        distinct_levels = {
            context.candidate_key.level_id
            for context in family.accepted_contexts
            if context.candidate_key.level_id is not None
        }
        distinct_resolutions = {
            context.candidate_key.resolution_id
            for context in family.accepted_contexts
            if context.candidate_key.resolution_id is not None
        }
        distinct_closures = {
            context.candidate_key.closure_id
            for context in family.accepted_contexts
            if context.candidate_key.closure_id is not None
        }
        print(f"run_id={artifacts.run_id}")
        print(f"family={artifacts.family_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        if artifacts.skeleton_path is not None:
            print(f"event_package_skeleton={artifacts.skeleton_path}")
        print(
            f"accepted_context_count={family.diagnostics_summary.accepted_context_count}"
        )
        print(f"distinct_level_count={len(distinct_levels)}")
        print(f"distinct_resolution_count={len(distinct_resolutions)}")
        print(f"distinct_closure_count={len(distinct_closures)}")
        return 0
    if (
        args.command == "benchmarks"
        and args.benchmark_name == "classical-master-test"
        and args.benchmark_command == "run"
    ):
        bundle = run_classical_master_test_benchmark(
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={bundle.run_id}")
        print(f"index={bundle.index_path}")
        print(
            f"exact_structural_feasible_hard_only={bundle.metrics_summary['exact_structural_feasible_hard_only']}"
        )
        print(f"gpd_str={bundle.metrics_summary['gpd_str']}")
        print(f"gpd_stat_clean={bundle.metrics_summary['gpd_stat_clean']}")
        return 0
    if (
        args.command == "benchmarks"
        and args.benchmark_name == "epistemic-six-state"
        and args.benchmark_command == "run"
    ):
        bundle = run_epistemic_six_state_benchmark(
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={bundle.run_id}")
        print(f"index={bundle.index_path}")
        print(
            "extendable_under_current_admissibility_semantics="
            f"{bundle.metrics_summary['exact_structural_feasible_hard_only']}"
        )
        print(f"gpd_str={bundle.metrics_summary['gpd_str']}")
        print(f"gpd_stat_clean={bundle.metrics_summary['gpd_stat_clean']}")
        return 0
    if (
        args.command == "benchmarks"
        and args.benchmark_name == "parity-context-witness"
        and args.benchmark_command == "run"
    ):
        bundle = run_parity_context_witness_benchmark(
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={bundle.run_id}")
        print(f"index={bundle.index_path}")
        print(
            "exact_structural_feasible_hard_only="
            f"{bundle.metrics_summary['exact_structural_feasible_hard_only']}"
        )
        print(f"gpd_str={bundle.metrics_summary['gpd_str']}")
        print(f"blocking_proposal_ids={bundle.relaxed_proposal_ids}")
        return 0
    if (
        args.command == "interventions"
        and args.interventions_command == "hidden-record"
    ):
        report = write_hidden_record_intervention_report(
            intervention_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        before = report.summary["before"]
        after = report.summary["after"]
        print(f"run_id={report.run_id}")
        print(f"augmented_instance={report.augmented_instance_path}")
        print(f"package_provenance={report.provenance_path}")
        print(f"before_stat={report.before_stat_path}")
        print(f"after_stat={report.after_stat_path}")
        print(f"summary={report.summary_path}")
        print(f"note={report.note_path}")
        print(f"result_note={report.result_note_path}")
        print(f"manifest={report.manifest_path}")
        print(f"before_gpd_str={before['gpd_str']}")
        print(f"after_gpd_str={after['gpd_str']}")
        print(f"before_gpd_stat={before['gpd_stat']}")
        print(f"after_gpd_stat={after['gpd_stat']}")
        print(f"conclusion={report.conclusion}")
        return 0
    if args.command == "interventions" and args.interventions_command == "flattening":
        report = write_flattening_intervention_report(
            intervention_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        before = report.summary["before"]
        after = report.summary["after"]
        print(f"run_id={report.run_id}")
        print(f"before_route_trace={report.before_route_trace_path}")
        print(f"after_route_trace={report.after_route_trace_path}")
        print(f"summary={report.summary_path}")
        print(f"note={report.note_path}")
        print(f"result_note={report.result_note_path}")
        print(f"manifest={report.manifest_path}")
        print(f"before_gpd_str={before['gpd_str']}")
        print(f"after_gpd_str={after['gpd_str']}")
        print(f"before_gpd_stat_status={before['gpd_stat_status']}")
        print(f"before_gpd_stat={before['gpd_stat']}")
        print(f"after_gpd_stat_status={after['gpd_stat_status']}")
        print(f"after_gpd_stat={after['gpd_stat']}")
        print(f"before_rm_status={before['rm_status']}")
        print(f"before_overall_rm={before['overall_rm']}")
        print(f"after_rm_status={after['rm_status']}")
        print(f"after_overall_rm={after['overall_rm']}")
        print(f"conclusion={report.conclusion}")
        return 0
    if args.command == "search" and args.search_command == "run-sweep":
        artifacts = run_search_sweep(
            sweep_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"atlas_csv={artifacts.atlas_csv_path}")
        print(f"atlas_json={artifacts.atlas_json_path}")
        print(f"regime_counts={artifacts.regime_counts_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for regime, count in sorted(artifacts.regime_counts.items()):
            print(f"{regime}={count}")
        return 0
    if (
        args.command == "search"
        and args.search_command == "run-targeted-nonextendability"
    ):
        artifacts = run_targeted_nonextendability_search(
            search_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"targeted_search_csv={artifacts.table_csv_path}")
        print(f"targeted_search_json={artifacts.table_json_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for label, count in sorted(artifacts.classification_counts.items()):
            print(f"{label}={count}")
        if artifacts.best_candidate_path is not None:
            print(f"best_candidate={artifacts.best_candidate_path}")
        if artifacts.negative_result_path is not None:
            print("negative_result=true")
            print(f"negative_result_json={artifacts.negative_result_path}")
        return 0
    if args.command == "search" and args.search_command == "run-atlas-upgrade":
        artifacts = run_atlas_upgrade(
            config_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"atlas_csv={artifacts.table_csv_path}")
        print(f"atlas_json={artifacts.table_json_path}")
        print(f"regime_counts={artifacts.regime_counts_path}")
        print(f"threshold_summary={artifacts.threshold_summary_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for regime, count in sorted(artifacts.regime_counts.items()):
            print(f"{regime}={count}")
        if artifacts.best_candidate_path is not None:
            print(f"best_candidate={artifacts.best_candidate_path}")
        if artifacts.negative_result_path is not None:
            print("negative_result=true")
            print(f"negative_result_json={artifacts.negative_result_path}")
        return 0
    if (
        args.command == "search"
        and args.search_command == "run-pica-targeted-obstruction"
    ):
        artifacts = run_pica_targeted_obstruction_search(
            search_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"targeted_search_csv={artifacts.table_csv_path}")
        print(f"targeted_search_json={artifacts.table_json_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for label, count in sorted(artifacts.classification_counts.items()):
            print(f"{label}={count}")
        print(f"outcome_kind={artifacts.outcome_kind}")
        print(f"outcome={artifacts.outcome_path}")
        return 0
    if args.command == "search" and args.search_command == "run-pica-closure-diverse":
        artifacts = run_pica_closure_diverse_search(
            search_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"pica_closure_diverse_csv={artifacts.table_csv_path}")
        print(f"pica_closure_diverse_json={artifacts.table_json_path}")
        print(f"context_pair_structure={artifacts.context_pair_structure_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for label, count in sorted(artifacts.classification_counts.items()):
            print(f"{label}={count}")
        print(f"outcome_kind={artifacts.outcome_kind}")
        print(f"outcome={artifacts.outcome_path}")
        return 0
    if (
        args.command == "search"
        and args.search_command == "run-frozen-slice-obstruction"
    ):
        artifacts = run_pica_frozen_slice_search(
            search_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"frozen_slice_search_csv={artifacts.table_csv_path}")
        print(f"frozen_slice_search_json={artifacts.table_json_path}")
        print(f"context_pair_structure={artifacts.context_pair_structure_path}")
        print(
            f"projection_family_admissibility={artifacts.projection_family_admissibility_path}"
        )
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for label, count in sorted(artifacts.classification_counts.items()):
            print(f"{label}={count}")
        print(f"outcome_kind={artifacts.outcome_kind}")
        print(f"outcome={artifacts.outcome_path}")
        return 0
    if args.command == "search" and args.search_command == "run-packaging-conflict":
        artifacts = run_pica_packaging_conflict_search(
            search_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            commutator_admissibility_mode=args.commutator_admissibility_mode,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"packaging_conflict_comparison_csv={artifacts.table_csv_path}")
        print(f"packaging_conflict_comparison_json={artifacts.table_json_path}")
        print(f"context_pair_structure={artifacts.context_pair_structure_path}")
        print(
            f"projection_family_admissibility={artifacts.projection_family_admissibility_path}"
        )
        print(f"commutator_summary={artifacts.commutator_summary_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for mode_name, counts in sorted(artifacts.classification_counts.items()):
            print(f"{mode_name}_counts={counts}")
        print(f"outcome_kind={artifacts.outcome_kind}")
        print(f"outcome={artifacts.outcome_path}")
        return 0
    if args.command == "search" and args.search_command == "run-mechanism-axis":
        artifacts = run_mechanism_axis_search(
            search_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"mechanism_axis_csv={artifacts.table_csv_path}")
        print(f"mechanism_axis_json={artifacts.table_json_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for label, count in sorted(artifacts.classification_counts.items()):
            print(f"class_{label}={count}")
        for label, count in sorted(artifacts.claim_level_counts.items()):
            print(f"claim_{label}={count}")
        print(f"adequacy_met={artifacts.adequacy['adequate']}")
        print(f"outcome_kind={artifacts.outcome_kind}")
        print(f"outcome={artifacts.outcome_path}")
        if artifacts.best_point_id is not None:
            print(f"best_point_id={artifacts.best_point_id}")
        return 0
    if args.command == "search" and args.search_command == "run-lens-axis":
        artifacts = run_lens_axis_search(
            search_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"lens_axis_csv={artifacts.table_csv_path}")
        print(f"lens_axis_json={artifacts.table_json_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(
            f"support_relation_diagnostics={artifacts.support_relation_diagnostics_path}"
        )
        print(
            f"quotient_feasibility_diagnostics={artifacts.quotient_feasibility_diagnostics_path}"
        )
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for label, count in sorted(artifacts.classification_counts.items()):
            print(f"class_{label}={count}")
        for label, count in sorted(artifacts.quotient_witness_counts.items()):
            print(f"quotient_{label}={count}")
        print(f"adequacy_met={artifacts.adequacy['adequate']}")
        print(f"outcome_kind={artifacts.outcome_kind}")
        print(f"outcome={artifacts.outcome_path}")
        if artifacts.best_point_id is not None:
            print(f"best_point_id={artifacts.best_point_id}")
        return 0
    if args.command == "search" and args.search_command == "run-packaging-axis":
        artifacts = run_packaging_axis_search(
            search_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"packaging_axis_csv={artifacts.table_csv_path}")
        print(f"packaging_axis_json={artifacts.table_json_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(
            "packaging_family_admissibility="
            f"{artifacts.packaging_family_admissibility_path}"
        )
        print(
            "package_conflict_diagnostics="
            f"{artifacts.package_conflict_diagnostics_path}"
        )
        print(
            "quotient_feasibility_diagnostics="
            f"{artifacts.quotient_feasibility_diagnostics_path}"
        )
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for label, count in sorted(artifacts.classification_counts.items()):
            print(f"class_{label}={count}")
        for label, count in sorted(artifacts.quotient_witness_counts.items()):
            print(f"quotient_{label}={count}")
        for label, count in sorted(artifacts.claim_level_counts.items()):
            print(f"claim_{label}={count}")
        print(f"adequacy_met={artifacts.adequacy['adequate']}")
        print(f"outcome_kind={artifacts.outcome_kind}")
        print(f"outcome={artifacts.outcome_path}")
        if artifacts.best_point_id is not None:
            print(f"best_point_id={artifacts.best_point_id}")
        return 0
    if (
        args.command == "search"
        and args.search_command == "close-lens-cross-resolution"
    ):
        artifacts = run_lens_axis_cross_resolution_closure(
            audit_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"adjudication={artifacts.adjudication_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        print(
            "accepted_only_survivor_count="
            f"{artifacts.quotient_result.accepted_proposal_set_result.survivor_count}"
        )
        if artifacts.quotient_result.natural_pairing_result is not None:
            print(
                "natural_pairing_survivor_count="
                f"{artifacts.quotient_result.natural_pairing_result.survivor_count}"
            )
        print(
            f"witness_classification={artifacts.quotient_result.witness_classification}"
        )
        print(f"final_adjudication={artifacts.adjudication.final_adjudication}")
        print(f"outcome_kind={artifacts.outcome_kind}")
        print(f"outcome={artifacts.outcome_path}")
        return 0
    if args.command == "search" and args.search_command == "finalize-lens-axis":
        artifacts = run_lens_axis_finalization(
            config_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"regime_table={artifacts.regime_table_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        print(
            "canonical_flagship_case_id="
            f"{artifacts.final_outcome.canonical_flagship_case_id}"
        )
        print(
            "accepted_proposal_obstruction="
            f"{artifacts.final_outcome.accepted_proposal_obstruction}"
        )
        print(
            "accepted_only_survivor_count="
            f"{artifacts.final_outcome.accepted_only_survivor_count}"
        )
        print(
            "natural_pairing_survivor_count="
            f"{artifacts.final_outcome.natural_pairing_survivor_count}"
        )
        print(f"final_claim_level={artifacts.final_outcome.final_claim_level}")
        print(f"outcome={artifacts.outcome_path}")
        return 0
    if args.command == "robustness" and args.robustness_command == "run-sweep":
        artifacts = run_noise_robustness_sweep(
            sweep_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"robustness_csv={artifacts.csv_path}")
        print(f"robustness_json={artifacts.json_path}")
        print(f"threshold_crossings={artifacts.threshold_crossings_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        print(f"first_crossings={artifacts.summary['first_crossings']}")
        return 0
    if args.command == "redteam" and args.redteam_command == "run-suite":
        artifacts = run_redteam_suite(
            suite_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"results_csv={artifacts.csv_path}")
        print(f"results_json={artifacts.json_path}")
        print(f"response_counts={artifacts.response_counts_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for response, count in artifacts.summary[
            "counts_by_framework_response"
        ].items():
            print(f"{response}={count}")
        return 0
    if (
        args.command == "falsification"
        and args.falsification_command == "run-discovered-case"
    ):
        artifacts = run_discovered_case_falsification(
            falsification_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        result = artifacts.result
        print(f"run_id={artifacts.run_id}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        print(f"selected_case_id={result.selected_case_id}")
        print(
            "baseline_candidate_exact_feasible="
            f"{result.baseline_all_accepted_proposals.exact_feasible}"
        )
        print(
            "baseline_candidate_gpd_str="
            f"{result.baseline_all_accepted_proposals.gpd_str}"
        )
        print(f"hidden_record_outcome={result.hidden_record.outcome}")
        print(f"flattening_outcome={result.flattening.outcome}")
        print(f"final_verdict={result.final_verdict}")
        return 0
    if (
        args.command == "falsification"
        and args.falsification_command == "run-flagship-bundle"
    ):
        artifacts = run_flagship_control_bundle(
            bundle_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        for case in artifacts.result.cases:
            print(f"{case.case_id}_final_verdict={case.final_verdict}")
        print(f"overall_bundle_verdict={artifacts.result.overall_bundle_verdict}")
        print(f"summary={artifacts.summary_path}")
        print(f"table_json={artifacts.table_json_path}")
        print(f"table_csv={artifacts.table_csv_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        return 0
    if args.command == "crosscheck" and args.crosscheck_command == "run":
        artifacts = run_exact_crosscheck(
            config_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"results={artifacts.results_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        if artifacts.model_path is not None:
            print(f"model={artifacts.model_path}")
        if artifacts.solution_path is not None:
            print(f"solution={artifacts.solution_path}")
        for row in artifacts.results.rows:
            print(
                f"target={row.target_id} mode={row.evaluation_mode} "
                f"status={row.crosscheck_status} feasibility={row.feasibility_status} "
                f"blocking={row.blocking_proxy.blocking_proposal_ids}"
            )
        return 0
    if args.command == "pipeline" and args.pipeline_command == "run-benchmarks":
        artifacts = run_benchmark_suite(
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        print(
            "benchmark_ids=" + ",".join(artifacts.summary["benchmark_ids"])  # type: ignore[index]
        )
        return 0
    if args.command == "pipeline" and args.pipeline_command == "run-interventions":
        artifacts = run_intervention_suite(
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for entry in artifacts.summary["interventions"]:  # type: ignore[index]
            print(f"{entry['intervention_id']}={entry['conclusion']}")
        return 0
    if args.command == "pipeline" and args.pipeline_command == "run-search":
        artifacts = run_search_suite(
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        for regime, count in sorted(
            artifacts.summary["regime_counts"].items()  # type: ignore[index]
        ):
            print(f"{regime}={count}")
        return 0
    if args.command == "pipeline" and args.pipeline_command == "run-lean":
        artifacts = run_lean_build(
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        print(f"success={artifacts.summary['success']}")
        print(f"return_code={artifacts.summary['return_code']}")
        return 0 if artifacts.summary["success"] else 1
    if args.command == "findings" and args.findings_command == "build-registry":
        artifacts = build_findings_registry(
            config_path=args.file,
            category=args.category,
            label=args.label,
            seed=args.seed,
            timestamp=args.timestamp,
            root=args.root,
            command=[sys.executable, "-m", "sixbirds_event", *sys.argv[1:]],
        )
        print(f"run_id={artifacts.run_id}")
        print(f"registry={artifacts.registry_path}")
        print(f"claim_evidence_map={artifacts.claim_evidence_map_path}")
        print(f"flagship_examples={artifacts.flagship_examples_path}")
        print(f"summary={artifacts.summary_path}")
        print(f"note={artifacts.note_path}")
        print(f"result_note={artifacts.result_note_path}")
        print(f"manifest={artifacts.manifest_path}")
        print(f"entry_count={artifacts.registry.entry_count}")
        print(f"claim_count={artifacts.registry.summary_counts['claim_count']}")
        print(f"flagship_count={artifacts.registry.summary_counts['flagship_count']}")
        print(
            "limitation_count="
            f"{artifacts.registry.summary_counts['negative_or_limitation_count']}"
        )
        return 0
    return 0
