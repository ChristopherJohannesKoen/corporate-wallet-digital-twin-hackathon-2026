import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const portfolio = JSON.parse(await fs.readFile(path.join(root, "outputs/data/portfolio.json"), "utf8"));
const facts = portfolio.public_evidence.facts;
const impact = portfolio.public_evidence.anchor_impact;
const outputDir = path.join(root, "outputs/audit");
const previewDir = path.join(root, "tmp/spreadsheets/public-facts");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const wb = Workbook.create();
await wb.comments.setSelf({ displayName: "Christopher Koen" });
const cover = wb.worksheets.add("Cover");
const publicFacts = wb.worksheets.add("Public Facts");
const anchors = wb.worksheets.add("Derived Anchors");
const impactSheet = wb.worksheets.add("Anchor Impact");
const sensitivity = wb.worksheets.add("Sensitivity");
const checks = wb.worksheets.add("Checks");
const sources = wb.worksheets.add("Sources");

const navy = "#07182A";
const blue = "#0B63E5";
const teal = "#0A8F77";
const amber = "#D99A1B";
const violet = "#7256C7";
const paleBlue = "#EEF5FF";
const paleTeal = "#EAF8F3";
const paleAmber = "#FFF6E3";
const paleViolet = "#F1EDFF";
const line = "#DCE4EE";
const muted = "#5E6C7C";

function title(sheet, titleText, subtitle, lastCol) {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastCol}1`).merge();
  sheet.getRange("A1").values = [[titleText]];
  sheet.getRange(`A1:${lastCol}1`).format = {
    fill: navy,
    font: { bold: true, color: "#FFFFFF", size: 20 },
    rowHeight: 34,
    verticalAlignment: "center",
  };
  sheet.getRange(`A2:${lastCol}2`).merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${lastCol}2`).format = {
    fill: "#F5F8FC",
    font: { color: muted, size: 10 },
    rowHeight: 25,
    verticalAlignment: "center",
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
    rowHeight: 28,
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

// Cover
title(cover, "Corporate Wallet Digital Twin", "Audited Public Facts & Anchor Register · model v1.1.0 · as of 2026-06-30", "H");
cover.getRange("A4:H4").merge();
cover.getRange("A4").values = [["Decision summary"]];
cover.getRange("A4:H4").format = { fill: blue, font: { bold: true, color: "#FFFFFF", size: 12 }, rowHeight: 26 };
cover.getRange("A6:B10").values = [
  ["Audited public facts", impact.audited_public_facts],
  ["Showcase clients", impact.showcase_clients.length],
  ["Active product anchors", impact.active_product_anchors],
  ["Median relative interval reduction", impact.median_relative_interval_width_reduction],
  ["Median confidence lift", impact.median_confidence_lift],
];
cover.getRange("D6:E10").values = [
  ["High-confidence before anchors", impact.before_high_confidence_opportunities],
  ["High-confidence after anchors", impact.after_high_confidence_opportunities],
  ["Sensitivity scenarios", portfolio.sensitivity.scenario_count],
  ["Trade Finance majority scenarios", portfolio.sensitivity.trade_finance_dominant_scenarios],
  ["Trade Finance #1 scenarios", portfolio.sensitivity.scenarios.filter((x) => x.top_product === "Trade finance").length],
];
cover.getRange("A6:A10").format = { fill: paleBlue, font: { bold: true, color: navy } };
cover.getRange("D6:D10").format = { fill: paleViolet, font: { bold: true, color: navy } };
cover.getRange("B6:B10").format = { font: { bold: true, color: teal, size: 14 } };
cover.getRange("E6:E10").format = { font: { bold: true, color: violet, size: 14 } };
cover.getRange("B9:B10").format.numberFormat = "0.0%";
cover.getRange("A12:H12").merge();
cover.getRange("A12").values = [["Model boundary"]];
cover.getRange("A12:H12").format = { fill: amber, font: { bold: true, color: "#FFFFFF" }, rowHeight: 24 };
cover.getRange("A13:H17").merge();
cover.getRange("A13").values = [[
  "Audited statements supply point facts, not a complete bankable wallet. Collections and payments are accounting-identity proxies; FX exposure/notional is annualised with a declared turnover range; current debt anchors liquidity/refinancing timing; Trade Finance uses an explicit sector utilisation range. USD facts are translated at ZAR17.86/USD for model comparability and remain labelled as translated assumptions."
]];
cover.getRange("A13:H17").format = { fill: paleAmber, font: { color: "#72520C", size: 10 }, wrapText: true, verticalAlignment: "top", borders: { preset: "outside", style: "thin", color: "#E8C97D" } };
cover.getRange("A19:H19").merge();
cover.getRange("A19").values = [[portfolio.sensitivity.conclusion]];
cover.getRange("A19:H19").format = { fill: portfolio.sensitivity.trade_finance_dominant_scenarios ? paleAmber : paleTeal, font: { bold: true, color: portfolio.sensitivity.trade_finance_dominant_scenarios ? "#805B0C" : teal, size: 11 }, rowHeight: 28 };
cover.getRange("A20:H22").merge();
cover.getRange("A20").values = [["Trade Finance is still the single #1 opportunity in all nine low/base/high economic-rate × low/base/high share-prior cases, but audited evidence activates other products strongly enough that Trade Finance occupies only 2 of the top 10 in every case."]];
cover.getRange("A20:H22").format = { fill: "#F8FAFC", font: { color: muted, size: 10 }, wrapText: true, verticalAlignment: "top" };
cover.getRange("A:H").format.columnWidth = 17;
cover.getRange("A:A").format.columnWidth = 32;
cover.getRange("D:D").format.columnWidth = 34;
cover.freezePanes.freezeRows(2);

// Public Facts
title(publicFacts, "Audited Public Facts", "Source values are preserved; Value ZAR is formula-translated. Every fact carries a page and a point-in-time public date.", "R");
const factHeaders = ["Fact ID", "Entity ID", "Entity name", "Concept", "Source value", "Unit", "Currency", "FX to ZAR", "Value ZAR", "Period start", "Period end", "Available date", "Audit status", "Source title", "Page", "Source URL", "Method", "Notes"];
publicFacts.getRange("A4:R4").values = [factHeaders];
header(publicFacts, "A4:R4");
const factRows = facts.map((fact) => [
  fact.fact_id, fact.entity_id, fact.entity_name, fact.concept, fact.value, fact.unit, fact.currency,
  fact.fx_to_zar, null, fact.period_start, fact.period_end, fact.available_date, fact.audit_status,
  fact.source_title, fact.page, fact.source_url, fact.method, fact.notes,
]);
publicFacts.getRange(`A5:R${4 + factRows.length}`).values = factRows;
for (let i = 0; i < factRows.length; i += 1) {
  const row = 5 + i;
  publicFacts.getRange(`I${row}`).formulas = [[`=E${row}*1000000*H${row}`]];
  await wb.comments.addThread({ cell: publicFacts.getRange(`P${row}`) }, `Source: ${facts[i].source_url}\nPage: ${facts[i].page}\nAvailable: ${facts[i].available_date}`);
}
body(publicFacts, `A5:R${4 + factRows.length}`);
publicFacts.getRange(`E5:E${4 + factRows.length}`).format.numberFormat = "#,##0.0";
publicFacts.getRange(`H5:H${4 + factRows.length}`).format.numberFormat = "0.0000";
publicFacts.getRange(`I5:I${4 + factRows.length}`).setNumberFormat("R#,##0");
publicFacts.getRange(`A5:R${4 + factRows.length}`).conditionalFormats.add("expression", { formula: "=$M5=\"audited\"", format: { fill: "#F2FBF8" } });
publicFacts.freezePanes.freezeRows(4);
publicFacts.getRange("A:R").format.columnWidth = 14;
publicFacts.getRange("A:A").format.columnWidth = 22;
publicFacts.getRange("C:C").format.columnWidth = 21;
publicFacts.getRange("D:D").format.columnWidth = 24;
publicFacts.getRange("N:N").format.columnWidth = 35;
publicFacts.getRange("P:P").format.columnWidth = 50;
publicFacts.getRange("Q:R").format.columnWidth = 35;

// Derived Anchors
title(anchors, "Derived Product Anchors", "Formula-driven transformations from the Public Facts sheet; model values are included as tie-out checks.", "N");
const anchorHeaders = ["Entity ID", "Entity name", "Product", "Low ZAR", "Base ZAR", "High ZAR", "Model base ZAR", "Variance", "Anchor", "Formula", "Assumption", "Fact IDs", "Period end", "Available date"];
anchors.getRange("A4:N4").values = [anchorHeaders];
header(anchors, "A4:N4");
const showcaseClients = portfolio.clients.filter((client) => impact.showcase_clients.includes(client.entity_id)).sort((a, b) => a.entity_id.localeCompare(b.entity_id));
const anchorRows = [];
const paymentRowByEntity = {};
for (const client of showcaseClients) {
  for (const product of ["Collections", "Payments", "Cross-border FX", "Liquidity", "Trade finance"]) {
    const anchor = client.public_anchors[product];
    anchorRows.push([client.entity_id, client.entity_name, product, null, null, null, anchor.base_zar, null, anchor.name, anchor.formula, anchor.transformation_assumption, anchor.fact_ids.join(", "), anchor.period_end, anchor.available_date]);
    if (product === "Payments") paymentRowByEntity[client.entity_id] = 5 + anchorRows.length - 1;
  }
}
anchors.getRange(`A5:N${4 + anchorRows.length}`).values = anchorRows;
const lastFactRow = 4 + factRows.length;
const sumConcept = (row, concept) => `SUMIFS('Public Facts'!$I$5:$I$${lastFactRow},'Public Facts'!$B$5:$B$${lastFactRow},$A${row},'Public Facts'!$D$5:$D$${lastFactRow},\"${concept}\")`;
for (let i = 0; i < anchorRows.length; i += 1) {
  const row = 5 + i;
  const entityId = anchorRows[i][0];
  const product = anchorRows[i][2];
  let baseFormula;
  let lowFormula;
  let highFormula;
  if (product === "Collections") {
    baseFormula = `=${sumConcept(row, "revenue")}+${sumConcept(row, "trade_receivables_open")}-${sumConcept(row, "trade_receivables_close")}`;
    lowFormula = `=E${row}*0.88`;
    highFormula = `=E${row}*1.12`;
  } else if (product === "Payments") {
    baseFormula = `=${sumConcept(row, "operating_cost_base")}+${sumConcept(row, "inventories_close")}-${sumConcept(row, "inventories_open")}+${sumConcept(row, "trade_payables_open")}-${sumConcept(row, "trade_payables_close")}`;
    lowFormula = `=E${row}*0.88`;
    highFormula = `=E${row}*1.12`;
  } else if (product === "Cross-border FX") {
    baseFormula = `=${sumConcept(row, "fx_exposure")}*2`;
    lowFormula = `=E${row}/2`;
    highFormula = `=E${row}*2`;
  } else if (product === "Liquidity") {
    baseFormula = `=${sumConcept(row, "current_debt")}+${sumConcept(row, "short_term_facilities")}`;
    lowFormula = `=E${row}*0.75`;
    highFormula = `=E${row}*1.5`;
  } else {
    const paymentRow = paymentRowByEntity[entityId];
    const mining = entityId === "E01" || entityId === "E02";
    baseFormula = `=E${paymentRow}*${mining ? 0.03 : 0.015}`;
    lowFormula = `=E${paymentRow}*${mining ? 0.01 : 0.005}`;
    highFormula = `=E${paymentRow}*${mining ? 0.06 : 0.04}`;
  }
  anchors.getRange(`D${row}:F${row}`).formulas = [[lowFormula, baseFormula, highFormula]];
  anchors.getRange(`H${row}`).formulas = [[`=E${row}-G${row}`]];
}
body(anchors, `A5:N${4 + anchorRows.length}`);
anchors.getRange(`D5:H${4 + anchorRows.length}`).setNumberFormat("R#,##0");
anchors.getRange(`H5:H${4 + anchorRows.length}`).conditionalFormats.add("cellIs", { operator: "notEqual", formula: 0, format: { fill: "#FDECEC", font: { color: "#9C2D2D", bold: true } } });
anchors.freezePanes.freezeRows(4);
anchors.getRange("A:N").format.columnWidth = 15;
anchors.getRange("B:B").format.columnWidth = 22;
anchors.getRange("I:K").format.columnWidth = 36;
anchors.getRange("L:L").format.columnWidth = 45;

// Anchor Impact
title(impactSheet, "Evidence Impact", "Relative interval compression and confidence lift measured before versus after audited anchors.", "I");
impactSheet.getRange("A4:I4").values = [["Entity ID", "Client", "Facts", "Active anchors", "Prior-only high confidence", "After high confidence", "Median interval reduction", "Median confidence lift", "Status"]];
header(impactSheet, "A4:I4", teal);
const impactRows = Object.entries(impact.by_client).map(([entityId, item]) => [entityId, item.entity_name, item.facts, item.active_anchors, 0, item.active_anchors, item.median_interval_reduction, item.median_confidence_lift, item.active_anchors === 5 ? "Complete showcase" : "Review"]);
impactSheet.getRange(`A5:I${4 + impactRows.length}`).values = impactRows;
body(impactSheet, `A5:I${4 + impactRows.length}`);
impactSheet.getRange(`G5:H${4 + impactRows.length}`).format.numberFormat = "0.0%";
impactSheet.getRange(`G5:G${4 + impactRows.length}`).conditionalFormats.add("dataBar", { color: teal, gradient: true });
impactSheet.getRange(`K4:M${4 + impactRows.length}`).values = [
  ["Client", "Interval reduction", "Confidence lift"],
  ...impactRows.map((row) => [row[1], row[6], row[7]]),
];
header(impactSheet, "K4:M4", navy);
body(impactSheet, `K5:M${4 + impactRows.length}`);
impactSheet.getRange(`L5:M${4 + impactRows.length}`).format.numberFormat = "0.0%";
impactSheet.getRange("K:K").format.columnWidth = 22;
impactSheet.getRange("L:M").format.columnWidth = 18;
const impactChart = impactSheet.charts.add("bar", impactSheet.getRange(`K4:M${4 + impactRows.length}`));
impactChart.title = "Audited Evidence Impact";
impactChart.hasLegend = true;
impactChart.xAxis = { axisType: "textAxis" };
impactChart.yAxis = { numberFormatCode: "0%", min: 0, max: 1 };
impactChart.setPosition("K10", "R27");
impactSheet.getRange("A:I").format.columnWidth = 18;
impactSheet.getRange("B:B").format.columnWidth = 23;

// Sensitivity
title(sensitivity, "Rate × Prior Sensitivity", "Nine explicit cases test whether Trade Finance remains dominant after public anchors are active.", "K");
sensitivity.getRange("A4:K4").values = [["Prior case", "Prior multiplier", "Rate case", "Top opportunity", "Top product", "Trade Finance top-10 count", "Trade Finance top-10 share", "Dominant?", "Portfolio gap P50", "Dominance definition", "Conclusion"]];
header(sensitivity, "A4:K4", violet);
const sensitivityRows = portfolio.sensitivity.scenarios.map((scenario) => [
  scenario.prior_case, scenario.prior_multiplier, scenario.rate_case, scenario.top_opportunity_id,
  scenario.top_product, scenario.trade_finance_top10_count, null, scenario.trade_finance_dominant ? "Yes" : "No",
  scenario.portfolio_gap_p50_zar, portfolio.sensitivity.definition, portfolio.sensitivity.conclusion,
]);
sensitivity.getRange(`A5:K${4 + sensitivityRows.length}`).values = sensitivityRows;
for (let i = 0; i < sensitivityRows.length; i += 1) {
  const row = 5 + i;
  sensitivity.getRange(`G${row}`).formulas = [[`=F${row}/10`]];
}
body(sensitivity, `A5:K${4 + sensitivityRows.length}`);
sensitivity.getRange(`B5:B${4 + sensitivityRows.length}`).format.numberFormat = "0.00x";
sensitivity.getRange(`G5:G${4 + sensitivityRows.length}`).format.numberFormat = "0%";
sensitivity.getRange(`I5:I${4 + sensitivityRows.length}`).setNumberFormat("R#,##0");
sensitivity.getRange(`H5:H${4 + sensitivityRows.length}`).conditionalFormats.add("containsText", { text: "No", format: { fill: paleTeal, font: { color: teal, bold: true } } });
sensitivity.freezePanes.freezeRows(4);
sensitivity.getRange("A:K").format.columnWidth = 17;
sensitivity.getRange("D:E").format.columnWidth = 24;
sensitivity.getRange("J:K").format.columnWidth = 42;

// Checks
title(checks, "Control Checks", "Formula checks must all return PASS or zero variance before the register is accepted.", "F");
checks.getRange("A4:F4").values = [["Check", "Formula", "Expected", "Actual", "Status", "Owner note"]];
header(checks, "A4:F4", teal);
const anchorLastRow = 4 + anchorRows.length;
const sensitivityLastRow = 4 + sensitivityRows.length;
checks.getRange("A5:F12").values = [
  ["Public fact count", "'=COUNTA('Public Facts'!A5:A35)", impact.audited_public_facts, null, null, "All point-in-time facts loaded"],
  ["Audited fact count", "'=COUNTIF('Public Facts'!M5:M35,\"audited\")", impact.audited_public_facts, null, null, "No unaudited showcase facts"],
  ["Page citation completeness", "'=COUNTBLANK('Public Facts'!O5:O35)", 0, null, null, "Every fact has a page"],
  ["Available-date completeness", "'=COUNTBLANK('Public Facts'!L5:L35)", 0, null, null, "Every fact has a public date"],
  ["Active anchor count", "'=COUNTA('Derived Anchors'!A5:A19)", impact.active_product_anchors, null, null, "Five anchors per showcase client"],
  ["Anchor formula tie-out", "'=SUM('Derived Anchors'!H5:H19)", 0, null, null, "Derived base equals pipeline base; each row is also exposed"],
  ["Sensitivity cases", "'=COUNTA(Sensitivity!A5:A13)", portfolio.sensitivity.scenario_count, null, null, "3 priors × 3 rates"],
  ["Trade Finance majority cases", "'=COUNTIF(Sensitivity!H5:H13,\"Yes\")", portfolio.sensitivity.trade_finance_dominant_scenarios, null, null, "Explicit majority definition"],
];
const checkFormulas = [
  `=COUNTA('Public Facts'!A5:A${lastFactRow})`,
  `=COUNTIF('Public Facts'!M5:M${lastFactRow},"audited")`,
  `=COUNTBLANK('Public Facts'!O5:O${lastFactRow})`,
  `=COUNTBLANK('Public Facts'!L5:L${lastFactRow})`,
  `=COUNTA('Derived Anchors'!A5:A${anchorLastRow})`,
  `=SUM('Derived Anchors'!H5:H${anchorLastRow})`,
  `=COUNTA(Sensitivity!A5:A${sensitivityLastRow})`,
  `=COUNTIF(Sensitivity!H5:H${sensitivityLastRow},"Yes")`,
];
for (let i = 0; i < checkFormulas.length; i += 1) {
  const row = 5 + i;
  checks.getRange(`D${row}`).formulas = [[checkFormulas[i]]];
  checks.getRange(`E${row}`).formulas = [[`=IF(ABS(D${row}-C${row})<0.01,"PASS","FAIL")`]];
}
body(checks, "A5:F12");
checks.getRange("E5:E12").conditionalFormats.add("containsText", { text: "PASS", format: { fill: paleTeal, font: { color: teal, bold: true } } });
checks.getRange("E5:E12").conditionalFormats.add("containsText", { text: "FAIL", format: { fill: "#FDECEC", font: { color: "#A02E2E", bold: true } } });
checks.getRange("A:F").format.columnWidth = 22;
checks.getRange("A:A").format.columnWidth = 30;
checks.getRange("B:B").format.columnWidth = 44;
checks.getRange("F:F").format.columnWidth = 35;

// Sources
title(sources, "Source Register", "Authoritative audited reports and the declared translation basis used in this prototype.", "H");
sources.getRange("A4:H4").values = [["Client", "Report", "Report period end", "Audit / approval date", "Available date", "Pages used", "Official URL", "Use in model"]];
header(sources, "A4:H4", blue);
const sourceRows = showcaseClients.map((client) => {
  const clientFacts = client.public_facts;
  return [
    client.entity_name,
    clientFacts[0].source_title,
    Math.max(...clientFacts.map((fact) => Date.parse(fact.period_end))) ? clientFacts.map((fact) => fact.period_end).sort().at(-1) : "",
    clientFacts[0].source_date,
    clientFacts.map((fact) => fact.available_date).sort().at(-1),
    [...new Set(clientFacts.map((fact) => fact.page))].join(", "),
    clientFacts[0].source_url,
    "Accounting, FX and debt-maturity anchors",
  ];
});
sourceRows.push(["Translation assumption", "Shoprite Holdings AFS 2025 closing-rate disclosure", "2025-06-29", "2025-10-01", "2025-10-13", "1", "https://www.shopriteholdings.co.za/docs/shp-afs-2025.pdf", "ZAR17.86/USD applied consistently to BHP and Glencore source-currency facts"]);
sources.getRange(`A5:H${4 + sourceRows.length}`).values = sourceRows;
body(sources, `A5:H${4 + sourceRows.length}`);
for (let i = 0; i < sourceRows.length; i += 1) {
  const row = 5 + i;
  await wb.comments.addThread({ cell: sources.getRange(`G${row}`) }, `Official source: ${sourceRows[i][6]}\nAccessed: 2026-08-07`);
}
sources.getRange("A:H").format.columnWidth = 19;
sources.getRange("B:B").format.columnWidth = 38;
sources.getRange("F:F").format.columnWidth = 26;
sources.getRange("G:G").format.columnWidth = 52;
sources.getRange("H:H").format.columnWidth = 45;

// Render every sheet and export.
const sheetNames = ["Cover", "Public Facts", "Derived Anchors", "Anchor Impact", "Sensitivity", "Checks", "Sources"];
for (const sheetName of sheetNames) {
  const preview = await wb.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName.toLowerCase().replaceAll(" ", "-")}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const selectedInspection = {
  sheets: (await wb.inspect({ kind: "sheet", include: "id,name", maxChars: 5000 })).ndjson,
  facts: (await wb.inspect({ kind: "region", sheetId: "Public Facts", range: "A4:I9", maxChars: 8000 })).ndjson,
  anchors: (await wb.inspect({ kind: "region", sheetId: "Derived Anchors", range: "A4:H19", maxChars: 12000 })).ndjson,
  checks: (await wb.inspect({ kind: "region", sheetId: "Checks", range: "A4:F12", maxChars: 10000 })).ndjson,
};
await fs.writeFile(path.join(outputDir, "Public-Facts-Anchor-Register.inspect.json"), JSON.stringify(selectedInspection, null, 2));

const errorCells = [];
for (const sheetName of sheetNames) {
  const sheet = wb.worksheets.getItem(sheetName);
  const used = sheet.getUsedRange();
  const values = used?.values ?? [];
  values.forEach((row, rowIndex) => row.forEach((value, colIndex) => {
    if (typeof value === "string" && /^#(REF|DIV\/0|VALUE|NAME|N\/A|NUM|NULL)!?/.test(value)) {
      errorCells.push({ sheetName, row: rowIndex + 1, col: colIndex + 1, value });
    }
  }));
}
if (errorCells.length) throw new Error(`Formula errors: ${JSON.stringify(errorCells)}`);

const output = await SpreadsheetFile.exportXlsx(wb);
const outputPath = path.join(outputDir, "Public-Facts-Anchor-Register.xlsx");
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, previewDir, sheets: sheetNames, factCount: facts.length, anchorCount: impact.active_product_anchors, errorCells }, null, 2));
