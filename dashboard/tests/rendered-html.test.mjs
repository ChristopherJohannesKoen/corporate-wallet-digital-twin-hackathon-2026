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

test("server-renders the V3.1.1 wallet-first shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>Corporate Wallet Digital Twin V3\.1\.1 · Wallet Portfolio<\/title>/i);
  assert.match(html, /Corporate Wallet Digital Twin V3\.1\.1/i);
});

test("uses V3.1.1 metadata and never ships the full fixture from the page", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);
  assert.match(page, /<Dashboard/);
  assert.match(layout, /Corporate Wallet Digital Twin V3\.1\.1/);
  assert.match(packageJson, /"version": "3.1.1"/);
  assert.doesNotMatch(page, /wallet-v311-fixture|v31-fixture|conversation_summaries|business_twins/);
  assert.doesNotMatch(page + layout, /codex-preview|_sites-preview|Starter Project/);
});
