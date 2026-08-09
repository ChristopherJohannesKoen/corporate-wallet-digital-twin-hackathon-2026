import Dashboard from "./Dashboard";
import { getChatGPTUser } from "./chatgpt-auth";
import { fixture } from "@/lib/wallet-api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const user = await getChatGPTUser();
  return <Dashboard viewer={user?.displayName ?? "Local model validator"} asOf={fixture.metadata.as_of} />;
}
