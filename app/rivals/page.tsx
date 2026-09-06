import type { Metadata } from "next";
import { AppHeader } from "../components/app/AppHeader";
import { RivalsWorkspace } from "../components/rivals/RivalsWorkspace";

export const metadata: Metadata = {
  title: "Rivals — Alpha Poker",
  description: "Practice direct challenges with your poker bot.",
};
export default async function RivalsPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const params = await searchParams;
  const tab =
    params.tab === "leaderboard" ||
    params.tab === "challenges" ||
    params.tab === "records"
      ? params.tab
      : "mine";
  return (
    <>
      <AppHeader />
      <RivalsWorkspace initialTab={tab} />
    </>
  );
}
