import { proxyWalletApi, v31Fixture, v31PointInTime } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const invalid = v31PointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  const weekStart = url.searchParams.get("week_start");
  if (!weekStart) return Response.json({ detail: "week_start is required" }, { status: 422 });
  const remote = await proxyWalletApi(`/v3/decision-twin${url.search}`);
  if (remote) return remote;
  if (weekStart !== v31Fixture.projection.metadata.week_start) {
    return Response.json({ detail: `coverage plan unavailable for week ${weekStart}` }, { status: 404 });
  }
  return Response.json(v31Fixture.projection, {
    headers: { "cache-control": "no-store", "x-wallet-mode": "governed-v31-fixture" },
  });
}
