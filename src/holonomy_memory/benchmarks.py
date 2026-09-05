from __future__ import annotations

from pathlib import Path

from .validation import load_benchmark_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_CONFIG_DIR = REPO_ROOT / "configs" / "benchmarks"

BENCHMARK_IDS = (
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

PAIR_MANIFEST_FILENAMES = (
    "flattenable_pair.completion.json",
    "latent_memory_pair.currentization.json",
)


def benchmark_manifest_paths() -> tuple[Path, ...]:
    return tuple(
        BENCHMARK_CONFIG_DIR / f"{benchmark_id}.benchmark.json"
        for benchmark_id in BENCHMARK_IDS
    )


def benchmark_manifest_path_for_id(benchmark_id: str) -> Path:
    if benchmark_id not in BENCHMARK_IDS:
        raise KeyError(f"unknown benchmark_id: {benchmark_id}")
    return BENCHMARK_CONFIG_DIR / f"{benchmark_id}.benchmark.json"


def load_benchmark_manifest_for_id(benchmark_id: str):
    return load_benchmark_manifest(benchmark_manifest_path_for_id(benchmark_id))


def pair_manifest_paths() -> tuple[Path, ...]:
    return tuple(BENCHMARK_CONFIG_DIR / filename for filename in PAIR_MANIFEST_FILENAMES)


def perturbation_manifest_paths() -> tuple[Path, ...]:
    return tuple(
        BENCHMARK_CONFIG_DIR / f"{benchmark_id}.perturbation.json"
        for benchmark_id in BENCHMARK_IDS
    )


def resolve_repo_relative_path(path: str) -> Path:
    return REPO_ROOT / path
