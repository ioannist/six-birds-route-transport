from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

for path in (REPO_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

pythonpath = os.environ.get("PYTHONPATH")
paths = [str(REPO_ROOT), str(SRC_ROOT)]
if pythonpath:
    paths.extend(part for part in pythonpath.split(os.pathsep) if part)
deduped: list[str] = []
for path in paths:
    if path not in deduped:
        deduped.append(path)
os.environ["PYTHONPATH"] = os.pathsep.join(deduped)
