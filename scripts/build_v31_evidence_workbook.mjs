import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.env.PROJECT_ROOT ? path.resolve(process.env.PROJECT_ROOT) : path.resolve(import.meta.dirname, "..");
const readJson = async (relativePath) => JSON.parse(await fs.readFile(path.join(root, relativePath), "utf8"));
const claims = await readJson("outputs/v31/v31_business_evidence_claims.json");
const twins = await readJson("outputs/v31/v31_business_twins.json");
const estimatesByClient = await readJson("outputs/v31/v31_solution_estimates.json");
const plan = await readJson("outputs/v31/v31_coverage_plan.json");
const report = await readJson("outputs/v31/v31_validation_report.json");
const fixture = await readJson("dashboard/app/data/v31-fixture.json");
const coverage = fixture.projection.evidence_coverage;
const outputPath = path.join(root, "outputs/audit/Public-Facts-Anchor-Register.xlsx");
const previewDir = path.join(root, "tmp/spreadsheets/public-facts-v31");
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const wb = Workbook.create();
await wb.comments.setSelf({ displayName: "Christopher Koen" });
const cover = wb.worksheets.add("Cover");
const evidence = wb.worksheets.add("Evidence Claims");
const clientCoverage = wb.worksheets.add("Client Coverage");
const twinCoverage = wb.worksheets.add("Business Twin");
const solutions = wb.worksheets.add("Solution Estimates");
const weeklyPlan = wb.worksheets.add("Weekly Plan");
const checks = wb.worksheets.add("Checks");
const sources = wb.worksheets.add("Sources");

const C = {
  navy: "#07182A", blue: "#0B63E5", teal: "#0A8F77", amber: "#D99A1B",
  red: "#B33A3A", violet: "#7256C7", paleBlue: "#EEF5FF", paleTeal: "#EAF8F3",
  paleAmber: "#FFF6E3", paleRed: "#FDECEC", line: "#DCE4EE", muted: "#5E6C7C",
};

function title(sheet, heading, subtitle, lastCol) {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastCol}1`).merge();
  sheet.getRange("A1").values = [[heading]];
  sheet.getRange(`A1:${lastCol}1`).format = {
    fill: C.navy, font: { bold: true, color: "#FFFFFF", size: 19 }, rowHeight: 36,
    verticalAlignment: "center",
  };
  sheet.getRange(`A2:${lastCol}2`).merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${lastCol}2`).format = {
    fill: "#F5F8FC", font: { color: C.muted, size: 10 }, rowHeight: 28,
    verticalAlignment: "center", wrapText: true,
  };
}

function header(sheet, address, fill = C.blue) {
  sheet.getRange(address).format = {
    fill, font: { bold: true, color: "#FFFFFF", size: 9 }, rowHeight: 30,
    horizontalAlignment: "left", verticalAlignment: "center", wrapText: true,
    borders: { preset: "all", style: "thin", color: C.line },
  };
}

function body(sheet, address) {
  sheet.getRange(address).format = {
    font: { color: C.navy, size: 9 }, verticalAlignment: "top", wrapText: true,
    borders: { preset: "all", style: "thin", color: C.line },
  };
}

function scalar(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "object") return JSON.stringify(value);
  return value;
}

function intervalMedian(item) {
  return item?.median ?? null;
}

// Cover: formula-driven, with every material interpretation boundary visible.
title(cover, "Corporate Wallet Digital Twin V3.1", "Business Evidence, Decision Impact & Release Register | as of 2026-06-30", "J");
cover.getRange("A4:J4").merge();
cover.getRange("A4").values = [["Governed V3.1 demonstration snapshot"]];
cover.getRange("A4:J4").format = { fill: C.blue, font: { bold: true, color: "#FFFFFF", size: 12 }, rowHeight: 27 };
cover.getRange("A6:B14").values = [
  ["Clients", null], ["Business Twin components", null], ["Typed evidence claims", null],
  ["Approved claims", null], ["Pending finance-SME review", null], ["Audited public E1 claims", null],
  ["Solution projections", null], ["Fail-closed projections", null], ["Weekly conversations", null],
];
cover.getRange("B6").formulas = [["=COUNTA('Client Coverage'!$A$5:$A$24)"]];
cover.getRange("B7").formulas = [["=COUNTA('Business Twin'!$A$5:$A$244)"]];
cover.getRange("B8").formulas = [["=COUNTA('Evidence Claims'!$A$5:$A$909)"]];
cover.getRange("B9").formulas = [["=COUNTIF('Evidence Claims'!$P$5:$P$909,\"APPROVED\")"]];
cover.getRange("B10").formulas = [["=COUNTIF('Evidence Claims'!$P$5:$P$909,\"PENDING_REVIEW\")"]];
cover.getRange("B11").formulas = [["=COUNTIF('Evidence Claims'!$O$5:$O$909,\"E1\")"]];
cover.getRange("B12").formulas = [["=COUNTA('Solution Estimates'!$A$5:$A$324)"]];
cover.getRange("B13").formulas = [["=COUNTIF('Solution Estimates'!$H$5:$H$324,\"FAIL_CLOSED_REQUIRED_INPUT_UNAVAILABLE\")"]];
cover.getRange("B14").formulas = [["=COUNTA('Weekly Plan'!$A$5:$A$12)"]];
cover.getRange("D6:E14").values = [
  ["Problem hypotheses", report.validation.problem_hypotheses],
  ["Conversation candidates", report.validation.conversation_candidates],
  ["Discovery-only candidates", report.validation.discovery_conversations],
  ["Graph nodes", report.validation.graph_nodes],
  ["Graph edges", report.validation.graph_edges],
  ["Business events", report.validation.business_events],
  ["VOI questions evaluated", report.validation.voi_questions_evaluated],
  ["VOI questions selected", report.validation.voi_questions_selected],
  ["Bank-production state", fixture.projection.release.bank_production_status],
];
cover.getRange("A6:A14").format = { fill: C.paleBlue, font: { bold: true, color: C.navy } };
cover.getRange("D6:D14").format = { fill: "#F1EDFF", font: { bold: true, color: C.navy } };
cover.getRange("B6:B14").format = { font: { bold: true, color: C.teal, size: 14 }, numberFormat: "#,##0" };
cover.getRange("E6:E14").format = { font: { bold: true, color: C.violet, size: 14 }, numberFormat: "#,##0" };
cover.getRange("A16:J16").merge();
cover.getRange("A16").values = [["Interpretation boundary"]];
cover.getRange("A16:J16").format = { fill: C.amber, font: { bold: true, color: "#FFFFFF" }, rowHeight: 24 };
cover.getRange("A17:J21").merge();
cover.getRange("A17").values = [["This is a controlled client demonstration built from 85 public E1 claims, 820 governed/simulated E0 claims and representative policy. All 20 clients have complete structural twins and an approved critical-path signal, but none yet reaches the target of 15 reviewed E1 claims per client. The 51 pending facts cannot support eligible client-facing statements. All 224 conversations are discovery-only because material bank feasibility remains UNKNOWN. Competitor share is not measured; causal incremental value is null; production status is NOT_PROMOTABLE."]];
cover.getRange("A17:J21").format = { fill: C.paleAmber, font: { color: "#72520C", size: 10 }, wrapText: true, verticalAlignment: "top", borders: { preset: "outside", style: "thin", color: "#E8C97D" } };
cover.getRange("A23:J23").merge();
cover.getRange("A23").values = [["Decision object: client × stakeholder role × business problem × solution bundle × engagement window. Observed, identified, posterior, scenario and causal values remain separate."]];
cover.getRange("A23:J23").format = { fill: C.paleTeal, font: { bold: true, color: C.teal, size: 10 }, rowHeight: 32, wrapText: true };
cover.getRange("A:J").format.columnWidth = 16;
cover.getRange("A:A").format.columnWidth = 35;
cover.getRange("D:D").format.columnWidth = 36;
cover.freezePanes.freezeRows(2);

// Evidence: typed, point-in-time, and auditable.
title(evidence, "Typed Business Evidence Claims", "905 claims; E1 public evidence and E0 governed/simulated claims remain explicitly distinct.", "V");
const evidenceHeaders = ["Claim ID", "Entity ID", "Concept", "Kind", "Claim class", "Money", "Ratio", "Count", "Text / category / date", "Currency", "Unit", "Period start", "Period end", "Available date", "Evidence tier", "Approval status", "Critical path", "Domains", "Source title", "Page", "Source URL", "Source hash"];
evidence.getRange("A4:V4").values = [evidenceHeaders]; header(evidence, "A4:V4");
const claimRows = claims.map((c) => [
  c.claim_id, c.entity_id, c.concept, c.kind, c.claim_class, c.money_value, c.ratio_value,
  c.count_value, scalar(c.text_value ?? c.categorical_value ?? c.date_value ?? c.supporting_text),
  c.currency, c.unit, c.period_start, c.period_end, c.available_date, c.tier, c.approval_status,
  c.critical_path, c.domains.join(", "), c.source_title, c.page, c.source_url, c.source_hash,
]);
evidence.getRange(`A5:V${4 + claimRows.length}`).values = claimRows; body(evidence, `A5:V${4 + claimRows.length}`);
evidence.getRange(`F5:F${4 + claimRows.length}`).format.numberFormat = "#,##0.00;[Red](#,##0.00);-";
evidence.getRange(`G5:G${4 + claimRows.length}`).format.numberFormat = "0.0000;[Red](0.0000);-";
evidence.getRange(`H5:H${4 + claimRows.length}`).format.numberFormat = "#,##0;[Red](#,##0);-";
evidence.getRange(`A5:V${4 + claimRows.length}`).conditionalFormats.add("expression", { formula: "=$P5=\"PENDING_REVIEW\"", format: { fill: C.paleAmber } });
evidence.getRange(`A5:V${4 + claimRows.length}`).conditionalFormats.add("expression", { formula: "=$O5=\"E1\"", format: { font: { color: C.teal, bold: true } } });
evidence.freezePanes.freezeRows(4); evidence.freezePanes.freezeColumns(2);
evidence.getRange("A:V").format.columnWidth = 14;
evidence.getRange("A:A").format.columnWidth = 28; evidence.getRange("C:C").format.columnWidth = 28;
evidence.getRange("I:I").format.columnWidth = 38; evidence.getRange("R:S").format.columnWidth = 28;
evidence.getRange("U:V").format.columnWidth = 46;

// Per-client evidence coverage and threshold checks.
title(clientCoverage, "Client Evidence Coverage", "Every client has a complete structural twin; the audited E1 depth gate remains open for all 20.", "N");
clientCoverage.getRange("A4:N4").values = [["Entity ID", "Entity name", "Sector", "Claims", "Approved", "Pending", "E1 claims", "Approved E1", "Domains", "Gaps", "Critical-path fact", "15 E1 threshold", "Coverage status", "Decision impact"]];
header(clientCoverage, "A4:N4", C.teal);
const clientRows = fixture.projection.client_index.map((client) => {
  const c = coverage.per_client[client.entity_id];
  return [client.entity_id, client.entity_name, client.sector, c.claims, c.approved_claims, c.e1_pending_claims, c.e1_claims, c.e1_approved_claims, c.domains_covered, c.gaps, c.has_approved_critical_path_fact, c.meets_e1_threshold, null, c.meets_e1_threshold ? "May satisfy the public-evidence depth gate" : "Discovery only; acquire and approve more public evidence"];
});
clientCoverage.getRange("A5:N24").values = clientRows;
for (let row = 5; row <= 24; row += 1) clientCoverage.getRange(`M${row}`).formulas = [[`=IF(L${row},\"COMPLETE\",\"E1 GATE OPEN\")`]];
body(clientCoverage, "A5:N24");
clientCoverage.getRange("M5:M24").conditionalFormats.add("containsText", { text: "OPEN", format: { fill: C.paleAmber, font: { color: "#805B0C", bold: true } } });
clientCoverage.freezePanes.freezeRows(4); clientCoverage.getRange("A:N").format.columnWidth = 15;
clientCoverage.getRange("B:C").format.columnWidth = 24; clientCoverage.getRange("N:N").format.columnWidth = 46;

// Business Twin: 12 component records per client.
title(twinCoverage, "Business Model Twin", "Twelve point-in-time domains per client; unknown values remain unknown and decision impacts stay traceable.", "N");
twinCoverage.getRange("A4:N4").values = [["Entity ID", "Entity name", "Sector", "Snapshot", "Domain", "Label", "Status", "Claim class", "Evidence tier", "Materiality", "Freshness days", "Evidence claim IDs", "Missing information", "Decision impacts"]];
header(twinCoverage, "A4:N4", C.violet);
const twinRows = [];
for (const twin of Object.values(twins).sort((a, b) => a.entity_id.localeCompare(b.entity_id))) {
  for (const component of twin.components) twinRows.push([
    twin.entity_id, twin.entity_name, twin.sector, twin.snapshot_id, component.domain, component.label,
    component.status, component.claim_class, component.evidence_tier, component.materiality,
    component.freshness_days, component.evidence_claim_ids.join(", "), component.missing_information.join("; "),
    JSON.stringify(component.decision_impacts),
  ]);
}
twinCoverage.getRange(`A5:N${4 + twinRows.length}`).values = twinRows; body(twinCoverage, `A5:N${4 + twinRows.length}`);
twinCoverage.getRange(`J5:J${4 + twinRows.length}`).format.numberFormat = "0%";
twinCoverage.getRange(`A5:N${4 + twinRows.length}`).conditionalFormats.add("expression", { formula: "=$G5=\"UNKNOWN\"", format: { fill: C.paleAmber } });
twinCoverage.freezePanes.freezeRows(4); twinCoverage.freezePanes.freezeColumns(2);
twinCoverage.getRange("A:N").format.columnWidth = 16; twinCoverage.getRange("B:C").format.columnWidth = 23;
twinCoverage.getRange("D:D").format.columnWidth = 28; twinCoverage.getRange("L:N").format.columnWidth = 46;

// All 320 solution projections, including fail-closed outcomes.
title(solutions, "Client–Solution Estimates", "All 16 solution families execute for all 20 clients; each row contains an estimate or an explicit fail-closed reason.", "R");
solutions.getRange("A4:R4").values = [["Entity ID", "Entity name", "Solution", "Solution label", "Family", "Principal quantity", "Available", "Model status", "Claim class", "Evidence tier", "Need probability", "Amount low", "Amount median", "Amount high", "Currency", "P(30d)", "P(60d)", "P(90d) / unavailable reason"]];
header(solutions, "A4:R4", C.blue);
const estimateRows = [];
for (const client of fixture.projection.client_index) {
  const records = estimatesByClient[client.entity_id];
  for (const key of Object.keys(records).sort()) {
    const e = records[key];
    estimateRows.push([client.entity_id, client.entity_name, e.solution, e.solution_label, e.family, e.principal_quantity, e.available, e.model_status, e.claim_class, e.evidence_tier, e.need_probability, e.amount_interval?.lower ?? null, intervalMedian(e.amount_interval), e.amount_interval?.upper ?? null, e.amount_interval?.currency ?? null, e.timing_probability_30d, e.timing_probability_60d, e.available ? e.timing_probability_90d : e.unavailable_reason]);
  }
}
solutions.getRange(`A5:R${4 + estimateRows.length}`).values = estimateRows; body(solutions, `A5:R${4 + estimateRows.length}`);
solutions.getRange(`K5:K${4 + estimateRows.length}`).format.numberFormat = "0.0%";
solutions.getRange(`L5:N${4 + estimateRows.length}`).format.numberFormat = '"R"#,##0;[Red]("R"#,##0);-';
solutions.getRange(`P5:Q${4 + estimateRows.length}`).format.numberFormat = "0.0%";
solutions.getRange(`A5:R${4 + estimateRows.length}`).conditionalFormats.add("expression", { formula: "=$G5=FALSE", format: { fill: C.paleRed, font: { color: C.red } } });
solutions.freezePanes.freezeRows(4); solutions.freezePanes.freezeColumns(2);
solutions.getRange("A:R").format.columnWidth = 15; solutions.getRange("B:B").format.columnWidth = 24;
solutions.getRange("D:F").format.columnWidth = 26; solutions.getRange("H:H").format.columnWidth = 36; solutions.getRange("R:R").format.columnWidth = 44;

// The auditable weekly plan is a deterministic output from the CVaR policy.
title(weeklyPlan, "Eight-Conversation Weekly Coverage Plan", `Week of ${plan.week_start} | ${plan.solver} ${plan.solver_status} | 512 common scenario draws`, "Q");
weeklyPlan.getRange("A4:Q4").values = [["Rank", "Client", "Sector", "Stakeholder", "Business problem", "Solution", "Family", "Action", "Eligibility", "Client value median", "Bank value median", "Selection stability", "Expected adjusted benefit", "CVaR10", "Frontier", "Why now", "Conversation ID"]];
header(weeklyPlan, "A4:Q4", C.teal);
const planRows = plan.entries.map((p) => [p.rank, p.entity_name, fixture.projection.client_index.find((c) => c.entity_id === p.entity_id)?.sector, p.stakeholder_role, p.problem_label, p.solution_label, p.family, p.action, p.eligibility, p.client_value_median, p.bank_value_median, p.selection_stability, p.adjusted_benefit_expected, p.adjusted_benefit_cvar10, p.frontier_state, p.why_now, p.conversation_id]);
weeklyPlan.getRange("A5:Q12").values = planRows; body(weeklyPlan, "A5:Q12");
weeklyPlan.getRange("J5:K12").format.numberFormat = '"R"#,##0;[Red]("R"#,##0);-';
weeklyPlan.getRange("L5:N12").format.numberFormat = "0.0%";
weeklyPlan.getRange("A5:Q12").conditionalFormats.add("expression", { formula: "=$H5=\"DISCOVERY\"", format: { fill: C.paleAmber } });
weeklyPlan.freezePanes.freezeRows(4); weeklyPlan.getRange("A:Q").format.columnWidth = 15;
weeklyPlan.getRange("B:B").format.columnWidth = 24; weeklyPlan.getRange("E:G").format.columnWidth = 25;
weeklyPlan.getRange("P:P").format.columnWidth = 72; weeklyPlan.getRange("Q:Q").format.columnWidth = 30;

// Checks: one assertion per row and a visible aggregate status.
title(checks, "Workbook & Decision Controls", "Checks reconcile the workbook to the V3.1 validation report; open external gates are reported rather than disguised.", "H");
checks.getRange("A4:H4").values = [["Check", "Actual", "Expected", "Difference", "Tolerance", "Status", "Where to fix", "Notes"]]; header(checks, "A4:H4", C.navy);
const checkDefinitions = [
  ["Clients", "=COUNTA('Client Coverage'!$A$5:$A$24)", 20, "Contracts/evidence"],
  ["Twin components", "=COUNTA('Business Twin'!$A$5:$A$244)", 240, "Business Twin"],
  ["Typed evidence claims", "=COUNTA('Evidence Claims'!$A$5:$A$909)", 905, "Evidence programme"],
  ["Pending facts", "=COUNTIF('Evidence Claims'!$P$5:$P$909,\"PENDING_REVIEW\")", 51, "Finance-SME review"],
  ["Solution projections", "=COUNTA('Solution Estimates'!$A$5:$A$324)", 320, "Solution estimators"],
  ["Weekly plan capacity", "=COUNTA('Weekly Plan'!$A$5:$A$12)", 8, "Coverage optimizer"],
  ["Named stakeholders", report.validation.named_stakeholders_displayed, 0, "Stakeholder policy"],
  ["Opaque confidence scores", report.validation.opaque_confidence_scores, 0, "Workbench"],
  ["Measured competitor-share claims", report.validation.measured_competitor_share_claims, 0, "Claim compiler"],
  ["Causal value claims", report.validation.causal_value_claims, 0, "Experiment gate"],
];
checks.getRange("A5:H14").values = checkDefinitions.map(([label, actual, expected, fix]) => [label, typeof actual === "string" ? null : actual, expected, null, 0, null, fix, ""]);
checkDefinitions.forEach(([_, actual], index) => { if (typeof actual === "string") checks.getRange(`B${index + 5}`).formulas = [[actual]]; });
for (let row = 5; row <= 14; row += 1) {
  checks.getRange(`D${row}`).formulas = [[`=B${row}-C${row}`]];
  checks.getRange(`F${row}`).formulas = [[`=IF(ABS(D${row})<=E${row},\"OK\",\"FAIL\")`]];
}
body(checks, "A5:H14");
checks.getRange("F5:F14").conditionalFormats.add("containsText", { text: "OK", format: { fill: C.paleTeal, font: { color: C.teal, bold: true } } });
checks.getRange("F5:F14").conditionalFormats.add("containsText", { text: "FAIL", format: { fill: C.paleRed, font: { color: C.red, bold: true } } });
checks.getRange("A16:E16").merge(); checks.getRange("A16").values = [["MODEL STATUS"]];
checks.getRange("F16:H16").merge(); checks.getRange("F16").formulas = [["=IF(COUNTIF(F5:F14,\"FAIL\")=0,\"PASS — INTERNAL REPRODUCTION\",\"FAIL\")"]];
checks.getRange("A16:H16").format = { fill: C.navy, font: { bold: true, color: "#FFFFFF", size: 11 }, rowHeight: 28 };
checks.getRange("A18:H21").merge(); checks.getRange("A18").values = [["External production gates remain open: the 15-approved-E1-per-client threshold, E3 multibank calibration, bank-approved economics, bank infrastructure/identity/entitlements/SIEM, live-provider adjudication, RM pilot, randomized trial and 30 clean shadow days. Internal PASS never means bank-production promotability."]];
checks.getRange("A18:H21").format = { fill: C.paleAmber, font: { color: "#72520C", size: 10 }, wrapText: true, verticalAlignment: "top" };
checks.getRange("A:H").format.columnWidth = 18; checks.getRange("A:A").format.columnWidth = 33; checks.getRange("G:H").format.columnWidth = 40;

// Sources and model registry references.
title(sources, "Sources & Artifact Lineage", "Stable repository paths and public-source URLs needed to reproduce and audit this workbook.", "F");
sources.getRange("A4:F4").values = [["Item", "Type", "As-of", "Source / path", "Owner", "Notes"]]; header(sources, "A4:F4", C.violet);
const uniquePublicSources = [...new Map(claims.filter((c) => c.source_url).map((c) => [c.source_url, c])).values()];
const sourceRows = [
  ["V3.1 business claims", "Repository artifact", "2026-06-30", "outputs/v31/v31_business_evidence_claims.json", "Evidence service", "Typed and versioned claims"],
  ["V3.1 Business Twins", "Repository artifact", "2026-06-30", "outputs/v31/v31_business_twins.json", "Business Twin service", "Twenty point-in-time snapshots"],
  ["V3.1 solution estimates", "Repository artifact", "2026-06-30", "outputs/v31/v31_solution_estimates.json", "Wallet model service", "320 projections including fail-closed rows"],
  ["V3.1 weekly plan", "Repository artifact", "2026-07-06", "outputs/v31/v31_coverage_plan.json", "Recommendation service", "CVaR plan and constraints"],
  ["V3.1 validation", "Repository artifact", "2026-06-30", "outputs/v31/v31_validation_report.json", "Model risk", "Reproduction and open-gate report"],
  ...uniquePublicSources.map((c) => [c.source_title, c.tier === "E1" ? "Public evidence" : "Governed/simulated source", c.source_date, c.source_url, c.reviewer_role ?? "Evidence Review", `Claim ${c.claim_id}; page ${c.page ?? "n/a"}; available ${c.available_date ?? "n/a"}`]),
];
sources.getRange(`A5:F${4 + sourceRows.length}`).values = sourceRows; body(sources, `A5:F${4 + sourceRows.length}`);
sources.getRange("A:F").format.columnWidth = 20; sources.getRange("A:A").format.columnWidth = 36; sources.getRange("D:D").format.columnWidth = 75; sources.getRange("F:F").format.columnWidth = 46;
sources.freezePanes.freezeRows(4);

// Compact inspection and visual verification of every sheet before export.
const keyInspection = await wb.inspect({ kind: "table", range: "Cover!A1:J23", include: "values,formulas", tableMaxRows: 25, tableMaxCols: 12, maxChars: 5000 });
const errorInspection = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan", maxChars: 4000 });
console.log(keyInspection.ndjson);
console.log(errorInspection.ndjson);

const renderRanges = {
  Cover: "A1:J23", "Evidence Claims": "A1:V20", "Client Coverage": "A1:N24",
  "Business Twin": "A1:N24", "Solution Estimates": "A1:R24", "Weekly Plan": "A1:Q12",
  Checks: "A1:H21", Sources: `A1:F${Math.min(24, 4 + sourceRows.length)}`,
};
for (const [sheetName, range] of Object.entries(renderRanges)) {
  const preview = await wb.render({ sheetName, range, scale: 1.25, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName.replaceAll(" ", "-").toLowerCase()}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, sheets: Object.keys(renderRanges), claims: claims.length, solutions: estimateRows.length, plan: planRows.length }, null, 2));
