from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from holonomy_memory import (
    SearchSpaceEstimate,
    estimate_search_space_size,
    list_search_space_paths,
    load_search_space,
)
from holonomy_memory.schemas import SearchSpace


REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_DIR = REPO_ROOT / "configs" / "search"


def test_search_space_inventory_and_estimates_are_deterministic() -> None:
    paths = list_search_space_paths()
    expected = (
        SEARCH_DIR / "cyclic_memory_small.search.json",
        SEARCH_DIR / "fixed_support_core_small.search.json",
        SEARCH_DIR / "groupoid_probe_small.search.json",
    )
    assert paths == expected

    for path in paths:
        search_space = load_search_space(path)
        estimate = estimate_search_space_size(search_space)
        repeated_estimate = estimate_search_space_size(search_space)

        assert isinstance(search_space, SearchSpace)
        assert isinstance(estimate, SearchSpaceEstimate)
        assert estimate == repeated_estimate
        assert estimate.raw_candidate_count > 0
        assert estimate.capped_candidate_count > 0
        assert estimate.capped_candidate_count <= search_space.max_candidates
        assert search_space.support_size_candidates
        assert search_space.interface_count_candidates
        assert search_space.carrier_family_candidates
        assert search_space.route_update_family_candidates
        assert search_space.observable_family_candidates
        assert search_space.continuation_catalog_family_candidates


def test_search_space_estimates_match_expected_counts() -> None:
    expected_counts = {
        "cyclic_memory_small.search.json": (256, 128),
        "fixed_support_core_small.search.json": (256, 64),
        "groupoid_probe_small.search.json": (128, 128),
    }
    for name, counts in expected_counts.items():
        estimate = estimate_search_space_size(load_search_space(SEARCH_DIR / name))
        assert (estimate.raw_candidate_count, estimate.capped_candidate_count) == counts


def test_search_space_validation_rejects_empty_numeric_candidate_list() -> None:
    payload = {
        "schema_version": "search-space.v1",
        "search_id": "bad_search",
        "seed": 0,
        "support_size_candidates": [],
        "hidden_state_size_candidates": [2],
        "interface_count_candidates": [2],
        "event_count_candidates": [1],
        "history_count_candidates": [2],
        "continuation_count_candidates": [1],
        "loop_count_candidates": [1],
        "carrier_family_candidates": ["none"],
        "route_update_family_candidates": ["identity_only"],
        "observable_family_candidates": ["support_indicator_basis"],
        "continuation_catalog_family_candidates": ["forward_only"],
        "max_candidates": 16,
        "same_support_required": True,
        "allow_loops": True,
        "require_closed_loops": False,
    }
    with pytest.raises(ValidationError):
        SearchSpace.model_validate(payload)


def test_search_space_validation_rejects_nonpositive_max_candidates() -> None:
    payload = {
        "schema_version": "search-space.v1",
        "search_id": "bad_cap",
        "seed": 0,
        "support_size_candidates": [2],
        "hidden_state_size_candidates": [2],
        "interface_count_candidates": [2],
        "event_count_candidates": [1],
        "history_count_candidates": [2],
        "continuation_count_candidates": [1],
        "loop_count_candidates": [1],
        "carrier_family_candidates": ["none"],
        "route_update_family_candidates": ["identity_only"],
        "observable_family_candidates": ["support_indicator_basis"],
        "continuation_catalog_family_candidates": ["forward_only"],
        "max_candidates": 0,
        "same_support_required": True,
        "allow_loops": True,
        "require_closed_loops": False,
    }
    with pytest.raises(ValidationError):
        SearchSpace.model_validate(payload)
