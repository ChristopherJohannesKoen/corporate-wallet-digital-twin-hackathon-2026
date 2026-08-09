import { fixture, pointInTime, proxyWalletApi } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ clientId: string }> }) {
  const { clientId } = await params;
  const url = new URL(request.url);
  const remote = await proxyWalletApi(`/v1/clients/${encodeURIComponent(clientId)}/twin${url.search}`);
  if (remote) return remote;
  const invalid = pointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  const client = fixture.clients[clientId];
  if (!client) return Response.json({ detail: "client not found" }, { status: 404 });
  return Response.json({
    client,
    opportunities: fixture.opportunities.filter((item) => item.entity_id === clientId),
    recommendations_visible_to_rm: false,
    shadow_notice: fixture.metadata.watermark,
  });
}
