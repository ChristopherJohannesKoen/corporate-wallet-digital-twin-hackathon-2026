import { promotionFixture, proxyWalletApi, v31PointInTime } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const invalid = v31PointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  const remote = await proxyWalletApi(`/v3/promotion/readiness${url.search}`);
  if (remote) return remote;
  // The fixture is a rehearsal and the header says so. A consumer that cannot
  // tell rehearsal data from bank data would be exactly the confusion the
  // REAL/REHEARSAL split exists to prevent.
  return Response.json(promotionFixture, {
    headers: { "cache-control": "no-store", "x-wallet-mode": "governed-v32-rehearsal-fixture" },
  });
}
