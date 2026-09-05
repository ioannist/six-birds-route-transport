from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from ..schemas import AuditStatus, PerturbationKind, PerturbationSweep
from .models import (
    PerturbationHookResult,
    PerturbationSweepPlan,
    PerturbationTargetResolution,
)


def resolve_perturbation_targets(
    config_like: object,
    sweep_manifest: PerturbationSweep,
) -> tuple[PerturbationTargetResolution, ...]:
    root = _normalize_config_like(config_like)
    resolutions: list[PerturbationTargetResolution] = []
    for target in sweep_manifest.targets:
        value: Any = root
        resolved = True
        reasons: list[str] = []
        for token in _tokenize_target_path(target.target_path):
            try:
                value = _apply_target_token(value, token)
            except (KeyError, IndexError, TypeError):
                resolved = False
                reasons.append(f"target path segment not found: {token}")
                break

        if resolved and not _is_perturbable_leaf(target.perturbation_kind, value):
            resolved = False
            reasons.append(
                f"target leaf is not perturbable for {target.perturbation_kind.value}: "
                f"{type(value).__name__}"
            )

        resolutions.append(
            PerturbationTargetResolution(
                target_path=target.target_path,
                perturbation_kind=target.perturbation_kind,
                resolved=resolved,
                resolved_location=target.target_path if resolved else None,
                resolved_type=type(value).__name__ if resolved else None,
                reasons=tuple(reasons),
            )
        )
    return tuple(resolutions)


def build_perturbation_sweep_plan(
    config_like: object,
    sweep_manifest: PerturbationSweep,
) -> PerturbationSweepPlan:
    resolutions = resolve_perturbation_targets(config_like, sweep_manifest)
    resolved_targets = tuple(resolution for resolution in resolutions if resolution.resolved)
    trial_ids = tuple(
        f"{sweep_manifest.sweep_id}:trial:{index}"
        for index in range(sweep_manifest.trial_count)
    )
    trial_seeds = tuple(
        sweep_manifest.seed + index
        for index in range(sweep_manifest.trial_count)
    )
    return PerturbationSweepPlan(
        sweep_id=sweep_manifest.sweep_id,
        benchmark_id=sweep_manifest.benchmark_id,
        seed=sweep_manifest.seed,
        trial_count=sweep_manifest.trial_count,
        resolved_targets=resolved_targets,
        trial_ids=trial_ids,
        trial_seeds=trial_seeds,
    )


def evaluate_perturbation_hook(
    config_like: object,
    sweep_manifest: PerturbationSweep,
) -> PerturbationHookResult:
    resolutions = resolve_perturbation_targets(config_like, sweep_manifest)
    resolved_target_count = sum(1 for resolution in resolutions if resolution.resolved)
    unresolved_target_count = len(resolutions) - resolved_target_count
    reasons: list[str] = []
    if unresolved_target_count == 0:
        status = AuditStatus.PASSED
        reasons.append("all perturbation targets resolved cleanly")
    elif resolved_target_count == 0:
        status = AuditStatus.FAILED
        reasons.append("no perturbation targets resolved")
    else:
        status = AuditStatus.INCONCLUSIVE
        reasons.append("some perturbation targets did not resolve")

    return PerturbationHookResult(
        status=status,
        sweep_id=sweep_manifest.sweep_id,
        benchmark_id=sweep_manifest.benchmark_id,
        resolved_target_count=resolved_target_count,
        unresolved_target_count=unresolved_target_count,
        trial_count=sweep_manifest.trial_count,
        reasons=tuple(reasons),
    )


def _normalize_config_like(config_like: object) -> object:
    if hasattr(config_like, "model_dump"):
        return config_like.model_dump(mode="python")
    if is_dataclass(config_like):
        return asdict(config_like)
    return config_like


def _tokenize_target_path(path: str) -> tuple[str | int, ...]:
    tokens: list[str | int] = []
    buffer = ""
    index = 0
    while index < len(path):
        character = path[index]
        if character == ".":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            index += 1
            continue
        if character == "[":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            end_index = path.index("]", index)
            tokens.append(int(path[index + 1 : end_index]))
            index = end_index + 1
            continue
        buffer += character
        index += 1
    if buffer:
        tokens.append(buffer)
    return tuple(tokens)


def _apply_target_token(value: object, token: str | int) -> object:
    if isinstance(token, int):
        if not isinstance(value, list):
            raise TypeError("list index applied to non-list target")
        return value[token]
    if isinstance(value, dict):
        return value[token]
    raise TypeError("dict key applied to non-dict target")


def _is_perturbable_leaf(kind: PerturbationKind, value: object) -> bool:
    if kind in {
        PerturbationKind.ADDITIVE,
        PerturbationKind.MULTIPLICATIVE,
        PerturbationKind.WEIGHT_SHIFT,
    }:
        return isinstance(value, (int, float))
    return True
