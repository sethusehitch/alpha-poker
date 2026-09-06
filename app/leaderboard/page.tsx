import type { Metadata } from "next";
import { AppHeader } from "../components/app/AppHeader";
import { StandingsWorkspace } from "../components/leaderboard/StandingsWorkspace";

export const metadata: Metadata = {
  title: "Leaderboard — Alpha Poker",
  description: "The latest official Alpha Poker league standings.",
};

export default function LeaderboardPage() {
  return (
    <>
      <AppHeader currentPath="/leaderboard" />
      <StandingsWorkspace />
    </>
  );
}
