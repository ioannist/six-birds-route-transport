#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$repo_root" python3 - <<'PY'
from __future__ import annotations

from dataclasses import dataclass
import fnmatch
import json
import os
import pathlib
import zipfile

root = pathlib.Path(os.environ["REPO_ROOT"]).resolve()
repo_name = root.name
version_file = root / ".package-repo-snapshot-version"
config_path = root / ".package-repo-snapshot.json"

raw_config: dict[str, object] = {}
if config_path.exists():
    parsed = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise SystemExit("Invalid .package-repo-snapshot.json: expected a JSON object.")
    raw_config = parsed


def _read_string_list(name: str) -> list[str]:
    raw = raw_config.get(name, [])
    if raw is None:
        return []
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise SystemExit(
            f"Invalid .package-repo-snapshot.json: expected {name} to be a list of strings."
        )
    return raw

default_excluded_dirs = {
    ".git",
    ".cache",
    ".lake",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
}
excluded_dirs = default_excluded_dirs | set(_read_string_list("exclude_dirs"))
default_excluded_paths = {
    ".package-repo-snapshot-version",
    "results",
}
excluded_paths = default_excluded_paths | {
    pathlib.PurePosixPath(path).as_posix().strip("/")
    for path in _read_string_list("exclude_paths")
    if path.strip("/")
}
excluded_globs = _read_string_list("exclude_globs")

current_version = -1
if version_file.exists():
    raw = version_file.read_text(encoding="utf-8").strip()
    if raw.isdigit():
        current_version = int(raw)

next_version = current_version + 1
zip_path = root / f"{repo_name}_snapshot_v{next_version}.zip"


@dataclass(frozen=True)
class IgnoreRule:
    base: pathlib.Path
    pattern: str
    negated: bool
    anchored: bool
    dir_only: bool


def _parse_gitignore(path: pathlib.Path) -> list[IgnoreRule]:
    rules: list[IgnoreRule] = []
    if not path.exists():
        return rules
    base = path.parent
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(r"\#") or line.startswith(r"\!"):
            line = line[1:]
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        anchored = line.startswith("/")
        if anchored:
            line = line[1:]
        dir_only = line.endswith("/")
        if dir_only:
            line = line[:-1]
        if not line:
            continue
        rules.append(
            IgnoreRule(
                base=base,
                pattern=line,
                negated=negated,
                anchored=anchored,
                dir_only=dir_only,
            )
        )
    return rules


def _match_rule(rule: IgnoreRule, rel_posix: str, is_dir: bool) -> bool:
    if rule.dir_only and not is_dir:
        parts = rel_posix.split("/")
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            if _match_rule(
                IgnoreRule(
                    base=rule.base,
                    pattern=rule.pattern,
                    negated=rule.negated,
                    anchored=rule.anchored,
                    dir_only=False,
                ),
                prefix,
                is_dir=True,
            ):
                return True
        return False
    if rule.anchored:
        return fnmatch.fnmatchcase(rel_posix, rule.pattern)
    if "/" in rule.pattern:
        return fnmatch.fnmatchcase(rel_posix, rule.pattern)
    return fnmatch.fnmatchcase(pathlib.PurePosixPath(rel_posix).name, rule.pattern)


def _is_explicitly_excluded(path: pathlib.Path) -> bool:
    rel = path.relative_to(root).as_posix()
    for excluded_path in excluded_paths:
        if rel == excluded_path or rel.startswith(f"{excluded_path}/"):
            return True
    return any(fnmatch.fnmatchcase(rel, pattern) for pattern in excluded_globs)


def _collect_rules(root_path: pathlib.Path) -> list[IgnoreRule]:
    rules: list[IgnoreRule] = []
    rules.append(
        IgnoreRule(
            base=root_path,
            pattern=".git",
            negated=False,
            anchored=False,
            dir_only=True,
        )
    )
    rules.append(
        IgnoreRule(
            base=root_path,
            pattern="*_snapshot.zip",
            negated=False,
            anchored=False,
            dir_only=False,
        )
    )
    rules.append(
        IgnoreRule(
            base=root_path,
            pattern="*_snapshot_v*.zip",
            negated=False,
            anchored=False,
            dir_only=False,
        )
    )
    for dirpath, dirnames, _ in os.walk(root_path):
        base_path = pathlib.Path(dirpath)
        if ".git" in dirnames:
            dirnames.remove(".git")
        dirnames[:] = [
            d
            for d in dirnames
            if d not in excluded_dirs and not _is_explicitly_excluded(base_path / d)
        ]
        ignore_path = pathlib.Path(dirpath) / ".gitignore"
        if ignore_path.exists():
            rules.extend(_parse_gitignore(ignore_path))
    return rules


def _is_ignored(path: pathlib.Path, rules: list[IgnoreRule]) -> bool:
    ignored = False
    for rule in rules:
        try:
            rel_to_rule = path.relative_to(rule.base).as_posix()
        except ValueError:
            continue
        if _match_rule(rule, rel_to_rule, path.is_dir()):
                ignored = not rule.negated
    return ignored


rules = _collect_rules(root)
files: list[pathlib.Path] = []
for dirpath, dirnames, filenames in os.walk(root):
    base_path = pathlib.Path(dirpath)
    dirnames[:] = [
        d
        for d in dirnames
        if d not in excluded_dirs and not _is_explicitly_excluded(base_path / d)
    ]
    for filename in filenames:
        path = base_path / filename
        if not path.exists():
            continue
        if _is_explicitly_excluded(path):
            continue
        if _is_ignored(path, rules):
            continue
        files.append(path)

if not files:
    raise SystemExit("No files to package (all files ignored).")

with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in files:
        rel = path.relative_to(root).as_posix()
        zf.write(path, rel)

version_file.write_text(str(next_version), encoding="utf-8")
previous_path = None
if current_version >= 0:
    previous_path = root / f"{repo_name}_snapshot_v{current_version}.zip"
if previous_path and previous_path.exists():
    previous_path.unlink()

print(f"Wrote {zip_path}")
PY
