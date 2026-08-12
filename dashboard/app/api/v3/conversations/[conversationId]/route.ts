import { proxyWalletApi, v31Fixture, v31PointInTime } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ conversationId: string }> }) {
  const { conversationId } = await params;
  const url = new URL(request.url);
  const invalid = v31PointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  const remote = await proxyWalletApi(`/v3/conversations/${encodeURIComponent(conversationId)}${url.search}`);
  if (remote) return remote;
  const item = v31Fixture.conversations[conversationId];
  return item
    ? Response.json(item, { headers: { "cache-control": "no-store" } })
    : Response.json({ detail: "conversation not found" }, { status: 404 });
}
