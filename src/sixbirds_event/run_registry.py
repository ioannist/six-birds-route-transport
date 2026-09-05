from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

from . import __version__
from .schemas.common import SchemaKind, is_repo_relative_path
from .schemas.run_manifest import RunManifest, SoftwareVersion
from .validation import load_model

DEFAULT_RESULTS_CATEGORIES = ("benchmarks", "search", "interventions")
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class RunSummary:
    run_id: str
    timestamp: str
    status: str
    category: str
    manifest_path: str


def get_repo_root(root: str | Path | None = None) -> Path:
    if root is None:
        return _DEFAULT_REPO_ROOT
    return Path(root).resolve()


def ensure_utc_timestamp(value: str | datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    if isinstance(value, datetime):
        dt = value
    else:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def format_manifest_timestamp(value: str | datetime | None = None) -> str:
    return ensure_utc_timestamp(value).isoformat().replace("+00:00", "Z")


def format_directory_timestamp(value: str | datetime | None = None) -> str:
    return ensure_utc_timestamp(value).strftime("%Y%m%dT%H%M%SZ")


def slugify(value: str | None) -> str:
    if value is None:
        return ""
    normalized = _SLUG_PATTERN.sub("_", value.strip().lower()).strip("_")
    return normalized


def generate_run_id(
    *,
    category: str,
    label: str | None = None,
    timestamp: str | datetime | None = None,
    run_id: str | None = None,
) -> str:
    if run_id:
        return run_id
    timestamp_token = format_directory_timestamp(timestamp).lower()
    label_token = slugify(label) or "run"
    return f"run_{category}_{timestamp_token}_{label_token}"


def ensure_results_category(category: str) -> str:
    normalized = slugify(category)
    if not normalized:
        raise ValueError("category must be a non-empty slug")
    return normalized


def repo_relative_path(path: str | Path, *, root: str | Path | None = None) -> str:
    repo_root = get_repo_root(root)
    candidate = Path(path)
    if candidate.is_absolute():
        rel = candidate.resolve().relative_to(repo_root)
        return rel.as_posix()
    value = candidate.as_posix()
    if not is_repo_relative_path(value):
        raise ValueError(f"path '{value}' must be a normalized repo-relative path")
    return value


def create_run_directory(
    *,
    category: str,
    label: str | None = None,
    timestamp: str | datetime | None = None,
    run_id: str | None = None,
    root: str | Path | None = None,
) -> tuple[Path, str, str]:
    repo_root = get_repo_root(root)
    normalized_category = ensure_results_category(category)
    manifest_timestamp = format_manifest_timestamp(timestamp)
    run_id_value = generate_run_id(
        category=normalized_category,
        label=label,
        timestamp=manifest_timestamp,
        run_id=run_id,
    )
    label_or_run = slugify(label) or run_id_value
    directory_name = f"{format_directory_timestamp(manifest_timestamp)}--{label_or_run}"
    run_dir = repo_root / "results" / normalized_category / directory_name
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir, run_id_value, manifest_timestamp


def detect_git_commit(*, root: str | Path | None = None) -> str | None:
    repo_root = get_repo_root(root)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def collect_software_version() -> SoftwareVersion:
    return SoftwareVersion(
        python=sys.version.split()[0],
        package=__version__,
    )


def build_run_manifest(
    *,
    run_id: str,
    timestamp: str | datetime,
    command: list[str],
    seed: int,
    input_artifacts: dict[str, str] | None = None,
    output_artifacts: dict[str, str] | None = None,
    status: str,
    metadata: dict[str, str | int | float | bool | None | list[str]] | None = None,
    git_commit: str | None = None,
) -> RunManifest:
    return RunManifest(
        manifest_format_version="run-manifest.v1",
        run_id=run_id,
        timestamp=format_manifest_timestamp(timestamp),
        command=command,
        seed=seed,
        input_artifacts=input_artifacts or {},
        output_artifacts=output_artifacts or {},
        software_version=collect_software_version(),
        status=status,
        git_commit=git_commit,
        metadata=metadata or {},
    )


def write_run_manifest(
    manifest: RunManifest,
    *,
    run_dir: str | Path,
) -> Path:
    path = Path(run_dir) / "run-manifest.json"
    path.write_text(
        json.dumps(manifest.model_dump(mode="json", exclude_none=True), indent=2)
        + "\n",
        encoding="utf-8",
    )
    return path


def create_dummy_run(
    *,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | datetime | None = None,
    run_id: str | None = None,
    root: str | Path | None = None,
    input_artifacts: dict[str, str] | None = None,
    command: list[str] | None = None,
) -> RunManifest:
    repo_root = get_repo_root(root)
    run_dir, run_id_value, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        run_id=run_id,
        root=repo_root,
    )
    dummy_output_path = run_dir / "dummy-output.json"
    dummy_output_path.write_text(
        json.dumps(
            {
                "run_id": run_id_value,
                "status": "succeeded",
                "kind": "dummy-run",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    category_name = ensure_results_category(category)
    output_artifacts = {
        "dummy_output": repo_relative_path(dummy_output_path, root=repo_root),
    }
    manifest = build_run_manifest(
        run_id=run_id_value,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "runs",
            "create-dummy",
            "--category",
            category_name,
        ],
        seed=seed,
        input_artifacts=input_artifacts or {},
        output_artifacts=output_artifacts,
        status="succeeded",
        git_commit=detect_git_commit(root=repo_root),
        metadata={
            "category": category_name,
            "label": slugify(label) or run_id_value,
            "root": repo_relative_path(run_dir, root=repo_root),
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return manifest


def list_runs(*, root: str | Path | None = None) -> list[RunSummary]:
    repo_root = get_repo_root(root)
    manifests = sorted(repo_root.glob("results/**/run-manifest.json"))
    summaries: list[RunSummary] = []
    for manifest_path in manifests:
        manifest = load_model(manifest_path, kind=SchemaKind.RUN_MANIFEST)
        assert isinstance(manifest, RunManifest)
        relative_manifest = repo_relative_path(manifest_path, root=repo_root)
        category = Path(relative_manifest).parts[1]
        summaries.append(
            RunSummary(
                run_id=manifest.run_id,
                timestamp=manifest.timestamp,
                status=manifest.status,
                category=category,
                manifest_path=relative_manifest,
            )
        )
    return summaries
