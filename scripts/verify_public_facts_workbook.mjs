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

const { FileBlob, SpreadsheetFile } = await loadArtifactTool();

const workbookPath = path.resolve(import.meta.dirname, "../outputs/audit/Public-Facts-Anchor-Register-V3.2.0.xlsx");
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheetNames = workbook.worksheets.items.map((sheet) => sheet.name);
const expectedSheets = ["Cover", "Public Facts", "Client Coverage", "Approved Anchors", "Wallet Decision Impact", "Evidence Queue", "Sensitivity", "Promotion Readiness", "Checks", "Sources"];
const errors = [];
for (const sheet of workbook.worksheets.items) {
  const values = sheet.getUsedRange()?.values ?? [];
  values.forEach((row, rowIndex) => row.forEach((value, colIndex) => {
    if (typeof value === "string" && /^#(REF|DIV\/0|VALUE|NAME|N\/A|NUM|NULL)!?/.test(value)) errors.push({ sheet: sheet.name, row: rowIndex + 1, col: colIndex + 1, value });
  }));
}
const checks = workbook.worksheets.getItem("Checks").getUsedRange().values;
if (JSON.stringify(sheetNames) !== JSON.stringify(expectedSheets)) throw new Error(`Unexpected sheets: ${JSON.stringify(sheetNames)}`);
if (errors.length) throw new Error(`Workbook contains formula errors: ${JSON.stringify(errors)}`);
if (checks.slice(4).filter((row) => row[0]).some((row) => row[3] !== "PASS")) throw new Error(`Workbook checks failed: ${JSON.stringify(checks)}`);
if (workbook.worksheets.getItem("Public Facts").getRange("A5:A86").values.flat().filter(Boolean).length !== 82) throw new Error("Expected 82 facts");
if (workbook.worksheets.getItem("Client Coverage").getRange("A5:A24").values.flat().filter(Boolean).length !== 20) throw new Error("Expected 20 clients");
if (workbook.worksheets.getItem("Promotion Readiness").getRange("B9:B200").values.flat().filter(Boolean).length !== 30) throw new Error("Expected 30 promotion gates");
console.log(JSON.stringify({ workbookPath, sheetNames, errors, checks }, null, 2));
