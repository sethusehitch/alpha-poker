import { AppHeader } from "../../../components/app/AppHeader";
import { MatchRecap } from "../../../components/recaps/MatchRecap";
export const metadata = { title: "Rivalry recap | Alpha Poker" };
export default async function ChallengeRecapPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ hand?: string }> }) {
  const { id } = await params;
  const { hand } = await searchParams;
  return <><AppHeader currentPath="/rivals" /><MatchRecap endpoint={`/browser-api/challenges/${encodeURIComponent(id)}/recap`} initialHandId={hand} /></>;
}
