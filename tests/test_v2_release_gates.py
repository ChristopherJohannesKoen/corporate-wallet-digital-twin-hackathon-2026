from wallet_twin_v2.release_gates import ReleaseMetrics, ShadowReleaseGate


def _passing_metrics(**overrides):
    values = dict(
        point_in_time_violations=0,
        critical_reconciliation_rate=1.0,
        interval_coverage_90=0.9,
        crps_improvement=0.11,
        production_economics_approved_rate=1.0,
        genai_schema_compliance=1.0,
        genai_critical_fact_accuracy=1.0,
        genai_candidate_precision=0.99,
        genai_abstention_accuracy=0.98,
        genai_numeric_preservation=1.0,
        genai_unsupported_critical_claims=0,
        prompt_injection_successes=0,
        entitlement_negative_test_pass_rate=1.0,
        unresolved_high_critical_vulnerabilities=0,
        availability=0.999,
        p95_read_latency_ms=749,
        event_latency_seconds=299,
        refresh_completion_hour_sast=6.0,
        unresolved_sev1_sev2=0,
        consecutive_shadow_days=30,
    )
    values.update(overrides)
    return ReleaseMetrics(**values)


def test_all_shadow_gates_must_pass_for_promotion():
    gate = ShadowReleaseGate()
    assert gate.promotable(gate.evaluate(_passing_metrics())) is True
    failed = gate.evaluate(_passing_metrics(unresolved_high_critical_vulnerabilities=1))
    assert gate.promotable(failed) is False
    assert next(result for result in failed if result.gate_id == "vulnerabilities").passed is False
