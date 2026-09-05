from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from holonomy_memory import (
    ClassificationEvidence,
    InterfaceEvidenceSummary,
    build_perturbation_sweep_plan,
    check_currentization,
    check_flattening,
    check_support_fixation,
    classify_regime,
    evaluate_perturbation_hook,
    load_route_transport_package,
    resolve_perturbation_targets,
)
from holonomy_memory.schemas import AuditStatus, ClassLabel, DiscrepancyMetricName
from holonomy_memory.validation import (
    load_completion_manifest,
    load_currentization_manifest,
    load_json_file,
    load_perturbation_sweep,
)


FIXTURES = Path("tests/holonomy_memory/fixtures")
TOY_FLAT = Path("configs/benchmarks/toy_flat_signatures.json")
TOY_SUPPORT_MISMATCH = Path("configs/benchmarks/toy_support_mismatch.json")


def test_controls_public_imports_are_clean() -> None:
    assert InterfaceEvidenceSummary.__name__ == "InterfaceEvidenceSummary"
    assert ClassificationEvidence.__name__ == "ClassificationEvidence"


def test_smoke_baseline_still_passes() -> None:
    import holonomy_memory
    import sixbirds_event

    assert holonomy_memory.__version__ == "0.0.0"
    assert sixbirds_event.__version__ == "0.0.0"


def test_support_fixation_pass_and_fail_paths() -> None:
    base_package = load_route_transport_package(TOY_FLAT)
    same_support_package = load_route_transport_package(TOY_FLAT)
    mismatch_package = load_route_transport_package(TOY_SUPPORT_MISMATCH)

    same_support = check_support_fixation(base_package, same_support_package)
    mismatch = check_support_fixation(base_package, mismatch_package, same_support_required=True)

    assert same_support.status == AuditStatus.PASSED
    assert same_support.is_same_support is True
    assert mismatch.status == AuditStatus.FAILED
    assert mismatch.is_same_support is False
    assert mismatch.mismatch_reasons == (
        "visible support labels differ: ['A', 'B'] != ['A', 'C']",
    )


def test_currentization_hook_passes_and_support_precondition_fails() -> None:
    manifest = load_currentization_manifest(FIXTURES / "currentization_manifest_stub.json")
    base_summary = _summary(
        benchmark_id=manifest.base_benchmark_id,
        interface_id="mid",
        witness_count=2,
        discrepancy_value=Fraction(1, 2),
    )
    refined_summary = _summary(
        benchmark_id=manifest.refined_benchmark_id,
        interface_id="mid",
        witness_count=0,
        discrepancy_value=Fraction(0, 1),
    )
    passing_support = _support_check(AuditStatus.PASSED)
    failing_support = _support_check(AuditStatus.FAILED)

    passed = check_currentization(
        manifest,
        base_summary,
        refined_summary,
        support_check=passing_support,
    )
    failed = check_currentization(
        manifest,
        base_summary,
        refined_summary,
        support_check=failing_support,
    )

    assert passed.status == AuditStatus.PASSED
    assert passed.dissolved is True
    assert passed.reasons == ("refined evidence dissolved predictive residue",)
    assert failed.status == AuditStatus.FAILED
    assert failed.dissolved is False
    assert failed.reasons == ("support fixation precondition failed",)


def test_flattening_hook_passes_and_support_precondition_fails() -> None:
    manifest = load_completion_manifest(FIXTURES / "completion_manifest_stub.json")
    base_summary = _summary(
        benchmark_id=manifest.base_benchmark_id,
        interface_id="mid",
        witness_count=1,
        discrepancy_value=Fraction(1, 3),
    )
    completed_summary = _summary(
        benchmark_id=manifest.completed_benchmark_id,
        interface_id="mid",
        witness_count=0,
        discrepancy_value=Fraction(0, 1),
    )
    passing_support = _support_check(AuditStatus.PASSED)
    failing_support = _support_check(AuditStatus.FAILED)

    passed = check_flattening(
        manifest,
        base_summary,
        completed_summary,
        support_check=passing_support,
    )
    failed = check_flattening(
        manifest,
        base_summary,
        completed_summary,
        support_check=failing_support,
    )

    assert passed.status == AuditStatus.PASSED
    assert passed.collapsed is True
    assert passed.reasons == ("completed evidence collapsed predictive residue",)
    assert failed.status == AuditStatus.FAILED
    assert failed.collapsed is False
    assert failed.reasons == ("support fixation precondition failed",)


def test_perturbation_hooks_resolve_and_report_unresolved_targets() -> None:
    sweep = load_perturbation_sweep(FIXTURES / "perturbation_sweep_stub.json")
    valid_config_like = {
        "transport_package": load_json_file(FIXTURES / "route_transport_package_stub.json")
    }
    invalid_config_like = {
        "transport_package": {
            "event_packages": [{"events": [{"weights": {"visible_a": 1.0}}]}]
        }
    }

    resolutions = resolve_perturbation_targets(valid_config_like, sweep)
    unresolved = resolve_perturbation_targets(invalid_config_like, sweep)
    plan = build_perturbation_sweep_plan(valid_config_like, sweep)
    hook_result = evaluate_perturbation_hook(invalid_config_like, sweep)

    assert resolutions[0].resolved is True
    assert resolutions[0].resolved_location == (
        "transport_package.event_packages[0].events[1].weights.visible_b"
    )
    assert resolutions[0].resolved_type == "float"
    assert unresolved[0].resolved is False
    assert unresolved[0].reasons == ("target path segment not found: 1",)
    assert plan.trial_ids == (
        "perturbation_sweep_stub:trial:0",
        "perturbation_sweep_stub:trial:1",
        "perturbation_sweep_stub:trial:2",
    )
    assert plan.trial_seeds == (0, 1, 2)
    assert hook_result.status == AuditStatus.FAILED
    assert hook_result.unresolved_target_count == 1
    assert hook_result.reasons == ("no perturbation targets resolved",)


def test_classifier_exercises_every_allowed_label_and_rule_ordering() -> None:
    cases = {
        "artifact_trap": ClassificationEvidence(
            benchmark_id="benchmark",
            interface_id="mid",
            witness_count=2,
            discrepancy_metric_name=DiscrepancyMetricName.EXACT_MAX_ABS_FUTURE_GAP,
            discrepancy_metric_value=Fraction(1, 2),
            support_fixation_status=AuditStatus.PASSED,
            currentization_status=AuditStatus.PASSED,
            flattening_status=AuditStatus.PASSED,
            artifact_trap_flag=True,
            dissipative_flag=False,
        ),
        "flat": ClassificationEvidence(
            benchmark_id="benchmark",
            interface_id="mid",
            witness_count=0,
            discrepancy_metric_name=DiscrepancyMetricName.EXACT_MAX_ABS_FUTURE_GAP,
            discrepancy_metric_value=Fraction(0, 1),
            support_fixation_status=AuditStatus.PASSED,
            currentization_status=AuditStatus.INCONCLUSIVE,
            flattening_status=AuditStatus.INCONCLUSIVE,
            artifact_trap_flag=False,
            dissipative_flag=False,
        ),
        "flattenable": ClassificationEvidence(
            benchmark_id="benchmark",
            interface_id="mid",
            witness_count=1,
            discrepancy_metric_name=DiscrepancyMetricName.EXACT_MAX_ABS_FUTURE_GAP,
            discrepancy_metric_value=Fraction(1, 3),
            support_fixation_status=AuditStatus.PASSED,
            currentization_status=AuditStatus.INCONCLUSIVE,
            flattening_status=AuditStatus.PASSED,
            artifact_trap_flag=False,
            dissipative_flag=False,
        ),
        "explicit_latent": ClassificationEvidence(
            benchmark_id="benchmark",
            interface_id="mid",
            witness_count=1,
            discrepancy_metric_name=DiscrepancyMetricName.EXACT_MAX_ABS_FUTURE_GAP,
            discrepancy_metric_value=Fraction(1, 4),
            support_fixation_status=AuditStatus.PASSED,
            currentization_status=AuditStatus.PASSED,
            flattening_status=AuditStatus.INCONCLUSIVE,
            artifact_trap_flag=False,
            dissipative_flag=False,
        ),
        "dissipative": ClassificationEvidence(
            benchmark_id="benchmark",
            interface_id="mid",
            witness_count=1,
            discrepancy_metric_name=DiscrepancyMetricName.EXACT_MAX_ABS_FUTURE_GAP,
            discrepancy_metric_value=Fraction(1, 5),
            support_fixation_status=AuditStatus.PASSED,
            currentization_status=AuditStatus.INCONCLUSIVE,
            flattening_status=AuditStatus.INCONCLUSIVE,
            artifact_trap_flag=False,
            dissipative_flag=True,
        ),
        "coherent_candidate": ClassificationEvidence(
            benchmark_id="benchmark",
            interface_id="mid",
            witness_count=2,
            discrepancy_metric_name=DiscrepancyMetricName.EXACT_MAX_ABS_FUTURE_GAP,
            discrepancy_metric_value=Fraction(2, 5),
            support_fixation_status=AuditStatus.PASSED,
            currentization_status=AuditStatus.INCONCLUSIVE,
            flattening_status=AuditStatus.INCONCLUSIVE,
            artifact_trap_flag=False,
            dissipative_flag=False,
            predictive_loop_is_nontrivial=True,
        ),
    }

    results = {name: classify_regime(evidence) for name, evidence in cases.items()}

    assert results["artifact_trap"].class_label == ClassLabel.ARTIFACT_TRAP
    assert results["flat"].class_label == ClassLabel.FLAT
    assert results["flattenable"].class_label == ClassLabel.FLATTENABLE
    assert results["explicit_latent"].class_label == ClassLabel.EXPLICIT_LATENT
    assert results["dissipative"].class_label == ClassLabel.DISSIPATIVE
    assert results["coherent_candidate"].class_label == ClassLabel.COHERENT_CANDIDATE
    assert results["artifact_trap"].reasons == ("artifact_trap_flag is set",)


def _summary(
    *,
    benchmark_id: str,
    interface_id: str,
    witness_count: int,
    discrepancy_value: Fraction,
) -> InterfaceEvidenceSummary:
    return InterfaceEvidenceSummary(
        benchmark_id=benchmark_id,
        interface_id=interface_id,
        history_count=2,
        current_class_count=1,
        predictive_class_count=2 if witness_count else 1,
        witness_count=witness_count,
        max_fiber_size=2,
        discrepancy_metric_name=DiscrepancyMetricName.EXACT_MAX_ABS_FUTURE_GAP,
        discrepancy_metric_value=discrepancy_value,
        current_loop_is_trivial=True,
        predictive_loop_is_nontrivial=bool(witness_count),
    )


def _support_check(status: AuditStatus):
    return check_support_fixation(
        load_route_transport_package(TOY_FLAT),
        load_route_transport_package(TOY_FLAT),
        same_support_required=True,
    ) if status == AuditStatus.PASSED else check_support_fixation(
        load_route_transport_package(TOY_FLAT),
        load_route_transport_package(TOY_SUPPORT_MISMATCH),
        same_support_required=True,
    )
