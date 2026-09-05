from __future__ import annotations

from collections import OrderedDict
from fractions import Fraction
from typing import Iterable, Mapping, Sequence


ExactNumber = Fraction | int | float | str


def to_fraction(value: ExactNumber, *, context: str) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"{context} must be an exact numeric value")


def ensure_exact_total(
    values: Iterable[Fraction], *, expected: Fraction, context: str
) -> None:
    total = sum(values, start=Fraction(0, 1))
    if total != expected:
        raise ValueError(f"{context} must sum to {expected}")


def normalize_sparse_distribution(
    keys: Sequence[str],
    raw: Mapping[str, ExactNumber],
    *,
    context: str,
    require_total: Fraction | None = None,
) -> tuple[Fraction, ...]:
    unknown_keys = set(raw) - set(keys)
    if unknown_keys:
        names = ", ".join(sorted(unknown_keys))
        raise ValueError(f"{context} references undeclared keys: {names}")

    values: list[Fraction] = []
    for key in keys:
        fraction = to_fraction(raw.get(key, 0), context=f"{context}[{key}]")
        if fraction < 0:
            raise ValueError(f"{context}[{key}] must be nonnegative")
        values.append(fraction)

    if require_total is not None:
        ensure_exact_total(values, expected=require_total, context=context)
    return tuple(values)


def normalize_sparse_kernel(
    source_keys: Sequence[str],
    target_keys: Sequence[str],
    raw: Mapping[str, Mapping[str, ExactNumber]],
    *,
    context: str,
) -> tuple[tuple[Fraction, ...], ...]:
    unknown_rows = set(raw) - set(source_keys)
    if unknown_rows:
        names = ", ".join(sorted(unknown_rows))
        raise ValueError(f"{context} references undeclared source states: {names}")

    rows: list[tuple[Fraction, ...]] = []
    for source_key in source_keys:
        row = raw.get(source_key, {})
        rows.append(
            normalize_sparse_distribution(
                target_keys,
                row,
                context=f"{context}[{source_key}]",
                require_total=Fraction(1, 1),
            )
        )
    return tuple(rows)


def ordered_fraction_mapping(
    keys: Sequence[str], values: Sequence[Fraction]
) -> OrderedDict[str, Fraction]:
    return OrderedDict(zip(keys, values, strict=True))


def project_state_distribution_to_support(
    state_distribution: Sequence[Fraction],
    *,
    state_ids: Sequence[str],
    support_labels: Sequence[str],
    support_projection: Mapping[str, str],
) -> tuple[Fraction, ...]:
    label_to_index = {label: index for index, label in enumerate(support_labels)}
    projected = [Fraction(0, 1) for _ in support_labels]
    for state_id, probability in zip(state_ids, state_distribution, strict=True):
        projected[label_to_index[support_projection[state_id]]] += probability
    return tuple(projected)


def apply_row_vector_to_kernel(
    row_vector: Sequence[Fraction],
    kernel_rows: Sequence[Sequence[Fraction]],
) -> tuple[Fraction, ...]:
    if len(row_vector) != len(kernel_rows):
        raise ValueError("row vector and kernel row count must match")
    if not kernel_rows:
        return tuple()

    target_width = len(kernel_rows[0])
    result = [Fraction(0, 1) for _ in range(target_width)]
    for probability, row in zip(row_vector, kernel_rows, strict=True):
        if len(row) != target_width:
            raise ValueError("kernel rows must have a consistent width")
        for index, value in enumerate(row):
            result[index] += probability * value
    return tuple(result)


def compose_row_stochastic_kernels(
    first_rows: Sequence[Sequence[Fraction]],
    second_rows: Sequence[Sequence[Fraction]],
) -> tuple[tuple[Fraction, ...], ...]:
    if not first_rows:
        return tuple()

    intermediate_width = len(first_rows[0])
    if intermediate_width != len(second_rows):
        raise ValueError("kernel dimensions do not align for composition")

    return tuple(apply_row_vector_to_kernel(row, second_rows) for row in first_rows)
