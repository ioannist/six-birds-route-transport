from __future__ import annotations

import json
from pathlib import Path

from .schemas.manifests import (
    BenchmarkManifest,
    CompletionManifest,
    CurrentizationManifest,
    PerturbationSweep,
    SearchSpace,
)
from .schemas.results import BenchmarkResultManifest
from .schemas.transport import RouteTransportPackageConfig


def load_json_file(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_route_transport_package_config(path: str | Path) -> RouteTransportPackageConfig:
    return RouteTransportPackageConfig.model_validate(load_json_file(path))


def load_benchmark_manifest(path: str | Path) -> BenchmarkManifest:
    return BenchmarkManifest.model_validate(load_json_file(path))


def load_completion_manifest(path: str | Path) -> CompletionManifest:
    return CompletionManifest.model_validate(load_json_file(path))


def load_currentization_manifest(path: str | Path) -> CurrentizationManifest:
    return CurrentizationManifest.model_validate(load_json_file(path))


def load_perturbation_sweep(path: str | Path) -> PerturbationSweep:
    return PerturbationSweep.model_validate(load_json_file(path))


def load_search_space(path: str | Path) -> SearchSpace:
    return SearchSpace.model_validate(load_json_file(path))


def load_benchmark_result_manifest(path: str | Path) -> BenchmarkResultManifest:
    return BenchmarkResultManifest.model_validate(load_json_file(path))
