import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const ROOT = path.resolve(process.argv[2] || process.cwd());
const OUT = path.join(ROOT, "output", "presentation");
const PORTFOLIO = JSON.parse(await fs.readFile(path.join(ROOT, "outputs", "data", "portfolio.json"), "utf8"));
const MANIFEST = JSON.parse(await fs.readFile(path.join(ROOT, "outputs", "client_demo", "client_demo_data_manifest.json"), "utf8"));
const OFFLINE = JSON.parse(await fs.readFile(path.join(ROOT, "outputs", "v2_validation", "offline_validation_report.json"), "utf8"));
const GENAI = JSON.parse(await fs.readFile(path.join(ROOT, "outputs", "v2_validation", "genai_golden_eval.json"), "utf8"));
const FIXTURE = JSON.parse(await fs.readFile(path.join(ROOT, "dashboard", "app", "data", "shadow-fixture.json"), "utf8"));
const SUBMISSION = JSON.parse(await fs.readFile(path.join(ROOT, "config", "submission.json"), "utf8"));
const COVER = path.join(ROOT, "output", "assets", "wallet-twin-cover.png");

const W = 1280;
const H = 720;
const C = {
  navy: "#071321", ink: "#0C1728", muted: "#627086", line: "#D7DEE8",
  panel: "#F1F4F8", paleBlue: "#EAF3FF", blue: "#0B63E5", blue2: "#69A7F7",
  teal: "#008B83", amber: "#E2951C", violet: "#7658D6", white: "#FFFFFF",
  greenPale: "#E7F5F2", amberPale: "#FFF4DF", violetPale: "#F0EDFF",
};

const deck = Presentation.create({ slideSize: { width: W, height: H } });

async function bytes(file) {
  const value = await fs.readFile(file);
  return value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength);
}
async function writeBlob(file, blob) {
  await fs.writeFile(file, new Uint8Array(await blob.arrayBuffer()));
}
function rect(slide, name, left, top, width, height, fill, lineFill = "none", radius = undefined) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect", name,
    position: { left, top, width, height }, fill,
    line: { style: "solid", fill: lineFill, width: lineFill === "none" ? 0 : 1 },
    ...(radius ? { borderRadius: radius } : {}),
  });
}
function rule(slide, name, left, top, width, fill = C.line, weight = 1) {
  return slide.shapes.add({
    geometry: "straightConnector1", name,
    position: { left, top, width, height: 0 }, fill: "none",
    line: { style: "solid", fill, width: weight },
  });
}
function text(slide, name, value, left, top, width, height, fontSize = 20, color = C.ink, bold = false, align = "left") {
  const box = slide.shapes.add({
    geometry: "textbox", name,
    position: { left, top, width, height }, fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  box.text = value;
  box.text.style = {
    fontSize, typeface: "Arial", color, bold, alignment: align,
    verticalAlignment: "top", autoFit: "shrinkText",
  };
  return box;
}
function footer(slide, number) {
  text(slide, `footer-team-${number}`, `TEAM: ${SUBMISSION.team_name} | ${SUBMISSION.team_members.join(", ")} | ${SUBMISSION.solution_version}`, 64, 681, 720, 18, 11, C.muted, true);
  text(slide, `footer-data-${number}`, "SYN BANK SIMULATION + PUBLIC E1 + REPRESENTATIVE BENCHMARKS", 786, 681, 390, 18, 10, C.muted, true, "right");
  text(slide, `footer-page-${number}`, String(number).padStart(2, "0"), 1185, 681, 32, 18, 11, C.muted, true, "right");
}
function slideTitle(slide, value, number, eyebrow) {
  text(slide, `eyebrow-${number}`, eyebrow.toUpperCase(), 64, 34, 740, 22, 13, C.blue, true);
  text(slide, `title-${number}`, value, 64, 69, 1120, 58, 42, C.ink, true);
  rule(slide, `title-rule-${number}`, 64, 145, 1152, C.line, 1);
  footer(slide, number);
}
function metric(slide, name, x, y, w, value, label, accent, note = "") {
  rule(slide, `${name}-rule`, x, y, w, accent, 4);
  text(slide, `${name}-value`, value, x, y + 18, w, 52, 37, C.ink, true);
  text(slide, `${name}-label`, label, x, y + 74, w, 28, 17, C.ink, true);
  if (note) text(slide, `${name}-note`, note, x, y + 108, w, 54, 15, C.muted, false);
}
function notes(slide, sourceLines, presenter) {
  slide.speakerNotes.textFrame.setText(`${presenter}\n\n[Sources]\n${sourceLines.map((source) => `- ${source}`).join("\n")}`);
}
function money(value, digits = 1) {
  if (Math.abs(value) >= 1e9) return `R${(value / 1e9).toFixed(digits)}bn`;
  if (Math.abs(value) >= 1e6) return `R${(value / 1e6).toFixed(digits)}m`;
  return `R${value.toFixed(0)}`;
}
const pct = (value, digits = 0) => `${(value * 100).toFixed(digits)}%`;

const ranked = [...PORTFOLIO.opportunities].sort((a, b) => b.priority_score - a.priority_score);
const top5 = ranked.slice(0, 5);
const bhpFx = PORTFOLIO.opportunities.find((row) => row.entity_id === "E01" && row.product === "Cross-border FX");
const calibration = OFFLINE.synthetic_calibration;
const timing = OFFLINE.historical_validation.timing_surrogate;
const globalSensitivity = FIXTURE.sensitivity;

// 1. Cover.
{
  const slide = deck.slides.add();
  slide.background.fill = C.navy;
  slide.images.add({
    blob: await bytes(COVER), contentType: "image/png",
    alt: "Abstract digital corporate wallet with transaction flows",
    fit: "cover", position: { left: 0, top: 0, width: W, height: H },
  });
  rect(slide, "cover-field", 0, 0, 690, H, C.navy);
  text(slide, "cover-kicker", "STANDARD BANK HACKATHON 2026", 64, 54, 480, 24, 14, "#7CB6FF", true);
  text(slide, "cover-title", "Corporate Wallet\nDigital Twin", 64, 138, 560, 176, 64, C.white, true);
  text(slide, "cover-subtitle", "See the wallet. Size the gap.\nChoose the moment.", 64, 354, 540, 86, 29, "#C7D5E8", false);
  rule(slide, "cover-rule", 64, 486, 440, "#2D4C6D", 1);
  text(slide, "cover-proof", "Evidence-first opportunity intelligence for corporate relationship teams", 64, 510, 520, 58, 19, C.white, false);
  text(slide, "cover-team", `TEAM: ${SUBMISSION.team_name}`, 64, 605, 520, 22, 14, C.white, true);
  text(slide, "cover-member", `MEMBER: ${SUBMISSION.team_members.join(", ")}`, 64, 635, 520, 22, 13, "#B9C8D9", false);
  text(slide, "cover-version", "V2.1 | AS OF 9 AUGUST 2026 | SYN BANK SIMULATION + PUBLIC E1", 64, 676, 650, 18, 11, "#8FA5BD", true);
  notes(slide, [
    "output/assets/wallet-twin-cover.png",
    "config/submission.json",
  ], "Open with the business decision: the bank sees its own activity but not the client's full wallet.");
}

// 2. Identification problem.
{
  const slide = deck.slides.add();
  slideTitle(slide, "One observed number cannot identify the full wallet", 2, "The decision problem");
  text(slide, "s2-thesis", "Syn Bank observes product activity. It does not observe total client wallet or competitor share. A single point estimate would hide that identification problem.", 64, 181, 485, 116, 24, C.ink, false);
  rect(slide, "s2-equation", 608, 176, 608, 224, C.navy);
  text(slide, "s2-A", "A", 650, 218, 100, 80, 62, C.white, true, "center");
  text(slide, "s2-eq", "=", 764, 232, 55, 60, 42, "#7CB6FF", true, "center");
  text(slide, "s2-q", "q", 835, 218, 100, 80, 62, C.white, true, "center");
  text(slide, "s2-x", "x", 949, 232, 55, 60, 42, "#7CB6FF", true, "center");
  text(slide, "s2-T", "T", 1021, 218, 100, 80, 62, C.white, true, "center");
  text(slide, "s2-label-A", "observed", 646, 311, 110, 24, 16, "#AFC0D4", false, "center");
  text(slide, "s2-label-q", "bank share", 825, 311, 120, 24, 16, "#AFC0D4", false, "center");
  text(slide, "s2-label-T", "total wallet", 1005, 311, 130, 24, 16, "#AFC0D4", false, "center");
  text(slide, "s2-answer", "Our answer is a claim ladder, not false precision", 64, 345, 490, 40, 27, C.ink, true);
  const claims = [
    ["OBSERVED", "Syn Bank activity", C.teal],
    ["BOUND", "Assumption-light interval", C.blue],
    ["POSTERIOR", "Prior + evidence", C.violet],
    ["SCENARIO", "Contestable economics", C.amber],
    ["CAUSAL", "Only after a trial", C.ink],
  ];
  claims.forEach((item, index) => {
    const x = 64 + index * 230;
    rule(slide, `s2-claim-rule-${index}`, x, 468, 196, item[2], 4);
    text(slide, `s2-claim-${index}`, item[0], x, 490, 196, 22, 13, item[2], true);
    text(slide, `s2-claim-copy-${index}`, item[1], x, 526, 196, 54, 18, C.ink, true);
  });
  rect(slide, "s2-proof", 64, 608, 1152, 42, C.paleBlue);
  text(slide, "s2-proof-text", "Every ranked value retains evidence tier, as-of time, interval, model version and commercial-input version.", 84, 619, 1110, 22, 17, C.blue, true);
  notes(slide, [
    "docs/Corporate_Wallet_Digital_Twin_V2_Technical_Foundations.md - sections on identification and claim classes",
    "docs/v2_model_validation.md",
    "contracts/jsonschema/claim.schema.json",
  ], "Pause on A=qT. One observation and two unknowns is the reason the system reports bounds and posteriors separately.");
}

// 3. Ranked commercial decision.
{
  const slide = deck.slides.add();
  slideTitle(slide, "The first call is Glencore Trade Finance", 3, "Portfolio action");
  rect(slide, "s3-callout", 64, 179, 392, 412, C.navy);
  text(slide, "s3-call-label", "NEXT CONVERSATION", 92, 207, 300, 22, 13, "#7CB6FF", true);
  text(slide, "s3-call-client", "Glencore", 92, 260, 320, 46, 36, C.white, true);
  text(slide, "s3-call-product", "Trade Finance", 92, 314, 320, 42, 31, C.white, true);
  text(slide, "s3-call-gap", money(top5[0].revenue_gap_zar.p50), 92, 388, 280, 55, 44, C.amber, true);
  text(slide, "s3-call-gap-label", "median scenario contribution gap", 92, 449, 280, 30, 16, "#B9C8D9", false);
  text(slide, "s3-call-confidence", `${pct(top5[0].top10_probability)} P(top 10) | E1 anchor`, 92, 503, 300, 26, 17, C.teal, true);
  text(slide, "s3-call-action", "Verify instrument mix and competitor concentration before meeting the client.", 92, 535, 300, 48, 16, C.white, false);

  text(slide, "s3-chart-title", "Top five uncertainty-adjusted opportunities", 500, 182, 650, 30, 22, C.ink, true);
  slide.charts.add("bar", {
    name: "s3-top5-chart",
    position: { left: 500, top: 226, width: 680, height: 314 },
    categories: top5.map((row) => `${row.entity_name} - ${row.product}`),
    series: [{ name: "Scenario gap (R m)", values: top5.map((row) => Number((row.revenue_gap_zar.p50 / 1e6).toFixed(1))), fill: C.blue }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd", numberFormatCode: "0.0" },
    xAxis: { title: "Median scenario contribution gap (R million)", majorGridlines: { style: "solid", fill: C.line, width: 1 } },
    yAxis: { reverseOrder: true },
  });
  rect(slide, "s3-pack", 500, 565, 680, 64, C.paleBlue);
  text(slide, "s3-pack-copy", "The recommendation pack supplies who, product, interval, evidence, timing window and the exact assumption to verify.", 520, 582, 640, 32, 17, C.blue, true);
  notes(slide, [
    "outputs/data/portfolio.json - opportunities sorted by priority_score",
    "outputs/opportunity_register.csv",
    "config/assumptions.json - scenario economics",
  ], "Lead with the decision, then explain that P(top 10) is rank uncertainty, not win probability.");
}

// 4. BHP worked evidence twin.
{
  const slide = deck.slides.add();
  slideTitle(slide, "BHP evidence materially narrows the FX interval", 4, "Auditable client walkthrough");
  const metrics = [
    [money(bhpFx.observed_activity_zar), "observed FX activity", C.teal],
    [pct(bhpFx.current_share.p50, 1), "posterior share median", C.violet],
    [money(bhpFx.total_wallet_zar.p50), "wallet median", C.blue],
    [money(bhpFx.revenue_gap_zar.p50), "scenario gap median", C.amber],
  ];
  const metricXs = [64, 350, 636, 944];
  metrics.forEach((item, index) => metric(slide, `s4-metric-${index}`, metricXs[index], 178, index === 3 ? 218 : 240, item[0], item[1], item[2]));

  text(slide, "s4-width-title", "Relative wallet interval width", 64, 361, 400, 30, 22, C.ink, true);
  const priorWidth = bhpFx.anchor_impact.prior_relative_interval_width;
  const anchoredWidth = bhpFx.anchor_impact.anchored_relative_interval_width;
  text(slide, "s4-prior-label", "Prior-led", 64, 411, 140, 24, 17, C.muted, true);
  rect(slide, "s4-prior-bar", 214, 409, 390 * priorWidth, 27, "#B7C2D0");
  text(slide, "s4-prior-value", priorWidth.toFixed(2), 214 + 390 * priorWidth + 12, 411, 80, 24, 17, C.ink, true);
  text(slide, "s4-anchor-label", "With FX anchor", 64, 464, 140, 24, 17, C.muted, true);
  rect(slide, "s4-anchor-bar", 214, 462, 390 * anchoredWidth, 27, C.teal);
  text(slide, "s4-anchor-value", anchoredWidth.toFixed(2), 214 + 390 * anchoredWidth + 12, 464, 80, 24, 17, C.ink, true);
  text(slide, "s4-reduction", `-${pct(bhpFx.anchor_impact.relative_interval_width_reduction)} width`, 64, 527, 310, 42, 32, C.teal, true);
  text(slide, "s4-confidence", `+${pct(bhpFx.anchor_impact.confidence_lift)} confidence`, 350, 527, 310, 42, 32, C.blue, true);

  rect(slide, "s4-source", 744, 355, 442, 250, C.paleBlue);
  text(slide, "s4-source-label", "POINT-IN-TIME ANCHOR", 774, 384, 350, 22, 13, C.blue, true);
  text(slide, "s4-source-title", "Audited multi-currency revenue", 774, 426, 350, 56, 27, C.ink, true);
  text(slide, "s4-source-body", "BHP Annual Report 2025 p.160\nPeriod end: 30 June 2025\nAvailable: 19 August 2025\nCurrency, unit and FX policy retained", 774, 496, 350, 104, 16, C.muted, false);
  notes(slide, [
    "outputs/evidence/E01.json - BHP Cross-border FX opportunity",
    "data/public_facts.csv - BHP-2025-FX",
    "BHP Annual Report 2025 p.160 (registered source; report file excluded from GitHub)",
  ], "Make the evidence trace explicit: page, period and available date. The anchor narrows the interval but does not become an exact wallet label.");
}

// 5. Public evidence coverage.
{
  const slide = deck.slides.add();
  slideTitle(slide, "E1 evidence now covers all 20 relationships", 5, "Evidence expansion");
  metric(slide, "s5-facts", 64, 180, 290, "82", "point-in-time E1 facts", C.blue, "Page, period, available date and source hash retained");
  metric(slide, "s5-clients", 438, 180, 290, "20 / 20", "relationships covered", C.teal, "All portfolio clients now have governed public evidence");
  metric(slide, "s5-review", 812, 180, 290, "51", "facts pending SME review", C.amber, "Page-grounded candidates; not relabelled as approved");

  text(slide, "s5-progress-title", "Coverage grew without weakening the evidence label", 64, 385, 660, 34, 25, C.ink, true);
  rect(slide, "s5-original", 64, 446, 390, 52, C.blue);
  text(slide, "s5-original-text", "31 seed facts | BHP, Glencore, Shoprite", 82, 461, 350, 24, 16, C.white, true);
  rect(slide, "s5-expanded", 454, 446, 646, 52, C.teal);
  text(slide, "s5-expanded-text", "+51 page-grounded facts | remaining 17 relationships", 474, 461, 610, 24, 16, C.white, true);
  text(slide, "s5-total", "= 82 E1 facts", 1115, 459, 100, 28, 18, C.ink, true, "right");

  const tierItems = [
    ["E0", "governed prior", C.muted],
    ["E1", "audited public", C.blue],
    ["E2", "client / RM attested", C.violet],
    ["E3", "multibank observed", C.teal],
    ["E4", "reconciled outcome", C.amber],
  ];
  tierItems.forEach((item, index) => {
    const x = 64 + index * 230;
    rule(slide, `s5-tier-rule-${index}`, x, 564, 196, item[2], 4);
    text(slide, `s5-tier-${index}`, item[0], x, 582, 44, 26, 17, item[2], true);
    text(slide, `s5-tier-copy-${index}`, item[1], x + 48, 582, 148, 34, 16, C.ink, true);
  });
  notes(slide, [
    "outputs/client_demo/client_demo_data_manifest.json - source_estate",
    "outputs/v2_validation/public_evidence_qa.json",
    "data/v2/public_evidence_coverage.csv",
    "data/v2/public_facts_expanded.csv",
  ], "State the honest distinction: all 20 have E1 coverage, while 51 expanded facts still await finance-SME approval.");
}

// 6. Model validation.
{
  const slide = deck.slides.add();
  slideTitle(slide, "Coverage survives the corrected validation design", 6, "Wallet-model evidence");
  metric(slide, "s6-wallet", 64, 182, 290, pct(calibration.split_conformal_audit.wallet.conformal_coverage_90, 1), "wallet interval coverage", C.teal, "Nominal 90%; entity-disjoint calibration and evaluation");
  metric(slide, "s6-share", 438, 182, 290, pct(calibration.split_conformal_audit.share.conformal_coverage_90, 1), "share interval coverage", C.blue, "Nominal 90%; evaluated across sectors");
  metric(slide, "s6-narrow", 812, 182, 290, pct(calibration.comparisons.e1_anchor_median_wallet_interval_narrowing, 1), "median E1 narrowing", C.violet, "Coverage retained in the known-truth stress lab");

  rect(slide, "s6-design", 64, 390, 690, 221, C.paleBlue);
  text(slide, "s6-design-label", "CORRECTED DESIGN", 90, 416, 280, 22, 13, C.blue, true);
  const designLines = [
    "Client-disjoint model fit, conformal calibration and evaluation",
    "Selection-weighted panel corrects the simulated inclusion mechanism",
    "Product and sector coverage reported, not only a portfolio average",
    "Posterior draws, CRPS and interval widths remain reproducible",
  ];
  designLines.forEach((value, index) => {
    rect(slide, `s6-dot-${index}`, 92, 459 + index * 34, 10, 10, C.teal, "none", "rounded-full");
    text(slide, `s6-line-${index}`, value, 120, 452 + index * 34, 600, 26, 17, C.ink, false);
  });

  rect(slide, "s6-boundary", 790, 390, 396, 221, C.amberPale);
  text(slide, "s6-boundary-label", "CLAIM BOUNDARY", 816, 416, 280, 22, 13, C.amber, true);
  text(slide, "s6-boundary-title", "Strong mechanics,\nnot empirical E3 accuracy", 816, 455, 330, 84, 28, C.ink, true);
  text(slide, "s6-boundary-copy", "The 1,500-row panel contains known synthetic truth. It cannot establish actual competitor share or bank-production calibration.", 816, 548, 330, 64, 17, C.muted, false);
  notes(slide, [
    "outputs/v2_validation/offline_validation_report.json - synthetic_calibration",
    "outputs/client_demo/representative_multibank_analog.csv",
    "docs/v2_model_validation.md",
  ], "Use the headline numbers, then immediately disclose that the panel validates mechanics rather than real-world competitor-share accuracy.");
}

// 7. Sensitivity.
{
  const slide = deck.slides.add();
  slideTitle(slide, "Trade Finance wins first rank, not portfolio majority", 7, "Rate and prior sensitivity");
  rect(slide, "s7-left", 64, 180, 500, 423, C.navy);
  text(slide, "s7-left-label", "FROZEN 3 x 3 BENCHMARK", 92, 209, 350, 22, 13, "#7CB6FF", true);
  text(slide, "s7-left-main", "#1 in 9 / 9", 92, 258, 350, 62, 46, C.white, true);
  text(slide, "s7-left-sub", "Trade Finance is the first-ranked product across low/base/high rate and prior cases.", 92, 333, 410, 82, 21, "#C7D5E8", false);
  const matrixX = 92; const matrixY = 442; const cellW = 121; const cellH = 42;
  ["LOW RATE", "BASE", "HIGH RATE"].forEach((label, col) => text(slide, `s7-col-${col}`, label, matrixX + col * (cellW + 8), matrixY - 26, cellW, 18, 11, "#8FA5BD", true, "center"));
  ["LOW PRIOR", "BASE", "HIGH PRIOR"].forEach((label, row) => {
    for (let col = 0; col < 3; col += 1) {
      rect(slide, `s7-cell-${row}-${col}`, matrixX + col * (cellW + 8), matrixY + row * (cellH + 8), cellW, cellH, row === 1 && col === 1 ? C.amber : "#17304A");
      const cellLabel = col === 0 ? `${["LOW P", "BASE P", "HIGH P"][row]} | TF #1` : "TF #1";
      text(slide, `s7-cell-text-${row}-${col}`, cellLabel, matrixX + col * (cellW + 8), matrixY + 12 + row * (cellH + 8), cellW, 18, col === 0 ? 10 : 14, C.white, true, "center");
    }
  });

  text(slide, "s7-global-label", "10,000-DRAW GLOBAL SENSITIVITY", 612, 190, 520, 22, 13, C.violet, true);
  metric(slide, "s7-first", 612, 230, 250, pct(globalSensitivity.product_summary["Trade finance"].first_rank_frequency), "TF first-rank frequency", C.violet, "Stable single highest-ranked product");
  metric(slide, "s7-top10", 914, 230, 250, pct(globalSensitivity.product_summary["Trade finance"].mean_top10_share, 1), "TF mean top-10 share", C.amber, "Important, but not a portfolio majority");
  metric(slide, "s7-fx", 612, 416, 250, pct(globalSensitivity.product_summary["Cross-border FX"].majority_dominance_frequency, 1), "FX majority frequency", C.blue, "The wider top 10 concentrates in FX");
  metric(slide, "s7-econ", 914, 416, 250, money(globalSensitivity.product_summary["Trade finance"].absolute_economics.p50), "TF absolute economics", C.teal, "Median across approved-shape scenario distributions");
  text(slide, "s7-conclusion", "Conclusion: start with the Trade Finance conversation; keep portfolio capacity diversified across FX and Liquidity.", 612, 590, 552, 46, 18, C.ink, true);
  notes(slide, [
    "outputs/data/portfolio.json - sensitivity.scenarios",
    "dashboard/app/data/shadow-fixture.json - sensitivity",
    "outputs/sensitivity_register.csv",
  ], "Give both conclusions. Trade Finance is the stable first product, but Cross-border FX dominates the breadth of the top ten in many global draws.");
}

// 8. GenAI controls.
{
  const slide = deck.slides.add();
  slideTitle(slide, "Controls, not GenAI, decide what publishes", 8, "Production-style GenAI");
  const stages = [
    ["1", "Extract", "Structured extraction candidate", C.blue],
    ["2", "Validate", "Currency, unit, period, arithmetic", C.teal],
    ["3", "Review", "Four-eyes evidence approval", C.amber],
    ["4", "Compile", "Only approved claims and citations", C.violet],
    ["5", "Brief", "Grounded narrative or fallback", C.ink],
  ];
  // Connectors first so they stay behind the nodes.
  for (let index = 0; index < stages.length - 1; index += 1) {
    rule(slide, `s8-link-${index}`, 182 + index * 225, 305, 93, C.line, 3);
  }
  stages.forEach((stage, index) => {
    const x = 64 + index * 225;
    rect(slide, `s8-stage-${index}`, x, 218, 190, 175, index % 2 === 0 ? C.paleBlue : C.greenPale, C.line, "rounded-lg");
    text(slide, `s8-num-${index}`, stage[0], x + 16, 238, 36, 32, 22, stage[3], true);
    text(slide, `s8-title-${index}`, stage[1], x + 16, 282, 156, 34, 25, C.ink, true);
    text(slide, `s8-copy-${index}`, stage[2], x + 16, 329, 156, 52, 16, C.muted, false);
  });
  metric(slide, "s8-checks", 64, 466, 250, "809", "governed checks", C.blue, "Schema, evidence, page grounding and stress");
  metric(slide, "s8-cases", 356, 466, 250, "36", "golden-set cases", C.violet, "Sealed split protocol and adjudication structure");
  metric(slide, "s8-stress", 648, 466, 250, "640", "stress cases", C.amber, "Exact, future, injection and missing evidence");
  metric(slide, "s8-fail", 940, 466, 250, "0", "validator failures", C.teal, "Deterministic scope; live-provider approval stays separate");
  notes(slide, [
    "outputs/v2_validation/genai_golden_eval.json",
    "src/wallet_twin_v2/genai_gateway.py",
    "src/wallet_twin_v2/genai_eval.py",
    "prompts/evidence_extraction.txt",
  ], "Explain that the model never publishes facts or acts in CRM. Deterministic checks and approval status control publication.");
}

// 9. Timing and causal boundary.
{
  const slide = deck.slides.add();
  slideTitle(slide, "Timing is usable; causal value stays prohibited", 9, "When to act and what not to claim");
  text(slide, "s9-timing-label", "TRANSACTION-DERIVED EVENT PROBABILITY", 64, 183, 520, 22, 13, C.blue, true);
  const horizons = [
    ["30 DAYS", timing.discrete_time_challenger.mean_surrogate_probability["30d"], C.blue],
    ["60 DAYS", timing.discrete_time_challenger.mean_surrogate_probability["60d"], C.teal],
    ["90 DAYS", timing.discrete_time_challenger.mean_surrogate_probability["90d"], C.violet],
  ];
  horizons.forEach((item, index) => {
    const x = 64 + index * 224;
    rule(slide, `s9-h-rule-${index}`, x, 229, 190, item[2], 4);
    text(slide, `s9-h-value-${index}`, pct(item[1], 1), x, 252, 190, 50, 37, C.ink, true);
    text(slide, `s9-h-label-${index}`, item[0], x, 309, 190, 24, 15, item[2], true);
  });
  rect(slide, "s9-timing-boundary", 64, 376, 640, 214, C.paleBlue);
  text(slide, "s9-timing-title", "3,440 start-stop intervals", 92, 406, 360, 42, 29, C.ink, true);
  text(slide, "s9-timing-copy", "Activation, dormancy and volume-uplift events support a transparent seasonal baseline and named 30/60/90-day windows.", 92, 463, 560, 62, 19, C.muted, false);
  text(slide, "s9-timing-decision", "Decision: retain seasonal baseline", 92, 546, 520, 28, 18, C.blue, true);

  rect(slide, "s9-causal", 752, 180, 434, 410, C.navy);
  text(slide, "s9-causal-label", "CAUSAL GATE", 782, 211, 280, 22, 13, "#7CB6FF", true);
  text(slide, "s9-zero", "0", 782, 255, 170, 74, 58, C.amber, true);
  text(slide, "s9-zero-label", "qualified RM outcomes", 782, 332, 310, 30, 18, C.white, true);
  text(slide, "s9-trial", "Trial instrumentation rehearsed:\n30 clusters | 1,500 eligible opportunities", 782, 393, 350, 70, 20, "#C7D5E8", false);
  text(slide, "s9-prohibit", "No uplift, optimal-share or causal incremental-value label is permitted.", 782, 505, 350, 72, 20, C.white, true);
  notes(slide, [
    "outputs/v2_validation/offline_validation_report.json - historical_validation.timing_surrogate",
    "outputs/client_demo/client_demo_data_manifest.json - trial_analog",
    "docs/v2_pilot_protocol.md",
  ], "The timing layer can prioritize a conversation, but transaction-derived events are not banker outcomes. The causal label remains closed.");
}

// 10. Close and pilot.
{
  const slide = deck.slides.add();
  slide.background.fill = C.navy;
  text(slide, "s10-kicker", "THE DECISION", 64, 48, 320, 22, 14, "#7CB6FF", true);
  text(slide, "s10-title", "Pilot the strongest twins\nunder controlled evidence", 64, 112, 760, 132, 54, C.white, true);
  text(slide, "s10-subtitle", "The hackathon solution is ready to demonstrate now. The next milestone converts governed scenarios into observed banker actions without overstating production readiness.", 64, 277, 780, 92, 24, "#C7D5E8", false);
  const steps = [
    ["01", "Start with evidence-rich clients", "BHP, Glencore and Shoprite plus the highest-value E1-covered relationships."],
    ["02", "Measure the recommendation", "Eligibility, exposure, evidence verification, RM action and outcome events."],
    ["03", "Promote only after gates pass", "Real E3 calibration, approved economics, identity controls and causal evidence."],
  ];
  steps.forEach((step, index) => {
    const x = 64 + index * 378;
    rule(slide, `s10-step-rule-${index}`, x, 435, 326, index === 2 ? C.amber : C.blue2, 4);
    text(slide, `s10-step-num-${index}`, step[0], x, 460, 44, 25, 14, "#7CB6FF", true);
    text(slide, `s10-step-title-${index}`, step[1], x, 497, 326, 50, 22, C.white, true);
    text(slide, `s10-step-copy-${index}`, step[2], x, 560, 326, 72, 17, "#9FB1C9", false);
  });
  text(slide, "s10-close", "A transparent commercial hypothesis today. A measurable learning system tomorrow.", 64, 666, 1000, 24, 17, C.white, true);
  text(slide, "s10-team", `${SUBMISSION.team_name} | ${SUBMISSION.team_members.join(", ")} | ${SUBMISSION.solution_version}`, 850, 666, 366, 24, 12, "#8FA5BD", true, "right");
  text(slide, "s10-repository", `CODE: ${SUBMISSION.repository_url}`, 64, 638, 860, 18, 11, "#7CB6FF", true);
  notes(slide, [
    "docs/client_demo_release.md",
    "docs/v2_pilot_protocol.md",
    "docs/production_deployment_runbook.md",
    "output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf",
    "notebooks/01_wallet_twin_demo.ipynb",
  ], "Close on the controlled pilot. The system is a strong, transparent hackathon solution now; bank production requires the external gates already documented.");
}

await fs.mkdir(OUT, { recursive: true });
for (const [index, slide] of deck.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  await writeBlob(path.join(OUT, `${stem}.png`), await deck.export({ slide, format: "png", scale: 1 }));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(OUT, `${stem}.layout.json`), await layout.text());
}
await writeBlob(path.join(OUT, "wallet-twin-deck-montage.webp"), await deck.export({ format: "webp", montage: true, scale: 1 }));
const pptx = await PresentationFile.exportPptx(deck);
await pptx.save(path.join(OUT, "Corporate-Wallet-Digital-Twin.pptx"));
console.log(JSON.stringify({ slides: deck.slides.items.length, output: path.join(OUT, "Corporate-Wallet-Digital-Twin.pptx") }, null, 2));
