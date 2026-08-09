import { fixture, pointInTime, proxyWalletApi } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const asOf = url.searchParams.get("as_of");
  const remote = await proxyWalletApi(`/v1/opportunities${url.search}`);
  if (remote) return remote;
  const invalid = pointInTime(asOf);
  if (invalid) return invalid;
  const product = url.searchParams.get("product");
  const clientId = url.searchParams.get("client_id");
  const items = fixture.opportunities.filter(
    (item) => (!product || item.product === product) && (!clientId || item.entity_id === clientId),
  );
  return Response.json({
    metadata: fixture.metadata,
    count: items.length,
    items,
    evidence_coverage: fixture.evidence_coverage,
    release: fixture.release,
  });
}
