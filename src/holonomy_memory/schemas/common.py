from __future__ import annotations

from math import isfinite
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict


class HolonomyMemoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def ensure_nonempty_string(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def ensure_repo_relative_path(value: str, field_name: str) -> str:
    ensure_nonempty_string(value, field_name)
    if value.startswith("/") or value.startswith("./"):
        raise ValueError(f"{field_name} must be a normalized repo-relative path")
    if value.endswith("/"):
        raise ValueError(f"{field_name} must be a normalized repo-relative path")
    if PurePosixPath(value).as_posix() != value:
        raise ValueError(f"{field_name} must use normalized POSIX separators")
    if ".." in PurePosixPath(value).parts:
        raise ValueError(f"{field_name} must not contain parent directory segments")
    return value


def ensure_unique_strings(values: Sequence[str], field_name: str) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    if duplicates:
        raise ValueError(f"{field_name} must be unique: {', '.join(duplicates)}")


def ensure_finite_nonnegative_number(value: float, field_name: str) -> float:
    if not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")
    numeric = float(value)
    if numeric < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return numeric


def ensure_probability_distribution(
    values: Mapping[str, float],
    field_name: str,
    *,
    expected_keys: set[str] | None = None,
    tolerance: float = 1e-9,
) -> None:
    if not values:
        raise ValueError(f"{field_name} must not be empty")
    if expected_keys is not None:
        unknown = set(values) - expected_keys
        if unknown:
            raise ValueError(
                f"{field_name} contains undeclared keys: {', '.join(sorted(unknown))}"
            )
    total = 0.0
    for key, raw_value in values.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} keys must be non-empty strings")
        numeric = ensure_finite_nonnegative_number(raw_value, f"{field_name}[{key}]")
        total += numeric
    if abs(total - 1.0) > tolerance:
        raise ValueError(f"{field_name} must sum to 1")


def ensure_kernel_rows(
    kernel: Mapping[str, Mapping[str, float]],
    field_name: str,
    *,
    expected_rows: set[str] | None = None,
    expected_cols: set[str] | None = None,
    tolerance: float = 1e-9,
) -> None:
    if not kernel:
        raise ValueError(f"{field_name} must not be empty")
    if expected_rows is not None:
        unknown_rows = set(kernel) - expected_rows
        if unknown_rows:
            raise ValueError(
                f"{field_name} contains undeclared rows: {', '.join(sorted(unknown_rows))}"
            )
    for row_key, row in kernel.items():
        if not isinstance(row_key, str) or not row_key.strip():
            raise ValueError(f"{field_name} rows must be non-empty strings")
        ensure_probability_distribution(
            row,
            f"{field_name}[{row_key}]",
            expected_keys=expected_cols,
            tolerance=tolerance,
        )
