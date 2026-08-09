import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = path.resolve(import.meta.dirname, "../outputs/audit/Public-Facts-Anchor-Register.xlsx");
const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheetNames = workbook.worksheets.items.map((sheet) => sheet.name);
const errors = [];
for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  const values = used?.values ?? [];
  values.forEach((row, rowIndex) => row.forEach((value, colIndex) => {
    if (typeof value === "string" && /^#(REF|DIV\/0|VALUE|NAME|N\/A|NUM|NULL)!?/.test(value)) {
      errors.push({ sheet: sheet.name, row: rowIndex + 1, col: colIndex + 1, value });
    }
  }));
}
const checks = workbook.worksheets.getItem("Checks").getRange("A4:F12").values;
const formulas = workbook.worksheets.getItem("Derived Anchors").getRange("D5:H19").formulas;
if (errors.length) throw new Error(`Workbook contains formula errors: ${JSON.stringify(errors)}`);
if (checks.slice(1).some((row) => row[4] !== "PASS")) throw new Error(`Workbook checks failed: ${JSON.stringify(checks)}`);
console.log(JSON.stringify({ workbookPath, sheetNames, errors, checks, derivedAnchorFormulaRows: formulas.length }, null, 2));
