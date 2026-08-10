import { pointInTime, proxyWalletApi, v3Fixture } from "@/lib/wallet-api";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const invalid = pointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  const proxied = await proxyWalletApi(`/v3/decision-lab?as_of=${encodeURIComponent(v3Fixture.metadata.as_of)}`);
  if (proxied) {
    if (!proxied.ok) return proxied;
    return Response.json(await proxied.json(), {
      headers: {
        "cache-control": "no-store",
        "x-wallet-mode": "bank-api-live-v3",
      },
    });
  }
  return Response.json(v3Fixture, {
    headers: {
      "cache-control": "no-store",
      "x-wallet-mode": "governed-v3-fixture",
    },
  });
}
