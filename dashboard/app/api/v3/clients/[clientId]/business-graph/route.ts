import { proxyWalletApi, v31Fixture, v31PointInTime } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ clientId: string }> }) {
  const { clientId } = await params;
  const url = new URL(request.url);
  const invalid = v31PointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  const remote = await proxyWalletApi(`/v3/clients/${encodeURIComponent(clientId)}/business-graph${url.search}`);
  if (remote) return remote;
  const item = v31Fixture.business_graphs[clientId];
  return item
    ? Response.json(item, { headers: { "cache-control": "no-store" } })
    : Response.json({ detail: "client not found" }, { status: 404 });
}
