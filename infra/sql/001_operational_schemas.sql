-- Executed by a migration identity; runtime roles receive access only to their schema.
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA IF NOT EXISTS evidence;
CREATE SCHEMA IF NOT EXISTS economics;
CREATE SCHEMA IF NOT EXISTS experiment;
CREATE SCHEMA IF NOT EXISTS recommendation;
CREATE SCHEMA IF NOT EXISTS entitlement;
CREATE SCHEMA IF NOT EXISTS decision_intelligence;
CREATE SCHEMA IF NOT EXISTS business_twin;
CREATE SCHEMA IF NOT EXISTS client_learning;

CREATE TABLE IF NOT EXISTS evidence.fact_workflow (
  fact_id uuid PRIMARY KEY,
  source_hash char(64) NOT NULL,
  candidate jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('DRAFT','PENDING_REVIEW','APPROVED','REJECTED','EXPIRED')),
  reviewer_ids text[] NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS economics.rate_card (
  rate_card_id uuid NOT NULL,
  version text NOT NULL,
  product text NOT NULL,
  payload jsonb NOT NULL,
  effective_from date NOT NULL,
  effective_to date,
  approval_status text NOT NULL,
  reconciled boolean NOT NULL DEFAULT false,
  PRIMARY KEY (rate_card_id, version),
  EXCLUDE USING gist (product WITH =, daterange(effective_from, effective_to, '[]') WITH &&)
);

CREATE TABLE IF NOT EXISTS experiment.assignment (
  assignment_id uuid PRIMARY KEY,
  opportunity_id text NOT NULL,
  cluster_id text NOT NULL,
  arm text NOT NULL,
  assignment_probability numeric(9,8) NOT NULL CHECK (assignment_probability > 0 AND assignment_probability <= 1),
  assigned_at timestamptz NOT NULL,
  artifact_versions jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment.outcome (
  event_id uuid PRIMARY KEY,
  opportunity_id text NOT NULL,
  outcome_code text NOT NULL,
  outcome_at timestamptz NOT NULL,
  censor_date date,
  payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment.pilot_session (
  session_id uuid PRIMARY KEY,
  rm_id_hash char(64) NOT NULL,
  team_id text NOT NULL,
  consent_reference_hash char(64) NOT NULL,
  task_ids text[] NOT NULL,
  started_at timestamptz NOT NULL,
  completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS experiment.pilot_feedback (
  feedback_id uuid PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES experiment.pilot_session(session_id),
  task_id text NOT NULL,
  completed boolean NOT NULL,
  verification_seconds integer NOT NULL CHECK (verification_seconds BETWEEN 0 AND 7200),
  actionability smallint NOT NULL CHECK (actionability BETWEEN 1 AND 5),
  comprehension smallint NOT NULL CHECK (comprehension BETWEEN 1 AND 5),
  omission_found boolean NOT NULL,
  overridden boolean NOT NULL,
  notes text NOT NULL,
  recorded_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment.event_outbox (
  event_id uuid PRIMARY KEY,
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  occurred_at timestamptz NOT NULL,
  published_at timestamptz
);

CREATE INDEX IF NOT EXISTS event_outbox_unpublished_idx
  ON experiment.event_outbox(occurred_at) WHERE published_at IS NULL;

CREATE TABLE IF NOT EXISTS recommendation.interaction (
  event_id uuid PRIMARY KEY,
  opportunity_id text NOT NULL,
  user_id_hash char(64) NOT NULL,
  event_type text NOT NULL,
  occurred_at timestamptz NOT NULL,
  payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS entitlement.access_decision (
  decision_id uuid PRIMARY KEY,
  occurred_at timestamptz NOT NULL,
  user_id_hash char(64) NOT NULL,
  client_id text,
  action text NOT NULL,
  allowed boolean NOT NULL,
  reason_codes text[] NOT NULL,
  policy_version text NOT NULL
);

-- V3 operational state is immutable by version. Analytical values remain in
-- Delta; these tables coordinate workflow, approvals and event publication.
CREATE TABLE IF NOT EXISTS decision_intelligence.reconstruction_run (
  reconstruction_id uuid PRIMARY KEY,
  as_of date NOT NULL,
  model_version text NOT NULL,
  transport_policy_version text NOT NULL,
  source_snapshot_hash char(64) NOT NULL,
  status text NOT NULL CHECK (status IN ('STARTED','COMPLETED','FAILED','QUARANTINED')),
  diagnostics jsonb NOT NULL,
  entitlement_domain text NOT NULL,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (as_of, model_version, source_snapshot_hash)
);

CREATE TABLE IF NOT EXISTS decision_intelligence.signal_publication (
  publication_id uuid PRIMARY KEY,
  reconstruction_id uuid NOT NULL REFERENCES decision_intelligence.reconstruction_run(reconstruction_id),
  opportunity_id text NOT NULL,
  signal_type text NOT NULL CHECK (signal_type IN ('LEAKAGE','CHANGE_POINT','PRODUCT_NEED','TREASURY_GRAPH')),
  artifact_version text NOT NULL,
  measurement_status text NOT NULL CHECK (measurement_status IN ('OBSERVED','IDENTIFIED_BOUND','POSTERIOR','SCENARIO')),
  payload jsonb NOT NULL,
  published_at timestamptz NOT NULL,
  UNIQUE (opportunity_id, signal_type, artifact_version)
);

CREATE TABLE IF NOT EXISTS decision_intelligence.portfolio_selection (
  selection_id uuid PRIMARY KEY,
  as_of date NOT NULL,
  policy_version text NOT NULL,
  scenario_snapshot_hash char(64) NOT NULL,
  cvar_alpha numeric(9,8) NOT NULL CHECK (cvar_alpha > 0 AND cvar_alpha < 1),
  capacity_limit integer NOT NULL CHECK (capacity_limit > 0),
  selected_opportunity_ids text[] NOT NULL,
  constraint_diagnostics jsonb NOT NULL,
  approval_status text NOT NULL CHECK (approval_status IN ('DRAFT','PENDING_REVIEW','APPROVED','REJECTED','EXPIRED')),
  approved_by_hash char(64),
  selected_at timestamptz NOT NULL,
  UNIQUE (as_of, policy_version, scenario_snapshot_hash)
);

CREATE TABLE IF NOT EXISTS decision_intelligence.evidence_acquisition_approval (
  approval_id uuid PRIMARY KEY,
  plan_id text NOT NULL,
  candidate_id text NOT NULL,
  policy_version text NOT NULL,
  expected_net_voi numeric(38,9) NOT NULL,
  decision text NOT NULL CHECK (decision IN ('APPROVED','REJECTED','DEFERRED')),
  decision_reason text NOT NULL,
  reviewer_id_hash char(64) NOT NULL,
  decided_at timestamptz NOT NULL,
  UNIQUE (plan_id, candidate_id, policy_version)
);

CREATE TABLE IF NOT EXISTS decision_intelligence.brief_compilation (
  compilation_id uuid PRIMARY KEY,
  opportunity_id text NOT NULL,
  template_version text NOT NULL,
  evidence_pack_hash char(64) NOT NULL,
  output_hash char(64) NOT NULL,
  claim_classes text[] NOT NULL,
  numeric_preservation_passed boolean NOT NULL,
  citation_precision_passed boolean NOT NULL,
  provider_used text NOT NULL,
  status text NOT NULL CHECK (status IN ('COMPILED','REJECTED','FALLBACK')),
  compiled_at timestamptz NOT NULL,
  UNIQUE (opportunity_id, template_version, evidence_pack_hash)
);

-- V3.1 workflow state. Analytical projections remain in Delta; PostgreSQL owns
-- only transactions, reviews, publication state and the event outbox.
CREATE TABLE IF NOT EXISTS business_twin.snapshot_publication (
  publication_id uuid PRIMARY KEY,
  snapshot_id text NOT NULL UNIQUE,
  as_of date NOT NULL,
  source_snapshot_hash char(64) NOT NULL,
  state text NOT NULL CHECK (state IN ('DRAFT','VALIDATED','PUBLISHED','REJECTED','ROLLED_BACK')),
  validation_report jsonb NOT NULL,
  promoted_atomically_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS business_twin.business_claim_review_task (
  task_id uuid PRIMARY KEY,
  claim_id text NOT NULL,
  client_id text NOT NULL,
  materiality text NOT NULL,
  status text NOT NULL CHECK (status IN ('PENDING_REVIEW','APPROVED','REJECTED','EXPIRED')),
  reviewer_ids_hash char(64)[] NOT NULL DEFAULT '{}',
  reviewer_lineage jsonb NOT NULL,
  opened_at timestamptz NOT NULL,
  completed_at timestamptz,
  UNIQUE (claim_id, status)
);

CREATE TABLE IF NOT EXISTS recommendation.coverage_plan_state (
  plan_id text PRIMARY KEY,
  as_of date NOT NULL,
  week_start date NOT NULL,
  selected_conversation_ids text[] NOT NULL,
  solver_status text NOT NULL,
  policy_version text NOT NULL,
  scenario_snapshot_hash char(64) NOT NULL,
  state text NOT NULL CHECK (state IN ('DRAFT','PUBLISHED','SUPERSEDED','ROLLED_BACK')),
  published_at timestamptz
);

CREATE TABLE IF NOT EXISTS recommendation.feasibility_attestation (
  attestation_id uuid PRIMARY KEY,
  conversation_id text NOT NULL,
  client_id text NOT NULL,
  gate text NOT NULL,
  status text NOT NULL CHECK (status IN ('PASS','FAIL','NOT_REQUIRED')),
  reason text NOT NULL,
  attested_by_role text NOT NULL,
  attested_by_hash char(64) NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  attested_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS client_learning.client_answer_review (
  answer_id uuid PRIMARY KEY,
  question_id text NOT NULL,
  conversation_id text NOT NULL,
  client_id text NOT NULL,
  response jsonb NOT NULL,
  respondent_hash char(64) NOT NULL,
  consent_reference_hash char(64) NOT NULL,
  scope text NOT NULL,
  status text NOT NULL CHECK (status IN ('PENDING_REVIEW','APPROVED','REJECTED','EXPIRED')),
  reviewer_lineage jsonb NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  submitted_at timestamptz NOT NULL,
  reviewed_at timestamptz
);

CREATE TABLE IF NOT EXISTS decision_intelligence.transactional_event_outbox (
  event_id uuid PRIMARY KEY,
  domain_topic text NOT NULL CHECK (domain_topic IN (
    'wallet-twin.business-twin.v1','wallet-twin.decision.v1',
    'wallet-twin.client-learning.v1','wallet-twin.audit.v1'
  )),
  event_type text NOT NULL,
  schema_version text NOT NULL,
  aggregate_id text NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  payload jsonb NOT NULL,
  occurred_at timestamptz NOT NULL,
  published_at timestamptz
);

CREATE INDEX IF NOT EXISTS v31_event_outbox_unpublished_idx
  ON decision_intelligence.transactional_event_outbox(occurred_at)
  WHERE published_at IS NULL;
