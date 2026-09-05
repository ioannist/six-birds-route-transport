from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

src_root_str = str(SRC_ROOT)
if src_root_str not in sys.path:
    sys.path.insert(0, src_root_str)

pythonpath = os.environ.get("PYTHONPATH")
if pythonpath:
    paths = pythonpath.split(os.pathsep)
    if src_root_str not in paths:
        os.environ["PYTHONPATH"] = os.pathsep.join([src_root_str, pythonpath])
else:
    os.environ["PYTHONPATH"] = src_root_str
