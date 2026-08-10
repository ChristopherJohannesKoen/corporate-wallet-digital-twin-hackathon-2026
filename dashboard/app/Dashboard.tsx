"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  Opportunity,
  OpportunityListResponse,
  ProductSensitivity,
  PublicFact,
  ShadowFixture,
  V3Fixture,
} from "@/lib/contracts";

type View = "Decision lab" | "Evidence twin" | "Models & gates";
type Explanation = {
  opportunity: Opportunity;
  facts: PublicFact[];
  missing_evidence: string[];
  narrative_mode: string;
};
type SensitivityResponse = {
  global: {
    draws: number;
    version: string;
    product_summary: Record<string, ProductSensitivity>;
    portfolio_economics: { p05: number; p50: number; p95: number };
    value_of_information: { driver: string; absolute_rank_correlation: number }[];
  };
  legacy_grid: Array<Record<string, unknown>>;
  benchmark_economics: ShadowFixture["benchmark_economics"];
  offline_validation: ShadowFixture["offline_validation"];
  genai_evaluation: ShadowFixture["genai_evaluation"];
  genai_provider_status: ShadowFixture["genai_provider_status"];
  shadow_replay: ShadowFixture["shadow_replay"];
  production_candidate: ShadowFixture["production_candidate"];
  public_evidence_qa: ShadowFixture["public_evidence_qa"];
  trial_rehearsal: ShadowFixture["trial_rehearsal"];
  operational_rehearsal: ShadowFixture["operational_rehearsal"];
  client_demo_data: ShadowFixture["client_demo_data"];
  client_demo_scorecard: ShadowFixture["client_demo_scorecard"];
  production_target: ShadowFixture["production_target"];
};

const PRODUCTS = ["All products", "Collections", "Payments", "Liquidity", "Cross-border FX", "Trade finance"];

function amount(value: number | string | null | undefined): number {
  return value == null ? 0 : Number(value);
}

function money(value: number | string | null | undefined, digits = 1): string {
  const numeric = amount(value);
  const absolute = Math.abs(numeric);
  if (absolute >= 1e9) return `R${(numeric / 1e9).toFixed(digits)}bn`;
  if (absolute >= 1e6) return `R${(numeric / 1e6).toFixed(digits)}m`;
  if (absolute >= 1e3) return `R${(numeric / 1e3).toFixed(digits)}k`;
  return `R${numeric.toFixed(0)}`;
}

function pct(value: number | null | undefined, digits = 0): string {
  return `${((value ?? 0) * 100).toFixed(digits)}%`;
}

function title(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function Pill({ tone = "neutral", children }: { tone?: string; children: React.ReactNode }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function Stat({ label, value, note, tone = "blue" }: { label: string; value: string; note: string; tone?: string }) {
  return (
    <article className={`stat stat-${tone}`}>
      <div className="stat-top"><span>{label}</span><i /></div>
      <strong>{value}</strong>
      <p>{note}</p>
    </article>
  );
}

function LayerCard({
  order,
  label,
  value,
  note,
  claim,
  state = "ready",
}: {
  order: string;
  label: string;
  value: string;
  note: string;
  claim: string;
  state?: "ready" | "blocked";
}) {
  return (
    <article className={`layer-card ${state === "blocked" ? "layer-blocked" : ""}`}>
      <span className="layer-order">{order}</span>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <small>{note}</small>
      </div>
      <Pill tone={state === "blocked" ? "blocked" : claim.toLowerCase().replaceAll(" ", "-")}>{claim}</Pill>
    </article>
  );
}

function Range({ interval, observed }: { interval: Opportunity["posterior_wallet"]; observed: number }) {
  const max = Math.max(interval.upper, observed, 1);
  const left = interval.lower / max * 100;
  const width = Math.max(2, (interval.upper - interval.lower) / max * 100);
  const median = interval.median / max * 100;
  const observedAt = observed / max * 100;
  return (
    <div className="range" aria-label={`90 percent interval ${money(interval.lower)} to ${money(interval.upper)}`}>
      <div className="range-track">
        <span className="range-band" style={{ left: `${left}%`, width: `${width}%` }} />
        <i className="range-mid" style={{ left: `${median}%` }} />
        <i className="range-observed" style={{ left: `${observedAt}%` }} />
      </div>
      <div className="range-label"><span>{money(interval.lower)}</span><b>{money(interval.median)} posterior</b><span>{money(interval.upper)}</span></div>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return <div className="empty-state"><span>—</span><p>{message}</p></div>;
}

export default function Dashboard({ viewer, asOf }: { viewer: string; asOf: string }) {
  const [view, setView] = useState<View>("Decision lab");
  const [portfolio, setPortfolio] = useState<OpportunityListResponse | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityResponse | null>(null);
  const [v3, setV3] = useState<V3Fixture | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [product, setProduct] = useState("All products");
  const [evidence, setEvidence] = useState("All evidence");
  const [targetShare, setTargetShare] = useState(40);
  const [scenarioValue, setScenarioValue] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch(`/api/v1/opportunities?as_of=${asOf}`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Client-demo API returned ${response.status}`);
        return response.json() as Promise<OpportunityListResponse>;
      })
      .then((data) => {
        if (!active) return;
        setPortfolio(data);
        setSelectedId(data.items[0]?.opportunity_id ?? "");
      })
      .catch((reason: Error) => active && setError(reason.message))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [asOf]);

  useEffect(() => {
    if (!selectedId) return;
    fetch(`/api/v1/opportunities/${encodeURIComponent(selectedId)}/explanation?as_of=${asOf}`, { cache: "no-store" })
      .then((response) => response.json())
      .then((data: Explanation) => setExplanation(data));
  }, [selectedId, asOf]);

  useEffect(() => {
    if (view !== "Models & gates" || sensitivity) return;
    fetch(`/api/v1/sensitivity?as_of=${asOf}`, { cache: "no-store" })
      .then((response) => response.json())
      .then((data: SensitivityResponse) => setSensitivity(data));
  }, [view, sensitivity, asOf]);

  useEffect(() => {
    if (view !== "Decision lab" || v3) return;
    fetch(`/api/v3/decision-lab?as_of=${asOf}`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(`V3 decision API returned ${response.status}`);
        return response.json() as Promise<V3Fixture>;
      })
      .then((data) => setV3(data))
      .catch((reason: Error) => setError(reason.message));
  }, [view, v3, asOf]);

  const visible = useMemo(() => {
    if (!portfolio) return [];
    return portfolio.items.filter((item) =>
      (product === "All products" || item.product === product)
      && (evidence === "All evidence" || item.evidence_tier === evidence),
    );
  }, [portfolio, product, evidence]);

  const selected = portfolio?.items.find((item) => item.opportunity_id === selectedId) ?? portfolio?.items[0];
  const selectedV3 = v3?.opportunities.find((item) => item.opportunity_id === selectedId) ?? v3?.opportunities[0];
  const publiclyAnchoredCount = portfolio?.items.filter((item) => item.calibration_status === "PUBLICLY_ANCHORED").length ?? 0;

  async function evaluateScenario() {
    if (!selected) return;
    const response = await fetch("/api/v1/scenarios/evaluate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ opportunity_id: selected.opportunity_id, as_of: asOf, target_share: targetShare / 100 }),
    });
    const data = await response.json() as { contestable_scenario_contribution?: { normalized_amount: number | string } };
    setScenarioValue(amount(data.contestable_scenario_contribution?.normalized_amount));
  }

  function openTwin(id: string) {
    setScenarioValue(null);
    setSelectedId(id);
    setView("Evidence twin");
  }

  function selectTwin(id: string) {
    setScenarioValue(null);
    setSelectedId(id);
  }

  if (loading) return <div className="loading"><i /><p>Loading governed point-in-time snapshot…</p></div>;
  if (error || !portfolio) return <div className="loading error"><b>Client-demo platform unavailable</b><p>{error || "No portfolio response"}</p></div>;

  return (
    <div className="app-shell">
      <header className="masthead">
        <div className="brand">
          <span className="brand-mark"><i /><i /><i /></span>
          <div><b>Corporate Wallet</b><small>Digital Twin · V3</small></div>
        </div>
        <div className="environment">
          <Pill tone="demo">Client demo</Pill>
          <span>As of <b>{asOf}</b></span>
          <span className="viewer">{viewer}</span>
        </div>
      </header>

      <div className="shadow-ribbon demo-ribbon">
        <span>CLIENT DEMONSTRATION</span>
        <p>Decision-support hypotheses are visible for demonstration; data provenance remains explicit at every layer.</p>
        <b>{portfolio.metadata.watermark}</b>
      </div>

      <nav className="primary-nav" aria-label="V3 workbench views">
        {(["Decision lab", "Evidence twin", "Models & gates"] as View[]).map((item) => (
          <button key={item} className={view === item ? "active" : ""} onClick={() => setView(item)}>
            <span>{item === "Decision lab" ? "01" : item === "Evidence twin" ? "02" : "03"}</span>{item}
          </button>
        ))}
      </nav>

      {view === "Decision lab" && (
        <main>
          <section className="intro">
            <div>
              <p className="kicker">Latent corporate financial system</p>
              <h1>Reconstruct what is unseen.<br /><em>Decide what matters next.</em></h1>
            </div>
            <div className="intro-copy">
              <p>{v3?.metadata.central_idea ?? "Loading the governed V3 decision layer."}</p>
              <div><span className="pulse" />Entropy reconstruction · BOCPD · robust portfolio · decision-directed RAG</div>
            </div>
          </section>

          <section className="stats-grid">
            <Stat label="Shadow network" value={v3 ? v3.validation.shadow_flow_edges.toLocaleString() : "—"} note="anonymous corridor × provider edges; exact mass balance" />
            <Stat label="RM capacity plan" value={v3 ? `${v3.action_portfolio.selected_actions.length}/${v3.action_portfolio.capacity}` : "—"} note="CVaR-aware actions under client, sector and product caps" tone="cyan" />
            <Stat label="Downside portfolio" value={v3 ? money(v3.action_portfolio.downside_cvar_zar) : "—"} note="representative lower-tail scenario value; not causal" tone="amber" />
            <Stat label="Evidence queue" value={v3 ? String(v3.evidence_acquisition.selected.length) : "—"} note="positive-net-VOI requests; no autonomous retrieval" tone="cyan" />
          </section>

          {v3 && selectedV3 ? (
            <>
              <section className="v3-grid">
                <article className="panel latent-panel">
                  <div className="panel-head">
                    <div><p className="kicker">Entropy-constrained shadow wallet</p><h2>{selectedV3.entity_name} · {selectedV3.product}</h2></div>
                    <Pill tone="scenario">Reconstructed</Pill>
                  </div>
                  <select className="v3-select" value={selectedV3.opportunity_id} onChange={(event) => selectTwin(event.target.value)}>
                    {v3.opportunities.map((item) => <option key={item.opportunity_id} value={item.opportunity_id}>{item.entity_name} · {item.product}</option>)}
                  </select>
                  <div className="v3-kpis">
                    <div><span>Observed Syn Bank</span><b>{money(selectedV3.shadow_wallet.observed_bank_flow)}</b></div>
                    <div><span>Latent external median</span><b>{money(selectedV3.shadow_wallet.latent_external_wallet.median)}</b></div>
                    <div><span>Inferred bank share</span><b>{pct(selectedV3.shadow_wallet.bank_share.median, 1)}</b></div>
                    <div><span>Network entropy</span><b>{pct(selectedV3.shadow_wallet.normalized_entropy, 1)}</b></div>
                  </div>
                  <div className="shadow-flows">
                    {selectedV3.shadow_wallet.flows.slice().sort((a, b) => b.amount.median - a.amount.median).slice(0, 8).map((flow) => (
                      <div key={flow.edge_id}>
                        <span>{flow.corridor}<small>{flow.provider_node}</small></span>
                        <i><em style={{ width: pct(flow.amount.median / Math.max(selectedV3.shadow_wallet.latent_external_wallet.median, 1)) }} /></i>
                        <b>{money(flow.amount.median)}</b>
                      </div>
                    ))}
                  </div>
                  <footer className="panel-foot"><span>256-member ensemble</span><p>Anonymous providers only. No edge is measured competitor activity.</p></footer>
                </article>

                <aside className="v3-signals">
                  <article className="panel signal-card"><p className="kicker">PU product need</p><strong>{pct(selectedV3.need.product_need_probability, 1)}</strong><span>SCAR-corrected probability</span><p>Known positives + unlabelled relationships; 33 transparent fixture positives.</p></article>
                  <article className="panel signal-card"><p className="kicker">Wallet leakage alarm</p><strong>{pct(selectedV3.leakage.alarm_probability, 1)}</strong><span>{selectedV3.leakage.severity} · modelled signal</span><p>{pct(selectedV3.leakage.observed_level_decline, 1)} observed level decline; {money(selectedV3.leakage.expected_external_flow_at_risk_zar)} scenario flow at risk.</p></article>
                  <article className="panel signal-card"><p className="kicker">Change-point horizon</p><strong>{pct(selectedV3.change_point.probability_90d, 1)}</strong><span>90-day event probability</span><p>Run-length mode {selectedV3.change_point.run_length_mode_months} months; representative replay, not RM-outcome calibrated.</p></article>
                </aside>
              </section>

              <section className="panel v3-actions">
                <div className="panel-head"><div><p className="kicker">Robust decision-focused optimization</p><h2>RM attention portfolio</h2></div><Pill tone="scenario">CVaR constrained</Pill></div>
                <div className="table-wrap"><table><thead><tr><th>#</th><th>Client / action</th><th>Need</th><th>Leakage</th><th>Expected scenario</th><th>Downside CVaR</th><th>Evidence</th></tr></thead><tbody>
                  {v3.action_portfolio.selected_actions.map((action, index) => <tr key={action.action_id}>
                    <td><span className="rank">{String(index + 1).padStart(2, "0")}</span></td><td><b>{action.entity_name}</b><small>{action.product} · {title(action.sector)}</small></td>
                    <td>{pct(action.need_probability, 1)}</td><td>{pct(action.leakage_probability, 1)}</td><td><b>{money(action.expected_scenario_value_zar)}</b><small>representative</small></td><td>{money(action.downside_cvar_zar)}</td><td><Pill tone={action.evidence_tier.toLowerCase()}>{action.evidence_tier}</Pill></td>
                  </tr>)}</tbody></table></div>
                <footer className="panel-foot"><span>{v3.action_portfolio.causal_status.replaceAll("_", " ")}</span><p>At most one action per client, four per product and four per sector.</p></footer>
              </section>

              <section className="v3-lower">
                <article className="panel voi-panel">
                  <div className="panel-head"><div><p className="kicker">Decision-directed evidence</p><h2>Retrieve only when information can change the decision</h2></div><Pill tone="posterior">Positive net VOI</Pill></div>
                  {v3.evidence_acquisition.selected.map((item) => <div className="voi-row" key={item.candidate_id}>
                    <div><b>{item.evidence_type}</b><span>{item.entity_id} · {item.product}</span></div><strong>{money(item.net_value_of_information_zar)}</strong><small>{pct(item.expected_interval_width_reduction)} width reduction · {item.required_approval}</small>
                  </div>)}
                  <footer className="panel-foot"><span>Autonomous retrieval disabled</span><p>{v3.evidence_acquisition.policy}</p></footer>
                </article>
                <aside className="panel sensor-panel">
                  <div className="panel-head"><div><p className="kicker">Registered public sensors</p><h2>Point-in-time priors</h2></div><Pill tone="blocked">Not connected</Pill></div>
                  {v3.public_sensors.sensors.map((sensor) => <a key={sensor.sensor_id} href={sensor.official_url} target="_blank" rel="noreferrer"><b>{sensor.owner}</b><span>{sensor.v3_use}</span><small>{sensor.claim_boundary}</small></a>)}
                </aside>
              </section>
            </>
          ) : <section className="panel"><EmptyState message="Loading the V3 point-in-time decision projection…" /></section>}

          <section className="panel control-panel">
            <div className="panel-head">
              <div><p className="kicker">Point-in-time opportunity projection</p><h2>Client-demo hypothesis register</h2></div>
              <div className="filters">
                <select aria-label="Product filter" value={product} onChange={(event) => setProduct(event.target.value)}>
                  {PRODUCTS.map((item) => <option key={item}>{item}</option>)}
                </select>
                <select aria-label="Evidence filter" value={evidence} onChange={(event) => setEvidence(event.target.value)}>
                  {["All evidence", "E0", "E1", "E2", "E3", "E4"].map((item) => <option key={item}>{item}</option>)}
                </select>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Rank</th><th>Client / product</th><th>Evidence</th><th>Observed</th><th>Identified set</th><th>Posterior wallet</th><th>90-day event</th><th>Economics</th><th /></tr></thead>
                <tbody>{visible.slice(0, 30).map((item) => (
                  <tr key={item.opportunity_id}>
                    <td><span className="rank">{String(item.rank ?? "–").padStart(2, "0")}</span></td>
                    <td><b>{item.entity_name}</b><small>{item.product} · {title(item.sector)}</small></td>
                    <td><Pill tone={item.evidence_tier.toLowerCase()}>{item.evidence_tier}</Pill><small>{title(item.calibration_status)}</small></td>
                    <td>{money(item.observed_activity.normalized_amount)}</td>
                    <td><b>{money(item.identification_bounds.lower)}–{money(item.identification_bounds.upper)}</b><small>not probabilistic</small></td>
                    <td><b>{money(item.posterior_wallet.median)}</b><small>90% {money(item.posterior_wallet.lower)}–{money(item.posterior_wallet.upper)}</small></td>
                    <td><div className="prob"><span style={{ width: pct(item.timing.probability_90d) }} /></div><small>{pct(item.timing.probability_90d)} baseline</small></td>
                    <td><Pill tone="simulated">Simulated</Pill><small>{item.commercial.causal_expected_incremental_value ? "causal" : "no causal value"}</small></td>
                    <td><button className="open-button" onClick={() => openTwin(item.opportunity_id)}>Inspect</button></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <footer className="panel-foot"><span>{visible.length} visible hypotheses</span><p>Rank is a representative demo scenario. It is not a measured competitor share, win probability, uplift estimate or financial recommendation.</p></footer>
          </section>

          <section className="control-band">
            <div><span>Evidence state</span><b>{publiclyAnchoredCount}/100 publicly anchored</b><p>All 20 clients have E1 coverage; competitor share is never labelled measured.</p></div>
            <div><span>Economics state</span><b>Scenario-ready</b><p>Three representative packs remain separate from bank-approved pricing.</p></div>
            <div><span>Simulation estate</span><b>9.4m+ reference rows</b><p>3.06m SynBank rows, 10k African trade rows and a 6.36m-row federated scale reference.</p></div>
            <div><span>Release state</span><b>Demo ready</b><p>Bank production remains fail-closed until accountable external gates pass.</p></div>
          </section>
        </main>
      )}

      {view === "Evidence twin" && selected && (
        <main>
          <section className="twin-heading">
            <div>
              <p className="kicker">Client × product × as-of</p>
              <select value={selectedId} onChange={(event) => selectTwin(event.target.value)}>
                {portfolio.items.map((item) => <option key={item.opportunity_id} value={item.opportunity_id}>{item.entity_name} · {item.product}</option>)}
              </select>
              <div className="twin-meta"><Pill tone={selected.evidence_tier.toLowerCase()}>{selected.evidence_tier}</Pill><span>{title(selected.calibration_status)}</span><span>Freshness {selected.freshness_days} days</span><span>Model {selected.artifacts.model_version}</span></div>
            </div>
            <aside><span>Recommendation state</span><b>Demo hypothesis</b><p>{selected.eligibility.reason_codes.map(title).join(" · ")}</p></aside>
          </section>

          <section className="layer-stack">
            <div className="section-label"><span>Five-layer interpretation contract</span><p>Each layer answers a different question. None may be relabelled as another.</p></div>
            <LayerCard order="01" label="Observed in SynBank simulation" value={money(selected.observed_activity.normalized_amount)} note="Activity observed inside the supplied simulation; not an actual bank relationship record." claim="Observed" />
            <LayerCard order="02" label="Assumption-light identified set" value={`${money(selected.identification_bounds.lower)} – ${money(selected.identification_bounds.upper)}`} note="Capacity/accounting constraints; not a probability interval." claim="Identified bound" />
            <LayerCard order="03" label="Model-based posterior" value={`${money(selected.posterior_wallet.median)} median`} note={`90% interval ${money(selected.posterior_wallet.lower)} – ${money(selected.posterior_wallet.upper)}.`} claim="Posterior" />
            <LayerCard order="04" label="Contestable contribution scenario" value={selected.commercial.contestable_scenario_contribution ? money(selected.commercial.contestable_scenario_contribution.normalized_amount) : "Withheld"} note="Representative rate-card scenario; never presented as booked or bank-approved value." claim="Scenario" />
            <LayerCard order="05" label="Causal expected incremental value" value="Withheld" note="Requires randomized assignment, outcomes, overlap and independent validation." claim="Blocked" state="blocked" />
          </section>

          <section className="twin-layout">
            <article className="panel wallet-detail">
              <div className="panel-head"><div><p className="kicker">Wallet distribution</p><h2>Posterior remains visibly uncertain</h2></div><Pill tone="posterior">90% interval</Pill></div>
              <div className="wallet-kpis">
                <div><span>Observed</span><b>{money(selected.observed_activity.normalized_amount)}</b></div>
                <div><span>Share median</span><b>{pct(selected.share_interval.median)}</b><small>{selected.share_claim === "OBSERVED" ? "measured" : "inferred"}</small></div>
                <div><span>Posterior median</span><b>{money(selected.posterior_wallet.median)}</b></div>
              </div>
              <Range interval={selected.posterior_wallet} observed={amount(selected.observed_activity.normalized_amount)} />
              <div className="equation"><code>A = qT</code><p>The bank observes A. q and T remain jointly unidentified without external wallet evidence; the identified set and posterior therefore stay separate.</p></div>
            </article>

            <aside className="panel scenario-lab">
              <p className="kicker">Governed scenario endpoint</p><h3>Evaluate—not optimize</h3>
              <label><span>Target share</span><b>{targetShare}%</b><input type="range" min="20" max="60" value={targetShare} onChange={(event) => setTargetShare(Number(event.target.value))} /></label>
              <button onClick={evaluateScenario}>Evaluate demo scenario</button>
              <div className="scenario-result"><span>Contestable contribution</span><b>{scenarioValue == null ? "Not evaluated" : money(scenarioValue)}</b><small>CLIENT-DEMO SCENARIO · NOT BANK-APPROVED PRICING</small></div>
              <p>No target is called optimal; no causal win probability exists.</p>
            </aside>
          </section>

          <section className="evidence-layout">
            <article className="panel evidence-panel">
              <div className="panel-head"><div><p className="kicker">Governed evidence projection</p><h2>{explanation?.facts.length ?? 0} cited facts supporting this product</h2></div><Pill tone={selected.evidence_tier.toLowerCase()}>{selected.evidence_tier}</Pill></div>
              {explanation?.facts.length ? (
                <div className="facts">
                  {explanation.facts.map((fact) => (
                    <a key={fact.fact_id} href={fact.source_url} target="_blank" rel="noreferrer">
                      <span>{title(fact.concept)}</span><b>{fact.currency} {Number(fact.value).toLocaleString()} {fact.unit}</b><small>{fact.source_title} · p.{fact.page} · available {fact.available_date}</small>
                    </a>
                  ))}
                </div>
              ) : <EmptyState message="No product-specific audited fact is available. The estimate is governed-prior-led." />}
            </article>
            <article className="panel missing-panel">
              <p className="kicker">Decision blockers</p><h3>Evidence still required</h3>
              <ul>{(explanation?.missing_evidence ?? ["E3 multibank observation", "approved bank economics", "causal outcome history"]).map((item) => <li key={item}><i />{item}</li>)}</ul>
              <div><span>Claim compiler</span><b>{explanation?.narrative_mode ?? "deterministic"}</b><p>No unrestricted retrieval, tools, client communication or database writes.</p></div>
            </article>
          </section>
        </main>
      )}

      {view === "Models & gates" && (
        <main>
          <section className="model-hero">
            <div><p className="kicker">Two-track release truth</p><h1>Demo what works.<br /><em>Block what is unproven.</em></h1></div>
            <div className="release-stack">
              <div className="gate-score demo-ready"><span>Client demonstration</span><b>READY</b><p>11/11 governed demo gates pass</p></div>
              <div className="gate-score"><span>Bank production</span><b>NOT PROMOTABLE</b><p>External approvals and live bank operation required</p></div>
            </div>
          </section>

          <section className="gate-grid">
            <article className="panel gate-list">
              <div className="panel-head"><div><p className="kicker">Blocking release gates</p><h2>Promotion remains fail-closed</h2></div><Pill tone="blocked">{portfolio.release.blocking_gates.length} open</Pill></div>
              {portfolio.release.blocking_gates.map((gate, index) => (
                <div className="gate-row" key={gate}><span>{String(index + 1).padStart(2, "0")}</span><b>{title(gate)}</b><Pill tone="blocked">Blocked</Pill></div>
              ))}
              <div className="gate-note">Passing code tests does not satisfy bank-data, model-validation, security-review or operating-history gates.</div>
            </article>

            <article className="panel architecture-card">
              <p className="kicker">Production target</p><h3>AWS + Databricks control plane</h3>
              <div className="architecture-flow">
                <span>Private EKS services</span><i>→</i><span>Delta + Unity Catalog</span><i>→</i><span>MLflow registry</span><i>→</i><span>Entitled workbench</span>
              </div>
              <ul><li>Object-locked evidence and snapshots</li><li>MSK recommendation and outcome events</li><li>OPA gateway policy plus Unity Catalog ABAC</li><li>OpenTelemetry into the approved SIEM</li></ul>
              {sensitivity?.production_target && <p className="architecture-proof">{sensitivity.production_target.controls_passed}/{sensitivity.production_target.controls_total} deployment control definitions verified · environment apply awaits bank accounts</p>}
            </article>
          </section>

          {sensitivity?.client_demo_scorecard && (
            <section className="panel candidate-panel demo-candidate">
              <div className="panel-head">
                <div><p className="kicker">Governed client-demo maturity</p><h2>Demonstration release scorecard</h2></div>
                <Pill tone="ready">Client demo ready</Pill>
              </div>
              <div className="candidate-scores">
                {Object.entries(sensitivity.client_demo_scorecard.demo_capability_scores).map(([area, result]) => (
                  <article key={area}>
                    <div><span>{title(area)}</span><b>{result.score.toFixed(1)}<small>/10</small></b></div>
                    <i><span style={{ width: `${result.score * 10}%` }} /></i>
                    <p>{result.basis}</p>
                  </article>
                ))}
              </div>
              <div className="machine-gates demo-estate">
                <div><span>SynBank source rows</span><b>{sensitivity.client_demo_data.source_estate.synbank_rows.toLocaleString()}</b><small>supplied banking simulation</small></div>
                <div><span>Representative wallet analog</span><b>{sensitivity.client_demo_data.representative_panel.observations.toLocaleString()}</b><small>300 peers · five products · known truth</small></div>
                <div><span>Audited E1 facts</span><b>{sensitivity.client_demo_data.source_estate.audited_public_e1_facts}</b><small>all 20 showcase clients</small></div>
                <div><span>African trade reference</span><b>{sensitivity.client_demo_data.source_estate.representative_trade_finance_rows.toLocaleString()}</b><small>pinned CC-BY-4.0 scenario rows</small></div>
                <div><span>FinQA reasoning benchmark</span><b>{sensitivity.client_demo_data.source_estate.finqa_numerical_reasoning_cases.toLocaleString()}</b><small>pinned public QA cases · evaluation only</small></div>
                <div><span>GenAI governed checks</span><b>{sensitivity.genai_evaluation.governed_evaluation_checks}</b><small>including 640-case stress suite</small></div>
                <div><span>Production controls as code</span><b>{sensitivity.production_target.controls_passed}/{sensitivity.production_target.controls_total}</b><small>definitions ready · environment not fabricated</small></div>
              </div>
              <footer className="panel-foot"><span>Claim boundary</span><p>Ready for an informed client demonstration. Representative and simulated records remain visibly distinct from direct E3 multibank observations, approved pricing and causal outcomes.</p></footer>
            </section>
          )}

          {sensitivity?.production_candidate?.scores && (
            <section className="panel candidate-panel">
              <div className="panel-head">
                <div><p className="kicker">Measured offline maturity</p><h2>Production-candidate scorecard</h2></div>
                <Pill tone="simulated">Bank gates remain open</Pill>
              </div>
              <div className="candidate-scores">
                {Object.entries(sensitivity.production_candidate.scores).map(([area, result]) => (
                  <article key={area}>
                    <div><span>{title(area)}</span><b>{result.score.toFixed(1)}<small>/10</small></b></div>
                    <i><span style={{ width: `${result.score * 10}%` }} /></i>
                    <p>{result.basis}</p>
                  </article>
                ))}
              </div>
              <div className="machine-gates">
                <div><span>Page-grounded E1</span><b>{sensitivity.public_evidence_qa.fact_passes}/{sensitivity.public_evidence_qa.facts}</b><small>51 await human approval</small></div>
                <div><span>Conformal wallet coverage</span><b>{pct(sensitivity.offline_validation.synthetic_calibration.split_conformal_audit.wallet.conformal_coverage_90, 1)}</b><small>synthetic known-truth holdout</small></div>
                <div><span>Timing Brier improvement</span><b>{pct(sensitivity.offline_validation.historical_validation.timing_surrogate.discrete_time_challenger.brier_improvement, 1)}</b><small>surrogate challenger only</small></div>
                <div><span>GenAI governed checks</span><b>{sensitivity.genai_evaluation.governed_evaluation_checks}</b><small>live providers not executed</small></div>
                <div><span>Local API P95</span><b>{sensitivity.operational_rehearsal.load.latency_ms.p95.toFixed(0)} ms</b><small>in-process rehearsal, not an SLO</small></div>
                <div><span>Negative entitlement tests</span><b>{pct(sensitivity.operational_rehearsal.entitlements.pass_rate)}</b><small>cross-role/client/economics denials</small></div>
              </div>
              <footer className="panel-foot"><span>Release truth</span><p>This is the strongest evidence-supported offline build. Only bank data, approvals, live-provider adjudication, banker participation and elapsed shadow operation can close the remaining production gates.</p></footer>
            </section>
          )}

          <section className="panel sensitivity-panel">
            <div className="panel-head">
              <div><p className="kicker">Correlated global sensitivity</p><h2>{sensitivity ? sensitivity.global.draws.toLocaleString() : "10,000"} Latin-hypercube draws</h2></div>
              <Pill tone="posterior">No encoded winner</Pill>
            </div>
            {sensitivity ? (
              <>
                <div className="sensitivity-grid">
                  {Object.entries(sensitivity.global.product_summary).map(([name, result]) => (
                    <article key={name} className={name === "Trade finance" ? "highlight" : ""}>
                      <span>{name}</span>
                      <b>{pct(result.first_rank_frequency, 1)}</b>
                      <small>first-ranked frequency</small>
                      <div><em>Top-10 {pct(result.mean_top10_share, 1)}</em><em>Majority {pct(result.majority_dominance_frequency, 1)}</em></div>
                    </article>
                  ))}
                </div>
                <div className="voi">
                  <span>Highest value-of-information drivers</span>
                  {sensitivity.global.value_of_information.slice(0, 4).map((item) => (
                    <div key={item.driver}><b>{title(item.driver)}</b><i><span style={{ width: pct(item.absolute_rank_correlation) }} /></i><em>{item.absolute_rank_correlation.toFixed(2)}</em></div>
                  ))}
                </div>
              </>
            ) : <EmptyState message="Loading global sensitivity artefact…" />}
          </section>

          {sensitivity && (
            <>
              <section className="section-label"><span>Offline validation evidence</span><p>{sensitivity.offline_validation.global_watermark}</p></section>
              <section className="governance-grid">
                <article>
                  <span>Known-truth calibration</span>
                  <b>{pct(sensitivity.offline_validation.synthetic_calibration.split_conformal_audit.wallet.conformal_coverage_90, 1)} conformal coverage</b>
                  <p>{pct(sensitivity.offline_validation.synthetic_calibration.comparisons.e1_anchor_median_wallet_interval_narrowing, 1)} narrower after E1 anchors; entity-disjoint synthetic mechanics only.</p>
                </article>
                <article>
                  <span>Timing validation</span>
                  <b>{pct(sensitivity.offline_validation.historical_validation.timing_surrogate.discrete_time_challenger.brier_improvement, 1)} Brier improvement</b>
                  <p>{sensitivity.offline_validation.historical_validation.timing_surrogate.start_stop_intervals.toLocaleString()} surrogate intervals; {sensitivity.offline_validation.historical_validation.timing_surrogate.qualified_rm_action_gate.outcome_events} valid RM-action outcomes.</p>
                </article>
                <article>
                  <span>GenAI golden set</span>
                  <b>{sensitivity.genai_evaluation.governed_evaluation_checks} governed checks</b>
                  <p>Sealed precision {pct(sensitivity.genai_evaluation.splits.sealed_test.candidate_precision)} · {sensitivity.genai_evaluation.splits.sealed_test.prompt_injection_successes} injection successes · no live provider run.</p>
                </article>
                <article>
                  <span>Event control replay</span>
                  <b>{sensitivity.shadow_replay.events} audit events</b>
                  <p>Eligibility and assignment only. RM visibility remains disabled; operating-day gate is still zero.</p>
                </article>
              </section>

              <section className="panel sensitivity-panel benchmark-panel">
                <div className="panel-head">
                  <div><p className="kicker">E0 governed benchmark economics</p><h2>Winner changes with the definition</h2></div>
                  <Pill tone="simulated">Not bank pricing</Pill>
                </div>
                <div className="sensitivity-grid benchmark-grid">
                  {Object.entries(sensitivity.benchmark_economics.packs).map(([name, pack]) => (
                    <article key={name}>
                      <span>{title(name)} pack</span>
                      <b>{money(pack.portfolio_scenario_value_zar)}</b>
                      <small>portfolio scenario value</small>
                      <div><em>Top product</em><em>{pack.top_product}</em></div>
                    </article>
                  ))}
                  <article className="highlight">
                    <span>Trade Finance robustness</span>
                    <b>{pct(sensitivity.global.product_summary["Trade finance"].first_rank_frequency, 0)}</b>
                    <small>first-rank frequency</small>
                    <div><em>Top-10 {pct(sensitivity.global.product_summary["Trade finance"].mean_top10_share, 1)}</em><em>Majority {pct(sensitivity.global.product_summary["Trade finance"].majority_dominance_frequency, 1)}</em></div>
                  </article>
                </div>
                <footer className="panel-foot"><span>Conclusion</span><p>Trade Finance owns the single highest-ranked opportunity, but Cross-border FX leads total scenario economics in all three E0 packs. Dominance is not a single invariant claim.</p></footer>
              </section>
            </>
          )}

          <section className="governance-grid">
            <article><span>Wallet model</span><b>Hierarchical + product-specific</b><p>Direct E3/E4 observations update pooled product/sector parameters.</p></article>
            <article><span>Timing model</span><b>Transparent baseline retained</b><p>Cox promotion requires ≥200 eligible events and ≥10 outcomes per degree of freedom.</p></article>
            <article><span>GenAI model</span><b>Three providers, fail-closed</b><p>OpenAI, Anthropic and Google require approval, pinned snapshots and rotated runtime credentials; deterministic fallback remains active.</p></article>
            <article><span>Causal policy</span><b>No uplift claim</b><p>Cluster assignment, propensities and outcomes are instrumented before learning.</p></article>
          </section>
        </main>
      )}

      <footer className="app-footer"><span>Corporate Wallet Digital Twin V3</span><p>Client demonstration · no financial decision, credit, pricing, booking, employee performance or automated client action</p><b>Schema v3 · Platform v3.0.0</b></footer>
    </div>
  );
}
