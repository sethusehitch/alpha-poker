"use client";
import { useEffect, useState } from "react";

type Pairing = { matchup_id: string; player_a: string; player_b: string; hands: number };
export function RoundRobinRecaps({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState<{ runId: string; items?: Pairing[]; error?: boolean } | null>(null);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    fetch(`/browser-api/runs/${encodeURIComponent(runId)}/matchups`, { cache: "no-store", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error("Unavailable");
        const data = await response.json();
        if (!controller.signal.aborted) setResult({ runId, items: data.matchups });
      }).catch(() => { if (!controller.signal.aborted) setResult({ runId, error: true }); });
    return () => controller.abort();
  }, [open, runId]);
  const current = result?.runId === runId ? result : null;
  return <details className="mt-6 rounded-xl border border-zinc-200 bg-white p-4" onToggle={event => setOpen(event.currentTarget.open)}><summary className="cursor-pointer text-sm font-semibold text-blue-700">View match recaps</summary>
    {open && (!current ? <p className="mt-3 text-sm text-zinc-500">Loading completed pairings…</p> : current.error ? <p className="mt-3 text-sm text-zinc-500">Pairings are unavailable. Close and reopen to retry.</p> : current.items?.length ? <ul className="mt-3 divide-y divide-zinc-100">{current.items.map(match => <li key={match.matchup_id}><a className="flex items-center justify-between gap-3 py-3 text-sm hover:text-blue-700" href={`/recaps/runs/${encodeURIComponent(runId)}/matches/${encodeURIComponent(match.matchup_id)}`}><span>{match.player_a} vs {match.player_b}<small className="ml-2 text-zinc-500">{match.hands} hands</small></span><span className="shrink-0 font-semibold text-blue-700">View recap</span></a></li>)}</ul> : <p className="mt-3 text-sm text-zinc-500">No retained pairings.</p>)}
  </details>;
}
