"use client";
/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import catalog from "../../../server/alpha_poker/dojo_catalog.json";
import { Portrait, OpponentCardSurface, OPPONENT_BACKDROP, OPPONENT_PANEL } from "../rivals/OpponentSurfaces";
import { useSession } from "../useSession";

type Bot = (typeof catalog.bots)[number];
type Progress = Record<string, { beaten: boolean }>;
function DojoPortrait({bot, className}: {bot: Bot; className: string}) {
  return <Portrait name={bot.name} avatar={{id: bot.character, url: `/characters/${bot.character}.webp`}} className={className} />;
}
function OpponentDrawer({ bot, beaten, onClose }: { bot: Bot; beaten: boolean; onClose: () => void }) {
  const panel = useRef<HTMLDivElement>(null);
  const [copyStatus, setCopyStatus] = useState("");
  const prompt = `Train my bot locally against ${bot.name} in the Alpha Poker dojo for 200 mirrored hands, then show me the highlights. Use opponent ID ${bot.id}. Ask before changing my strategy. If I'm signed in, offer to sync my local practice result.`;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const elements = panel.current?.querySelectorAll<HTMLElement>('button, a[href], textarea');
        if (!elements?.length) return;
        const first = elements[0], last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    window.addEventListener("keydown", handler);
    return () => { document.body.style.overflow = overflow; window.removeEventListener("keydown", handler); previous?.focus(); };
  }, [onClose]);
  return createPortal(<div className={OPPONENT_BACKDROP} onMouseDown={onClose}>
    <div ref={panel} role="dialog" aria-modal="true" aria-labelledby="dojo-opponent-title" className={OPPONENT_PANEL} onMouseDown={e => e.stopPropagation()}>
      <button onClick={onClose} aria-label="Close opponent" className="absolute right-5 top-4 rounded p-2 text-2xl text-zinc-500 focus-visible:outline-blue-600">×</button>
      <div className="overflow-y-auto pt-8">
        <div className="text-center"><DojoPortrait bot={bot} className="h-40 w-40" /><h2 id="dojo-opponent-title" className="mt-5 text-3xl font-bold">{bot.name}</h2>
          <p className="mt-2 text-lg text-zinc-600">{bot.rating.toLocaleString()} Dojo Elo</p>
          <p className="mt-3 text-sm font-semibold text-blue-700">{bot.difficulty}</p></div>
        <p className="mt-8 border-t border-zinc-100 pt-6 text-base leading-relaxed text-zinc-600">{bot.description}</p>
        <p className="mt-6 text-sm font-semibold text-zinc-600">{beaten ? "✓ Beaten locally" : "Not beaten yet"}</p>
        <button className="mt-6 w-full rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-blue-600" onClick={async () => { try { await navigator.clipboard.writeText(prompt); setCopyStatus("Copied. Paste into Claude or Codex."); } catch { setCopyStatus("Select and copy the prompt below."); } }}>Copy training prompt</button>
        <p role="status" className="mt-2 text-sm text-blue-700">{copyStatus}</p>
        <textarea aria-label="Training prompt" readOnly value={prompt} className="mt-3 min-h-36 w-full resize-none rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-sm leading-relaxed" />
        <p className="mt-3 text-sm text-zinc-500">Paste into Claude or Codex. Your agent runs the match on your computer.</p>
        <div className="mt-6 border-t border-zinc-100 pt-5 text-sm leading-relaxed text-zinc-500">A local checkmark requires 200 mirrored hands, a positive net result, and no bot errors. Synced results are self-reported local practice, not verified wins. Public Elo is unchanged.</div>
      </div>
    </div>
  </div>, document.body);
}

export function DojoWorkspace() {
  const { session } = useSession();
  const [selected, setSelected] = useState<string | null>(null);
  const [savedProgress, setProgress] = useState<{owner: string; progress: Progress} | null>(null);
  const progress = savedProgress && savedProgress.owner === session?.username ? savedProgress.progress : {};
  const [error, setError] = useState("");
  useEffect(() => {
    let controller = new AbortController();
    setError("");
    const username = session?.username;
    const load = () => {
      controller.abort();
      controller = new AbortController();
      const request = controller;
      if (!username) return;
      fetch("/browser-api/dojo/progress", { signal: request.signal })
        .then(async r => { if (!r.ok) throw new Error(); return r.json(); })
        .then(data => { if (!request.signal.aborted) { setProgress({owner: username, progress: data.progress}); setError(""); } })
        .catch(e => { if (e.name !== "AbortError" && !request.signal.aborted) setError("Couldn’t load saved progress. Opponents are still available."); });
    };
    load();
    window.addEventListener("focus", load);
    return () => { controller.abort(); window.removeEventListener("focus", load); };
  }, [session?.username]);
  useEffect(() => {
    const update = () => setSelected(new URLSearchParams(location.search).get("opponent"));
    update(); window.addEventListener("popstate", update); return () => window.removeEventListener("popstate", update);
  }, []);
  const choose = useCallback((id: string | null) => { const url = new URL(location.href); if (id) url.searchParams.set("opponent", id); else url.searchParams.delete("opponent"); history.pushState(null, "", url); setSelected(id); }, []);
  const close = useCallback(() => choose(null), [choose]);
  const current = catalog.bots.find(bot => bot.id === selected);
  const next = catalog.bots.find(bot => !progress[bot.id]?.beaten)?.id;
  return <main className="min-h-[85vh] bg-[#f8faff] px-5 py-10 sm:px-8"><div className="mx-auto max-w-[76rem]">
    <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Training Dojo</h1>
    <p className="mt-3 text-lg text-zinc-600">Choose an opponent. Train with your coding agent.</p>
    <p className="mt-6 text-sm text-zinc-500">{session ? `${Object.values(progress).filter(p => p.beaten).length} of 5 beaten locally` : "All five available. Sign in to see synced practice progress."}</p>
    {error && <p role="alert" className="mt-3 text-sm text-amber-700">{error}</p>}
    <div className="mt-7 grid grid-cols-[repeat(auto-fit,minmax(min(100%,17.25rem),20.5625rem))] gap-5">
      {catalog.bots.map(bot => <OpponentCardSurface key={bot.id} selected={selected === bot.id}>
        <div className="flex gap-4 pt-3">
          <DojoPortrait bot={bot} className="h-28 w-28" />
          <div className="min-w-0 pt-2">
            <h2 className="text-xl font-bold">{bot.name}</h2>
            <p className="mt-3 text-xl font-bold">{bot.rating.toLocaleString()}</p>
            <p className="text-sm text-zinc-500">Dojo Elo</p>
            <p className="mt-3 text-sm font-semibold text-blue-700">{bot.difficulty}</p>
          </div>
        </div>
        <p className="text-base text-zinc-600">{bot.style}</p>
        <p className="text-sm font-semibold text-blue-700">{progress[bot.id]?.beaten ? "✓ Beaten locally" : next === bot.id ? "Suggested next" : "Available"}</p>
        <button onClick={() => choose(bot.id)} className="rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-blue-600">View opponent</button>
      </OpponentCardSurface>)}
    </div><p className="mt-7 max-w-2xl text-sm text-zinc-500">{catalog.rating_note} All practice uses play chips. Your public Elo won’t change.</p>
    {current && <OpponentDrawer key={current.id} bot={current} beaten={!!progress[current.id]?.beaten} onClose={close} />}
  </div></main>;
}
