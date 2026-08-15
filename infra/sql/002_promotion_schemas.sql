-- V3.2 promotion schema.
--
-- The invariants that matter here are enforced in the database as well as in
-- Python. wallet_twin_v32 refuses to construct a synthetic real-track verdict,
-- but that only binds code paths that go through the contracts; a direct INSERT
-- would not. The CHECK constraints below close that gap, so the separation
-- survives an operator with a psql session.
--
-- Everything is append-only. A promotion position that can be edited in place
-- has no audit value: the question a reviewer asks is "what did we believe, and
-- when, and on what evidence", and an UPDATE destroys the answer.

CREATE SCHEMA IF NOT EXISTS promotion;

-- ---------------------------------------------------------------------------
-- Evidence offered in support of a gate.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS promotion.gate_evidence (
  evidence_id text PRIMARY KEY,
  gate_id text NOT NULL,
  mode text NOT NULL CHECK (mode IN (
    'NOT_AVAILABLE','SYNTHETIC_REHEARSAL','SIMULATED_POLICY',
    'PUBLIC_APPROVED','PUBLIC_PACKAGE','REAL_BANK','BANK_ATTESTED'
  )),
  artifact_uri text NOT NULL,
  content_sha256 char(64) NOT NULL,
  summary text NOT NULL,
  -- The four time fields, kept apart. as_of is the business date the evidence
  -- describes; generated_at is when it was computed; published_at is when it
  -- became visible; simulation_clock is virtual time and must be NULL unless
  -- the evidence is synthetic.
  as_of date NOT NULL,
  generated_at timestamptz NOT NULL,
  published_at timestamptz,
  simulation_clock timestamptz,
  expires_at timestamptz,
  produced_by text NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT evidence_published_after_generated
    CHECK (published_at IS NULL OR published_at >= generated_at),
  CONSTRAINT evidence_expires_after_generated
    CHECK (expires_at IS NULL OR expires_at > generated_at),
  -- Virtual time on real evidence would let a simulated day be read as an
  -- elapsed one.
  CONSTRAINT simulation_clock_only_on_synthetic_evidence
    CHECK (simulation_clock IS NULL OR mode IN ('SYNTHETIC_REHEARSAL','SIMULATED_POLICY'))
);

CREATE INDEX IF NOT EXISTS gate_evidence_gate_idx
  ON promotion.gate_evidence(gate_id, as_of DESC);

-- ---------------------------------------------------------------------------
-- DSSE envelopes. Signature material only; never private keys.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS promotion.evidence_envelope (
  envelope_id text PRIMARY KEY,
  evidence_id text NOT NULL REFERENCES promotion.gate_evidence(evidence_id),
  payload_type text NOT NULL,
  payload_sha256 char(64) NOT NULL,
  mode text NOT NULL CHECK (mode IN (
    'NOT_AVAILABLE','SYNTHETIC_REHEARSAL','SIMULATED_POLICY',
    'PUBLIC_APPROVED','PUBLIC_PACKAGE','REAL_BANK','BANK_ATTESTED'
  )),
  key_id text NOT NULL,
  trust_domain text NOT NULL,
  signature_algorithm text NOT NULL,
  signature text,
  signature_status text NOT NULL DEFAULT 'UNSIGNED',
  signed_at timestamptz,
  expires_at timestamptz,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  -- A rehearsal trust domain cannot carry bank authority. This is the same
  -- refusal TrustedKey.__post_init__ makes, restated where a direct INSERT
  -- would otherwise bypass it.
  CONSTRAINT rehearsal_domain_cannot_sign_real_evidence
    CHECK (trust_domain <> 'rehearsal' OR mode IN ('SYNTHETIC_REHEARSAL','SIMULATED_POLICY')),
  CONSTRAINT signature_status_matches_signature
    CHECK (
      (signature IS NULL AND signature_status = 'UNSIGNED')
      OR (signature IS NOT NULL AND signature_status <> 'UNSIGNED')
    )
);

-- ---------------------------------------------------------------------------
-- Gate evaluations. One gate, one track, one verdict, append-only.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS promotion.gate_evaluation (
  evaluation_id uuid PRIMARY KEY,
  gate_id text NOT NULL,
  transition_id text NOT NULL,
  track text NOT NULL CHECK (track IN ('REAL','REHEARSAL')),
  outcome text NOT NULL CHECK (outcome IN (
    'PASS','FAIL','UNKNOWN','NOT_REQUIRED','WAIVED'
  )),
  evidence_mode text CHECK (evidence_mode IN (
    'NOT_AVAILABLE','SYNTHETIC_REHEARSAL','SIMULATED_POLICY',
    'PUBLIC_APPROVED','PUBLIC_PACKAGE','REAL_BANK','BANK_ATTESTED'
  )),
  evidence_ids text[] NOT NULL DEFAULT '{}',
  envelope_ids text[] NOT NULL DEFAULT '{}',
  measured_value double precision,
  threshold text,
  reason_codes text[] NOT NULL DEFAULT '{}',
  failure_injection_verified boolean NOT NULL DEFAULT false,
  waived_by text,
  waiver_rationale text,
  evaluated_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  -- The central invariant of the entire twin, restated at the storage layer.
  CONSTRAINT synthetic_evidence_cannot_support_a_real_verdict
    CHECK (
      track <> 'REAL'
      OR evidence_mode NOT IN ('SYNTHETIC_REHEARSAL','SIMULATED_POLICY','NOT_AVAILABLE')
    ),
  -- A PASS with no evidence is an assertion, not an evaluation.
  CONSTRAINT pass_requires_evidence
    CHECK (
      outcome <> 'PASS'
      OR (evidence_mode IS NOT NULL AND array_length(evidence_ids, 1) >= 1)
    ),
  -- An anonymous waiver is unauditable.
  CONSTRAINT waiver_requires_named_approver
    CHECK ((outcome = 'WAIVED') = (waived_by IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS gate_evaluation_latest_idx
  ON promotion.gate_evaluation(gate_id, track, evaluated_at DESC);

-- ---------------------------------------------------------------------------
-- Four-eyes approval of a promotion.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS promotion.promotion_approval (
  approval_id text PRIMARY KEY,
  decision_id text NOT NULL,
  decision_payload_sha256 char(64) NOT NULL
    CHECK (decision_payload_sha256 ~ '^[0-9a-f]{64}$'),
  transition_id text NOT NULL,
  track text NOT NULL CHECK (track IN ('REAL','REHEARSAL')),
  submitted_by text NOT NULL,
  submitted_role text NOT NULL,
  reviewed_by text NOT NULL,
  reviewed_role text NOT NULL,
  decision text NOT NULL CHECK (decision IN ('APPROVED','REJECTED')),
  rationale text NOT NULL,
  submitted_at timestamptz NOT NULL,
  reviewed_at timestamptz NOT NULL,
  reason_codes text[] NOT NULL DEFAULT '{}',
  recorded_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT four_eyes_submitter_cannot_review
    CHECK (submitted_by <> reviewed_by),
  CONSTRAINT four_eyes_roles_must_differ
    CHECK (submitted_role <> reviewed_role),
  CONSTRAINT review_follows_submission
    CHECK (reviewed_at >= submitted_at)
);

-- ---------------------------------------------------------------------------
-- Published promotion positions. Append-only history, not current state.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS promotion.promotion_decision (
  decision_id text PRIMARY KEY,
  decision_payload_sha256 char(64) NOT NULL
    CHECK (decision_payload_sha256 ~ '^[0-9a-f]{64}$'),
  signed_envelope jsonb NOT NULL,
  signature_verified boolean NOT NULL,
  signer_key_id text NOT NULL,
  trust_domain text NOT NULL,
  as_of date NOT NULL,
  generated_at timestamptz NOT NULL,
  published_at timestamptz,
  real_state text NOT NULL CHECK (real_state IN (
    'OFFLINE_CANDIDATE','SHADOW_READY','PILOT_READY','SCALE_READY','CAUSAL_CHAMPION'
  )),
  rehearsed_state text NOT NULL CHECK (rehearsed_state IN (
    'OFFLINE_CANDIDATE','SHADOW_READY','PILOT_READY','SCALE_READY','CAUSAL_CHAMPION'
  )),
  bank_shadow_authorized boolean NOT NULL,
  passed_real_transitions text[] NOT NULL DEFAULT '{}',
  passed_rehearsal_transitions text[] NOT NULL DEFAULT '{}',
  granted_capabilities text[] NOT NULL DEFAULT '{}',
  promotion_machinery_readiness double precision NOT NULL
    CHECK (promotion_machinery_readiness BETWEEN 0 AND 1),
  bank_evidence_readiness double precision NOT NULL
    CHECK (bank_evidence_readiness BETWEEN 0 AND 1),
  synthetic_weight_excluded_from_ber double precision NOT NULL DEFAULT 0,
  state_machine_version text NOT NULL,
  contracts_version text NOT NULL,
  reason_codes text[] NOT NULL DEFAULT '{}',
  recorded_at timestamptz NOT NULL DEFAULT now(),
  -- Authorisation cannot precede the state that confers it.
  CONSTRAINT authorisation_follows_the_real_state
    CHECK (
      bank_shadow_authorized = false
      OR real_state IN ('SHADOW_READY','PILOT_READY','SCALE_READY','CAUSAL_CHAMPION')
    )
  -- Deliberately absent: any column holding a single composite promotability
  -- figure. PMR and BER are stored separately so a working rehearsal can never
  -- be read as bank readiness.
);

CREATE INDEX IF NOT EXISTS promotion_decision_as_of_idx
  ON promotion.promotion_decision(as_of DESC, generated_at DESC);

CREATE TABLE IF NOT EXISTS promotion.promotion_transition (
  transition_record_id uuid PRIMARY KEY,
  transition_id text NOT NULL,
  target_state text NOT NULL,
  decision_id text NOT NULL REFERENCES promotion.promotion_decision(decision_id),
  track text NOT NULL CHECK (track IN ('REAL','REHEARSAL')),
  request_idempotency_key text NOT NULL UNIQUE,
  requested_by text NOT NULL,
  approval_ids text[] NOT NULL DEFAULT '{}',
  recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS promotion.trust_key_cache (
  cache_record_id uuid PRIMARY KEY,
  key_id text NOT NULL,
  trust_domain text NOT NULL,
  allowed_modes text[] NOT NULL,
  allowed_environments text[] NOT NULL,
  owner_roles text[] NOT NULL,
  approver_roles text[] NOT NULL,
  valid_from timestamptz NOT NULL,
  valid_to timestamptz,
  revoked_at timestamptz,
  registry_hash char(64) NOT NULL,
  observed_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Rehearsal clock. Constrained so a rehearsal can never record a bank day.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS promotion.rehearsal_clock (
  clock_id text NOT NULL,
  observed_at timestamptz NOT NULL DEFAULT now(),
  simulation_clock timestamptz NOT NULL,
  rehearsal_days_elapsed integer NOT NULL CHECK (rehearsal_days_elapsed >= 0),
  consecutive_clean_rehearsal_days integer NOT NULL
    CHECK (consecutive_clean_rehearsal_days >= 0),
  elapsed_bank_shadow_days integer NOT NULL DEFAULT 0,
  incidents_injected integer NOT NULL DEFAULT 0,
  last_reset_reason text,
  PRIMARY KEY (clock_id, observed_at),
  CONSTRAINT clean_days_within_simulated_days
    CHECK (consecutive_clean_rehearsal_days <= rehearsal_days_elapsed),
  -- The single most load-bearing constraint in this file. A simulated day is
  -- not a bank day, and the gate that needs thirty elapsed bank days reads
  -- this column.
  CONSTRAINT a_rehearsal_records_no_bank_days
    CHECK (elapsed_bank_shadow_days = 0)
);

CREATE TABLE IF NOT EXISTS promotion.rehearsal_run (
  run_id text PRIMARY KEY,
  scenario_id text NOT NULL,
  status text NOT NULL CHECK (status IN ('CREATED','RUNNING','PASSED','FAILED')),
  started_at timestamptz NOT NULL,
  completed_at timestamptz,
  scenario_hash char(64) NOT NULL,
  signer_key_id text NOT NULL,
  idempotency_key text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS promotion.rehearsal_day (
  run_id text NOT NULL REFERENCES promotion.rehearsal_run(run_id),
  simulation_day integer NOT NULL,
  simulation_clock timestamptz NOT NULL,
  clean boolean NOT NULL,
  checks jsonb NOT NULL,
  day_result_hash char(64) NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, simulation_day)
);

CREATE TABLE IF NOT EXISTS promotion.rehearsal_incident (
  incident_id text PRIMARY KEY,
  run_id text NOT NULL REFERENCES promotion.rehearsal_run(run_id),
  simulation_day integer NOT NULL,
  incident_type text NOT NULL,
  severity text NOT NULL,
  reset_required boolean NOT NULL,
  payload jsonb NOT NULL,
  injected_at timestamptz NOT NULL,
  idempotency_key text NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- Promotion outbox. Separate from the decision_intelligence outbox because the
-- promotion service owns its own persistence and never writes another
-- service's tables.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS promotion.transactional_event_outbox (
  event_id uuid PRIMARY KEY,
  domain_topic text NOT NULL CHECK (domain_topic = 'wallet-twin.promotion.v1'),
  event_type text NOT NULL,
  schema_version text NOT NULL,
  track text NOT NULL CHECK (track IN ('REAL','REHEARSAL')),
  aggregate_id text NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  payload jsonb NOT NULL,
  occurred_at timestamptz NOT NULL,
  published_at timestamptz,
  -- Simulated scenarios did not happen at the bank.
  CONSTRAINT rehearsal_only_events_stay_on_the_rehearsal_track
    CHECK (
      event_type NOT IN ('RehearsalScenarioExecuted','RehearsalIncidentInjected')
      OR track = 'REHEARSAL'
    )
);

CREATE INDEX IF NOT EXISTS promotion_outbox_unpublished_idx
  ON promotion.transactional_event_outbox(occurred_at)
  WHERE published_at IS NULL;

-- ---------------------------------------------------------------------------
-- Append-only enforcement. Revoking UPDATE and DELETE is what makes the
-- "append-only" claim a property of the database rather than a convention.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION promotion.refuse_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION
    'promotion.% is append-only; % is refused. Supersede the row with a new '
    'evaluation or decision instead, so the earlier position stays auditable.',
    TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
  target text;
BEGIN
  FOREACH target IN ARRAY ARRAY[
    'gate_evidence','evidence_envelope','gate_evaluation',
    'promotion_approval','promotion_decision','promotion_transition',
    'trust_key_cache','rehearsal_clock','rehearsal_run',
    'rehearsal_day','rehearsal_incident'
  ] LOOP
    EXECUTE format(
      'DROP TRIGGER IF EXISTS %I_append_only ON promotion.%I',
      target, target
    );
    EXECUTE format(
      'CREATE TRIGGER %I_append_only BEFORE UPDATE OR DELETE ON promotion.%I '
      'FOR EACH ROW EXECUTE FUNCTION promotion.refuse_mutation()',
      target, target
    );
  END LOOP;
END $$;
