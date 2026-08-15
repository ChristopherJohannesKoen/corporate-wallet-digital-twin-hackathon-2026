import { getChatGPTUser } from "@/app/chatgpt-auth";
import fixtureJson from "@/app/data/shadow-fixture.json";
import v3FixtureJson from "@/app/data/v3-fixture.json";
import v31FixtureJson from "@/app/data/v31-fixture.json";
import walletV311Json from "@/app/data/wallet-v311-fixture.json";
import promotionJson from "@/app/data/promotion-fixture.json";
import submissionTruthJson from "@/app/data/submission-truth-v3.2.0.json";
import type { Opportunity, PromotionReadiness, ShadowFixture, SubmissionTruth, V3Fixture, V31Fixture, WalletOpportunityDetail, WalletPortfolioProjection } from "./contracts";

export const fixture = fixtureJson as unknown as ShadowFixture;
export const v3Fixture = v3FixtureJson as unknown as V3Fixture;
export const v31Fixture = v31FixtureJson as unknown as V31Fixture;
export const walletV311Fixture = walletV311Json as unknown as {
  projection: WalletPortfolioProjection;
  details: Record<string, WalletOpportunityDetail>;
};
export const promotionFixture = promotionJson as unknown as PromotionReadiness;
export const submissionTruth = submissionTruthJson as unknown as SubmissionTruth;

export async function proxyWalletApi(path: string, init?: RequestInit): Promise<Response | null> {
  const baseUrl = process.env.WALLET_API_BASE_URL;
  if (!baseUrl) return null;
  const user = await getChatGPTUser();
  if (!user) return new Response(JSON.stringify({ detail: "authenticated bank identity required" }), { status: 401 });
  const headers = new Headers(init?.headers);
  headers.set("content-type", "application/json");
  headers.set("x-user-id", user.userId);
  headers.set("x-user-roles", process.env.WALLET_USER_ROLES ?? "SHADOW_OPERATOR,MODEL_VALIDATOR");
  headers.set("x-user-team", process.env.WALLET_USER_TEAM ?? "model-risk");
  headers.set("x-user-clients", process.env.WALLET_USER_CLIENTS ?? "*");
  headers.set("x-user-products", process.env.WALLET_USER_PRODUCTS ?? "*");
  return fetch(`${baseUrl.replace(/\/$/, "")}${path}`, { ...init, headers, cache: "no-store" });
}

export function pointInTime(asOf: string | null): Response | null {
  if (!asOf) return Response.json({ detail: "as_of is required" }, { status: 422 });
  if (asOf !== fixture.metadata.as_of) return Response.json({ detail: `snapshot unavailable: ${asOf}` }, { status: 404 });
  return null;
}

export function v31PointInTime(asOf: string | null): Response | null {
  if (!asOf) return Response.json({ detail: "as_of is required" }, { status: 422 });
  if (asOf !== v31Fixture.projection.metadata.as_of) {
    return Response.json({ detail: `snapshot unavailable: ${asOf}` }, { status: 404 });
  }
  return null;
}

export function findOpportunity(id: string): Opportunity | undefined {
  return fixture.opportunities.find((item) => item.opportunity_id === id);
}

export function numeric(value: number | string | null | undefined): number {
  return value == null ? 0 : Number(value);
}
