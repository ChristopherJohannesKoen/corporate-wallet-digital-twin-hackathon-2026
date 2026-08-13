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
  WalletOpportunityDetail,
  WalletPortfolioCell,
  WalletPortfolioProjection,
} from "@/lib/contracts";

type View = "Wallet portfolio" | "Coverage plan" | "Client twin" | "Governance";
type WalletMetric = "contestable contribution" | "observed activity" | "posterior wallet" | "estimated Syn share" | "contestable gap" | "evidence status";

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

function heatMetricValue(cell: WalletPortfolioCell, metric: WalletMetric): number {
  if (metric === "observed activity") return Number(cell.observed_activity.normalized_amount);
  if (metric === "posterior wallet") return cell.posterior_wallet.median;
  if (metric === "estimated Syn share") return cell.share_interval.median;
  if (metric === "contestable gap") return cell.contestable_activity.median;
  if (metric === "evidence status") return cell.anchor_activation === "ACTIVATED" ? 1 : 0;
  return cell.scenario_contribution?.median ?? 0;
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
  const [view, setView] = useState<View>("Wallet portfolio");
  const [projection, setProjection] = useState<V31DecisionTwin | null>(null);
  const [wallet, setWallet] = useState<WalletPortfolioProjection | null>(null);
  const [walletMetric, setWalletMetric] = useState<WalletMetric>("contestable contribution");
  const [walletOpportunityId, setWalletOpportunityId] = useState("");
  const [walletDetail, setWalletDetail] = useState<WalletOpportunityDetail | null>(null);
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
    Promise.all([
      getJson<WalletPortfolioProjection>(`/api/v3/wallet-portfolio?as_of=${asOf}`),
      getJson<V31DecisionTwin>(`/api/v3/decision-twin?as_of=${asOf}&week_start=${weekStart}`),
    ])
      .then(([walletData, data]) => {
        if (!active) return;
        setWallet(walletData);
        setProjection(data);
        setSelectedId(data.coverage_plan.entries[0]?.conversation_id ?? data.conversation_summaries[0]?.conversation_id ?? "");
        setWalletOpportunityId(walletData.top_opportunity_ids[0] ?? walletData.cells[0]?.opportunity_id ?? "");
      })
      .catch((reason: Error) => active && setError(reason.message))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [asOf, weekStart]);

  useEffect(() => {
    if (!walletOpportunityId) return;
    let active = true;
    getJson<WalletOpportunityDetail>(`/api/v3/wallet-opportunities/${encodeURIComponent(walletOpportunityId)}?as_of=${asOf}`)
      .then((detail) => active && setWalletDetail(detail))
      .catch((reason: Error) => active && setError(reason.message));
    return () => { active = false; };
  }, [walletOpportunityId, asOf]);

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
  const walletClients = useMemo(() => {
    if (!wallet) return [];
    const index = new Map<string, { entity_id: string; entity_name: string; sector: string }>();
    wallet.cells.forEach((cell) => index.set(cell.entity_id, { entity_id: cell.entity_id, entity_name: cell.entity_name, sector: cell.sector }));
    return [...index.values()].sort((a, b) => a.entity_name.localeCompare(b.entity_name));
  }, [wallet]);

  const walletMax = useMemo(() => wallet ? Math.max(...wallet.cells.map((cell) => heatMetricValue(cell, walletMetric)), 1) : 1, [wallet, walletMetric]);

  function walletCellLabel(cell: WalletPortfolioCell): string {
    if (walletMetric === "estimated Syn share") return pct(cell.share_interval.median, 1);
    if (walletMetric === "evidence status") return cell.anchor_activation === "ACTIVATED" ? "E1 approved" : "E0 prior";
    return money(heatMetricValue(cell, walletMetric));
  }

  function selectClient(clientId: string) {
    const candidate = projection?.conversation_summaries.find(
      (item) => item.entity_id === clientId && planIds.has(item.conversation_id),
    ) ?? projection?.conversation_summaries.find((item) => item.entity_id === clientId);
    if (candidate) setSelectedId(candidate.conversation_id);
  }

  if (loading) return <div className="dt-loading"><i /><p>Building the point-in-time Decision Twin…</p></div>;
  if (error || !projection || !wallet) return <div className="dt-loading dt-error"><b>Wallet Twin unavailable</b><p>{error || "No projection returned"}</p></div>;

  return (
    <div className="dt-shell">
      <header className="dt-masthead">
        <div className="dt-brand"><span className="dt-brand-mark"><i /><i /><i /></span><div><b>Corporate Wallet</b><small>Digital Twin · V3.1.1</small></div></div>
        <div className="dt-session"><Status tone="demo">Client demonstration</Status><span>As of <b>{asOf}</b></span><span>{viewer}</span></div>
      </header>

      <div className="dt-boundary"><b>GOVERNED DEMONSTRATION</b><span>{projection.metadata.watermark}</span><em>{projection.release.bank_production_status}</em></div>

      <nav className="dt-nav" aria-label="Decision Twin views">
        {(["Wallet portfolio", "Coverage plan", "Client twin", "Governance"] as View[]).map((item, index) => (
          <button key={item} onClick={() => setView(item)} className={view === item ? "active" : ""}><span>0{index + 1}</span>{item}</button>
        ))}
      </nav>

      {view === "Wallet portfolio" && (
        <main className="dt-main">
          <section className="dt-wallet-hero">
            <div><p className="dt-kicker">Observed activity → latent wallet → contestable gap</p><h1>Find the wallet gap.<br /><em>Then earn the conversation.</em></h1></div>
            <div className="dt-wallet-boundary"><b>{wallet.approved_anchor_cells} approved-anchor cells</b><span>{wallet.prior_led_cells} prior-led cells</span><small>31 approved · 51 pending source facts</small></div>
          </section>

          <section className="dt-wallet-controls" aria-label="Heatmap metric">
            {(["contestable contribution", "observed activity", "posterior wallet", "estimated Syn share", "contestable gap", "evidence status"] as WalletMetric[]).map((metric) => (
              <button key={metric} className={walletMetric === metric ? "active" : ""} onClick={() => setWalletMetric(metric)}>{metric}</button>
            ))}
          </section>

          <section className="dt-wallet-workspace">
            <article className="dt-panel dt-heatmap-panel">
              <div className="dt-panel-head"><div><p className="dt-kicker">Complete 20 × 5 opportunity surface</p><h2>{label(walletMetric)}</h2></div><Status tone="scenario">{wallet.cells.length} governed cells</Status></div>
              <div className="dt-heatmap" style={{ gridTemplateColumns: `minmax(150px, 1.25fr) repeat(${wallet.products.length}, minmax(88px, 1fr))` }}>
                <span className="dt-heat-corner">Client / product</span>
                {wallet.products.map((product) => <b className="dt-heat-head" key={product}>{product === "Cross-border FX" ? "FX exposure" : product === "Liquidity" ? "Liquidity flow" : product}</b>)}
                {walletClients.map((client) => {
                  const cells = wallet.products.map((product) => wallet.cells.find((cell) => cell.entity_id === client.entity_id && cell.product === product)!);
                  return [<div className="dt-heat-client" key={`${client.entity_id}:label`}><b>{client.entity_name}</b><small>{client.sector}</small></div>, ...cells.map((cell) => {
                    const ratio = walletMetric === "evidence status" ? (cell.anchor_activation === "ACTIVATED" ? 1 : .12) : Math.max(.06, Math.sqrt(heatMetricValue(cell, walletMetric) / walletMax));
                    const active = walletOpportunityId === cell.opportunity_id;
                    return <button key={cell.opportunity_id} className={`dt-heat-cell ${active ? "selected" : ""} ${cell.anchor_activation === "ACTIVATED" ? "anchored" : "prior"}`} onClick={() => setWalletOpportunityId(cell.opportunity_id)} style={{ "--heat": ratio } as React.CSSProperties}><b>{walletCellLabel(cell)}</b><small>{cell.anchor_activation === "ACTIVATED" ? "E1 approved" : "E0 prior-led"}</small></button>;
                  })];
                })}
              </div>
              <footer className="dt-heatmap-note">FX is an exposure proxy. Liquidity is a liquidity-flow opportunity proxy. Heterogeneous product quantities are never summed as “banking spend”; only scenario contribution is aggregated.</footer>
            </article>

            <aside className="dt-panel dt-wallet-detail">
              {walletDetail ? <>
                <div className="dt-panel-head"><div><p className="dt-kicker">Wallet forensic drill-down</p><h2>{walletDetail.cell.entity_name} · {walletDetail.cell.product}</h2></div><Status tone={walletDetail.cell.anchor_activation === "ACTIVATED" ? "ready" : "blocked"}>{walletDetail.cell.approval_state}</Status></div>
                <div className="dt-wallet-equation"><b>A = qT</b><span>Observed activity is only one share of latent total wallet</span></div>
                <div className="dt-wallet-variables">
                  <article><span>A · observed</span><b>{money(walletDetail.explanation.A.value)}</b><small>OBSERVED · Syn Bank simulation</small></article>
                  <article><span>T · total wallet P10/P50/P90</span><b>{money(walletDetail.explanation.T.p50)}</b><small>{money(walletDetail.explanation.T.p10)} — {money(walletDetail.explanation.T.p90)}</small></article>
                  <article><span>q · estimated Syn share</span><b>{pct(walletDetail.explanation.q.p50, 1)}</b><small>{pct(walletDetail.explanation.q.p10, 1)} — {pct(walletDetail.explanation.q.p90, 1)} · POSTERIOR</small></article>
                  <article><span>q* · target scenario</span><b>{pct(walletDetail.explanation.q_star.value)}</b><small>SCENARIO · not an optimized claim</small></article>
                  <article><span>G · contestable P10/P50/P90</span><b>{money(walletDetail.explanation.G.p50)}</b><small>{money(walletDetail.explanation.G.p10)} — {money(walletDetail.explanation.G.p90)}</small></article>
                  <article><span>Scenario contribution</span><b>{money(walletDetail.cell.scenario_contribution?.median)}</b><small>Representative economics · not causal value</small></article>
                </div>
                <div className="dt-wallet-action"><span>Permitted action now</span><b>{label(walletDetail.cell.permitted_action_now)}</b><p>{walletDetail.cell.conditional_action}</p></div>
                {walletDetail.decision_twin_action && <button className="dt-link-button" onClick={() => { setSelectedId(walletDetail.decision_twin_action!.conversation_id); setView("Coverage plan"); }}>Continue to stakeholder, problem and timing →</button>}
              </> : <p>Loading wallet cell…</p>}
            </aside>
          </section>

          <section className="dt-wallet-summary">
            {wallet.product_summaries.map((summary) => <article className="dt-panel" key={summary.product}><span>{summary.product}</span><b>{money(summary.scenario_contribution_zar)}</b><small>scenario contribution · {summary.approved_anchor_cells} approved / {summary.prior_led_cells} prior-led</small></article>)}
          </section>
        </main>
      )}

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

          <section className="dt-panel dt-capabilities"><div className="dt-panel-head"><div><p className="dt-kicker">V3.1.1 implementation</p><h2>Decision Twin capabilities now operating in the demo</h2></div><Status tone="ready">3.1.1</Status></div><div>{projection.release.new_v31_capabilities.map((capability) => <article key={capability}><i>✓</i><span>{capability}</span></article>)}</div></section>
        </main>
      )}

      <footer className="dt-footer"><span>Corporate Wallet Digital Twin V3.1.1</span><p>Hackathon submission surface · no automated pricing, credit, booking, CRM-stage change or customer communication</p><b>{projection.release.bank_production_status}</b></footer>
    </div>
  );
}
