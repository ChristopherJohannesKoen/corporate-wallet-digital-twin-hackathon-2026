import Dashboard from "./Dashboard";
import { getChatGPTUser } from "./chatgpt-auth";
import { v31Fixture } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const user = await getChatGPTUser();
  return (
    <Dashboard
      viewer={user?.displayName ?? "Local model validator"}
      asOf={v31Fixture.projection.metadata.as_of}
      weekStart={v31Fixture.projection.metadata.week_start}
    />
  );
}
