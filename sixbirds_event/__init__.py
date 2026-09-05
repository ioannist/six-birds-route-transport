from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__version__ = "0.0.0"

_repo_root = Path(__file__).resolve().parent.parent
_src_package = _repo_root / "src" / "sixbirds_event"

__path__ = extend_path(__path__, __name__)
if _src_package.is_dir():
    __path__.append(str(_src_package))
