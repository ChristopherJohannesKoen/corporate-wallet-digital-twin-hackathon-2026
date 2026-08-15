import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the V3.2.0 wallet-first shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>Corporate Wallet Digital Twin V3\.2\.0 · Promotion Readiness<\/title>/i);
  assert.match(html, /Corporate Wallet Digital Twin V3\.2\.0/i);
});

test("uses V3.2.0 metadata and never ships the full fixture from the page", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);
  assert.match(page, /<Dashboard/);
  assert.match(layout, /Corporate Wallet Digital Twin V3\.2\.0/);
  assert.match(packageJson, /"version": "3.2.0"/);
  // promotion-fixture joins the deny-list: the page must fetch it through the
  // API route like every other fixture, not inline it into the served HTML.
  assert.doesNotMatch(page, /wallet-v311-fixture|v31-fixture|promotion-fixture|conversation_summaries|business_twins/);
  assert.doesNotMatch(page + layout, /codex-preview|_sites-preview|Starter Project/);
});

test("the promotion view publishes two scores and never a combined one", async () => {
  const dashboard = await readFile(new URL("../app/Dashboard.tsx", import.meta.url), "utf8");
  assert.match(dashboard, /Promotion readiness/);
  assert.match(dashboard, /promotion_machinery_readiness/);
  assert.match(dashboard, /bank_evidence_readiness/);
  // The prohibition that a later refactor could undo without anyone noticing.
  // Enforced in Python by assert_no_composite_score; enforced here so it cannot
  // be reintroduced in the view alone.
  assert.doesNotMatch(dashboard, /promotability|overall_readiness|composite_score|readiness_score/i);
});

test("simulated and elapsed bank days are rendered as a pair", async () => {
  const dashboard = await readFile(new URL("../app/Dashboard.tsx", import.meta.url), "utf8");
  // The second number is what keeps the first honest. A view showing only the
  // rehearsal count would read as a month of bank operation.
  assert.match(dashboard, /consecutive_clean_rehearsal_days/);
  assert.match(dashboard, /elapsed_bank_shadow_days/);
});
