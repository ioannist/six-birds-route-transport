from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .benchmarks import REPO_ROOT
from .schemas import SearchSpace
from .validation import load_search_space as _load_search_space


SEARCH_CONFIG_DIR = REPO_ROOT / "configs" / "search"


@dataclass(frozen=True)
class SearchSpaceEstimate:
    search_id: str
    raw_candidate_count: int
    capped_candidate_count: int
    dimension_factors: tuple[tuple[str, int], ...]


def list_search_space_paths() -> tuple[Path, ...]:
    return tuple(sorted(SEARCH_CONFIG_DIR.glob("*.search.json")))


def search_space_path_for_id(search_id: str) -> Path:
    candidate = SEARCH_CONFIG_DIR / f"{search_id}.search.json"
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"unknown search space id: {search_id}")


def load_search_space(path: str | Path) -> SearchSpace:
    return _load_search_space(path)


def load_search_space_for_id(search_id: str) -> SearchSpace:
    return load_search_space(search_space_path_for_id(search_id))


def estimate_search_space_size(search_space: SearchSpace) -> SearchSpaceEstimate:
    dimension_factors = (
        ("support_size_candidates", len(search_space.support_size_candidates)),
        ("hidden_state_size_candidates", len(search_space.hidden_state_size_candidates)),
        ("interface_count_candidates", len(search_space.interface_count_candidates)),
        ("event_count_candidates", len(search_space.event_count_candidates)),
        ("history_count_candidates", len(search_space.history_count_candidates)),
        ("continuation_count_candidates", len(search_space.continuation_count_candidates)),
        ("loop_count_candidates", len(search_space.loop_count_candidates)),
        (
            "carrier_family_candidates",
            max(1, len(search_space.carrier_family_candidates)),
        ),
        (
            "route_update_family_candidates",
            max(1, len(search_space.route_update_family_candidates)),
        ),
        (
            "observable_family_candidates",
            max(1, len(search_space.observable_family_candidates)),
        ),
        (
            "continuation_catalog_family_candidates",
            max(1, len(search_space.continuation_catalog_family_candidates)),
        ),
    )
    raw_candidate_count = 1
    for _, factor in dimension_factors:
        raw_candidate_count *= factor
    return SearchSpaceEstimate(
        search_id=search_space.search_id,
        raw_candidate_count=raw_candidate_count,
        capped_candidate_count=min(raw_candidate_count, search_space.max_candidates),
        dimension_factors=dimension_factors,
    )
