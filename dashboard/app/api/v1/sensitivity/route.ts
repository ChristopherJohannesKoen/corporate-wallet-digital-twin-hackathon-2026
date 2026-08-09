import { fixture, pointInTime, proxyWalletApi } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const remote = await proxyWalletApi(`/v1/sensitivity${url.search}`);
  if (remote) return remote;
  const invalid = pointInTime(url.searchParams.get("as_of"));
  if (invalid) return invalid;
  return Response.json({
    global: fixture.sensitivity,
    legacy_grid: fixture.legacy_sensitivity,
    benchmark_economics: fixture.benchmark_economics,
    offline_validation: fixture.offline_validation,
    genai_evaluation: fixture.genai_evaluation,
    genai_provider_status: fixture.genai_provider_status,
    shadow_replay: fixture.shadow_replay,
    production_candidate: fixture.production_candidate,
    public_evidence_qa: fixture.public_evidence_qa,
    trial_rehearsal: fixture.trial_rehearsal,
    operational_rehearsal: fixture.operational_rehearsal,
    client_demo_data: fixture.client_demo_data,
    client_demo_scorecard: fixture.client_demo_scorecard,
    production_target: fixture.production_target,
  });
}
