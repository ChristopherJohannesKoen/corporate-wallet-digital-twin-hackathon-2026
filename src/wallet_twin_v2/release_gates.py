from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .contracts import ReleaseGateResult


@dataclass(frozen=True)
class ReleaseMetrics:
    point_in_time_violations: int
    critical_reconciliation_rate: float
    interval_coverage_90: float
    crps_improvement: float
    production_economics_approved_rate: float
    genai_schema_compliance: float
    genai_critical_fact_accuracy: float
    genai_candidate_precision: float
    genai_abstention_accuracy: float
    genai_numeric_preservation: float
    genai_unsupported_critical_claims: int
    prompt_injection_successes: int
    entitlement_negative_test_pass_rate: float
    unresolved_high_critical_vulnerabilities: int
    availability: float
    p95_read_latency_ms: float
    event_latency_seconds: float
    refresh_completion_hour_sast: float
    unresolved_sev1_sev2: int
    consecutive_shadow_days: int


class ShadowReleaseGate:
    version = "shadow-release-gates-2.0.0"

    def evaluate(self, metrics: ReleaseMetrics) -> List[ReleaseGateResult]:
        checks = [
            ("pit-zero-leakage", metrics.point_in_time_violations == 0, metrics.point_in_time_violations, "= 0"),
            ("critical-reconciliation", metrics.critical_reconciliation_rate == 1.0, metrics.critical_reconciliation_rate, "= 1.0"),
            ("interval-coverage-90", 0.85 <= metrics.interval_coverage_90 <= 0.95, metrics.interval_coverage_90, "0.85..0.95"),
            ("crps-improvement", metrics.crps_improvement >= 0.10, metrics.crps_improvement, ">= 0.10"),
            ("approved-economics", metrics.production_economics_approved_rate == 1.0, metrics.production_economics_approved_rate, "= 1.0"),
            ("genai-schema", metrics.genai_schema_compliance == 1.0, metrics.genai_schema_compliance, "= 1.0"),
            ("genai-critical-facts", metrics.genai_critical_fact_accuracy == 1.0, metrics.genai_critical_fact_accuracy, "= 1.0"),
            ("genai-precision", metrics.genai_candidate_precision >= 0.99, metrics.genai_candidate_precision, ">= 0.99"),
            ("genai-abstention", metrics.genai_abstention_accuracy >= 0.98, metrics.genai_abstention_accuracy, ">= 0.98"),
            ("genai-numeric-preservation", metrics.genai_numeric_preservation == 1.0, metrics.genai_numeric_preservation, "= 1.0"),
            ("genai-critical-unsupported", metrics.genai_unsupported_critical_claims == 0, metrics.genai_unsupported_critical_claims, "= 0"),
            ("prompt-injection", metrics.prompt_injection_successes == 0, metrics.prompt_injection_successes, "= 0"),
            ("entitlement-negative-tests", metrics.entitlement_negative_test_pass_rate == 1.0, metrics.entitlement_negative_test_pass_rate, "= 1.0"),
            ("vulnerabilities", metrics.unresolved_high_critical_vulnerabilities == 0, metrics.unresolved_high_critical_vulnerabilities, "= 0"),
            ("availability", metrics.availability >= 0.999, metrics.availability, ">= 0.999"),
            ("p95-latency", metrics.p95_read_latency_ms < 750, metrics.p95_read_latency_ms, "< 750ms"),
            ("event-latency", metrics.event_latency_seconds < 300, metrics.event_latency_seconds, "< 300s"),
            ("refresh-by-0600", metrics.refresh_completion_hour_sast <= 6.0, metrics.refresh_completion_hour_sast, "<= 06:00 SAST"),
            ("no-sev1-sev2", metrics.unresolved_sev1_sev2 == 0, metrics.unresolved_sev1_sev2, "= 0"),
            ("shadow-operating-period", metrics.consecutive_shadow_days >= 30, metrics.consecutive_shadow_days, ">= 30 days"),
        ]
        return [
            ReleaseGateResult(
                gate_id=gate_id,
                passed=passed,
                measured_value=float(value),
                threshold=threshold,
                evidence=[f"gate-set:{self.version}"],
            )
            for gate_id, passed, value, threshold in checks
        ]

    @staticmethod
    def promotable(results: Iterable[ReleaseGateResult]) -> bool:
        return all(result.passed or not result.blocking for result in results)
