import { proxyWalletApi, submissionTruth, v31Fixture, v31PointInTime } from "@/lib/wallet-api";

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
  const accepted = submissionTruth.genai.showcase_briefs[clientId] ?? null;
  return Response.json({
    entity_id: clientId,
    as_of: url.searchParams.get("as_of"),
    notes: conversations.map((item, index) => ({
      conversation_id: item.conversation_id,
      deterministic_brief: v31Fixture.briefs[item.conversation_id],
      accepted_provider_brief: index === 0 ? accepted : null,
      provider_evaluations: index === 0 && accepted ? [accepted] : [],
      live_provider_status: index === 0 && accepted
        ? "HACKATHON_EXTERNAL_PROVIDER_ACCEPTED"
        : "DETERMINISTIC_FALLBACK_AVAILABLE",
    })),
    live_evaluation: {
      evaluation_scope: submissionTruth.genai.evaluation_scope,
      target_runs: submissionTruth.genai.target_runs,
      runs: submissionTruth.genai.runs,
      accepted_runs: submissionTruth.genai.accepted_runs,
      blocked_runs: submissionTruth.genai.blocked_runs,
      submission_gate_passed: submissionTruth.genai.submission_gate_passed,
      accepted_providers: submissionTruth.genai.accepted_providers,
      accepted_clients: submissionTruth.genai.accepted_clients,
      bank_authorized_live_genai: false,
      claim_boundary: submissionTruth.genai.claim_boundary,
    },
    claim_boundary: "Accepted provider briefs passed every critical hackathon validator. This is not bank-authorized LIVE_GENAI; deterministic output remains available beside it.",
  });
}
