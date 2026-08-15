import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";

const ROOT = path.resolve(process.argv[2] || process.cwd());
const OUT = path.join(ROOT, "output", "presentation");
const OUTPUT_PPTX = path.join(OUT, "Corporate-Wallet-Digital-Twin.pptx");
const FALLBACK_MANIFEST = path.join(ROOT, "assets", "presentation", "v3.2-committed-artifact-manifest.json");

const digest = async (file) => createHash("sha256").update(await fs.readFile(file)).digest("hex");
const TEXT_SOURCE_EXTENSIONS = new Set([".js", ".json", ".mjs", ".ts", ".tsx"]);

async function sourceDigest(file) {
  const data = await fs.readFile(file);
  if (!TEXT_SOURCE_EXTENSIONS.has(path.extname(file).toLowerCase())) {
    return createHash("sha256").update(data).digest("hex");
  }
  // Git's Windows checkout may use CRLF while canonical exporters write LF.
  // Line endings are not authoring semantics, so normalize them for source
  // provenance while retaining a byte-exact digest for the PPTX itself.
  const normalized = data.toString("utf8").replace(/\r\n?/g, "\n");
  return createHash("sha256").update(normalized, "utf8").digest("hex");
}

async function verifyCommittedArtifact() {
  const manifest = JSON.parse(await fs.readFile(FALLBACK_MANIFEST, "utf8"));
  if (await digest(OUTPUT_PPTX) !== manifest.deck_sha256) {
    throw new Error("Committed PowerPoint hash does not match its fallback manifest");
  }
  for (const source of manifest.sources) {
    if (await sourceDigest(path.join(ROOT, source.path)) !== source.sha256) {
      throw new Error(`PowerPoint authoring source drifted: ${source.path}`);
    }
  }
  return manifest;
}

// OOXML writers legitimately restamp package metadata. If the committed deck
// and every authoring input already match, rebuilding would change bytes without
// changing content and would make a clean reproducibility verdict impossible.
// Verify and preserve that exact artifact. Any input drift falls through to the
// real authoring path below and is rebuilt when the workspace runtime exists.
try {
  await verifyCommittedArtifact();
  console.log(JSON.stringify({
    status: "PASS_COMMITTED_ARTIFACT_HASH_VERIFIED",
    output: OUTPUT_PPTX,
    authoring_runtime: "NOT_REQUIRED_INPUTS_UNCHANGED",
  }, null, 2));
  process.exit(0);
} catch {
  // Expected while authoring inputs are being changed.
}

async function loadArtifactTool() {
  try {
    return await import("@oai/artifact-tool");
  } catch {
    const dependencies = process.env.CODEX_RUNTIME_DEPENDENCIES || path.join(
      os.homedir(), ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies",
    );
    const entrypoint = path.join(
      dependencies, "node", "node_modules", "@oai", "artifact-tool", "dist", "artifact_tool.mjs",
    );
    return import(pathToFileURL(entrypoint).href);
  }
}

let artifactTool;
try {
  artifactTool = await loadArtifactTool();
} catch (error) {
  // The authoring package is supplied by the Codex workspace rather than the
  // public lockfile. A clean clone without it verifies the exact committed deck
  // and every authoring input, then preserves the artifact. Drift fails closed.
  throw new Error(
    `PowerPoint authoring runtime is unavailable and the committed artifact ` +
    `does not match its source manifest: ${error instanceof Error ? error.message : String(error)}`,
  );
}
const { FileBlob, PresentationFile } = artifactTool;

const SOURCE = path.join(ROOT, "assets", "presentation", "Corporate-Wallet-Digital-Twin-V3.2-Starter.pptx");
const HEATMAP = path.join(ROOT, "tmp", "v311-deck", "wallet-heatmap.png");
const PUBLIC_REPO = "https://github.com/ChristopherJohannesKoen/corporate-wallet-digital-twin-hackathon-2026-public";
const PROMOTION = JSON.parse(await fs.readFile(path.join(ROOT, "dashboard", "app", "data", "promotion-fixture.json"), "utf8"));
const TRUTH = JSON.parse(await fs.readFile(path.join(ROOT, "data", "v2", "submission_truth_v3.2.0.json"), "utf8"));
const TOP = TRUTH.wallet.top_opportunities;

// Rebuild from the same committed projection on every authoring run. No local
// dashboard server or ignored screenshot is an input to the final deck.
execFileSync(process.execPath, [path.join(ROOT, "scripts", "capture_wallet_heatmap.mjs"), ROOT], {
  cwd: ROOT,
  stdio: "inherit",
  env: process.env,
});

const presentation = await PresentationFile.importPptx(await FileBlob.load(SOURCE));
const inspected = await presentation.inspect({
  kind: "slide,textbox,shape,image,chart",
  include: "id,slide,name,text,bbox,chartType",
  maxChars: 200000,
});
const records = inspected.ndjson
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => JSON.parse(line));
const byName = new Map(records.filter((record) => record.name).map((record) => [record.name, record]));

function setText(name, value) {
  const record = byName.get(name);
  if (!record) throw new Error(`Missing text shape: ${name}`);
  const shape = presentation.resolve(record.id);
  shape.text.replace(record.text ?? "", value);
}

function setMany(values) {
  for (const [name, value] of Object.entries(values)) setText(name, value);
}

function styledText(name, value, { fontSize, color, bold = false }) {
  const record = byName.get(name);
  if (!record) throw new Error(`Missing text shape: ${name}`);
  const shape = presentation.resolve(record.id);
  shape.text = value;
  shape.text.style = {
    fontSize,
    typeface: "Arial",
    color,
    bold,
    alignment: "left",
    verticalAlignment: "top",
    autoFit: "shrinkText",
  };
}

function slideAt(oneBased) {
  return presentation.slides.getItem(oneBased - 1);
}

function setNotes(oneBased, presenter, sources) {
  slideAt(oneBased).speakerNotes.textFrame.setText([
    presenter,
    "",
    "[Sources]",
    ...sources.map((source) => `- ${source}`),
  ].join("\n"));
}

for (const n of [2, 3, 4, 5, 6, 7, 8, 9]) {
  const sourceNo = { 2: 2, 3: 4, 4: 3, 5: 9, 6: 5, 7: 7, 8: 6, 9: 8 }[n];
  setText(`footer-team-${sourceNo}`, "TEAM: Corporate Wallet Digital Twin | Christopher Koen | V3.2.0");
  setText(`footer-data-${sourceNo}`, "CONFIDENTIAL SYN BANK ACTIVITY + APPROVED PUBLIC E1 + GOVERNED PRIORS");
  setText(`footer-page-${sourceNo}`, String(n).padStart(2, "0"));
}

// 1 â€” opening thesis.
setMany({
  "cover-proof": "Find the latent wallet. Quantify the gap. Plan the governed conversation.",
  "cover-version": "V3.2.0 | AS OF 30 JUNE 2026 | HACKATHON SUBMISSION",
});
styledText("cover-subtitle", "See the wallet. Size the gap.\nChoose the conversation.", { fontSize: 29, color: "#C7D5E8" });
setNotes(1, "Lead with the commercial answer: Syn Bank observes only its own activity. The solution estimates an interval for total client wallet and bank share, sizes the contestable gap, then turns it into an evidence-backed relationship-manager conversation.", [
  "dashboard/app/data/wallet-v311-fixture.json",
  "outputs/v2_validation/measurement_policy_sensitivity.json",
  PUBLIC_REPO,
]);

// 2 — latent-wallet equation and claim ladder.
setMany({
  "eyebrow-2": "THE LATENT-WALLET PROBLEM",
  "title-2": "One observed number cannot identify the full wallet",
  "s2-thesis": "Syn Bank observes A—its own client–product activity. Total wallet T and bank share q remain latent. The identity A=qT admits many answers, so V3.2 reports bounds and posterior intervals rather than false precision.",
  "s2-answer": "The claim ladder keeps evidence, inference and economics distinct",
  "s2-claim-copy-1": "Identification interval",
  "s2-claim-copy-2": "Wallet + share distribution",
  "s2-claim-copy-3": "Target-share economics",
  "s2-proof-text": "Observed ≠ inferred ≠ scenario ≠ causal. Measured competitor share and causal incremental value remain prohibited without E3 observations and a qualified trial.",
});
setNotes(2, "Explain the core identification problem using A=qT. A is observed in supplied Syn Bank activity; T and q are not. Approved public anchors can narrow plausible T, while governed priors form a posterior interval. Nothing in this chain directly observes competitor transactions.", [
  "src/wallet_twin_v2/wallet_model.py",
  "src/wallet_twin_v2/measurement_policy.py",
  "docs/methodology.md",
]);

// 3 — supplied data and product transformation.
setMany({
  "eyebrow-4": "SUPPLIED DATA → FIVE PRODUCT LENSES",
  "title-4": "Every supplied relationship is modelled",
  "s4-metric-0-value": "3.064m",
  "s4-metric-0-label": "supplied rows",
  "s4-metric-1-value": "20",
  "s4-metric-1-label": "supplied relationships",
  "s4-metric-2-value": "5",
  "s4-metric-2-label": "product mappings",
  "s4-metric-3-value": "100",
  "s4-metric-3-label": "client × product cells",
  "s4-width-title": "Private evaluator transformation",
  "s4-prior-label": "Transaction legs",
  "s4-prior-value": "C / P / L",
  "s4-anchor-label": "Specialist feeds",
  "s4-anchor-value": "FX / TF",
  "s4-reduction": "PIT aggregated",
  "s4-confidence": "hash + schema retained",
  "s4-source-label": "SCOPE NOTE",
  "s4-source-title": "Brief says 50; supply contains 20",
});
styledText("s4-source-body", "Collections + Payments\nLiquidity-flow proxy\nCross-border FX exposure\nTrade Finance instruments", { fontSize: 16, color: "#627086" });
const shadowTotalBar = presentation.resolve(byName.get("s4-prior-bar").id);
const shadowComponentsBar = presentation.resolve(byName.get("s4-anchor-bar").id);
shadowComponentsBar.frame = { ...shadowComponentsBar.frame, width: shadowTotalBar.frame.width * 0.62 };
setNotes(3, "Show the supplied-data chain. Transaction legs produce Collections, Payments and a liquidity-flow opportunity proxy. Cross-border activity provides an FX exposure proxy; instruments provide Trade Finance activity. The conceptual problem statement mentions fifty clients, while the supplied archive contains twenty relationships; all twenty are modelled.", [
  "notebooks/01_wallet_twin_demo.ipynb",
  "output/notebook/01_wallet_twin_demo.html",
  "dashboard/app/data/wallet-v311-fixture.json",
]);

// 4 — observed activity, approved anchors and priors.
setMany({
  "eyebrow-3": "GOVERNED MEASUREMENT",
  "title-3": "Only approved evidence is allowed to narrow the wallet",
  "s3-call-label": "AUTHORITATIVE SOURCE ESTATE",
  "s3-call-client": "82 public facts",
  "s3-call-product": "31 approved · 51 pending",
  "s3-call-gap": "15",
  "s3-call-gap-label": "active anchored cells",
  "s3-call-confidence": "85 E0 prior-led cells · three approved-anchor clients",
  "s3-call-action": "Pending candidates may pass deterministic QA, but cannot activate anchors, change ranks or enter banker-facing claim paths.",
  "s3-chart-title": "E1 pooling-weight sensitivity",
  "s3-pack-copy": "Measurement policy v2-wallet-measurement-policy-1.1.0 fixes E1 at 0.35. The 0.20 / 0.35 / 0.50 sweep reports coverage, CRPS, width and rank effects.",
});
const chartRecord = records.find((record) => record.kind === "chart" && record.slide === 4);
if (!chartRecord) throw new Error("Missing portfolio chart");
const chart = presentation.resolve(chartRecord.id);
chart.series.getItemAt(0).categories = ["E1 weight 0.20", "E1 weight 0.35", "E1 weight 0.50"];
chart.series.getItemAt(0).values = [5.826, 4.374, 3.293];
chart.xAxis = { title: "Known-truth interval width (ZAR bn)", numberFormatCode: "0.0\"bn\"" };
setNotes(4, "Approval is authoritative. Thirty-one approved facts activate fifteen client–product anchors for BHP, Glencore and Shoprite; fifty-one candidates remain pending and cannot alter estimation. The active E1 pooling weight is 0.35, with 0.20 and 0.50 evaluated as sensitivity arms.", [
  "outputs/v2_validation/public_evidence_qa.json",
  "outputs/v2_validation/measurement_policy_sensitivity.json",
  "src/wallet_twin_v2/measurement_policy.py",
]);

// 5 — 20 × 5 opportunity heatmap.
setMany({
  "eyebrow-9": `THE 20 × 5 COMMERCIAL SURFACE · TOP FIVE ${new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", notation: "compact", maximumFractionDigits: 1 }).format(TOP.slice(0, 5).reduce((sum, item) => sum + item.scenario_contribution_median_zar, 0))}`,
  "title-9": "Start with Glencore Trade Finance—then BHP",
  "s9-timing-label": "DEFAULT COLOUR: CONTESTABLE SCENARIO CONTRIBUTION",
  "s9-h-value-0": "100",
  "s9-h-label-0": "INTERACTIVE CELLS",
  "s9-h-value-1": "15",
  "s9-h-label-1": "E1 APPROVED",
  "s9-h-value-2": "85",
  "s9-h-label-2": "E0 PRIOR-LED",
  "s9-timing-title": "Five product lenses · one explicit evidence state",
  "s9-timing-copy": "Toggle A, posterior T, estimated q, contestable G or approval status. FX and Liquidity remain labelled proxies.",
  "s9-timing-decision": "Click a cell to open A / T / q / q* / G",
  "s9-causal-label": "AGGREGATION RULE",
  "s9-zero": "0",
  "s9-zero-label": "heterogeneous spend totals",
  "s9-prohibit": "Product activities are never summed as a single banking-spend number. Only scenario contribution is aggregated.",
});
styledText("s9-trial", "WALLET FIRST\nCoverage Plan is the governed action layer below this evidence.", { fontSize: 18, color: "#C7D5E8" });
const heatmapCover = slideAt(5).shapes.add({
  geometry: "rect",
  position: { left: 54, top: 152, width: 1180, height: 516 },
  fill: "white",
  line: { style: "solid", fill: "#D7DEE8", width: 1 },
});
const heatmapImage = slideAt(5).images.add({
  blob: await fs.readFile(HEATMAP),
  contentType: "image/png",
  alt: "Corporate Wallet Digital Twin 20 by 5 wallet portfolio heatmap showing approved and prior-led cells",
  fit: "contain",
  position: { left: 70, top: 160, width: 1140, height: 500 },
});
setNotes(5, `Show the actual rendered Wallet Portfolio view. The default colour encodes portfolio-wide contestable scenario contribution. A, T, q and G views use relative intensity within each product column. The leading opportunities are ${TOP.slice(0, 5).map((item) => `${item.entity_name} ${item.product} R${(item.scenario_contribution_median_zar / 1e6).toFixed(2)}m`).join("; ")}.`, [
  "dashboard/app/Dashboard.tsx",
  "dashboard/app/data/wallet-v311-fixture.json",
  "src/wallet_twin_v31/wallet_portfolio.py",
]);

// 6 — BHP forensic drill-down.
setMany({
  "eyebrow-5": "BHP FORENSIC DRILL-DOWN",
  "title-5": "Trade Finance: A → T → q → q* → G",
  "s5-facts-value": "R1.445bn",
  "s5-facts-label": "A · observed activity",
  "s5-facts-note": "Syn Bank supplied annual trade-flow activity",
  "s5-clients-value": "R5.15–22.08bn",
  "s5-clients-label": "T · posterior wallet",
  "s5-clients-note": "P10–P90; P50 R8.93bn",
  "s5-review-value": "6.5–28.0%",
  "s5-review-label": "q · estimated share",
  "s5-review-note": "P50 16.2%; POSTERIOR, not measured competitor share",
  "s5-progress-title": "q* = 40% governed target-share scenario",
  "s5-original-text": "G P50 = R2.126bn contestable activity",
  "s5-expanded-text": "Scenario contribution P50 = R7.367m",
  "s5-total": "Rank #2 · E1 approved",
  "s5-tier-0": "A",
  "s5-tier-copy-0": "observed activity",
  "s5-tier-1": "T",
  "s5-tier-copy-1": "wallet posterior",
  "s5-tier-2": "q",
  "s5-tier-copy-2": "A ÷ T",
  "s5-tier-3": "q*",
  "s5-tier-copy-3": "40% scenario",
  "s5-tier-4": "G",
  "s5-tier-copy-4": "max(q*T−A,0)",
});
setNotes(6, "Walk the BHP Trade Finance cell. Syn Bank observes A=R1.445bn. Approved issuer accounting anchors constrain the total-wallet measurement; the posterior T spans R5.15bn–R22.08bn, implying q=6.5%–28.0%. A 40% target-share scenario creates a median contestable activity gap of R2.126bn and R7.367m representative scenario contribution.", [
  "dashboard/app/data/wallet-v311-fixture.json — E01-trade-finance",
  "BHP Annual Report 2025 — approved facts BHP-2025-COST, INV and AP",
  "outputs/audit/Public-Facts-Anchor-Register-V3.2.0.xlsx",
]);

// 7 — wallet gap to governed conversation.
setMany({
  "eyebrow-7": "DECISION TWIN ACTION LAYER",
  "title-7": "Wallet gap → stakeholder → problem → solution → timing",
  "s7-left-label": "BHP TRADE FINANCE CELL",
  "s7-left-main": "#2 in wallet",
  "s7-left-sub": "The wallet interval starts the investigation; it does not automatically become a product pitch.",
  "s7-col-0": "STAKEHOLDER",
  "s7-col-1": "PROBLEM",
  "s7-col-2": "SOLUTION",
  "s7-cell-text-0-0": "TREASURER",
  "s7-cell-text-0-1": "WC PRESSURE",
  "s7-cell-text-0-2": "TRADE FINANCE",
  "s7-cell-text-1-0": "CFO",
  "s7-cell-text-1-1": "SUPPLY RISK",
  "s7-cell-text-1-2": "+ SCF",
  "s7-cell-text-2-0": "FIN OPS",
  "s7-cell-text-2-1": "CONFIRM",
  "s7-cell-text-2-2": "DISCOVERY",
  "s7-global-label": "WHY NOW: DATED EVENT + PREPARATION WINDOW",
  "s7-first-value": "14 AUG",
  "s7-first-label": "dated trade event",
  "s7-first-note": "106 bank-observed trade events inside 90 days",
  "s7-top10-value": "45d",
  "s7-top10-label": "preparation lead",
  "s7-top10-note": "Engagement window opens 30 June",
  "s7-fx-value": "8",
  "s7-fx-label": "weekly conversations",
  "s7-fx-note": "All discovery under unknown bank gates",
  "s7-econ-value": "NULL",
  "s7-econ-label": "causal value",
  "s7-econ-note": "No qualified RM trial history",
  "s7-conclusion": "Permitted action now: validate wallet, stakeholder and feasibility. Conditional commercial action begins only after the missing facts and required gates are confirmed.",
});
setNotes(7, "The Decision Twin remains the action layer, not a replacement for share-of-wallet estimation. For BHP, 106 bank-observed trade events include a dated 14 August event. With a 45-day preparation lead, the engagement window opens on 30 June. The 36% 90-day seasonal baseline stays visible as an uncalibrated challenger, not the sole urgency claim. Missing feasibility converts the action into discovery.", [
  "outputs/v31/v31_coverage_plan.json",
  "src/wallet_twin_v31/conversations.py",
  "src/wallet_twin_v31/questions.py",
]);

// 8 — grounded GenAI proof and live-provider boundary.
setMany({
  "eyebrow-6": "GROUNDED GENAI BRIEFING",
  "title-6": "A closed evidence pack controls every published word",
  "s6-wallet-value": String(TRUTH.genai.accepted_runs),
  "s6-wallet-label": "accepted outputs",
  "s6-wallet-note": `${TRUTH.genai.target_runs} targets · all three showcase clients covered`,
  "s6-share-value": "3",
  "s6-share-label": "providers accepted",
  "s6-share-note": "OpenAI · Anthropic · Google; exact pinned models",
  "s6-narrow-value": String(TRUTH.genai.blocked_runs),
  "s6-narrow-label": "unsafe output blocked",
  "s6-narrow-note": "Claim compiler rejected before publication; fallback retained",
  "s6-design-label": "CONTROLLED WORKFLOW",
  "s6-line-0": "BHP · OpenAI gpt-5.6-sol · accepted",
  "s6-line-1": "Glencore · Anthropic claude-sonnet-5 · accepted",
  "s6-line-2": "Shoprite · Google gemini-3.6-flash · accepted",
  "s6-line-3": "One Anthropic/BHP output blocked; deterministic fallback retained",
  "s6-boundary-title": "8 accepted; one blocked safely",
  "s6-boundary-copy": "Every accepted output passed schema, number, sign, currency, citation, abstention and unsupported-claim checks. This is hackathon external-provider evaluation—not bank-authorized LIVE_GENAI.",
});
styledText("s6-boundary-title", "8 accepted;\none blocked safely", { fontSize: 26, color: "#0F1F33", bold: true });
setNotes(8, "GenAI is a bounded narrator. Eight of nine genuine provider outputs passed every critical validator, covering OpenAI, Anthropic, Google and all three showcase clients. The ninth output was generated but rejected by the claim compiler before publication, which demonstrates fail-closed control rather than a hidden failure. Deterministic fallback remains beside every accepted brief. This is hackathon evaluation, not bank provider approval.", [
  "outputs/v2_validation/live_provider_comparison.json",
  "data/v2/submission_truth_v3.2.0.json",
  "outputs/v2_validation/genai_golden_eval.json",
  "src/wallet_twin_v2/live_provider_eval.py",
]);

// 9 — Analytical trust and compact promotion boundary.
setMany({
  "eyebrow-8": "ANALYTICAL TRUST + PROMOTION BOUNDARY",
  "title-8": "Trade Finance stays first; the portfolio mix still moves",
  "s8-title-0": "Stress",
  "s8-copy-0": "10,000 correlated scenario draws",
  "s8-title-1": "Prior",
  "s8-copy-1": "E1 weight 0.20 / 0.35 / 0.50",
  "s8-title-2": "Coverage",
  "s8-copy-2": "Known-truth only; no E3 claim",
  "s8-title-3": "Selection",
  "s8-copy-3": "Top-eight composition is not invariant",
  "s8-title-4": "Permission",
  "s8-copy-4": "Real: OFFLINE\nRehearsal: SHADOW",
  "s8-checks-value": "10k",
  "s8-checks-label": "scenario draws",
  "s8-checks-note": "Rates, wallet, share and commercial inputs",
  "s8-cases-value": `${Math.round(TRUTH.sensitivity.trade_finance_first_rank_frequency * 100)}%`,
  "s8-cases-label": "TF first-ranked",
  "s8-cases-note": "Global sensitivity—not a hard-coded winner",
  "s8-stress-value": `${(TRUTH.sensitivity.trade_finance_majority_dominance_frequency * 100).toFixed(1)}%`,
  "s8-stress-label": "TF majority dominance",
  "s8-stress-note": "Absolute economics still varies materially",
  "s8-fail-value": String(TRUTH.promotion.elapsed_bank_shadow_days),
  "s8-fail-label": "elapsed bank days",
  "s8-fail-note": `PMR 100% · BER 0% · rehearsed only to ${TRUTH.promotion.rehearsed_state}`,
});
setNotes(9, "Trade Finance is first-ranked in all 10,000 global sensitivity draws and majority-dominant in 87.8%, but its absolute economics vary and the top-eight portfolio is not invariant across E1 pooling weights. Coverage and CRPS are known-truth rehearsal metrics only. The compact permission boundary is equally explicit: real state OFFLINE_CANDIDATE; rehearsal only to SHADOW_READY; PMR 100%, BER 0%, and zero elapsed bank shadow days.", [
  "dashboard/app/data/shadow-fixture.json — sensitivity.product_summary.Trade finance",
  "outputs/v2_validation/measurement_policy_sensitivity.json",
  "data/v2/submission_truth_v3.2.0.json",
]);

// 10 — conclusion and next steps.
setMany({
  "s10-step-title-0": "See the wallet",
  "s10-step-copy-0": "Twenty relationships × five products reveal where observed activity sits below a governed total-wallet interval.",
  "s10-step-title-1": "Size the gap",
  "s10-step-copy-1": "Target-share scenarios convert the interval into contestable activity and transparent commercial value.",
  "s10-step-title-2": "Choose the conversation",
  "s10-step-copy-2": "Stakeholder, issue, bundle, dated trigger, feasibility and the next-best question make the gap actionable.",
  "s10-close": "Hackathon ready. Real state OFFLINE_CANDIDATE; rehearsal SHADOW_READY; bank production NOT_PROMOTABLE.",
  "s10-team": "Corporate Wallet Digital Twin | Christopher Koen | V3.2.0",
  "s10-repository": `CODE: ${PUBLIC_REPO}`,
});
styledText("s10-title", "See the wallet.\nSize the gap.\nChoose the conversation.", { fontSize: 49, color: "#FFFFFF", bold: true });
styledText("s10-subtitle", "The highest-value discovery starts with Glencore Trade Finance, then BHP. Eight priority conversations turn governed wallet intervals into a focused coverage plan.", { fontSize: 23, color: "#C7D5E8" });
setNotes(10, "Close on the commercial decision. The ranked surface begins with Glencore Trade Finance at R17.0m representative scenario contribution, followed by BHP Trade Finance at R7.37m. The relationship manager receives eight priority discovery conversations, not a generic model score. Governance is the final boundary, not the central pitch: hackathon ready; bank production NOT_PROMOTABLE.", [
  "data/v2/submission_truth_v3.2.0.json",
  "outputs/v2_validation/production_candidate_scorecard.json",
  "notebooks/01_wallet_twin_demo.ipynb",
  "output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf",
  "outputs/judging_manifest_v3.2.0.json",
  PUBLIC_REPO,
]);

await fs.mkdir(OUT, { recursive: true });
for (let index = 0; index < presentation.slides.count; index += 1) {
  const slide = presentation.slides.getItem(index);
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  const png = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(OUT, `${stem}.png`), new Uint8Array(await png.arrayBuffer()));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(OUT, `${stem}.layout.json`), await layout.text());
}
const montage = await presentation.export({ format: "webp", montage: true, scale: 1 });
await fs.writeFile(path.join(OUT, "wallet-twin-deck-montage.webp"), new Uint8Array(await montage.arrayBuffer()));
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(OUTPUT_PPTX);
console.log(JSON.stringify({ slides: presentation.slides.count, output: OUTPUT_PPTX }, null, 2));

