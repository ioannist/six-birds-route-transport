from __future__ import annotations

from pathlib import Path

from holonomy_memory.benchmarks import BENCHMARK_IDS


def test_relative_recombination_is_explicitly_dropped() -> None:
    note_path = Path("docs/results/relative_recombination.md")

    assert "relative_recombination" not in BENCHMARK_IDS
    assert note_path.is_file()

    note = note_path.read_text(encoding="utf-8")
    assert "decision: DROP" in note
    assert "candidate_validated: yes" in note
    assert "candidate_ran_under_current_engine: yes" in note
    assert "single-continuation witness" in note
