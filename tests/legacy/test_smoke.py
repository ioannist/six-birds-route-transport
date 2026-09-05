from __future__ import annotations

import subprocess
import sys


def test_package_import_and_cli_help() -> None:
    import sixbirds_event

    assert sixbirds_event.__version__ == "0.0.0"

    result = subprocess.run(
        [sys.executable, "-m", "sixbirds_event", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
