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

export type AmountInterval = { lower: number; median: number; upper: number; currency: string };

export type V3Opportunity = {
  opportunity_id: string;
  entity_id: string;
  entity_name: string;
  sector: string;
  product: string;
  as_of: string;
  v2_rank: number | null;
  evidence_tier: EvidenceTier;
  decision_score: number;
  commercial_status: string;
  need: {
    positive_label_observed: boolean;
    labelled_positive_probability: number;
    product_need_probability: number;
    selection_constant: number;
    assumptions: string[];
    method: string;
  };
  shadow_wallet: {
    reconstruction_id: string;
    observed_bank_flow: number;
    total_wallet: AmountInterval;
    latent_external_wallet: AmountInterval;
    bank_share: AmountInterval;
    normalized_entropy: number;
    ensemble_draws: number;
    method: string;
    measurement_status: string;
    flows: Array<{
      edge_id: string;
      corridor: string;
      provider_node: string;
      amount: AmountInterval;
      observed_by_bank: boolean;
      claim_class: ClaimClass;
      provenance: string;
    }>;
  };
  change_point: {
    current_probability: number;
    recent_peak_probability: number;
    run_length_mode_months: number;
    signed_level_shift: number;
    probability_30d: number;
    probability_60d: number;
    probability_90d: number;
    calibration_status: string;
  };
  leakage: {
    alarm_probability: number;
    expected_external_flow_at_risk_zar: number;
    observed_level_decline: number;
    severity: string;
    reason_codes: string[];
    measurement_status: string;
  };
};

export type V3Fixture = {
  metadata: {
    title: string;
    version: string;
    as_of: string;
    central_idea: string;
    deployment_mode: string;
    watermark: string;
  };
  opportunities: V3Opportunity[];
  treasury_graphs: Record<string, {
    entity_id: string;
    treasury_complexity_index: number;
    measurement_status: string;
    gleif_resolution_status: string;
    nodes: Array<{ node_id: string; label: string; node_type: string }>;
    edges: Array<{ source: string; target: string; weight: number; claim_class: string; provenance: string }>;
  }>;
  action_portfolio: {
    capacity: number;
    expected_scenario_value_zar: number;
    downside_cvar_zar: number;
    commercial_status: string;
    causal_status: string;
    constraints: Record<string, number>;
    selected_actions: Array<{
      action_id: string;
      opportunity_id: string;
      entity_id: string;
      entity_name: string;
      sector: string;
      product: string;
      robust_score: number;
      expected_scenario_value_zar: number;
      downside_cvar_zar: number;
      need_probability: number;
      leakage_probability: number;
      evidence_tier: EvidenceTier;
    }>;
  };
  evidence_acquisition: {
    capacity: number;
    total_expected_net_voi_zar: number;
    policy: string;
    autonomous_external_retrieval: boolean;
    selected: Array<{
      candidate_id: string;
      opportunity_id: string;
      entity_id: string;
      product: string;
      evidence_type: string;
      expected_decision_value_zar: number;
      acquisition_cost_zar: number;
      latency_penalty_zar: number;
      net_value_of_information_zar: number;
      expected_interval_width_reduction: number;
      expected_rank_flip_probability: number;
      retrieve: boolean;
      required_approval: string;
    }>;
  };
  public_sensors: {
    ingestion_status: string;
    sensors: Array<{
      sensor_id: string;
      owner: string;
      official_url: string;
      dimensions: string[];
      v3_use: string;
      claim_boundary: string;
    }>;
  };
  validation: {
    opportunities: number;
    clients: number;
    shadow_flow_edges: number;
    max_mass_balance_error_zar: number;
    pu_labelled_positives: number;
    change_point_series: number;
    rm_actions_selected: number;
    positive_net_voi_requests: number;
    measured_competitor_share_claims: number;
    causal_value_claims: number;
  };
  release: {
    client_demo_status: string;
    bank_production_status: string;
    new_v3_capabilities: string[];
    blocking_external_gates: string[];
  };
};

export type V31PlanEntry = {
  rank: number;
  conversation_id: string;
  entity_id: string;
  entity_name: string;
  stakeholder_role: string;
  problem: string;
  problem_label: string;
  primary_solution: string;
  solution_label: string;
  family: string;
  why_now: string;
  client_value_median: number | null;
  client_value_status: string;
  bank_value_median: number | null;
  bank_value_status: string;
  selection_stability: number;
  frontier_state: string;
  eligibility: string;
  action: string;
  adjusted_benefit_expected: number;
  adjusted_benefit_cvar10: number;
};

export type V31ConversationSummary = {
  conversation_id: string;
  entity_id: string;
  entity_name: string;
  sector: string;
  stakeholder_role: string;
  problem: string;
  problem_label: string;
  primary_solution: string;
  supporting_solutions: string[];
  why_now: string;
  client_value_median: number | null;
  client_value_monetised: boolean;
  bank_value_median: number | null;
  bank_value_status: string;
  selection_stability: number;
  weekly_rank: number | null;
  client_frontier_member: boolean;
  portfolio_frontier_member: boolean;
  action: string;
  eligibility: string;
  evidence_tiers: EvidenceTier[];
  freshness_days: number;
  interval_width: number | null;
  assumption_load: number;
  calibration_status: string;
};

export type V31DecisionTwin = {
  metadata: {
    title: string;
    version: string;
    as_of: string;
    week_start: string;
    decision_object: string;
    central_idea: string;
    deployment_mode: string;
    watermark: string;
  };
  coverage_plan: {
    plan_id: string;
    capacity: number;
    above_the_fold: number;
    solver_status: string;
    degraded_fallback: boolean;
    expected_adjusted_benefit: number;
    cvar10_adjusted_benefit: number;
    commercial_status: string;
    causal_status: string;
    entries: V31PlanEntry[];
  };
  conversation_count: number;
  conversation_summaries: V31ConversationSummary[];
  client_index: Array<{
    entity_id: string;
    entity_name: string;
    sector: string;
    supported_domain_count: number;
    claim_count: number;
    approved_claim_count: number;
    evidence_gaps: number;
    change_digest_items: number;
  }>;
  evidence_coverage: {
    total_claims: number;
    total_gaps: number;
    approval_counts: Record<string, number>;
    all_clients_meet_claim_threshold: boolean;
    all_clients_meet_domain_threshold: boolean;
    all_clients_meet_e1_threshold: boolean;
    e1_threshold_status: string;
    e1_threshold_shortfall_clients: string[];
    tier_counts: Record<string, number>;
  };
  validation: Record<string, string | number | boolean | string[]>;
  release: {
    client_demo_status: string;
    bank_production_status: string;
    blocking_external_gates: string[];
    new_v31_capabilities: string[];
  };
  event_topics: Record<string, number>;
};

export type V31Conversation = {
  conversation_id: string;
  entity_id: string;
  entity_name: string;
  sector: string;
  as_of: string;
  week_start: string;
  stakeholder: {
    primary_role: string;
    secondary_roles: string[];
    ownership_rationale: string;
    requires_rm_confirmation: boolean;
    named_contact_status: string;
  };
  problem: {
    problem: string;
    label: string;
    intensity: IntervalEstimate;
    probability: number;
    calibration_status: string;
    supporting_evidence: string[];
    disconfirming_evidence: string[];
    reason_codes: string[];
  };
  solution_bundle: { primary: string; supporting: string[]; prerequisites: string[] };
  engagement_window: {
    trigger_name: string | null;
    trigger_supported: boolean;
    start_date: string;
    end_date: string;
    probability_30d: number;
    probability_60d: number;
    probability_90d: number;
    why_now: string;
    calibration_status: string;
  };
  client_value: {
    monetised_total: AmountInterval | null;
    non_monetised_dimensions: string[];
    assumptions: string[];
    watermark: string;
  };
  bank_value: {
    direct_contribution: AmountInterval | null;
    relationship_value_3y: AmountInterval | null;
    causal_incremental_value: null;
    status: string;
    causal_status: string;
    reason_codes: string[];
    watermark: string;
  };
  risk_and_feasibility: {
    blocked: boolean;
    material_unknowns: string[];
    permitted_action: string;
    friction_score: number;
    risk_score: number;
    feasibility_multiplier: number;
    required_confirmations: string[];
    banker_confirmation_notice: string;
    gates: Array<{ gate: string; status: string; required: boolean; reason: string }>;
  };
  pareto_status: {
    client_frontier_member: boolean;
    portfolio_frontier_member: boolean;
    client_frontier_probability: number;
    portfolio_frontier_probability: number;
    dominance_threshold: number;
  };
  policy_rank: {
    weekly_rank: number | null;
    selected: boolean;
    selection_stability: number;
    solver_status: string;
    reasons: string[];
  };
  next_best_question: null | {
    question_id: string;
    question_text: string;
    variable_label: string;
    net_voi_zar: number;
    scenario_draws: number;
    can_change_rank: boolean;
    can_change_bundle: boolean;
    can_change_feasibility: boolean;
    can_change_abstention: boolean;
  };
  why: string;
  how: string;
  what: string;
  evidence_tiers: EvidenceTier[];
  evidence_claim_ids: string[];
  eligibility: string;
  eligibility_reasons: string[];
  watermark: string;
};

export type V31Brief = {
  headline: string;
  why: string;
  how: string;
  what: string;
  client_value_statement: string;
  bank_value_statement: string;
  feasibility_statement: string;
  primary_question: string | null;
  citations: Array<{ claim_id: string; citation: string }>;
  missing_evidence: string[];
  abstentions: string[];
  prohibited_claims: string[];
  compiler: string;
  provider_used: string;
};

export type V31BusinessTwin = {
  entity_id: string;
  entity_name: string;
  sector: string;
  as_of: string;
  snapshot_version: string;
  claim_count: number;
  approved_claim_count: number;
  supported_domain_count: number;
  components: Array<{
    domain: string;
    label: string;
    status: string;
    claim_class: ClaimClass;
    evidence_tier: EvidenceTier;
    materiality: number;
    freshness_days: number;
    facts: Record<string, string | number | boolean | null>;
    missing_information: string[];
    decision_impacts: { problems: string[]; solutions: string[]; timing: string[] };
  }>;
  evidence_gaps: Array<{ domain: string; reason: string; acquisition_route: string; material: boolean }>;
  watermark: string;
};

export type V31Graph = {
  graph_id: string;
  entity_id: string;
  as_of: string;
  attribute_node_count: number;
  event_node_count: number;
  review_candidate_edges: number;
  measurement_status: string;
  identity_resolution_status: string;
  nodes: Array<{ node_id: string; label: string; node_type: string; layer: string; review_state: string }>;
  edges: Array<{ edge_id: string; source: string; target: string; edge_type: string; layer: string; approval_status: string }>;
  explanation_paths: Array<{ path_id: string; narrative: string; node_ids: string[] }>;
};

export type V31Digest = {
  digest_id: string;
  entity_id: string;
  since: string;
  as_of: string;
  no_change_statement: string | null;
  items: Array<{
    change_type: string;
    subject: string;
    before: string | null;
    after: string;
    decision_impact: string;
    materiality: number;
  }>;
};

export type V31FundingRoutes = {
  entity_id: string;
  as_of: string;
  requirement: AmountInterval | null;
  requirement_status: string;
  routes: Array<{ route: string; probability: number; score: number; drivers: Record<string, number> }>;
  missing_inputs: string[];
  model_status: string;
  challenger_status: string;
};

export type V31Fixture = {
  projection: V31DecisionTwin;
  conversations: Record<string, V31Conversation>;
  briefs: Record<string, V31Brief>;
  business_twins: Record<string, V31BusinessTwin>;
  business_graphs: Record<string, V31Graph>;
  change_digests: Record<string, V31Digest>;
  funding_routes: Record<string, V31FundingRoutes>;
};

export type WalletPortfolioCell = {
  opportunity_id: string;
  entity_id: string;
  entity_name: string;
  sector: string;
  product: string;
  product_quantity_semantics: string;
  as_of: string;
  observed_activity: Money;
  identification_bounds: IntervalEstimate;
  posterior_wallet: IntervalEstimate;
  share_interval: IntervalEstimate;
  target_share_scenario: number;
  contestable_activity: AmountInterval & { unit: string };
  scenario_contribution: (AmountInterval & { unit: string }) | null;
  timing: Opportunity["timing"];
  evidence_tier: EvidenceTier;
  approval_state: string;
  anchor_activation: string;
  calibration_status: string;
  share_claim_class: ClaimClass;
  commercial_claim_class: ClaimClass;
  rank: number | null;
  active_fact_ids: string[];
  pending_fact_ids: string[];
  permitted_action_now: string;
  conditional_action: string;
  artifact_versions: Opportunity["artifacts"] & { measurement_policy_version?: string | null };
};

export type WalletPortfolioProjection = {
  version: string;
  as_of: string;
  clients: number;
  products: string[];
  cells: WalletPortfolioCell[];
  product_summaries: Array<{
    product: string;
    cells: number;
    observed_activity_zar: number;
    scenario_contribution_zar: number;
    approved_anchor_cells: number;
    prior_led_cells: number;
  }>;
  top_opportunity_ids: string[];
  approved_anchor_cells: number;
  prior_led_cells: number;
  approved_source_facts: number;
  pending_source_facts: number;
  active_anchor_policy_version: string;
  measurement_policy_version: string;
  claim_boundary: Record<string, string>;
  release: { hackathon_status: string; bank_production_status: string; data_mode: string };
};

export type WalletOpportunityDetail = {
  cell: WalletPortfolioCell;
  equation: string;
  contestable_equation: string;
  explanation: {
    A: { value: number; unit: string; claim_class: ClaimClass };
    T: { p10: number; p50: number; p90: number; claim_class: ClaimClass };
    q: { p10: number; p50: number; p90: number; identity_check: boolean; declared_tolerance: string };
    q_star: { value: number; claim_class: ClaimClass };
    G: { p10: number; p50: number; p90: number; claim_class: ClaimClass };
  };
  supporting_facts: Array<Record<string, string | number | boolean | null>>;
  decision_twin_action: null | {
    conversation_id: string;
    stakeholder_role: string;
    problem: string;
    solution_bundle: string[];
    why_now: string;
    permitted_action: string;
    conditional_action: string;
  };
  claim_boundary: Record<string, string>;
};
