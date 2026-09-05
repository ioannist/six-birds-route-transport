from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_holonomy_memory_scaffold_smoke() -> None:
    import holonomy_memory
    import sixbirds_event

    assert holonomy_memory.__version__ == "0.0.0"
    assert sixbirds_event.__version__ == "0.0.0"

    holonomy_help = subprocess.run(
        [sys.executable, "-m", "holonomy_memory", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert holonomy_help.returncode == 0
    assert "usage:" in holonomy_help.stdout.lower()

    legacy_help = subprocess.run(
        [sys.executable, "-m", "sixbirds_event", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert legacy_help.returncode == 0
    assert "usage:" in legacy_help.stdout.lower()

    expected_dirs = [
        Path("src/holonomy_memory"),
        Path("tests/holonomy_memory"),
        Path("configs/benchmarks"),
        Path("configs/search"),
        Path("artifacts/results"),
        Path("artifacts/tables"),
        Path("artifacts/figures"),
        Path("docs/ops"),
        Path("docs/results"),
        Path("lean"),
    ]
    for path in expected_dirs:
        assert path.is_dir(), path
