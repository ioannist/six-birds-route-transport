from __future__ import annotations

from pydantic import Field, model_validator

from .common import (
    HolonomyMemoryModel,
    ensure_finite_nonnegative_number,
    ensure_nonempty_string,
    ensure_repo_relative_path,
    ensure_unique_strings,
)
from .enums import (
    BenchmarkManifestVersion,
    ComparisonManifestVersion,
    EffectIntent,
    PerturbationKind,
    PerturbationSweepVersion,
    SearchSpaceVersion,
)
from .transport import RouteTransportPackageConfig


class BenchmarkManifest(HolonomyMemoryModel):
    schema_version: BenchmarkManifestVersion = BenchmarkManifestVersion.V1
    benchmark_id: str
    transport_package: RouteTransportPackageConfig | None = None
    transport_package_ref: str | None = None
    interfaces_to_measure: list[str] = Field(min_length=1)
    loops_to_test: list[str] = Field(min_length=1)
    completion_manifest_ref: str | None = None
    currentization_manifest_ref: str | None = None
    perturbation_sweep_ref: str | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_benchmark_manifest(self) -> "BenchmarkManifest":
        ensure_nonempty_string(self.benchmark_id, "benchmark_id")
        if (self.transport_package is None) == (self.transport_package_ref is None):
            raise ValueError(
                "exactly one of transport_package or transport_package_ref must be provided"
            )
        if self.transport_package_ref is not None:
            ensure_repo_relative_path(
                self.transport_package_ref, "transport_package_ref"
            )
        if self.completion_manifest_ref is not None:
            ensure_repo_relative_path(
                self.completion_manifest_ref, "completion_manifest_ref"
            )
        if self.currentization_manifest_ref is not None:
            ensure_repo_relative_path(
                self.currentization_manifest_ref, "currentization_manifest_ref"
            )
        if self.perturbation_sweep_ref is not None:
            ensure_repo_relative_path(
                self.perturbation_sweep_ref, "perturbation_sweep_ref"
            )
        ensure_unique_strings(self.interfaces_to_measure, "interfaces_to_measure")
        ensure_unique_strings(self.loops_to_test, "loops_to_test")
        for item in self.interfaces_to_measure + self.loops_to_test + self.tags:
            ensure_nonempty_string(item, "benchmark manifest list entries")
        return self


class ComparisonManifestBase(HolonomyMemoryModel):
    schema_version: ComparisonManifestVersion = ComparisonManifestVersion.V1
    manifest_id: str
    base_benchmark_id: str
    same_support_required: bool
    expected_effect: EffectIntent
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_common(self) -> "ComparisonManifestBase":
        ensure_nonempty_string(self.manifest_id, "manifest_id")
        ensure_nonempty_string(self.base_benchmark_id, "base_benchmark_id")
        for tag in self.tags:
            ensure_nonempty_string(tag, "tags")
        return self


class CompletionManifest(ComparisonManifestBase):
    completed_benchmark_id: str

    @model_validator(mode="after")
    def validate_completion_manifest(self) -> "CompletionManifest":
        ensure_nonempty_string(self.completed_benchmark_id, "completed_benchmark_id")
        return self


class CurrentizationManifest(ComparisonManifestBase):
    refined_benchmark_id: str

    @model_validator(mode="after")
    def validate_currentization_manifest(self) -> "CurrentizationManifest":
        ensure_nonempty_string(self.refined_benchmark_id, "refined_benchmark_id")
        return self


class PerturbationTargetSpec(HolonomyMemoryModel):
    target_path: str
    perturbation_kind: PerturbationKind
    magnitude: float = Field(ge=0)
    radius: float | None = Field(default=None, ge=0)
    lower_bound: float | None = None
    upper_bound: float | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "PerturbationTargetSpec":
        ensure_nonempty_string(self.target_path, "target_path")
        ensure_finite_nonnegative_number(self.magnitude, "magnitude")
        if self.radius is not None:
            ensure_finite_nonnegative_number(self.radius, "radius")
        if self.lower_bound is not None:
            ensure_finite_nonnegative_number(self.lower_bound, "lower_bound")
        if self.upper_bound is not None:
            ensure_finite_nonnegative_number(self.upper_bound, "upper_bound")
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError("lower_bound must be less than or equal to upper_bound")
        return self


class PerturbationSweep(HolonomyMemoryModel):
    schema_version: PerturbationSweepVersion = PerturbationSweepVersion.V1
    sweep_id: str
    benchmark_id: str
    seed: int
    trial_count: int = Field(ge=1)
    targets: list[PerturbationTargetSpec] = Field(min_length=1)
    acceptance_threshold: float | None = Field(default=None, ge=0, le=1)
    stop_after_failures: int | None = Field(default=None, ge=0)
    max_accepted_fraction: float | None = Field(default=None, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sweep(self) -> "PerturbationSweep":
        ensure_nonempty_string(self.sweep_id, "sweep_id")
        ensure_nonempty_string(self.benchmark_id, "benchmark_id")
        for tag in self.tags:
            ensure_nonempty_string(tag, "tags")
        return self


class SearchSpace(HolonomyMemoryModel):
    schema_version: SearchSpaceVersion = SearchSpaceVersion.V1
    search_id: str
    seed: int
    support_size_candidates: list[int] = Field(min_length=1)
    hidden_state_size_candidates: list[int] = Field(min_length=1)
    interface_count_candidates: list[int] = Field(min_length=1)
    event_count_candidates: list[int] = Field(min_length=1)
    history_count_candidates: list[int] = Field(min_length=1)
    continuation_count_candidates: list[int] = Field(min_length=1)
    loop_count_candidates: list[int] = Field(min_length=1)
    carrier_family_candidates: list[str] = Field(default_factory=list)
    route_update_family_candidates: list[str] = Field(default_factory=list)
    observable_family_candidates: list[str] = Field(default_factory=list)
    continuation_catalog_family_candidates: list[str] = Field(default_factory=list)
    max_candidates: int = Field(ge=1)
    same_support_required: bool
    allow_loops: bool
    require_closed_loops: bool
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_search_space(self) -> "SearchSpace":
        ensure_nonempty_string(self.search_id, "search_id")
        if self.require_closed_loops and not self.allow_loops:
            raise ValueError("require_closed_loops implies allow_loops")
        for candidate_list_name in (
            "support_size_candidates",
            "hidden_state_size_candidates",
            "interface_count_candidates",
            "event_count_candidates",
            "history_count_candidates",
            "continuation_count_candidates",
            "loop_count_candidates",
        ):
            candidate_list = getattr(self, candidate_list_name)
            if any(value < 1 for value in candidate_list):
                raise ValueError(f"{candidate_list_name} must contain only positive integers")
        for family_list_name in (
            "carrier_family_candidates",
            "route_update_family_candidates",
            "observable_family_candidates",
            "continuation_catalog_family_candidates",
        ):
            family_list = getattr(self, family_list_name)
            ensure_unique_strings(family_list, family_list_name)
            for family_label in family_list:
                ensure_nonempty_string(family_label, family_list_name)
        for tag in self.tags:
            ensure_nonempty_string(tag, "tags")
        return self
