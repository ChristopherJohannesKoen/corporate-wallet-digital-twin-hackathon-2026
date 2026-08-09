-- Executed by a migration identity; runtime roles receive access only to their schema.
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA IF NOT EXISTS evidence;
CREATE SCHEMA IF NOT EXISTS economics;
CREATE SCHEMA IF NOT EXISTS experiment;
CREATE SCHEMA IF NOT EXISTS recommendation;
CREATE SCHEMA IF NOT EXISTS entitlement;

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
