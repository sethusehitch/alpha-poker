import { AppHeader } from "../../../../../components/app/AppHeader";
import { MatchRecap } from "../../../../../components/recaps/MatchRecap";
export const metadata = { title: "Match recap | Alpha Poker" };
export default async function RoundRobinRecapPage({ params, searchParams }: { params: Promise<{ run_id: string; matchup_id: string }>; searchParams: Promise<{ hand?: string }> }) {
  const { run_id, matchup_id } = await params;
  const { hand } = await searchParams;
  return <><AppHeader currentPath="/leaderboard" /><MatchRecap endpoint={`/browser-api/runs/${encodeURIComponent(run_id)}/matchups/${encodeURIComponent(matchup_id)}/recap`} initialHandId={hand} /></>;
}
