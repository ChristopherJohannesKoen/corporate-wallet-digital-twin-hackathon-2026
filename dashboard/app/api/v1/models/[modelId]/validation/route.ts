import { fixture, proxyWalletApi } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ modelId: string }> }) {
  const { modelId } = await params;
  const url = new URL(request.url);
  const remote = await proxyWalletApi(`/v1/models/${encodeURIComponent(modelId)}/validation${url.search}`);
  if (remote) return remote;
  return Response.json({
    model_id: modelId,
    status: fixture.release.status,
    promotable: false,
    gates: fixture.release.blocking_gates.map((name, index) => ({
      gate_id: `fixture-blocker-${index + 1}`,
      label: name,
      passed: false,
      blocking: true,
    })),
    reason: "Bank-owned calibration, finance inputs, evaluation volume and operating history remain unavailable.",
  });
}
