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
const COVER = path.join(ROOT, "dashboard", "public", "og.png");

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
  setText(`footer-team-${sourceNo}`, "TEAM: Corporate Wallet Digital Twin | Christopher Koen | V3.0");
  setText(`footer-data-${sourceNo}`, "SYN BANK SIMULATION + PUBLIC E1 + REPRESENTATIVE PRIORS");
  setText(`footer-page-${sourceNo}`, String(n).padStart(2, "0"));
}

// 1 — opening thesis.
setMany({
  "cover-proof": "Latent-network reconstruction and decision intelligence for corporate relationship teams",
  "cover-version": "V3.0 | AS OF 10 AUGUST 2026 | SYN BANK SIMULATION + PUBLIC E1",
});
styledText("cover-subtitle", "Reconstruct the unseen wallet.\nDecide what matters next.", { fontSize: 29, color: "#C7D5E8" });
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
setNotes(1, "Open with the V3 shift: the system no longer stops at a wallet estimate. It reconstructs an anonymous latent network, detects time-sensitive signals, allocates RM capacity, and requests only decision-relevant evidence.", [
  "docs/v3_methodology.md",
  "dashboard/app/data/v3-fixture.json",
  "config/submission.json",
]);

// 2 — partial-observation problem and claim ladder.
setMany({
  "eyebrow-2": "THE PARTIAL-OBSERVATION PROBLEM",
  "title-2": "Partial observation cannot reveal the full financial system",
  "s2-thesis": "Syn Bank observes its own product activity—not the total client wallet, external allocation or response to an RM action. V3 makes that partial-observation boundary explicit.",
  "s2-answer": "V3 preserves the claim ladder—and reconstructs only as scenario",
  "s2-claim-copy-1": "Accounting interval",
  "s2-claim-copy-2": "Wallet distribution",
  "s2-claim-copy-3": "Anonymous shadow network",
  "s2-proof-text": "All 1,500 external edges remain SCENARIO, SYNTHETIC_SIMULATION and RECONSTRUCTED_NOT_MEASURED; causal value remains withheld.",
});
setNotes(2, "Explain A = q × T as an identification problem. Public and accounting anchors constrain T, but they do not observe competitor transactions. The Shadow Wallet is therefore an auditable scenario reconstruction, never measured share.", [
  "docs/v3_methodology.md",
  "src/wallet_twin_v3/contracts.py",
  "src/wallet_twin_v3/shadow_network.py",
  "Anand, Craig and von Peter, BIS Working Paper 455 (2014)",
]);

// 3 — entropy-constrained Shadow Wallet.
setMany({
  "eyebrow-4": "SHADOW WALLET RECONSTRUCTION",
  "title-4": "The Shadow Wallet balances every reconstructed flow",
  "s4-metric-0-value": "R1.1bn",
  "s4-metric-0-label": "observed Syn Bank flow",
  "s4-metric-1-value": "7.2%",
  "s4-metric-1-label": "scenario bank-share median",
  "s4-metric-2-value": "R15.0bn",
  "s4-metric-2-label": "total-wallet median",
  "s4-metric-3-value": "R13.9bn",
  "s4-metric-3-label": "latent external median",
  "s4-width-title": "External-wallet reconciliation",
  "s4-prior-label": "Posterior total",
  "s4-prior-value": "R15.0bn",
  "s4-anchor-label": "Observed + latent",
  "s4-anchor-value": "R15.0bn",
  "s4-reduction": "R0 balance error",
  "s4-confidence": "256 ensemble draws",
  "s4-source-label": "METHOD",
  "s4-source-title": "Entropy-regularised transport",
});
styledText("s4-source-body", "5 corridors × 3 anonymous providers\nPosterior supplies total mass\nSinkhorn preserves marginals\nNo competitor identities inferred", { fontSize: 16, color: "#627086" });
const shadowTotalBar = presentation.resolve(byName.get("s4-prior-bar").id);
const shadowComponentsBar = presentation.resolve(byName.get("s4-anchor-bar").id);
shadowComponentsBar.frame = { ...shadowComponentsBar.frame, width: shadowTotalBar.frame.width };
setNotes(3, "Use Glencore Trade Finance as the worked example. The reconstruction distributes posterior-constrained external mass over five corridor priors and three anonymous provider nodes. Exact reconciliation is a mechanical property, not proof that the individual edges are true.", [
  "dashboard/app/data/v3-fixture.json — E02-trade-finance",
  "src/wallet_twin_v3/shadow_network.py",
  "Cuturi, Sinkhorn Distances, NeurIPS 2013",
  "docs/v3_methodology.md",
]);

// 4 — robust portfolio action.
setMany({
  "eyebrow-3": "ROBUST RM PORTFOLIO",
  "title-3": "Twelve RM actions survive capacity and downside risk",
  "s3-call-label": "NEXT ACTION",
  "s3-call-client": "Glencore",
  "s3-call-product": "Trade Finance",
  "s3-call-gap": "R11.1m",
  "s3-call-gap-label": "expected scenario value",
  "s3-call-confidence": "R5.0m downside CVaR | 100% need",
  "s3-call-action": "Verify external wallet and instrument mix before contact; causal incremental value is withheld.",
  "s3-chart-title": "Top five CVaR-aware action values",
  "s3-pack-copy": "Capacity: 12. At most one action per client, four per product and four per sector. The selected portfolio contains four Trade Finance, four FX and four Liquidity actions.",
});
const chartRecord = records.find((record) => record.kind === "chart" && record.slide === 4);
if (!chartRecord) throw new Error("Missing portfolio chart");
const chart = presentation.resolve(chartRecord.id);
chart.series.getItemAt(0).categories = [
  "Glencore – TF",
  "BHP – TF",
  "MTN – FX",
  "Bid Corp – FX",
  "Anglo American – Liquidity",
];
chart.series.getItemAt(0).values = [11.1, 4.6, 3.7, 2.6, 2.6];
chart.xAxis = { numberFormatCode: "0.0\"m\"" };
setNotes(4, "Lead with the scarce-capacity decision. V3 optimizes a portfolio rather than ranking 100 independent rows. The robust score combines expected scenario value with lower-tail CVaR and enforces client, product and sector constraints.", [
  "dashboard/app/data/v3-fixture.json — action_portfolio",
  "src/wallet_twin_v3/decision_portfolio.py",
  "docs/v3_methodology.md",
]);

// 5 — BOCPD and leakage signal.
setMany({
  "eyebrow-9": "TEMPORAL DYNAMICS",
  "title-9": "Change-points surface leakage risk without claiming leakage",
  "s9-timing-label": "GLENCORE TRADE FINANCE — MODELLED SIGNAL",
  "s9-h-value-0": "4.6%",
  "s9-h-label-0": "CURRENT CP",
  "s9-h-value-1": "17.6%",
  "s9-h-label-1": "RECENT PEAK",
  "s9-h-value-2": "30.6%",
  "s9-h-label-2": "90-DAY EVENT",
  "s9-timing-title": "100 Bayesian run-length series",
  "s9-timing-copy": "Each 36-month client-product sequence updates a run-length posterior. Observed decline scales the alarm; no decline means no leakage signal.",
  "s9-timing-decision": "Decision: route the signal to RM verification",
  "s9-causal-label": "CLAIM BOUNDARY",
  "s9-zero": "0",
  "s9-zero-label": "confirmed leakage events",
  "s9-prohibit": "No competitor transfer, churn or causal-loss claim is permitted from the change-point score alone.",
});
styledText("s9-trial", "MODELLED SIGNAL\nNot confirmed leakage; needs named events and RM outcomes.", { fontSize: 18, color: "#C7D5E8" });
setNotes(5, "The leakage alarm multiplies recent change-point evidence, observed decline and reconstructed external-wallet exposure. It is a prioritization signal for verification, not evidence that a competitor captured flow.", [
  "src/wallet_twin_v3/event_dynamics.py",
  "dashboard/app/data/v3-fixture.json — E02-trade-finance",
  "Adams and MacKay, Bayesian Online Changepoint Detection (2007)",
]);

// 6 — value-of-information queue.
setMany({
  "eyebrow-5": "DECISION-DIRECTED EVIDENCE",
  "title-5": "Retrieve evidence only when it can change the portfolio",
  "s5-facts-value": "8",
  "s5-facts-label": "positive-net-VOI requests",
  "s5-facts-note": "Selected after utility, evidence cost and latency",
  "s5-clients-value": "R43.3m",
  "s5-clients-label": "expected net information value",
  "s5-clients-note": "Representative decision value—not booked or causal value",
  "s5-review-value": "0",
  "s5-review-label": "autonomous retrievals",
  "s5-review-note": "Approval remains mandatory for every acquisition",
  "s5-progress-title": "Value comes from decision change—not semantic relevance",
  "s5-original-text": "Score rank uncertainty and portfolio sensitivity",
  "s5-expanded-text": "Subtract acquisition cost and latency penalty",
  "s5-total": "= 8 evidence requests",
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
setNotes(6, "This is Decision-Directed RAG. Evidence acquisition is selected only when its expected impact on portfolio utility exceeds cost and delay. Retrieval remains non-autonomous and subject to approval and entitlement controls.", [
  "src/wallet_twin_v3/voi.py",
  "dashboard/app/data/v3-fixture.json — evidence_acquisition",
  "Bilgic and Getoor, Value of Information Lattice (2014)",
  "docs/v3_methodology.md",
]);

// 7 — sensitivity continuity and diversified action portfolio.
setMany({
  "title-7": "Trade Finance stays first-ranked, not portfolio-dominant",
  "s7-left-sub": "Trade Finance remains the first-ranked product across all frozen low/base/high rate and prior cases.",
  "s7-conclusion": "V3 selects four Trade Finance, four FX and four Liquidity actions—diversified under scarce RM capacity.",
});
setNotes(7, "Preserve the V2 continuity benchmark. Trade Finance survives all nine rate/prior cases as the first-ranked product, yet the 10,000-draw global sensitivity and the V3 constrained portfolio both argue against treating it as the entire strategy.", [
  "dashboard/app/data/shadow-fixture.json — sensitivity",
  "docs/v3_methodology.md",
  "dashboard/app/data/shadow-fixture.json — sensitivity.product_summary",
]);

// 8 — representative validation and honest boundaries.
setMany({
  "eyebrow-6": "V3 MECHANICAL VALIDATION",
  "title-6": "V3 adds structure without inventing empirical truth",
  "s6-wallet-value": "1,500",
  "s6-wallet-label": "shadow-wallet edges",
  "s6-wallet-note": "Exact flow reconciliation across 100 client-product networks",
  "s6-share-value": "100",
  "s6-share-label": "change-point series",
  "s6-share-note": "Deterministic temporal replay; not RM-outcome calibrated",
  "s6-narrow-value": "8 / 8",
  "s6-narrow-label": "selected VOI positive",
  "s6-narrow-note": "All retrieval remains non-autonomous",
  "s6-design-label": "CONTROLLED DESIGN",
  "s6-line-0": "256-draw entropy transport uses anonymous provider nodes",
  "s6-line-1": "PU probabilities retain their SCAR assumption and selection constant",
  "s6-line-2": "CVaR portfolio enforces client, product and sector capacity caps",
  "s6-line-3": "All /v3 routes inherit deny-by-default ABAC and as-of contracts",
  "s6-boundary-title": "Strong mechanics,\nnot measured competitors",
  "s6-boundary-copy": "No E3 competitor share, bank-approved economics or causal RM outcomes exist. V3 reports zero measured-share and zero causal-value claims.",
});
setNotes(8, "Separate mechanical validation from empirical calibration. V3 proves mass balance, constraints, deterministic replay, provenance and claim suppression. It does not claim representative-bank accuracy without E3 and RM outcomes.", [
  "dashboard/app/data/v3-fixture.json — validation",
  "tests/test_v3_decision_intelligence.py",
  "docs/v3_implementation_status.md",
]);

// 9 — decision-directed RAG and governed brief.
setMany({
  "eyebrow-8": "DECISION-DIRECTED RAG + GENAI",
  "title-8": "Ask for evidence before asking for prose",
  "s8-title-0": "Score",
  "s8-copy-0": "Portfolio sensitivity and uncertainty",
  "s8-title-1": "Value",
  "s8-copy-1": "Expected utility gain minus cost",
  "s8-title-2": "Acquire",
  "s8-copy-2": "Approved, entitled evidence only",
  "s8-title-3": "Compile",
  "s8-copy-3": "Claims, numbers and citations",
  "s8-title-4": "Brief",
  "s8-copy-4": "LLM gateway or deterministic fallback",
  "s8-checks-value": "8",
  "s8-checks-label": "VOI requests",
  "s8-checks-note": "Decision-selected, never autonomous",
  "s8-cases-value": "809",
  "s8-cases-label": "governed checks",
  "s8-cases-note": "Schema, evidence, page grounding and stress",
  "s8-stress-value": "640",
  "s8-stress-label": "stress cases",
  "s8-stress-note": "Exact, future, injection and missing evidence",
  "s8-fail-value": "0",
  "s8-fail-label": "autonomous actions",
  "s8-fail-note": "No CRM, client, pricing or retrieval action is delegated",
});
setNotes(9, "The LLM is last, not first. V3 selects evidence by value of information, requires approval, compiles a closed claim pack, and permits the model only to narrate approved content. Deterministic fallback remains operational.", [
  "src/wallet_twin_v3/briefing.py",
  "src/wallet_twin_v2/genai_gateway.py",
  "prompts/v3_decision_brief.schema.json",
  "outputs/v2_validation/genai_golden_eval.json",
]);

// 10 — summary and explicit production gates.
setMany({
  "s10-step-title-0": "Reconstruct the unseen wallet",
  "s10-step-copy-0": "100 client-product networks, 1,500 anonymous external edges and exact mass balance.",
  "s10-step-title-1": "Allocate scarce attention",
  "s10-step-copy-1": "Twelve CVaR-aware actions plus eight positive-net-value evidence requests.",
  "s10-step-title-2": "Close external gates",
  "s10-step-copy-2": "E3 calibration, approved economics, bank identity/infrastructure, live evaluation and RM trial.",
  "s10-close": "A better decision today. A measurable learning system tomorrow.",
  "s10-team": "Corporate Wallet Digital Twin | Christopher Koen | V3.0",
});
styledText("s10-title", "Demonstrate the latent decision lab\nthen earn production", { fontSize: 54, color: "#FFFFFF", bold: true });
styledText("s10-subtitle", "V3 turns partial observations into reconstructed wallets, temporal signals, constrained actions and a deliberate evidence queue—without overstating what was measured.", { fontSize: 24, color: "#C7D5E8" });
setNotes(10, "Close on the implemented V3 decision loop and the remaining external gates. The client demo is complete and reproducible; production claims remain deliberately fail-closed until bank data, controls and supervised outcomes exist.", [
  "docs/v3_implementation_status.md",
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
