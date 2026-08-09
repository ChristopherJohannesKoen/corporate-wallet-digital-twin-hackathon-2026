import { findOpportunity, fixture, pointInTime, proxyWalletApi } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ opportunityId: string }> }) {
  const { opportunityId } = await params;
  const url = new URL(request.url);
  const remote = await proxyWalletApi(`/v1/opportunities/${encodeURIComponent(opportunityId)}/explanation${url.search}`);
  if (remote) return remote;
  const invalid = pointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  const opportunity = findOpportunity(opportunityId);
  if (!opportunity) return Response.json({ detail: "opportunity not found" }, { status: 404 });
  const facts = opportunity.evidence_fact_ids.map((id) => fixture.facts[id]).filter(Boolean);
  return Response.json({
    opportunity,
    layers: {
      observed: opportunity.observed_activity,
      identified_bound: opportunity.identification_bounds,
      posterior: opportunity.posterior_wallet,
      commercial_scenario: opportunity.commercial,
      causal: null,
    },
    facts,
    narrative_mode: "deterministic",
    missing_evidence: [
      opportunity.evidence_tier === "E3" || opportunity.evidence_tier === "E4" ? null : "E3 multibank observation",
      "approved bank economics",
      "causal outcome history",
    ].filter(Boolean),
  });
}
