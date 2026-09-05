from __future__ import annotations

from enum import Enum


class RouteTransportSchemaVersion(str, Enum):
    V1 = "route-transport-package.v1"


class BenchmarkManifestVersion(str, Enum):
    V1 = "benchmark-manifest.v1"


class ComparisonManifestVersion(str, Enum):
    V1 = "comparison-manifest.v1"


class PerturbationSweepVersion(str, Enum):
    V1 = "perturbation-sweep.v1"


class SearchSpaceVersion(str, Enum):
    V1 = "search-space.v1"


class BenchmarkResultManifestVersion(str, Enum):
    V1 = "benchmark-result-manifest.v1"


class PerturbationKind(str, Enum):
    ADDITIVE = "additive"
    MULTIPLICATIVE = "multiplicative"
    STRUCTURAL = "structural"
    SUPPORT_RELABEL = "support_relabel"
    WEIGHT_SHIFT = "weight_shift"


class EffectIntent(str, Enum):
    COMPLETION = "completion"
    CURRENTIZATION = "currentization"
    SUPPORT_PRESERVING = "support_preserving"
    SUPPORT_REFINING = "support_refining"


class AuditStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    SKIPPED = "skipped"


class DiscrepancyMetricName(str, Enum):
    PSD_EXACT_GAP = "psd_exact_gap"
    EXACT_MAX_ABS_FUTURE_GAP = "exact_max_abs_future_gap"


class ClassLabel(str, Enum):
    FLAT = "flat"
    ARTIFACT_TRAP = "artifact_trap"
    FLATTENABLE = "flattenable"
    DISSIPATIVE = "dissipative"
    EXPLICIT_LATENT = "explicit_latent"
    COHERENT_CANDIDATE = "coherent_candidate"
