export type EvidenceTier = "E0" | "E1" | "E2" | "E3" | "E4";
export type ClaimClass = "OBSERVED" | "IDENTIFIED_BOUND" | "POSTERIOR" | "SCENARIO" | "CAUSAL";
export type CalibrationStatus = "PRIOR_LED" | "PUBLICLY_ANCHORED" | "CLIENT_VALIDATED" | "EMPIRICALLY_CALIBRATED";

export type Money = {
  amount: string | number;
  currency: string;
  source_unit: string;
  normalized_amount: string | number;
  normalized_currency: string;
  fx_policy_ref: string | null;
};

export type IntervalEstimate = {
  lower: number;
  median: number;
  upper: number;
  nominal_coverage: number;
  model_version: string;
  as_of: string;
  claim_class: ClaimClass;
};

export type CommercialResult = {
  status: "BLOCKED" | "SIMULATED" | "APPROVED_SCENARIO" | "CAUSAL";
  observed_contribution: Money | null;
  contestable_scenario_contribution: Money | null;
  causal_expected_incremental_value: Money | null;
  net_unit_contribution_bps: number | null;
  target_share: number | null;
  watermark: string | null;
  reason_codes: string[];
  rate_card_ref: string | null;
};

export type Opportunity = {
  opportunity_id: string;
  entity_id: string;
  entity_name: string;
  sector: string;
  product: string;
  as_of: string;
  observed_activity: Money;
  identification_bounds: IntervalEstimate;
  posterior_wallet: IntervalEstimate;
  share_interval: IntervalEstimate;
  share_claim: ClaimClass;
  evidence_tier: EvidenceTier;
  calibration_status: CalibrationStatus;
  freshness_days: number;
  timing: {
    event_name: string;
    probability_30d: number;
    probability_60d: number;
    probability_90d: number;
    method: string;
    calibration_status: string;
    as_of: string;
  };
  commercial: CommercialResult;
  eligibility: { state: "BLOCKED" | "SHADOW_ONLY" | "ALLOWED"; reason_codes: string[]; evaluated_at: string };
  rank: number | null;
  rank_probability: number | null;
  evidence_fact_ids: string[];
  artifacts: {
    model_version: string;
    dataset_version: string;
    prior_version: string;
    transformation_version: string;
    rate_card_version: string | null;
    prompt_version: string | null;
    schema_version: string;
  };
};

export type ClientRecord = {
  entity_id: string;
  entity_name: string;
  sector: string;
  as_of: string;
  relationship_breadth: number;
  country_count: number;
  public_facts: PublicFact[];
  evidence_tier: EvidenceTier;
  active_public_anchors: number;
  competitor_activity_status: string;
  pricing_status: string;
  opportunity_ids: string[];
};

export type PublicFact = {
  fact_id: string;
  concept: string;
  value: number;
  currency: string;
  unit: string;
  period_end: string;
  available_date: string;
  source_title: string;
  source_url: string;
  page: string;
  audit_status: string;
};

export type ProductSensitivity = {
  first_rank_frequency: number;
  mean_top10_share: number;
  majority_dominance_frequency: number;
  absolute_economics: { p05: number; p50: number; p95: number };
};

export type ShadowFixture = {
  metadata: {
    version: string;
    as_of: string;
    deployment_mode: string;
    recommendations_visible_to_rm: boolean;
    recommendation_hypotheses_visible_to_demo_users?: boolean;
    source: string;
    watermark: string;
  };
  opportunities: Opportunity[];
  clients: Record<string, ClientRecord>;
  facts: Record<string, PublicFact>;
  sensitivity: {
    version: string;
    draws: number;
    product_summary: Record<string, ProductSensitivity>;
    portfolio_economics: { p05: number; p50: number; p95: number };
    value_of_information: { driver: string; absolute_rank_correlation: number }[];
  };
  legacy_sensitivity: Array<Record<string, unknown>>;
  evidence_coverage: {
    clients: number;
    e1_clients: number;
    e1_facts: number;
    approved_e1_facts: number;
    pending_sme_facts: number;
    e2_plus_economic_value_share: number;
    pilot_gate: number;
    pilot_ready: boolean;
  };
  benchmark_economics: {
    production_eligible: boolean;
    watermark: string;
    packs: Record<string, { portfolio_scenario_value_zar: number; top_product: string; target_share: number }>;
  };
  offline_validation: {
    global_watermark: string;
    synthetic_calibration: {
      comparisons: {
        e1_anchor_median_wallet_interval_narrowing: number;
        e1_anchor_coverage_preserved: boolean;
        selection_weighted_share_crps_improvement_vs_frozen_prior: number;
      };
      metrics: Record<string, { wallet_90_coverage: number }>;
      split_conformal_audit: {
        share: { conformal_coverage_90: number; conformal_scale_factor: number };
        wallet: { conformal_coverage_90: number; conformal_scale_factor: number };
      };
    };
    historical_validation: {
      rolling_origin_seasonal_naive: { nominal_90_interval_coverage: number };
      timing_surrogate: {
        qualified_rm_action_gate: { outcome_events: number; passed: boolean };
        start_stop_intervals: number;
        discrete_time_challenger: {
          brier_improvement: number;
          production_claim_allowed: boolean;
          promotion_gate: { surrogate_performance_pass: boolean; qualified_rm_outcomes_pass: boolean };
        };
      };
    };
  };
  genai_evaluation: {
    dataset_cases: number;
    governed_evaluation_checks: number;
    splits: Record<string, { candidate_precision: number; correct_abstention: number; prompt_injection_successes: number }>;
    page_grounding_replay: { official_documents: number; document_passes: number; facts: number; fact_passes: number; human_approvals_completed: number };
    release_gate: { passed: boolean; production_release_allowed: boolean; external_provider_results: Record<string, string> };
  };
  genai_provider_status: {
    selected_provider: string;
    providers: Record<string, { enabled: boolean; model_snapshot_configured: boolean; credential_configured: boolean }>;
  };
  shadow_replay: { events: number; recommendations_visible_to_rm: boolean; production_release_allowed: boolean };
  production_candidate: {
    status: string;
    scores: Record<string, { score: number; basis: string }>;
    machine_gates: Record<string, string | number | boolean>;
    non_delegable_gates: string[];
    production_release_allowed: boolean;
  };
  client_demo_data: {
    version: string;
    status: string;
    watermark: string;
    source_estate: {
      synbank_rows: number;
      audited_public_e1_facts: number;
      representative_trade_finance_rows: number;
      remote_federated_transaction_rows: number;
      finqa_numerical_reasoning_cases: number;
      named_client_competitor_observations: number;
    };
    representative_panel: { relationships: number; observations: number; products: number; production_e3_eligible: boolean };
    trial_analog: { eligible_opportunities: number; clusters: number; qualified_actions_30d: number; production_causal_claim_allowed: boolean };
    claim_boundary: { client_demo_ready: boolean; bank_production_ready: boolean; measured_share_label_allowed: boolean; causal_uplift_label_allowed: boolean };
  };
  client_demo_scorecard: {
    status: string;
    watermark: string;
    demo_capability_scores: Record<string, { score: number; basis: string }>;
    demo_gates: Record<string, boolean>;
    client_demo_release_allowed: boolean;
    bank_production_release_allowed: boolean;
  };
  production_target: {
    implementation_definitions_ready: boolean;
    controls_passed: number;
    controls_total: number;
    environment_state: Record<string, boolean>;
    bank_production_release_allowed: boolean;
  };
  public_evidence_qa: {
    documents: number;
    document_passes: number;
    facts: number;
    fact_passes: number;
    ready_for_finance_sme: number;
    human_approvals_completed: number;
  };
  trial_rehearsal: {
    event_records: number;
    production_claim_allowed: boolean;
    aa_diagnostic: { passes_no_mechanical_effect: boolean };
  };
  operational_rehearsal: {
    load: { latency_ms: { p95: number }; availability: number; production_slo_claim_allowed: boolean };
    entitlements: { pass_rate: number };
    recovery: { byte_identical: boolean };
    shadow_period: { clean_days: number; production_consecutive_shadow_days: number; production_gate_passed: boolean };
  };
  release: {
    status: string;
    client_demo_status?: string;
    bank_production_status?: string;
    shadow_days: number;
    blocking_gates: string[];
  };
};

export type OpportunityListResponse = {
  metadata: ShadowFixture["metadata"];
  count: number;
  items: Opportunity[];
  evidence_coverage: ShadowFixture["evidence_coverage"];
  release: ShadowFixture["release"];
};
