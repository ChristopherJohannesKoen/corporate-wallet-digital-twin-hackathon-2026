import { proxyWalletApi, v31Fixture, v31PointInTime } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request, context: { params: Promise<{ clientId: string }> }) {
  const url = new URL(request.url);
  const invalid = v31PointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  const { clientId } = await context.params;
  const remote = await proxyWalletApi(`/v3/clients/${encodeURIComponent(clientId)}/briefing-notes${url.search}`);
  if (remote) return remote;
  const conversations = v31Fixture.projection.conversation_summaries
    .filter((item) => item.entity_id === clientId)
    .sort((a, b) => (a.weekly_rank ?? 10_000) - (b.weekly_rank ?? 10_000))
    .slice(0, 3);
  return Response.json({
    entity_id: clientId,
    as_of: url.searchParams.get("as_of"),
    notes: conversations.map((item) => ({
      conversation_id: item.conversation_id,
      brief: v31Fixture.briefs[item.conversation_id],
      provider_evaluations: [],
      live_provider_status: "NOT_EXECUTED_WITHOUT_FRESH_ENVIRONMENT_CREDENTIAL",
    })),
    claim_boundary: "Provider results appear only after critical validators pass; deterministic fallback remains available.",
  });
}
