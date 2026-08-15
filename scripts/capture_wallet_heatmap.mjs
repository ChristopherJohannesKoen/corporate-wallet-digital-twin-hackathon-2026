/** Render a deterministic 20 × 5 wallet heatmap directly from the fixture.
 *
 * No dashboard server or browser session is required. The screenshot uses the
 * exact projection consumed by the workbench and preserves its scale contract:
 * scenario contribution is global; A/T/q/G are within-product relative views.
 */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const root = path.resolve(process.argv[2] || path.join(import.meta.dirname, ".."));
const output = path.join(root, "tmp", "v311-deck", "wallet-heatmap.png");
const fixture = JSON.parse(await fs.readFile(path.join(root, "dashboard", "app", "data", "wallet-v311-fixture.json"), "utf8")).projection;

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    const dependencies = process.env.CODEX_RUNTIME_DEPENDENCIES || path.join(
      os.homedir(), ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies",
    );
    return import(pathToFileURL(path.join(dependencies, "node", "node_modules", "playwright", "index.mjs")).href);
  }
}

const products = fixture.products;
const clients = [...new Map(fixture.cells.map((cell) => [cell.entity_id, {
  entity_id: cell.entity_id, entity_name: cell.entity_name, sector: cell.sector,
}])).values()].sort((a, b) => a.entity_name.localeCompare(b.entity_name));
const maxContribution = Math.max(...fixture.cells.map((cell) => cell.scenario_contribution?.median ?? 0), 1);

const money = (value) => {
  if (Math.abs(value) >= 1e9) return `R${(value / 1e9).toFixed(1)}bn`;
  if (Math.abs(value) >= 1e6) return `R${(value / 1e6).toFixed(1)}m`;
  if (Math.abs(value) >= 1e3) return `R${(value / 1e3).toFixed(0)}k`;
  return `R${value.toFixed(0)}`;
};
const escape = (value) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const productLabel = (product) => product === "Cross-border FX" ? "FX exposure" : product === "Liquidity" ? "Liquidity flow" : product;

const cells = clients.map((client) => {
  const row = products.map((product) => fixture.cells.find((cell) => cell.entity_id === client.entity_id && cell.product === product));
  return `<div class="client"><b>${escape(client.entity_name)}</b><small>${escape(client.sector)}</small></div>${row.map((cell) => {
    const value = cell.scenario_contribution?.median ?? 0;
    const heat = Math.max(.06, Math.sqrt(value / maxContribution));
    const anchored = cell.anchor_activation === "ACTIVATED";
    return `<div class="cell ${anchored ? "anchored" : "prior"}" style="--heat:${heat}"><b>${money(value)}</b><small>${anchored ? "E1 approved" : "E0 prior-led"}</small></div>`;
  }).join("")}`;
}).join("");

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;background:#fff;color:#102033;font-family:Arial,sans-serif}.wrap{width:1450px;padding:22px 26px 18px}.head{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:13px}.kicker{color:#0b6ce2;font-size:13px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.head h1{margin:5px 0 0;font-size:29px}.head p{margin:0;color:#607286;font-size:13px;text-align:right}.grid{display:grid;grid-template-columns:240px repeat(5,1fr);gap:2px;background:#dfe6ed;border:1px solid #d3dde6}.corner,.product,.client,.cell{min-height:42px;padding:6px 9px;background:#fff}.corner,.product{min-height:46px;display:flex;align-items:center;background:#07192a;color:#fff}.corner{color:#78b6ff;font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.product{justify-content:center;font-size:12px;text-align:center}.client b,.cell b,.client small,.cell small{display:block}.client b{font-size:11px}.client small,.cell small{margin-top:3px;color:#607286;font-size:8px}.cell{position:relative;background:color-mix(in srgb,#0b6ce2 calc(var(--heat)*72%),#f5f8fb);color:color-mix(in srgb,#fff calc(var(--heat)*105%),#102033);text-align:center}.cell b{font-size:12px}.cell small{color:inherit;opacity:.75}.cell:after{position:absolute;inset:auto 0 0;height:3px;content:""}.cell.anchored:after{background:#11957d}.cell.prior:after{background:#d39b36}.foot{display:flex;justify-content:space-between;margin-top:10px;color:#607286;font-size:10px}.foot b{color:#102033}.legend{display:flex;gap:18px}.legend span:before{display:inline-block;width:14px;height:3px;margin:0 5px 2px 0;content:""}.legend .a:before{background:#11957d}.legend .p:before{background:#d39b36}
</style></head><body><div class="wrap"><div class="head"><div><div class="kicker">Wallet portfolio · contestable scenario contribution</div><h1>20 relationships × 5 product lenses</h1></div><p>Global colour scale · click-through variables A / T / q / q* / G</p></div><div class="grid"><div class="corner">Client / product</div>${products.map((product) => `<div class="product">${escape(productLabel(product))}</div>`).join("")}${cells}</div><div class="foot"><div>FX and Liquidity are labelled proxies. Heterogeneous product quantities are not summed.</div><div class="legend"><span class="a"><b>15</b> approved-anchor cells</span><span class="p"><b>85</b> prior-led cells</span></div></div></div></body></html>`;

const { chromium } = await loadPlaywright();
const launch = { headless: true };
if (process.env.CHROMIUM_EXECUTABLE) launch.executablePath = process.env.CHROMIUM_EXECUTABLE;
else if (process.platform === "win32") launch.executablePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const browser = await chromium.launch(launch);
const page = await browser.newPage({ viewport: { width: 1500, height: 1120 }, deviceScaleFactor: 1.5 });
await page.setContent(html, { waitUntil: "load" });
await fs.mkdir(path.dirname(output), { recursive: true });
await page.locator(".wrap").screenshot({ path: output });
await browser.close();
console.log(JSON.stringify({ status: "PASS", output, cells: fixture.cells.length }, null, 2));
