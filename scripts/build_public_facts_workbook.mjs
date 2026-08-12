import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadArtifactTool() {
  try {
    return await import("@oai/artifact-tool");
  } catch {
    const dependencies = process.env.CODEX_RUNTIME_DEPENDENCIES || path.join(os.homedir(), ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies");
    return import(pathToFileURL(path.join(dependencies, "node", "node_modules", "@oai", "artifact-tool", "dist", "artifact_tool.mjs")).href);
  }
}

const { SpreadsheetFile, Workbook } = await loadArtifactTool();

const root = path.resolve(import.meta.dirname, "..");
const v2 = JSON.parse(await fs.readFile(path.join(root, "dashboard/app/data/shadow-fixture.json"), "utf8"));
const walletBundle = JSON.parse(await fs.readFile(path.join(root, "dashboard/app/data/wallet-v311-fixture.json"), "utf8"));
const wallet = walletBundle.projection;
const reviewPack = JSON.parse(await fs.readFile(path.join(root, "outputs/audit/V3.1.1-Finance-SME-Review-Pack.json"), "utf8"));
const measurementSensitivity = JSON.parse(await fs.readFile(path.join(root, "outputs/v2_validation/measurement_policy_sensitivity.json"), "utf8"));
const legacy = JSON.parse(await fs.readFile(path.join(root, "legacy/v1/fixtures/portfolio.json"), "utf8"));
const facts = Object.values(v2.facts).sort((a, b) => a.entity_id.localeCompare(b.entity_id) || a.fact_id.localeCompare(b.fact_id));
const opportunities = [...wallet.cells].sort((a, b) => a.rank - b.rank || a.opportunity_id.localeCompare(b.opportunity_id));
const evidenceQueue = [...reviewPack.facts].sort((a, b) => a.portfolio_priority_rank - b.portfolio_priority_rank || a.entity_id.localeCompare(b.entity_id) || a.fact_id.localeCompare(b.fact_id));
const outputDir = path.join(root, "outputs/audit");
const previewDir = path.join(root, "tmp/spreadsheets/public-facts-v311");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const wb = Workbook.create();
await wb.comments.setSelf({ displayName: "Corporate Wallet Digital Twin V3.1.1" });
const cover = wb.worksheets.add("Cover");
const publicFacts = wb.worksheets.add("Public Facts");
const coverage = wb.worksheets.add("Client Coverage");
const anchors = wb.worksheets.add("Approved Anchors");
const impact = wb.worksheets.add("Wallet Decision Impact");
const queue = wb.worksheets.add("Evidence Queue");
const sensitivity = wb.worksheets.add("Sensitivity");
const checks = wb.worksheets.add("Checks");
const sources = wb.worksheets.add("Sources");

const navy = "#07182A";
const blue = "#0B63E5";
const teal = "#0A8F77";
const amber = "#D99A1B";
const red = "#B33A3A";
const violet = "#7256C7";
const paleBlue = "#EEF5FF";
const paleTeal = "#EAF8F3";
const paleAmber = "#FFF6E3";
const paleRed = "#FDECEC";
const paleViolet = "#F1EDFF";
const line = "#DCE4EE";
const muted = "#5E6C7C";
const zar = (value) => Math.round(Number(value));

function title(sheet, titleText, subtitle, lastCol) {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastCol}1`).merge();
  sheet.getRange("A1").values = [[titleText]];
  sheet.getRange(`A1:${lastCol}1`).format = {
    fill: navy,
    font: { bold: true, color: "#FFFFFF", size: 20 },
    rowHeight: 35,
    verticalAlignment: "center",
  };
  sheet.getRange(`A2:${lastCol}2`).merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${lastCol}2`).format = {
    fill: "#F5F8FC",
    font: { color: muted, size: 10 },
    rowHeight: 26,
    verticalAlignment: "center",
    wrapText: true,
  };
}

function header(sheet, address, fill = blue) {
  sheet.getRange(address).format = {
    fill,
    font: { bold: true, color: "#FFFFFF", size: 9 },
    horizontalAlignment: "left",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: line },
    rowHeight: 30,
  };
}

function body(sheet, address) {
  sheet.getRange(address).format = {
    font: { color: navy, size: 9 },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: line },
  };
}

// Cover and decision boundary.
title(cover, "Corporate Wallet Digital Twin V3.1.1", "Public Facts, Approval, Anchor & Wallet-Impact Register | as of 2026-06-30", "J");
cover.getRange("A4:J4").merge();
cover.getRange("A4").values = [["Governed evidence and decision snapshot"]];
cover.getRange("A4:J4").format = { fill: blue, font: { bold: true, color: "#FFFFFF", size: 12 }, rowHeight: 26 };
cover.getRange("A6:B12").values = [
  ["Public E1 facts", null],
  ["Clients with E1 coverage", null],
  ["Finance-SME approved", null],
  ["Pending SME review", null],
  ["Approved showcase anchors", null],
  ["Wallet cells (20 x 5)", null],
  ["Prior-led wallet cells", null],
];
cover.getRange("B6").formulas = [["=COUNTA('Public Facts'!A5:A86)"]];
cover.getRange("B7").formulas = [["=COUNTA('Client Coverage'!A5:A24)"]];
cover.getRange("B8").formulas = [["=COUNTIF('Public Facts'!M5:M86,\"APPROVED\")"]];
cover.getRange("B9").formulas = [["=COUNTIF('Public Facts'!M5:M86,\"PENDING_REVIEW\")"]];
cover.getRange("B10").formulas = [["=COUNTA('Approved Anchors'!A5:A19)"]];
cover.getRange("B11").formulas = [["=COUNTA('Wallet Decision Impact'!A5:A104)"]];
cover.getRange("B12").formulas = [["=COUNTIF('Wallet Decision Impact'!H5:H104,\"E0\")"]];
cover.getRange("D6:E12").values = [
  ["Approved anchored cells", null],
  ["Developer-verified pending facts", reviewPack.qa.developer_verified],
  ["Priority review clients", reviewPack.portfolio_prioritisation.selected_client_count],
  ["Trade Finance first-rank frequency", v2.sensitivity.product_summary["Trade finance"].first_rank_frequency],
  ["Trade Finance mean top-10 share", v2.sensitivity.product_summary["Trade finance"].mean_top10_share],
  ["Trade Finance majority frequency", v2.sensitivity.product_summary["Trade finance"].majority_dominance_frequency],
  ["Bank-production state", wallet.release.bank_production_status],
];
cover.getRange("E6").formulas = [["=COUNTIF('Wallet Decision Impact'!H5:H104,\"E1\")"]];
cover.getRange("A6:A12").format = { fill: paleBlue, font: { bold: true, color: navy } };
cover.getRange("D6:D12").format = { fill: paleViolet, font: { bold: true, color: navy } };
cover.getRange("B6:B12").format = { font: { bold: true, color: teal, size: 14 } };
cover.getRange("E6:E12").format = { font: { bold: true, color: violet, size: 14 } };
cover.getRange("E9:E11").format.numberFormat = "0.0%";
cover.getRange("A14:J14").merge();
cover.getRange("A14").values = [["Claim boundary — enforced in the workbook and product"]];
cover.getRange("A14:J14").format = { fill: amber, font: { bold: true, color: "#FFFFFF" }, rowHeight: 24 };
cover.getRange("A15:J19").merge();
cover.getRange("A15").values = [["The source estate contains 82 E1 public facts: 31 APPROVED and 51 PENDING_REVIEW. Deterministic QA marks all 51 pending records DEVELOPER_VERIFIED, but that state is not finance-SME approval. Exactly 15 client-product cells may use approved anchors; 85 remain E0 prior-led. The active E1 pooling weight is 0.35 under v2-wallet-measurement-policy-1.1.0; the V1 weight 0.84 is retired. Typed/derived claims are not additional audited observations. No competitor share or causal uplift is labelled measured."]];
cover.getRange("A15:J19").format = { fill: paleAmber, font: { color: "#72520C", size: 10 }, wrapText: true, verticalAlignment: "top", borders: { preset: "outside", style: "thin", color: "#E8C97D" } };
cover.getRange("A21:J21").merge();
cover.getRange("A21").values = [["Trade Finance is first-ranked in 100% and majority-dominant in 87.8% of the current 10,000 governed benchmark draws. Under the separate E1-weight sweep it stays first but its top-10 share falls from 70% to 30%. Dominance is an output to re-test, never a release condition."]];
cover.getRange("A21:J21").format = { fill: paleTeal, font: { bold: true, color: teal, size: 10 }, rowHeight: 31, wrapText: true };
cover.getRange("A:J").format.columnWidth = 16;
cover.getRange("A:A").format.columnWidth = 34;
cover.getRange("D:D").format.columnWidth = 38;
cover.freezePanes.freezeRows(2);

// Public facts: one row per canonical point-in-time fact.
title(publicFacts, "Canonical Public Facts", "82 point-in-time E1 facts across 20 clients; approval and source lineage are explicit.", "R");
const factHeaders = ["Fact ID", "Entity ID", "Entity name", "Concept", "Value", "Unit", "Currency", "Period start", "Period end", "Available date", "Evidence tier", "Confidence", "Approval status", "Source title", "Page", "Source URL", "Document SHA-256", "V3.1.1 use boundary"];
publicFacts.getRange("A4:R4").values = [factHeaders];
header(publicFacts, "A4:R4");
const factRows = facts.map((fact) => [fact.fact_id, fact.entity_id, fact.entity_name, fact.concept, fact.value, fact.unit, fact.currency, fact.period_start, fact.period_end, fact.available_date, fact.tier, fact.confidence, fact.approval_status, fact.source_title, fact.page, fact.source_url, fact.document_hash, fact.approval_status === "APPROVED" ? "APPROVED: may activate a governed E1 anchor" : "DEVELOPER_VERIFIED / PENDING_REVIEW: excluded from all active anchors and eligible claim paths"]);
publicFacts.getRange(`A5:R${4 + factRows.length}`).values = factRows;
body(publicFacts, `A5:R${4 + factRows.length}`);
publicFacts.getRange(`E5:E${4 + factRows.length}`).format.numberFormat = "#,##0.00";
publicFacts.getRange(`L5:L${4 + factRows.length}`).format.numberFormat = "0.0%";
publicFacts.getRange(`A5:R${4 + factRows.length}`).conditionalFormats.add("expression", { formula: "=$M5=\"APPROVED\"", format: { fill: paleTeal } });
publicFacts.getRange(`A5:R${4 + factRows.length}`).conditionalFormats.add("expression", { formula: "=$M5=\"PENDING_REVIEW\"", format: { fill: paleAmber } });
for (let index = 0; index < facts.length; index += 1) {
  const row = index + 5;
  await wb.comments.addThread({ cell: publicFacts.getRange(`P${row}`) }, `Source: ${facts[index].source_url}\nPage: ${facts[index].page}\nAvailable: ${facts[index].available_date}\nSHA-256: ${facts[index].document_hash}`);
}
publicFacts.freezePanes.freezeRows(4);
publicFacts.getRange("A:R").format.columnWidth = 14;
publicFacts.getRange("A:A").format.columnWidth = 25;
publicFacts.getRange("C:D").format.columnWidth = 23;
publicFacts.getRange("N:N").format.columnWidth = 40;
publicFacts.getRange("P:P").format.columnWidth = 48;
publicFacts.getRange("Q:Q").format.columnWidth = 34;
publicFacts.getRange("R:R").format.columnWidth = 38;

// Formula-driven coverage by client.
title(coverage, "Client Evidence Coverage", "Coverage counts derive directly from the Public Facts sheet; approval is not inferred from presence.", "J");
coverage.getRange("A4:J4").values = [["Entity ID", "Entity name", "Total E1 facts", "Approved", "Pending review", "Approval rate", "Concepts represented", "Source documents", "Coverage status", "Decision boundary"]];
header(coverage, "A4:J4", teal);
const clientMap = new Map();
for (const fact of facts) {
  const item = clientMap.get(fact.entity_id) ?? { entity_name: fact.entity_name, concepts: new Set(), sources: new Set() };
  item.concepts.add(fact.concept);
  item.sources.add(fact.source_title);
  clientMap.set(fact.entity_id, item);
}
const clients = [...clientMap.entries()].sort(([a], [b]) => a.localeCompare(b));
coverage.getRange(`A5:J${4 + clients.length}`).values = clients.map(([entityId, item]) => [entityId, item.entity_name, null, null, null, null, [...item.concepts].sort().join(", "), item.sources.size, null, "E1 public evidence only; E3 required for measured share"]);
for (let index = 0; index < clients.length; index += 1) {
  const row = index + 5;
  coverage.getRange(`C${row}`).formulas = [[`=COUNTIF('Public Facts'!$B$5:$B$86,A${row})`]];
  coverage.getRange(`D${row}`).formulas = [[`=COUNTIFS('Public Facts'!$B$5:$B$86,A${row},'Public Facts'!$M$5:$M$86,"APPROVED")`]];
  coverage.getRange(`E${row}`).formulas = [[`=COUNTIFS('Public Facts'!$B$5:$B$86,A${row},'Public Facts'!$M$5:$M$86,"PENDING_REVIEW")`]];
  coverage.getRange(`F${row}`).formulas = [[`=IF(C${row}=0,0,D${row}/C${row})`]];
  coverage.getRange(`I${row}`).formulas = [[`=IF(D${row}=C${row},"APPROVED",IF(D${row}>0,"PARTIAL","PENDING"))`]];
}
body(coverage, `A5:J${4 + clients.length}`);
coverage.getRange(`F5:F${4 + clients.length}`).format.numberFormat = "0.0%";
coverage.getRange(`I5:I${4 + clients.length}`).conditionalFormats.add("containsText", { text: "APPROVED", format: { fill: paleTeal, font: { color: teal, bold: true } } });
coverage.getRange(`I5:I${4 + clients.length}`).conditionalFormats.add("containsText", { text: "PENDING", format: { fill: paleAmber, font: { color: "#805B0C", bold: true } } });
coverage.getRange("L4:N24").values = [["Client", "Approved", "Pending"], ...clients.map(([entityId, item], index) => [item.entity_name, null, null])];
header(coverage, "L4:N4", navy);
for (let index = 0; index < clients.length; index += 1) {
  const row = index + 5;
  coverage.getRange(`M${row}`).formulas = [[`=D${row}`]];
  coverage.getRange(`N${row}`).formulas = [[`=E${row}`]];
}
body(coverage, "L5:N24");
const coverageChart = coverage.charts.add("bar", coverage.getRange("L4:N24"));
coverageChart.title = "Approval coverage by client";
coverageChart.hasLegend = true;
coverageChart.setPosition("L27", "T47");
coverage.freezePanes.freezeRows(4);
coverage.getRange("A:J").format.columnWidth = 17;
coverage.getRange("B:B").format.columnWidth = 24;
coverage.getRange("G:G").format.columnWidth = 42;
coverage.getRange("J:J").format.columnWidth = 40;
coverage.getRange("L:L").format.columnWidth = 24;

// Approved anchor continuity for the three showcase clients.
title(anchors, "Approved Product Anchors", "15 active calculations for BHP, Glencore and Shoprite; approved facts only; E1 pooling weight 0.35.", "P");
anchors.getRange("A4:P4").values = [["Entity ID", "Entity name", "Product", "Anchor", "Low ZAR", "Base ZAR", "High ZAR", "Interval width", "Relative width", "Weight", "Formula", "Assumption", "Fact IDs", "Source pages", "Available date", "Lineage"]];
header(anchors, "A4:P4", violet);
const showcase = ["E01", "E02", "E09"];
const productOrder = ["Collections", "Payments", "Cross-border FX", "Liquidity", "Trade finance"];
const anchorRows = [];
for (const entityId of showcase) {
  const client = legacy.clients.find((item) => item.entity_id === entityId);
  for (const product of productOrder) {
    const anchor = client.public_anchors[product];
    anchorRows.push([entityId, client.entity_name, product, anchor.name, zar(anchor.low_zar), zar(anchor.base_zar), zar(anchor.high_zar), null, null, 0.35, anchor.formula, anchor.transformation_assumption, anchor.fact_ids.join(", "), anchor.source_pages.join("; "), anchor.available_date, "V1 formula frozen; V3.1.1 approval-authoritative activation; measurement policy 1.1.0"]);
  }
}
anchors.getRange(`A5:P${4 + anchorRows.length}`).values = anchorRows;
for (let index = 0; index < anchorRows.length; index += 1) {
  const row = index + 5;
  anchors.getRange(`H${row}`).formulas = [[`=G${row}-E${row}`]];
  anchors.getRange(`I${row}`).formulas = [[`=IF(F${row}=0,0,H${row}/F${row})`]];
}
body(anchors, `A5:P${4 + anchorRows.length}`);
anchors.getRange(`E5:H${4 + anchorRows.length}`).setNumberFormat("R#,##0");
anchors.getRange(`I5:J${4 + anchorRows.length}`).format.numberFormat = "0.0%";
anchors.freezePanes.freezeRows(4);
anchors.getRange("A:P").format.columnWidth = 15;
anchors.getRange("B:B").format.columnWidth = 23;
anchors.getRange("D:D").format.columnWidth = 30;
anchors.getRange("K:L").format.columnWidth = 42;
anchors.getRange("M:N").format.columnWidth = 40;
anchors.getRange("P:P").format.columnWidth = 42;

// V3 decision impact across all 100 opportunities.
title(impact, "V3.1.1 Wallet Decision Impact", "The complete 20 x 5 surface: A, T, q, q*, contestable gap, economics and approval boundary.", "T");
impact.getRange("A4:T4").values = [["Rank", "Opportunity ID", "Entity ID", "Client", "Sector", "Product", "Approval state", "Evidence tier", "Observed A", "T P10", "T P50", "T P90", "q P10", "q P50", "q P90", "q*", "G P50", "Contribution P50 ZAR", "Action now", "Claim boundary"]];
header(impact, "A4:T4");
const impactRows = opportunities.map((item) => [item.rank, item.opportunity_id, item.entity_id, item.entity_name, item.sector, item.product, item.approval_state, item.evidence_tier, zar(item.observed_activity.normalized_amount), zar(item.posterior_wallet.lower), zar(item.posterior_wallet.median), zar(item.posterior_wallet.upper), item.share_interval.lower, item.share_interval.median, item.share_interval.upper, item.target_share_scenario, zar(item.contestable_activity?.median ?? 0), zar(item.scenario_contribution?.median ?? 0), item.permitted_action_now, `${item.share_claim_class}/${item.commercial_claim_class}; ${item.anchor_activation}`]);
impact.getRange(`A5:T${4 + impactRows.length}`).values = impactRows;
body(impact, `A5:T${4 + impactRows.length}`);
impact.getRange(`I5:L${4 + impactRows.length}`).setNumberFormat("#,##0");
impact.getRange(`M5:P${4 + impactRows.length}`).format.numberFormat = "0.0%";
impact.getRange(`Q5:R${4 + impactRows.length}`).setNumberFormat("R#,##0");
impact.getRange(`A5:T${4 + impactRows.length}`).conditionalFormats.add("expression", { formula: "=$G5=\"APPROVED\"", format: { fill: paleTeal } });
impact.freezePanes.freezeRows(4);
impact.getRange("A:T").format.columnWidth = 15;
impact.getRange("B:B").format.columnWidth = 28;
impact.getRange("D:D").format.columnWidth = 23;
impact.getRange("T:T").format.columnWidth = 48;

// Evidence acquisition queue.
title(queue, "Finance-SME Four-Eyes Queue", "51 developer-verified candidates; workflow priority covers 81.79% of prior-led scenario value; every human decision field is blank.", "N");
queue.getRange("A4:N4").values = [["Priority rank", "80% cohort", "Fact ID", "Entity ID", "Client", "Concept", "Value", "Currency", "Unit", "Page", "Developer QA", "Approval", "Finance SME decision", "Independent approver decision"]];
header(queue, "A4:N4", violet);
const queueRows = evidenceQueue.map((item) => [item.portfolio_priority_rank, item.in_80pct_review_priority ? "PRIORITY" : "DEFERRED", item.fact_id, item.entity_id, item.entity_name, item.concept, item.value, item.currency, item.unit, item.page, item.developer_qa_state, item.approval_status, "", ""]);
queue.getRange(`A5:N${4 + queueRows.length}`).values = queueRows;
body(queue, `A5:N${4 + queueRows.length}`);
queue.getRange(`G5:G${4 + queueRows.length}`).setNumberFormat("#,##0.00");
queue.getRange(`A5:N${4 + queueRows.length}`).conditionalFormats.add("expression", { formula: "=$B5=\"SELECTED\"", format: { fill: paleTeal } });
queue.freezePanes.freezeRows(4);
queue.getRange("A:N").format.columnWidth = 16;
queue.getRange("C:C").format.columnWidth = 34;
queue.getRange("E:E").format.columnWidth = 26;
queue.getRange("F:F").format.columnWidth = 30;
queue.getRange("M:N").format.columnWidth = 32;

// Global 10,000-draw sensitivity.
title(sensitivity, "Global Sensitivity", "10,000 reproducible Latin-hypercube draws; product dominance is an output, never a release condition.", "J");
sensitivity.getRange("A4:J4").values = [["Product", "First-ranked frequency", "Mean top-10 share", "Majority-dominance frequency", "Economics P05", "Economics P50", "Economics P95", "Trade Finance first?", "Trade Finance majority?", "Interpretation"]];
header(sensitivity, "A4:J4", violet);
const productSummary = Object.entries(v2.sensitivity.product_summary);
const sensitivityRows = productSummary.map(([product, item]) => [product, item.first_rank_frequency, item.mean_top10_share, item.majority_dominance_frequency, zar(item.absolute_economics.p05), zar(item.absolute_economics.p50), zar(item.absolute_economics.p95), product === "Trade finance" && item.first_rank_frequency >= 0.5 ? "YES" : "NO", product === "Trade finance" && item.majority_dominance_frequency >= 0.5 ? "YES" : "NO", product === "Trade finance" ? (item.majority_dominance_frequency >= 0.5 ? "Dominant in the 10,000-draw benchmark; must be re-tested with approved rates and E3 evidence" : "First-ranked but not majority-dominant") : item.majority_dominance_frequency >= 0.5 ? "Frequently occupies the majority of top 10" : "Not dominant"]);
sensitivity.getRange(`A5:J${4 + sensitivityRows.length}`).values = sensitivityRows;
body(sensitivity, `A5:J${4 + sensitivityRows.length}`);
sensitivity.getRange(`B5:D${4 + sensitivityRows.length}`).format.numberFormat = "0.0%";
sensitivity.getRange(`E5:G${4 + sensitivityRows.length}`).setNumberFormat("R#,##0");
sensitivity.getRange("A12:D12").values = [["Draws", "Seed", "Version", "Correlation policy"]];
header(sensitivity, "A12:D12", navy);
sensitivity.getRange("A13:D13").values = [[v2.sensitivity.draws, v2.sensitivity.seed, v2.sensitivity.version, "Governed matrix in canonical fixture"]];
body(sensitivity, "A13:D13");
sensitivity.getRange("F12:J12").values = [["Driver", "Absolute rank correlation", "Priority", "Policy use", "Boundary"]];
header(sensitivity, "F12:J12", teal);
const voiRows = v2.sensitivity.value_of_information.map((item, index) => [item.driver, item.absolute_rank_correlation, index + 1, "Evidence/rate calibration priority", "Sensitivity, not causality"]);
sensitivity.getRange(`F13:J${12 + voiRows.length}`).values = voiRows;
body(sensitivity, `F13:J${12 + voiRows.length}`);
sensitivity.getRange(`G13:G${12 + voiRows.length}`).format.numberFormat = "0.0%";
sensitivity.getRange("A:J").format.columnWidth = 20;
sensitivity.getRange("J:J").format.columnWidth = 38;
sensitivity.getRange("A25:J25").values = [["E1 weight", "Mean width", "Coverage 90%", "CRPS", "Top-10 changes", "Trade first-rank", "Trade top-10 share", "Trade majority", "Policy status", "Interpretation"]];
header(sensitivity, "A25:J25", amber);
const weightRows = Object.entries(measurementSensitivity.arms).map(([weight, item]) => [Number(weight), item.known_truth_diagnostics.median_wallet_interval_width_zar, item.known_truth_diagnostics.wallet_90_coverage, item.known_truth_diagnostics.wallet_scaled_crps, weight === "0.35" ? 0 : measurementSensitivity.comparisons[weight].top8_overlap_with_baseline, item.trade_finance.first_ranked ? 1 : 0, item.trade_finance.top10_share, item.trade_finance.majority_dominant ? 1 : 0, weight === "0.35" ? "ACTIVE" : "SENSITIVITY", `${item.known_truth_diagnostics.status}; ranking sensitivity only, not client calibration`]);
sensitivity.getRange(`A26:J${25 + weightRows.length}`).values = weightRows;
body(sensitivity, `A26:J${25 + weightRows.length}`);
sensitivity.getRange(`A26:A${25 + weightRows.length}`).format.numberFormat = "0%";
sensitivity.getRange(`C26:D${25 + weightRows.length}`).format.numberFormat = "0.0000";
sensitivity.getRange(`F26:H${25 + weightRows.length}`).format.numberFormat = "0.0%";

// Formula checks.
title(checks, "V3 Register Control Checks", "All checks must evaluate PASS before the workbook is accepted as a submission artifact.", "F");
checks.getRange("A4:F4").values = [["Check", "Expected", "Actual", "Status", "Control meaning", "Owner"]];
header(checks, "A4:F4", teal);
const checkRows = [
  ["Public fact count", 82, "=COUNTA('Public Facts'!A5:A86)", "All canonical facts loaded", "Evidence service"],
  ["Client coverage", 20, "=COUNTA('Client Coverage'!A5:A24)", "All showcase relationships represented", "Data owner"],
  ["Approved facts", 31, "=COUNTIF('Public Facts'!M5:M86,\"APPROVED\")", "Approval is explicit", "Finance SME"],
  ["Pending facts", 51, "=COUNTIF('Public Facts'!M5:M86,\"PENDING_REVIEW\")", "Pending facts are not promoted", "Finance SME"],
  ["E1 tier completeness", 82, "=COUNTIF('Public Facts'!K5:K86,\"E1\")", "No tier silently defaulted", "Evidence service"],
  ["Page citation completeness", 0, "=COUNTBLANK('Public Facts'!O5:O86)", "Every fact has a page", "Evidence service"],
  ["Available-date completeness", 0, "=COUNTBLANK('Public Facts'!J5:J86)", "Point-in-time eligibility", "Model risk"],
  ["Approved anchors", 15, "=COUNTA('Approved Anchors'!A5:A19)", "Five anchors for each showcase client", "Product finance"],
  ["Wallet cell count", 100, "=COUNTA('Wallet Decision Impact'!A5:A104)", "20 clients x five products", "Model owner"],
  ["Approved anchored cells", 15, "=COUNTIF('Wallet Decision Impact'!H5:H104,\"E1\")", "Only approved facts activate anchors", "Model risk"],
  ["Prior-led cells", 85, "=COUNTIF('Wallet Decision Impact'!H5:H104,\"E0\")", "Pending facts excluded", "Model risk"],
  ["Developer-verified pending facts", 51, "=COUNTIF('Evidence Queue'!K5:K55,\"DEVELOPER_VERIFIED\")", "QA is not approval", "Evidence owner"],
  ["Measured competitor shares", 0, "=COUNTIF('Wallet Decision Impact'!T5:T104,\"*MEASURED*\")", "No inferred share is measured", "Model risk"],
  ["Trade Finance first-ranked frequency", 1, `='Sensitivity'!B${5 + productSummary.findIndex(([product]) => product === "Trade finance")}`, "Dominance is read from sensitivity output", "Model risk"],
  ["Trade Finance majority frequency", v2.sensitivity.product_summary["Trade finance"].majority_dominance_frequency, `='Sensitivity'!D${5 + productSummary.findIndex(([product]) => product === "Trade finance")}`, "Reported, never hard-coded as a release gate", "Model risk"],
];
checks.getRange(`A5:F${4 + checkRows.length}`).values = checkRows.map(([name, expected, , meaning, owner]) => [name, expected, null, null, meaning, owner]);
for (let index = 0; index < checkRows.length; index += 1) {
  const row = index + 5;
  checks.getRange(`C${row}`).formulas = [[checkRows[index][2]]];
  checks.getRange(`D${row}`).formulas = [[`=IF(ABS(C${row}-B${row})<0.0001,"PASS","FAIL")`]];
}
body(checks, `A5:F${4 + checkRows.length}`);
checks.getRange(`D5:D${4 + checkRows.length}`).conditionalFormats.add("containsText", { text: "PASS", format: { fill: paleTeal, font: { color: teal, bold: true } } });
checks.getRange(`D5:D${4 + checkRows.length}`).conditionalFormats.add("containsText", { text: "FAIL", format: { fill: paleRed, font: { color: red, bold: true } } });
checks.getRange("A:F").format.columnWidth = 22;
checks.getRange("A:A").format.columnWidth = 34;
checks.getRange("E:E").format.columnWidth = 42;
checks.getRange("F:F").format.columnWidth = 25;

// Unique source register.
title(sources, "Public Source Register", "Unique documents underlying the 82 facts; URLs, pages, point-in-time availability and approval counts remain traceable.", "J");
sources.getRange("A4:J4").values = [["Source title", "Entity ID", "Client", "Fact count", "Approved", "Pending", "Pages used", "Latest period end", "Latest available date", "Official URL"]];
header(sources, "A4:J4");
const sourceMap = new Map();
for (const fact of facts) {
  const key = `${fact.entity_id}|${fact.source_title}|${fact.source_url}`;
  const item = sourceMap.get(key) ?? { entity_id: fact.entity_id, entity_name: fact.entity_name, title: fact.source_title, url: fact.source_url, pages: new Set(), periods: [], dates: [] };
  item.pages.add(fact.page);
  item.periods.push(fact.period_end);
  item.dates.push(fact.available_date);
  sourceMap.set(key, item);
}
const sourceRows = [...sourceMap.values()].sort((a, b) => a.entity_id.localeCompare(b.entity_id) || a.title.localeCompare(b.title));
sources.getRange(`A5:J${4 + sourceRows.length}`).values = sourceRows.map((item) => [item.title, item.entity_id, item.entity_name, null, null, null, [...item.pages].sort((a, b) => a - b).join(", "), item.periods.sort().at(-1), item.dates.sort().at(-1), item.url]);
for (let index = 0; index < sourceRows.length; index += 1) {
  const row = index + 5;
  sources.getRange(`D${row}`).formulas = [[`=COUNTIFS('Public Facts'!$B$5:$B$86,B${row},'Public Facts'!$N$5:$N$86,A${row})`]];
  sources.getRange(`E${row}`).formulas = [[`=COUNTIFS('Public Facts'!$B$5:$B$86,B${row},'Public Facts'!$N$5:$N$86,A${row},'Public Facts'!$M$5:$M$86,"APPROVED")`]];
  sources.getRange(`F${row}`).formulas = [[`=COUNTIFS('Public Facts'!$B$5:$B$86,B${row},'Public Facts'!$N$5:$N$86,A${row},'Public Facts'!$M$5:$M$86,"PENDING_REVIEW")`]];
  await wb.comments.addThread({ cell: sources.getRange(`J${row}`) }, `Official source: ${sourceRows[index].url}`);
}
body(sources, `A5:J${4 + sourceRows.length}`);
sources.getRange("A:J").format.columnWidth = 18;
sources.getRange("A:A").format.columnWidth = 44;
sources.getRange("C:C").format.columnWidth = 24;
sources.getRange("G:G").format.columnWidth = 26;
sources.getRange("J:J").format.columnWidth = 52;

const sheetNames = ["Cover", "Public Facts", "Client Coverage", "Approved Anchors", "Wallet Decision Impact", "Evidence Queue", "Sensitivity", "Checks", "Sources"];
for (const sheetName of sheetNames) {
  const preview = await wb.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName.toLowerCase().replaceAll(" ", "-")}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const selectedInspection = {
  sheets: (await wb.inspect({ kind: "sheet", include: "id,name", maxChars: 5000 })).ndjson,
  cover: (await wb.inspect({ kind: "region", sheetId: "Cover", range: "A1:J21", maxChars: 12000 })).ndjson,
  facts: (await wb.inspect({ kind: "region", sheetId: "Public Facts", range: "A4:R10", maxChars: 12000 })).ndjson,
  coverage: (await wb.inspect({ kind: "region", sheetId: "Client Coverage", range: "A4:J24", maxChars: 20000 })).ndjson,
  checks: (await wb.inspect({ kind: "region", sheetId: "Checks", range: `A4:F${4 + checkRows.length}`, maxChars: 16000 })).ndjson,
};
await fs.writeFile(path.join(outputDir, "Public-Facts-Anchor-Register.inspect.json"), JSON.stringify(selectedInspection, null, 2));

const errors = [];
for (const sheetName of sheetNames) {
  const values = wb.worksheets.getItem(sheetName).getUsedRange()?.values ?? [];
  values.forEach((row, rowIndex) => row.forEach((value, colIndex) => {
    if (typeof value === "string" && /^#(REF|DIV\/0|VALUE|NAME|N\/A|NUM|NULL)!?/.test(value)) errors.push({ sheetName, row: rowIndex + 1, col: colIndex + 1, value });
  }));
}
if (errors.length) throw new Error(`Formula errors: ${JSON.stringify(errors)}`);

const output = await SpreadsheetFile.exportXlsx(wb);
const outputPath = path.join(outputDir, "Public-Facts-Anchor-Register-V3.1.1.xlsx");
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, previewDir, sheets: sheetNames, factCount: facts.length, clientCount: clients.length, anchorCount: anchorRows.length, opportunityCount: opportunities.length, errors }, null, 2));
