import { proxyWalletApi, v31PointInTime, walletV311Fixture } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const invalid = v31PointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  const remote = await proxyWalletApi(`/v3/wallet-portfolio${url.search}`);
  if (remote) return remote;
  return Response.json(walletV311Fixture.projection, {
    headers: { "cache-control": "no-store", "x-wallet-mode": "governed-v311-fixture" },
  });
}
