/** Cloudflare Worker entry point. Dynamic image parsing is intentionally disabled. */
import handler from "vinext/server/app-router-entry";

interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/_vinext/image") {
      return new Response("Image optimization is disabled", { status: 404 });
    }

    return handler.fetch(request, env, ctx);
  },
};

export default worker;
