import { findOpportunity, numeric, proxyWalletApi } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = (await request.json()) as { opportunity_id?: string; as_of?: string; target_share?: number; capacity?: number | null };
  const remote = await proxyWalletApi("/v1/scenarios/evaluate", { method: "POST", body: JSON.stringify(body) });
  if (remote) return remote;
  if (!body.opportunity_id || !body.as_of || body.target_share == null) {
    return Response.json({ detail: "opportunity_id, as_of and target_share are required" }, { status: 422 });
  }
  const opportunity = findOpportunity(body.opportunity_id);
  if (!opportunity) return Response.json({ detail: "opportunity not found" }, { status: 404 });
  const wallet = opportunity.posterior_wallet.median;
  const observed = numeric(opportunity.observed_activity.normalized_amount);
  let contestableActivity = Math.max(body.target_share * wallet - observed, 0);
  if (body.capacity) contestableActivity = Math.min(contestableActivity, Math.max(body.capacity - observed, 0));
  const netBps = opportunity.commercial.net_unit_contribution_bps ?? 0;
  const value = contestableActivity * netBps / 10_000;
  return Response.json({
    status: "SIMULATED",
    contestable_scenario_contribution: {
      amount: value,
      currency: "ZAR",
      source_unit: "annual_contribution",
      normalized_amount: value,
      normalized_currency: "ZAR",
      fx_policy_ref: "identity-zar",
    },
    causal_expected_incremental_value: null,
    net_unit_contribution_bps: netBps,
    target_share: body.target_share,
    watermark: "CLIENT-DEMO SCENARIO ECONOMICS — REPRESENTATIVE INPUTS — NOT BANK-APPROVED PRICING",
    reason_codes: ["CLIENT_DEMO_CALCULATION", "NO_CAUSAL_WIN_PROBABILITY"],
    rate_card_ref: opportunity.commercial.rate_card_ref,
  });
}
