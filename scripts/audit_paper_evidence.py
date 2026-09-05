"""Compare a fresh evidence run to tracked JSON, ignoring only runtime and root paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from holonomy_memory.analysis.quotients import (
    compute_current_partition,
    compute_predictive_partition,
    predictive_refines_current,
)
from holonomy_memory.benchmarks import BENCHMARK_IDS, load_benchmark_manifest_for_id
from holonomy_memory.core import load_route_transport_package
from holonomy_memory.discovery import (
    enumerate_discovery_candidates,
    realize_discovery_candidate,
)
from holonomy_memory.discovery_multispace import DEFAULT_MULTISPACE_SEARCH_IDS

ROOT = Path(__file__).resolve().parents[1]


def normalize(value: object, fresh: Path) -> object:
    if isinstance(value, dict):
        return {k: normalize(v, fresh) for k, v in value.items() if k != "runtime"}
    if isinstance(value, list):
        return [normalize(v, fresh) for v in value]
    if isinstance(value, str):
        for base in (fresh, ROOT):
            value = value.removeprefix(str(base) + "/")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fresh_root", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    fresh = args.fresh_root.resolve()
    compared, mismatched = [], []
    for path in sorted((fresh / "artifacts/results").rglob("*.json")):
        relative = path.relative_to(fresh)
        baseline = ROOT / relative
        if not baseline.is_file():
            continue
        same = normalize(json.loads(path.read_text()), fresh) == normalize(
            json.loads(baseline.read_text()), fresh
        )
        compared.append(str(relative))
        if not same:
            mismatched.append(str(relative))

    required = {
        "artifacts/results/benchmark_suite.json",
        "artifacts/results/robustness/core_suite.robustness.json",
        "artifacts/results/discovery/discovery_smoke.json",
        "artifacts/results/discovery/multi_space.discovery.json",
        "artifacts/results/discovery/multi_space.dedup.json",
        "artifacts/results/discovery/promoted_exemplars.json",
    }
    missing = sorted(required - set(compared))
    manuscript = (ROOT / "paper/main.tex").read_text()
    bibliography = (ROOT / "paper/references.bib").read_text()
    keys = re.findall(r"@\w+\{([^,]+),", bibliography)
    cited = {
        key.strip()
        for group in re.findall(r"\\cite\w*\{([^}]+)\}", manuscript)
        for key in group.split(",")
    }
    undefined = sorted(cited - set(keys))
    unused = sorted(set(keys) - cited)
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    partition_checks = []

    def check_package(name, package, reported_interfaces):
        for interface in sorted({h.target_interface_id for h in package.histories}):
            current = compute_current_partition(package, interface)
            predictive = compute_predictive_partition(package, interface)
            partition_checks.append(
                {
                    "model": name,
                    "interface": interface,
                    "current_size": current.class_count,
                    "predictive_size": predictive.class_count,
                    "refines": predictive_refines_current(current, predictive),
                    "reported_comparison_interface": interface in reported_interfaces,
                }
            )

    for benchmark in BENCHMARK_IDS:
        manifest = load_benchmark_manifest_for_id(benchmark)
        check_package(
            benchmark,
            load_route_transport_package(ROOT / manifest.transport_package_ref),
            manifest.interfaces_to_measure,
        )
    for search in DEFAULT_MULTISPACE_SEARCH_IDS:
        atlas = json.loads(
            (fresh / f"artifacts/results/discovery/{search}.atlas.json").read_text()
        )
        primary = {
            c["candidate_id"]: c["primary_interface_id"] for c in atlas["candidates"]
        }
        for spec in enumerate_discovery_candidates(search_id=search):
            check_package(
                f"{search}:{spec.candidate_id}",
                realize_discovery_candidate(spec, search_id=search),
                [primary[spec.candidate_id]],
            )
    refinement_failures = [c for c in partition_checks if not c["refines"]]
    reported_refinement_failures = [
        c for c in refinement_failures if c["reported_comparison_interface"]
    ]
    report = {
        "compared_artifact_count": len(compared),
        "compared_artifacts": compared,
        "mismatched_artifacts": mismatched,
        "missing_required_artifacts": missing,
        "ignored_fields": ["runtime"],
        "path_normalization": "Strip only the repository and fresh-output absolute root prefixes",
        "undefined_citations": undefined,
        "unused_bibliography_keys": unused,
        "duplicate_bibliography_keys": duplicates,
        "partition_checks": partition_checks,
        "refinement_failures": refinement_failures,
        "reported_interface_refinement_passed": not reported_refinement_failures,
        "full_catalog_refinement_passed": not refinement_failures,
        "scope": "Reported benchmark and discovery-primary comparisons; terminal catalog failures remain disclosed",
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("paper/main.tex", "paper/references.bib")
        },
        "passed": not (
            mismatched
            or missing
            or undefined
            or unused
            or duplicates
            or reported_refinement_failures
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ("compared_artifacts", "partition_checks")
            },
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
