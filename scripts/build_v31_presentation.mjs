import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

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

const { FileBlob, PresentationFile } = await loadArtifactTool();

const ROOT = path.resolve(process.argv[2] || process.cwd());
const SOURCE = path.join(ROOT, "assets", "presentation", "Corporate-Wallet-Digital-Twin-V3-Template.pptx");
const OUT = path.join(ROOT, "output", "presentation");
const COVER = path.join(ROOT, "dashboard", "public", "og-v31.png");

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
  setText(`footer-team-${sourceNo}`, "TEAM: Corporate Wallet Digital Twin | Christopher Koen | V3.1.0");
  setText(`footer-data-${sourceNo}`, "SYN BANK SIMULATION + PUBLIC E1 + REPRESENTATIVE PRIORS");
  setText(`footer-page-${sourceNo}`, String(n).padStart(2, "0"));
}

// 1 â€” opening thesis.
setMany({
  "cover-proof": "Business-model reconstruction and decision intelligence for corporate relationship teams",
  "cover-version": "V3.1.0 | AS OF 30 JUNE 2026 | CLIENT DEMO — PUBLIC E1 + SYN BANK",
});
styledText("cover-subtitle", "Know the business.\nPlan the right conversation.", { fontSize: 29, color: "#C7D5E8" });
const coverImageRecord = records.find((record) => record.kind === "image" && record.slide === 1);
if (!coverImageRecord) throw new Error("Missing cover image");
const coverImage = presentation.resolve(coverImageRecord.id);
const placement = {
  frame: coverImage.frame,
  crop: coverImage.crop,
  fit: coverImage.fit,
  alt: coverImage.alt,
  prompt: coverImage.prompt,
  geometry: coverImage.geometry,
  borderRadius: coverImage.borderRadius,
  rotation: coverImage.rotation,
  flipHorizontal: coverImage.flipHorizontal,
  flipVertical: coverImage.flipVertical,
  lockAspectRatio: coverImage.lockAspectRatio,
};
coverImage.replace({
  blob: await fs.readFile(COVER),
  contentType: "image/png",
  alt: "Abstract latent corporate financial network with observed and reconstructed flows",
  fit: placement.fit || "cover",
  prompt: "Premium abstract corporate-finance network: observed bank node and partially hidden wallet flows, deep navy with cyan, violet and amber accents; no text or logos.",
});
coverImage.frame = placement.frame;
coverImage.crop = placement.crop;
coverImage.geometry = placement.geometry;
coverImage.borderRadius = placement.borderRadius;
coverImage.rotation = placement.rotation;
coverImage.flipHorizontal = placement.flipHorizontal;
coverImage.flipVertical = placement.flipVertical;
coverImage.lockAspectRatio = placement.lockAspectRatio;
setNotes(1, "Open with the V3.1 shift: the final analytical object is a client conversation, not a product row. The twin reconstructs the business, detects a problem, resolves the responsible role, evaluates solution bundles, separates client from bank value and allocates eight weekly conversations.", [
  "docs/Corporate_Wallet_Digital_Twin_V3_1_System_Dossier.md",
  "dashboard/app/data/v31-fixture.json",
  "config/submission.json",
]);

// 2 â€” partial-observation problem and claim ladder.
setMany({
  "eyebrow-2": "THE DECISION OBJECT",
  "title-2": "The decision starts beyond a client–product row",
  "s2-thesis": "Syn Bank observes product activity—not the full business model, total wallet, decision owner or response to an RM action. V3.1 adds the context needed for a governed conversation.",
  "s2-answer": "One claim ladder governs every twin, value and conversation",
  "s2-claim-copy-1": "Accounting interval",
  "s2-claim-copy-2": "Wallet distribution",
  "s2-claim-copy-3": "Problem, bundle and value",
  "s2-proof-text": "85 E1 and 820 E0 claims remain separated; measured competitor share and causal value remain zero; unknown bank feasibility stays UNKNOWN.",
});
setNotes(2, "Explain that V3.1 extends the V3 wallet substrate without changing its interpretation. Public and accounting evidence can constrain a wallet and support a business problem; it cannot reveal competitor transactions or causal RM impact.", [
  "src/wallet_twin_v31/contracts.py",
  "outputs/v31/v31_validation_report.json",
  "docs/Corporate_Wallet_Digital_Twin_V3_1_Technical_Foundations.md",
]);

// 3 â€” entropy-constrained Shadow Wallet.
setMany({
  "eyebrow-4": "BUSINESS MODEL TWIN",
  "title-4": "Twenty clients receive the same twelve-domain twin",
  "s4-metric-0-value": "20",
  "s4-metric-0-label": "client twins",
  "s4-metric-1-value": "240",
  "s4-metric-1-label": "domain components",
  "s4-metric-2-value": "905",
  "s4-metric-2-label": "typed evidence claims",
  "s4-metric-3-value": "71",
  "s4-metric-3-label": "explicit evidence gaps",
  "s4-width-title": "Evidence and graph projection",
  "s4-prior-label": "Approved claims",
  "s4-prior-value": "854",
  "s4-anchor-label": "Pending review",
  "s4-anchor-value": "51",
  "s4-reduction": "12/12 domains each",
  "s4-confidence": "993 nodes · 1,154 edges",
  "s4-source-label": "BOUNDARY",
  "s4-source-title": "Unknown remains unknown",
});
styledText("s4-source-body", "Attribute + event graph\nPoint-in-time availability\nApproved lineage on every path\nNo named people in demo", { fontSize: 16, color: "#627086" });
const shadowTotalBar = presentation.resolve(byName.get("s4-prior-bar").id);
const shadowComponentsBar = presentation.resolve(byName.get("s4-anchor-bar").id);
shadowComponentsBar.frame = { ...shadowComponentsBar.frame, width: Math.max(28, shadowTotalBar.frame.width * 51 / 854) };
setNotes(3, "Every client receives the same twelve Business Twin domains. The register is structurally complete but not public-evidence complete: all clients remain below the target of 15 reviewed E1 claims, and the gap is a release blocker rather than a filled assumption.", [
  "outputs/v31/v31_business_twins.json",
  "outputs/v31/v31_business_evidence_claims.json",
  "outputs/v31/v31_validation_report.json",
]);

// 4 â€” robust portfolio action.
setMany({
  "eyebrow-3": "MONDAY-MORNING COVERAGE PLAN",
  "title-3": "Eight conversations survive feasibility and downside risk",
  "s3-call-label": "NEXT ACTION",
  "s3-call-client": "Bid Corporation",
  "s3-call-product": "Liquidity · Treasurer",
  "s3-call-gap": "R13.7m",
  "s3-call-gap-label": "client-value proxy",
  "s3-call-confidence": "R4.0m bank scenario | 79.2% stability",
  "s3-call-action": "Discovery only: validate the liquidity structure and feasibility before any product proposal.",
  "s3-chart-title": "Top five client-value scenarios",
  "s3-pack-copy": "Capacity: 8. At most two per client; one per client/role; three per solution and sector. Solver status: OPTIMAL over 512 common draws.",
});
const chartRecord = records.find((record) => record.kind === "chart" && record.slide === 4);
if (!chartRecord) throw new Error("Missing portfolio chart");
const chart = presentation.resolve(chartRecord.id);
chart.series.getItemAt(0).categories = ["Bid Corp · Liquidity", "Sanlam · Payments", "Sanlam · Liquidity", "BHP · FX", "Shoprite · FX"];
chart.series.getItemAt(0).values = [13.7, 17.0, 17.0, 14.6, 5.9];
chart.xAxis = { title: "Client-value proxy (R million)", numberFormatCode: "0.0\"m\"" };
setNotes(4, "Lead with the banker decision: eight discovery conversations, selected after Pareto filtering and mixed-integer CVaR optimization. Unknown bank feasibility prevents product-proposal actions even when a need signal and scenario value are high.", [
  "outputs/v31/v31_coverage_plan.json",
  "src/wallet_twin_v31/portfolio.py",
  "config/v31_decision_policy.json",
]);

// 5 â€” BOCPD and leakage signal.
setMany({
  "eyebrow-9": "BHP EXPLANATION PATH",
  "title-9": "BHP’s FX case is valuable—but not yet urgent",
  "s9-timing-label": "BHP · TREASURER · FX EXPOSURE · DISCOVERY",
  "s9-h-value-0": "90.3%",
  "s9-h-label-0": "NEED SCENARIO",
  "s9-h-value-1": "R14.6m",
  "s9-h-label-1": "CLIENT PROXY",
  "s9-h-value-2": "R8.1m",
  "s9-h-label-2": "BANK SCENARIO",
  "s9-timing-title": "Event → impact → problem → role → bundle → value",
  "s9-timing-copy": "Audited FX evidence plus observed cross-border activity supports the problem; no dated trigger supports time-critical urgency.",
  "s9-timing-decision": "Decision: ask who signs off—and abstain from urgency",
  "s9-causal-label": "CLAIM BOUNDARY",
  "s9-zero": "0",
  "s9-zero-label": "causal value claims",
  "s9-prohibit": "Hedge ratio, decision authority and bank feasibility remain unknown; product proposal and guaranteed-saving claims are prohibited.",
});
styledText("s9-trial", "DISCOVERY ONLY\nClient and bank value are separate; causal value is null.", { fontSize: 18, color: "#C7D5E8" });
setNotes(5, "Walk the BHP path. The problem is well supported, but the engagement trigger is not. V3.1 therefore surfaces a discovery conversation and the highest-VOI decision-authority question rather than inventing urgency or proposing a product.", [
  "dashboard/app/data/v31-fixture.json — conv:686ef2a1e7530b6d84a28714",
  "src/wallet_twin_v31/business_graph.py",
  "src/wallet_twin_v31/conversations.py",
]);

// 6 â€” value-of-information queue.
setMany({
  "eyebrow-5": "ACTIVE COVERAGE LEARNING",
  "title-5": "Ask only when the answer can change the decision",
  "s5-facts-value": "308",
  "s5-facts-label": "positive-net-VOI questions",
  "s5-facts-note": "Selected from 891 evaluations with 512 common draws",
  "s5-clients-value": "R10.6k",
  "s5-clients-label": "BHP question net VOI",
  "s5-clients-note": "Decision value—not booked, client or causal value",
  "s5-review-value": "0",
  "s5-review-label": "direct model updates",
  "s5-review-note": "Every submitted answer remains pending until approval",
  "s5-progress-title": "Value comes from decision change—not semantic relevance",
  "s5-original-text": "Model explicit answer states and decision effects",
  "s5-expanded-text": "Subtract question cost and delay penalty",
  "s5-total": "1 primary question",
  "s5-tier-0": "E3",
  "s5-tier-copy-0": "multibank observation",
  "s5-tier-1": "RATE",
  "s5-tier-copy-1": "approved economics",
  "s5-tier-2": "E2",
  "s5-tier-copy-2": "client / RM attestation",
  "s5-tier-3": "PIT",
  "s5-tier-copy-3": "point-in-time source",
  "s5-tier-4": "4EYE",
  "s5-tier-copy-4": "human approval",
});
setNotes(6, "The governing question is not 'what is uncertain?' but 'what answer could change rank, bundle, feasibility or abstention?' The client answer becomes a pending E2 candidate and cannot change the twin until a reviewer approves it.", [
  "src/wallet_twin_v31/questions.py",
  "outputs/v31/v31_validation_report.json",
  "Sundin et al., Active Learning for Decision-Making, ICML 2019",
]);

// 7 â€” sensitivity continuity and diversified action portfolio.
setMany({
  "title-7": "Trade Finance remains robust—but conversations diversify",
  "s7-left-sub": "The five-product V3 benchmark remains reproducible: Trade Finance is first-ranked in all frozen rate/prior cases.",
  "s7-conclusion": "V3.1 selects two Trade Finance, three FX and three transaction-banking conversations after stakeholder, problem, feasibility and concentration constraints.",
});
setNotes(7, "Preserve the V3 continuity benchmark. Trade Finance survives the frozen five-product rate/prior cases, yet the V3.1 conversation plan diversifies because the decision object also contains business problem, stakeholder, feasibility, timing and concentration.", [
  "dashboard/app/data/shadow-fixture.json â€” sensitivity",
  "docs/v3_methodology.md",
  "dashboard/app/data/shadow-fixture.json â€” sensitivity.product_summary",
]);

// 8 â€” representative validation and honest boundaries.
setMany({
  "eyebrow-6": "V3.1 REPRESENTATIVE VALIDATION",
  "title-6": "Complete mechanics still do not create bank evidence",
  "s6-wallet-value": "320",
  "s6-wallet-label": "solution projections",
  "s6-wallet-note": "Sixteen solution families across all twenty clients",
  "s6-share-value": "224",
  "s6-share-label": "conversation candidates",
  "s6-share-note": "All discovery-only under unknown bank feasibility",
  "s6-narrow-value": "8 / 8",
  "s6-narrow-label": "plan constraints satisfied",
  "s6-narrow-note": "Mixed-integer solver status: OPTIMAL",
  "s6-design-label": "CONTROLLED DESIGN",
  "s6-line-0": "Twenty twins × twelve components reproduce point-in-time",
  "s6-line-1": "All 320 solution rows return an interval or fail-closed reason",
  "s6-line-2": "Pareto + CVaR enforce role, client, solution and sector limits",
  "s6-line-3": "Every V3.1 read requires as_of and deny-by-default ABAC",
  "s6-boundary-title": "Strong mechanics,\nnot measured competitors",
  "s6-boundary-copy": "No E3 share, approved economics or RM outcomes exist. Measured-share and causal-value claims: zero.",
});
setNotes(8, "Separate representative validation from bank-production validation. V3.1 proves contracts, point-in-time reconstruction, fail-closed estimators, graph integrity, constraints, deterministic replay and claim suppression; it does not prove a bank's empirical accuracy.", [
  "outputs/v31/v31_validation_report.json",
  "tests/test_v31_decision_twin.py",
  "docs/v31_implementation_status.md",
]);

// 9 â€” decision-directed RAG and governed brief.
setMany({
  "eyebrow-8": "CONTROLLED GENAI",
  "title-8": "The narrator translates a closed decision pack",
  "s8-title-0": "Score",
  "s8-copy-0": "Deterministic problem, value and rank",
  "s8-title-1": "Value",
  "s8-copy-1": "Question utility minus cost and delay",
  "s8-title-2": "Acquire",
  "s8-copy-2": "Approved, entitled claims only",
  "s8-title-3": "Compile",
  "s8-copy-3": "Why–How–What closed pack",
  "s8-title-4": "Brief",
  "s8-copy-4": "LLM gateway or deterministic fallback",
  "s8-checks-value": "224",
  "s8-checks-label": "deterministic briefs",
  "s8-checks-note": "One closed pack per conversation",
  "s8-cases-value": "100%",
  "s8-cases-label": "schema requirement",
  "s8-cases-note": "Numbers and citations must survive exactly",
  "s8-stress-value": "0",
  "s8-stress-label": "unsupported paths allowed",
  "s8-stress-note": "Unknown urgency and roles force abstention",
  "s8-fail-value": "0",
  "s8-fail-label": "autonomous actions",
  "s8-fail-note": "No CRM, client, pricing or retrieval action is delegated",
});
setNotes(9, "The LLM is last, not first. V3.1 compiles a closed Why–How–What pack and permits the provider only to translate approved content. Arithmetic, ranks, graph paths, values, VOI and citations remain deterministic; provider failure returns the deterministic brief.", [
  "src/wallet_twin_v31/briefs.py",
  "src/wallet_twin_v2/genai_gateway.py",
  "prompts/v3_decision_brief.schema.json",
  "outputs/v2_validation/genai_golden_eval.json",
]);

// 10 â€” summary and explicit production gates.
setMany({
  "s10-step-title-0": "Reconstruct the client business",
  "s10-step-copy-0": "Twenty twelve-domain twins, temporal graphs, problems, stakeholders and sixteen solution families.",
  "s10-step-title-1": "Plan eight conversations",
  "s10-step-copy-1": "Pareto-filtered, CVaR-aware discovery actions plus positive-net-VOI client questions.",
  "s10-step-title-2": "Close external gates",
  "s10-step-copy-2": "E3 calibration, approved economics, bank identity/infrastructure, live evaluation and RM trial.",
  "s10-close": "A better conversation today. A measurable learning system tomorrow.",
  "s10-team": "Corporate Wallet Digital Twin | Christopher Koen | V3.1.0",
});
styledText("s10-title", "Demonstrate the Decision Twin\nthen earn bank production", { fontSize: 54, color: "#FFFFFF", bold: true });
styledText("s10-subtitle", "V3.1 turns partial evidence into business context, solution bundles, dual value, governed conversations and an active learning loop—without overstating what was measured.", { fontSize: 24, color: "#C7D5E8" });
setNotes(10, "Close on the implemented V3.1 decision loop and the remaining external gates. The client demo is complete and reproducible; bank-production claims remain deliberately fail-closed until bank data, controls and supervised outcomes exist.", [
  "docs/v31_implementation_status.md",
  "docs/production_deployment_runbook.md",
  "notebooks/01_wallet_twin_demo.ipynb",
  "output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf",
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
await pptx.save(path.join(OUT, "Corporate-Wallet-Digital-Twin.pptx"));
console.log(JSON.stringify({ slides: presentation.slides.count, output: path.join(OUT, "Corporate-Wallet-Digital-Twin.pptx") }, null, 2));

