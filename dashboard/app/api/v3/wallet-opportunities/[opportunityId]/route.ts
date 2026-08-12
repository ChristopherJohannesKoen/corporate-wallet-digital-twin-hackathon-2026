import { proxyWalletApi, v31PointInTime, walletV311Fixture } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request, context: { params: Promise<{ opportunityId: string }> }) {
  const url = new URL(request.url);
  const invalid = v31PointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  const { opportunityId } = await context.params;
  const remote = await proxyWalletApi(`/v3/wallet-opportunities/${encodeURIComponent(opportunityId)}${url.search}`);
  if (remote) return remote;
  const detail = walletV311Fixture.details[opportunityId];
  if (!detail) return Response.json({ detail: `unknown wallet opportunity: ${opportunityId}` }, { status: 404 });
  return Response.json(detail, {
    headers: { "cache-control": "no-store", "x-wallet-mode": "governed-v311-fixture" },
  });
}
