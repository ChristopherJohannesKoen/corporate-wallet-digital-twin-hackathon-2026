"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  V31Brief,
  V31BusinessTwin,
  V31Conversation,
  V31DecisionTwin,
  V31Digest,
  V31FundingRoutes,
  V31Graph,
  V31PlanEntry,
} from "@/lib/contracts";

type View = "Coverage plan" | "Client twin" | "Governance";

function money(value: number | null | undefined): string {
  if (value == null) return "Unavailable";
  const absolute = Math.abs(value);
  if (absolute >= 1e9) return `R${(value / 1e9).toFixed(1)}bn`;
  if (absolute >= 1e6) return `R${(value / 1e6).toFixed(1)}m`;
  if (absolute >= 1e3) return `R${(value / 1e3).toFixed(1)}k`;
  return `R${value.toFixed(0)}`;
}

function pct(value: number | null | undefined, digits = 0): string {
  return `${((value ?? 0) * 100).toFixed(digits)}%`;
}

function label(value: string): string {
  return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (character) => character.toUpperCase())
    .replace(/\bFx\b/g, "FX").replace(/\bDcm\b/g, "DCM").replace(/\bEsg\b/g, "ESG")
    .replace(/\bMa\b/g, "M&A").replace(/\bCoo\b/g, "COO").replace(/\bCfo\b/g, "CFO");
}

function Status({ children, tone = "neutral" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`dt-status dt-${tone}`}>{children}</span>;
}

function Metric({ label: metricLabel, value, note }: { label: string; value: string; note: string }) {
  return (
    <article className="dt-metric">
      <span>{metricLabel}</span>
      <b>{value}</b>
      <p>{note}</p>
    </article>
  );
}

function PlanRow({ item, selected, onSelect }: { item: V31PlanEntry; selected: boolean; onSelect: () => void }) {
  return (
    <button className={`dt-plan-row ${selected ? "selected" : ""}`} onClick={onSelect}>
      <span className="dt-rank">{String(item.rank).padStart(2, "0")}</span>
      <div className="dt-plan-client"><b>{item.entity_name}</b><small>{label(item.stakeholder_role)}</small></div>
      <div className="dt-plan-issue"><b>{item.problem_label}</b><small>{item.solution_label}</small></div>
      <div className="dt-plan-value"><b>{money(item.client_value_median)}</b><small>client proxy</small></div>
      <div className="dt-plan-value"><b>{money(item.bank_value_median)}</b><small>bank scenario</small></div>
      <div className="dt-plan-stability"><b>{pct(item.selection_stability)}</b><small>selection stability</small></div>
      <Status tone="discovery">Discovery</Status>
    </button>
  );
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json() as Promise<T>;
}

export default function Dashboard({ viewer, asOf, weekStart }: { viewer: string; asOf: string; weekStart: string }) {
  const [view, setView] = useState<View>("Coverage plan");
  const [projection, setProjection] = useState<V31DecisionTwin | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [conversation, setConversation] = useState<V31Conversation | null>(null);
  const [brief, setBrief] = useState<V31Brief | null>(null);
  const [twin, setTwin] = useState<V31BusinessTwin | null>(null);
  const [graph, setGraph] = useState<V31Graph | null>(null);
  const [digest, setDigest] = useState<V31Digest | null>(null);
  const [funding, setFunding] = useState<V31FundingRoutes | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getJson<V31DecisionTwin>(`/api/v3/decision-twin?as_of=${asOf}&week_start=${weekStart}`)
      .then((data) => {
        if (!active) return;
        setProjection(data);
        setSelectedId(data.coverage_plan.entries[0]?.conversation_id ?? data.conversation_summaries[0]?.conversation_id ?? "");
      })
      .catch((reason: Error) => active && setError(reason.message))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [asOf, weekStart]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      getJson<V31Conversation>(`/api/v3/conversations/${encodeURIComponent(selectedId)}?as_of=${asOf}`),
      getJson<V31Brief>(`/api/v3/conversations/${encodeURIComponent(selectedId)}/brief?as_of=${asOf}`),
    ])
      .then(async ([nextConversation, nextBrief]) => {
        if (!active) return;
        setConversation(nextConversation);
        setBrief(nextBrief);
        const clientId = nextConversation.entity_id;
        const [nextTwin, nextGraph, nextDigest, nextFunding] = await Promise.all([
          getJson<V31BusinessTwin>(`/api/v3/clients/${clientId}/business-twin?as_of=${asOf}`),
          getJson<V31Graph>(`/api/v3/clients/${clientId}/business-graph?as_of=${asOf}&explainable_only=true`),
          getJson<V31Digest>(`/api/v3/clients/${clientId}/change-digest?since=2026-03-31&as_of=${asOf}`),
          getJson<V31FundingRoutes>(`/api/v3/funding-routes/${clientId}?as_of=${asOf}`),
        ]);
        if (!active) return;
        setTwin(nextTwin);
        setGraph(nextGraph);
        setDigest(nextDigest);
        setFunding(nextFunding);
      })
      .catch((reason: Error) => active && setError(reason.message));
    return () => { active = false; };
  }, [selectedId, asOf]);

  const plan = useMemo(() => projection?.coverage_plan.entries ?? [], [projection]);
  const topFive = plan.slice(0, 5);
  const planIds = useMemo(() => new Set(plan.map((item) => item.conversation_id)), [plan]);

  function selectClient(clientId: string) {
    const candidate = projection?.conversation_summaries.find(
      (item) => item.entity_id === clientId && planIds.has(item.conversation_id),
    ) ?? projection?.conversation_summaries.find((item) => item.entity_id === clientId);
    if (candidate) setSelectedId(candidate.conversation_id);
  }

  if (loading) return <div className="dt-loading"><i /><p>Building the point-in-time Decision Twin…</p></div>;
  if (error || !projection) return <div className="dt-loading dt-error"><b>Decision Twin unavailable</b><p>{error || "No projection returned"}</p></div>;

  return (
    <div className="dt-shell">
      <header className="dt-masthead">
        <div className="dt-brand"><span className="dt-brand-mark"><i /><i /><i /></span><div><b>Corporate Wallet</b><small>Digital Twin · V3.1</small></div></div>
        <div className="dt-session"><Status tone="demo">Client demonstration</Status><span>As of <b>{asOf}</b></span><span>{viewer}</span></div>
      </header>

      <div className="dt-boundary"><b>GOVERNED DEMONSTRATION</b><span>{projection.metadata.watermark}</span><em>{projection.release.bank_production_status}</em></div>

      <nav className="dt-nav" aria-label="Decision Twin views">
        {(["Coverage plan", "Client twin", "Governance"] as View[]).map((item, index) => (
          <button key={item} onClick={() => setView(item)} className={view === item ? "active" : ""}><span>0{index + 1}</span>{item}</button>
        ))}
      </nav>

      {view === "Coverage plan" && (
        <main className="dt-main">
          <section className="dt-hero">
            <div><p className="dt-kicker">Monday morning · week of {weekStart}</p><h1>Your five most valuable<br /><em>conversations this week</em></h1></div>
            <p>{projection.metadata.central_idea}</p>
          </section>

          <section className="dt-metrics">
            <Metric label="Governed weekly plan" value={`${plan.length}/${projection.coverage_plan.capacity}`} note={`${projection.coverage_plan.solver_status} mixed-integer CVaR solution; no degraded fallback`} />
            <Metric label="Business Twins" value={String(projection.validation.clients)} note="Every client has 12 component records and a change digest" />
            <Metric label="Solution projections" value={String(projection.validation.solution_projections)} note={`${projection.validation.available_solution_estimates} available · ${projection.validation.fail_closed_solution_estimates} fail closed`} />
            <Metric label="Typed evidence claims" value={projection.evidence_coverage.total_claims.toLocaleString()} note={`${projection.evidence_coverage.approval_counts.APPROVED} approved · ${projection.evidence_coverage.approval_counts.PENDING_REVIEW} awaiting review`} />
          </section>

          <section className="dt-workspace">
            <article className="dt-panel dt-plan-panel">
              <div className="dt-panel-head"><div><p className="dt-kicker">Pareto frontier → governed policy rank</p><h2>Highest-value conversations</h2></div><Status tone="scenario">Representative values</Status></div>
              <div className="dt-table-labels"><span>Rank</span><span>Client / owner</span><span>Issue / solution</span><span>Client value</span><span>Bank value</span><span>Stability</span><span>Action</span></div>
              {topFive.map((item) => <PlanRow key={item.conversation_id} item={item} selected={selectedId === item.conversation_id} onSelect={() => setSelectedId(item.conversation_id)} />)}
            </article>

            <aside className="dt-panel dt-brief-panel">
              {conversation && brief ? (
                <>
                  <div className="dt-panel-head"><div><p className="dt-kicker">Closed-pack conversation brief</p><h2>{brief.headline}</h2></div><Status tone="deterministic">{brief.compiler}</Status></div>
                  <div className="dt-brief-block"><span>Why</span><p>{brief.why}</p></div>
                  <div className="dt-brief-block"><span>How</span><p>{brief.how}</p></div>
                  <div className="dt-brief-block"><span>What</span><p>{brief.what}</p></div>
                  <div className="dt-dual-value"><div><span>Client value</span><b>{money(conversation.client_value.monetised_total?.median)}</b><small>{brief.client_value_statement}</small></div><div><span>Bank value</span><b>{money(conversation.bank_value.direct_contribution?.median)}</b><small>{brief.bank_value_statement}</small></div></div>
                  <div className="dt-question"><span>Highest positive-net-VOI question</span><b>{brief.primary_question ?? "No decision-changing question has positive net VOI."}</b><small>{conversation.next_best_question ? `${money(conversation.next_best_question.net_voi_zar)} net VOI · ${conversation.next_best_question.scenario_draws} common draws` : "Abstained"}</small></div>
                  <button className="dt-link-button" onClick={() => setView("Client twin")}>Open complete client twin →</button>
                </>
              ) : <p>Loading conversation…</p>}
            </aside>
          </section>

          <section className="dt-panel dt-full-plan">
            <div className="dt-panel-head"><div><p className="dt-kicker">Full weekly capacity</p><h2>All eight selected conversations</h2></div><span className="dt-object">{projection.metadata.decision_object}</span></div>
            <div className="dt-mini-plan">
              {plan.map((item) => (
                <button key={item.conversation_id} onClick={() => setSelectedId(item.conversation_id)} className={selectedId === item.conversation_id ? "selected" : ""}>
                  <span>{item.rank}</span><b>{item.entity_name}</b><small>{label(item.stakeholder_role)} · {item.problem_label}</small><em>{item.solution_label}</em>
                </button>
              ))}
            </div>
            <footer><b>Selection contract</b><p>No failed gate; no dominated same-client bundle; ≤2/client; ≤1/client-role; ≤3/family; ≤3/sector. Material unknowns permit discovery only.</p></footer>
          </section>
        </main>
      )}

      {view === "Client twin" && (
        <main className="dt-main">
          <section className="dt-client-heading">
            <div><p className="dt-kicker">Point-in-time Business Model Twin</p><h1>{twin?.entity_name ?? "Client"}</h1><p>{twin?.sector} · {twin?.supported_domain_count}/12 supported or inferred domains · {twin?.approved_claim_count}/{twin?.claim_count} approved claims</p></div>
            <label>Client<select value={conversation?.entity_id ?? ""} onChange={(event) => selectClient(event.target.value)}>{projection.client_index.map((client) => <option key={client.entity_id} value={client.entity_id}>{client.entity_name}</option>)}</select></label>
          </section>

          {conversation && twin && (
            <>
              <section className="dt-change-strip"><div><span>What changed?</span><b>{digest?.items.length ?? 0} point-in-time changes since {digest?.since}</b></div>{digest?.items.slice(0, 3).map((item) => <article key={`${item.change_type}:${item.subject}`}><span>{label(item.change_type)}</span><b>{item.subject}</b><p>{item.after}</p></article>)}</section>

              <section className="dt-client-grid">
                <article className="dt-panel dt-conversation-card">
                  <div className="dt-panel-head"><div><p className="dt-kicker">Selected conversation</p><h2>{conversation.problem.label}</h2></div><Status tone="discovery">{label(conversation.risk_and_feasibility.permitted_action)}</Status></div>
                  <div className="dt-owner"><span>Responsible stakeholder</span><b>{label(conversation.stakeholder.primary_role)}</b><p>{conversation.stakeholder.ownership_rationale}</p></div>
                  <div className="dt-solution"><span>Governed solution bundle</span><b>{label(conversation.solution_bundle.primary)}</b><p>{conversation.solution_bundle.supporting.map(label).join(" + ") || "No supporting solution"}</p></div>
                  <div className="dt-why-now"><span>Why now</span><p>{conversation.engagement_window.why_now}</p><div><b>30d {pct(conversation.engagement_window.probability_30d)}</b><b>60d {pct(conversation.engagement_window.probability_60d)}</b><b>90d {pct(conversation.engagement_window.probability_90d)}</b></div></div>
                </article>

                <article className="dt-panel dt-feasibility">
                  <div className="dt-panel-head"><div><p className="dt-kicker">Six operational gates</p><h2>Feasibility stays explicit</h2></div><Status tone="blocked">{conversation.risk_and_feasibility.material_unknowns.length} unknown</Status></div>
                  {conversation.risk_and_feasibility.gates.map((gate) => <div className="dt-gate" key={gate.gate}><span>{label(gate.gate)}</span><Status tone={gate.status === "PASS" ? "ready" : gate.status === "UNKNOWN" ? "blocked" : "neutral"}>{gate.status}</Status><p>{gate.reason}</p></div>)}
                  <footer>{conversation.risk_and_feasibility.banker_confirmation_notice}</footer>
                </article>
              </section>

              <section className="dt-panel dt-business-twin">
                <div className="dt-panel-head"><div><p className="dt-kicker">Twelve-component client model</p><h2>Business facts remain supported, inferred or unknown</h2></div><Status tone="observed">Snapshot {twin.snapshot_version}</Status></div>
                <div className="dt-components">{twin.components.map((component, index) => {
                  const impacts = [...component.decision_impacts.problems, ...component.decision_impacts.solutions];
                  return <article key={component.domain}><span>{String(index + 1).padStart(2, "0")}</span><div><b>{component.label}</b><p>{impacts.slice(0, 2).map(label).join(" · ") || "No current decision impact"}</p><small>{component.freshness_days == null ? "unknown freshness" : `${component.freshness_days}d freshness`} · {component.evidence_tier} · {component.claim_class}</small></div><Status tone={component.status === "UNKNOWN" ? "blocked" : component.status === "SUPPORTED" ? "ready" : "scenario"}>{component.status}</Status></article>;
                })}</div>
              </section>

              <section className="dt-client-grid dt-lower-grid">
                <article className="dt-panel dt-graph-card">
                  <div className="dt-panel-head"><div><p className="dt-kicker">Dynamic Business Knowledge Graph</p><h2>Evidence-backed explanation path</h2></div><Status tone="scenario">{graph?.measurement_status ?? "MODELLED"}</Status></div>
                  <div className="dt-graph-stats"><div><b>{graph?.attribute_node_count}</b><span>attribute nodes</span></div><div><b>{graph?.event_node_count}</b><span>event nodes</span></div><div><b>{graph?.edges.length}</b><span>edges</span></div><div><b>{graph?.review_candidate_edges}</b><span>review candidates</span></div></div>
                  <div className="dt-path"><span>Event</span><i>→</i><span>Business impact</span><i>→</i><span>{conversation.problem.label}</span><i>→</i><span>{label(conversation.stakeholder.primary_role)}</span><i>→</i><span>{label(conversation.solution_bundle.primary)}</span><i>→</i><span>Client value</span><i>→</i><span>Bank value</span></div>
                  <p>{graph?.identity_resolution_status}</p>
                </article>

                <article className="dt-panel dt-funding-card">
                  <div className="dt-panel-head"><div><p className="dt-kicker">Funding Route Intelligence</p><h2>{money(funding?.requirement?.median)} requirement</h2></div><Status tone="scenario">{funding?.requirement_status ?? "Unavailable"}</Status></div>
                  {funding?.routes.map((route) => <div className="dt-route" key={route.route}><span>{label(route.route)}</span><i><b style={{ width: pct(route.probability) }} /></i><em>{pct(route.probability, 1)}</em></div>)}
                  <footer>{funding?.model_status}</footer>
                </article>
              </section>

              <section className="dt-panel dt-question-card"><div><p className="dt-kicker">Active Coverage Learning</p><h2>{conversation.next_best_question?.question_text ?? "No question selected"}</h2><p>A response creates a pending E2 candidate. It cannot alter approved evidence, intervals or the plan until review and a new point-in-time snapshot.</p></div><div><span>Net VOI</span><b>{money(conversation.next_best_question?.net_voi_zar)}</b><small>{conversation.next_best_question?.can_change_rank ? "Can change rank" : "Rank stable"} · {conversation.next_best_question?.can_change_feasibility ? "Can resolve feasibility" : "Feasibility unchanged"}</small></div></section>
            </>
          )}
        </main>
      )}

      {view === "Governance" && (
        <main className="dt-main">
          <section className="dt-governance-hero"><div><p className="dt-kicker">Release truth</p><h1>Demo complete.<br /><em>Bank production fail-closed.</em></h1></div><div><Status tone="ready">{projection.release.client_demo_status}</Status><Status tone="blocked">{projection.release.bank_production_status}</Status></div></section>
          <section className="dt-governance-grid">
            <article className="dt-panel"><p className="dt-kicker">Evidence integrity</p><h2>{projection.evidence_coverage.total_claims} typed claims</h2><ul><li>{projection.evidence_coverage.tier_counts.E1} E1 claims relinked and governed</li><li>{projection.evidence_coverage.approval_counts.PENDING_REVIEW} claims remain pending review</li><li>Every client meets ≥15 typed claims and ≥9 domains</li><li>All 20 clients remain below the stricter 15-approved-E1 target</li></ul><Status tone="blocked">{label(projection.evidence_coverage.e1_threshold_status)}</Status></article>
            <article className="dt-panel"><p className="dt-kicker">Interpretation contract</p><h2>Five labels never collapse</h2><ol><li><b>Observed</b> — Syn Bank simulation activity</li><li><b>Identified bound</b> — assumption-light set</li><li><b>Posterior</b> — model-based distribution</li><li><b>Scenario</b> — governed commercial assumption</li><li><b>Causal</b> — withheld until trial gates pass</li></ol><p>No opaque confidence score, measured competitor share or uplift claim is displayed.</p></article>
            <article className="dt-panel"><p className="dt-kicker">Domain event fabric</p><h2>{Object.values(projection.event_topics).reduce((sum, value) => sum + value, 0).toLocaleString()} immutable events</h2>{Object.entries(projection.event_topics).map(([topic, count]) => <div className="dt-topic" key={topic}><span>{topic.replace("wallet-twin.", "")}</span><b>{count}</b></div>)}</article>
            <article className="dt-panel"><p className="dt-kicker">Production target</p><h2>AWS + Databricks control plane</h2><div className="dt-stack"><span>Private EKS services</span><i>→</i><span>Delta + Unity Catalog</span><i>→</i><span>MLflow registry</span><i>→</i><span>Entitled workbench</span></div><p>Object Lock · MSK domain topics · OPA ABAC · row filters · OpenTelemetry · SIEM</p></article>
          </section>

          <section className="dt-panel dt-open-gates"><div className="dt-panel-head"><div><p className="dt-kicker">Non-delegable external gates</p><h2>What code and public data cannot legitimately close</h2></div><Status tone="blocked">{projection.release.blocking_external_gates.length} open</Status></div><div>{projection.release.blocking_external_gates.map((gate, index) => <article key={gate}><span>{String(index + 1).padStart(2, "0")}</span><b>{gate}</b><Status tone="blocked">Open</Status></article>)}</div></section>

          <section className="dt-panel dt-capabilities"><div className="dt-panel-head"><div><p className="dt-kicker">V3.1 implementation</p><h2>Decision Twin capabilities now operating in the demo</h2></div><Status tone="ready">3.1.0</Status></div><div>{projection.release.new_v31_capabilities.map((capability) => <article key={capability}><i>✓</i><span>{capability}</span></article>)}</div></section>
        </main>
      )}

      <footer className="dt-footer"><span>Corporate Wallet Digital Twin V3.1.0</span><p>Client demonstration · no automated pricing, credit, booking, CRM-stage change or customer communication</p><b>{projection.release.bank_production_status}</b></footer>
    </div>
  );
}
