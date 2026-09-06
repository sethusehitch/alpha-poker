import type { Metadata } from "next";
import { AppHeader } from "../../components/app/AppHeader";
import { HandReplay } from "../../components/rivals/HandReplay";

export const metadata: Metadata = { title: "Hand replay — Alpha Poker" };

export default async function HandPage({
  params,
  searchParams,
}: {
  params: Promise<{ hand_id: string }>;
  searchParams: Promise<{ rival?: string; result?: string }>;
}) {
  const { hand_id } = await params;
  const query = await searchParams;
  const back =
    query.rival && query.result
      ? `/rivals?rival=${encodeURIComponent(query.rival)}&result=${encodeURIComponent(query.result)}`
      : "/rivals";
  return (
    <>
      <AppHeader />
      <main className="mx-auto min-h-[calc(100vh-4.5rem)] max-w-3xl px-5 py-12 sm:px-8">
        <a href={back} className="text-sm font-semibold text-blue-700">
          ← Back to Rivals
        </a>
        <p className="mt-8 text-xs font-bold tracking-[0.18em] text-blue-700">
          DIRECT CHALLENGE
        </p>
        <h1 className="mt-2 text-4xl font-bold tracking-tight">Hand replay</h1>
        <p className="mt-3 text-zinc-600">
          Focused replay for hand{" "}
          <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-sm">
            {hand_id}
          </code>
          .
        </p>
        <HandReplay handId={hand_id} />
      </main>
    </>
  );
}
