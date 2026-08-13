import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const dependencies = process.env.CODEX_RUNTIME_DEPENDENCIES || path.join(os.homedir(), ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies");
const { chromium } = await import(pathToFileURL(path.join(dependencies, "node", "node_modules", "playwright", "index.mjs")).href);

const root = path.resolve(import.meta.dirname, "..");
const output = path.join(root, "tmp", "v311-deck", "wallet-heatmap.png");
const baseUrl = process.env.WALLET_DASHBOARD_URL || "http://127.0.0.1:3000";
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROMIUM_EXECUTABLE || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
});
const page = await browser.newPage({ viewport: { width: 1600, height: 1050 }, deviceScaleFactor: 1.5 });
await page.goto(baseUrl, { waitUntil: "networkidle", timeout: 60_000 });
await page.getByRole("heading", { name: /Find the wallet gap/i }).waitFor({ timeout: 30_000 });
await page.addStyleTag({ content: `
  .dt-heatmap{gap:1px!important;padding:8px 10px!important}
  .dt-heat-corner,.dt-heat-head,.dt-heat-client,.dt-heat-cell{min-height:24px!important;padding:3px 5px!important}
  .dt-heat-client b,.dt-heat-cell b{font-size:7px!important}
  .dt-heat-client small,.dt-heat-cell small{margin-top:1px!important;font-size:4.5px!important}
  .dt-heatmap-note{padding:6px 12px!important;font-size:6px!important}
` });
const heatmap = page.locator(".dt-heatmap");
await heatmap.waitFor({ state: "visible" });
await fs.mkdir(path.dirname(output), { recursive: true });
await heatmap.screenshot({ path: output });
await browser.close();
console.log(output);
