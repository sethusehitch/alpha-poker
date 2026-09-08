"use client";
/* eslint-disable react-hooks/set-state-in-effect, @next/next/no-location-assign-relative-destination */
import { useEffect, useState } from "react";
import { useSession } from "../useSession";
import { emit } from "../uiBus";
import { CharacterPicker } from "./CharacterPicker";
import { CharacterImage } from "./CharacterImage";
import { type Avatar } from "./avatar";

export function ProfileWorkspace() {
  const { session, loaded } = useSession();
  const [data, setData] = useState<{ username: string; avatar: Avatar } | null>(null);
  const [welcome, setWelcome] = useState(false);
  const [editing, setEditing] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [retry, setRetry] = useState(0);
  const username = session?.username;
  useEffect(() => {
    setWelcome(new URLSearchParams(window.location.search).get("welcome") === "1");
  }, []);
  useEffect(() => {
    if (!username) return;
    let active = true;
    fetch("/browser-api/account/avatar").then(async response => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.error?.message ?? "Could not load your character.");
      if (active) { setData({ username, avatar: result.avatar }); setError(""); }
    }).catch(reason => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [username, retry]);
  function finish(avatar: Avatar) {
    if (!session) return;
    setData({ username: session.username, avatar });
    emit("avatar-changed", { username: session.username, avatar });
    setSaved(true);
    setEditing(false);
    if (welcome) window.location.assign("/#instructions");
  }
  const current = data?.username === session?.username ? data : null;
  const pickerOpen = Boolean(current && (welcome || editing));
  useEffect(() => {
    emit("character-picker-changed", { open: pickerOpen });
    return () => emit("character-picker-changed", { open: false });
  }, [pickerOpen]);
  return <main className="mx-auto min-h-[calc(100dvh-4.5rem)] max-w-3xl px-4 py-10 sm:px-6 sm:py-16">
    {!loaded ? <p role="status">Loading your profile…</p> : !session ? <section className="rounded-3xl border border-zinc-200 bg-white p-8 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">Your character. Your identity.</h1>
      <p className="mt-3 text-zinc-600">Log in to choose your character.</p>
      <button onClick={() => emit("open-account", {})} className="mt-6 rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white">Log in</button>
    </section> : <>
      <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-blue-600">{welcome ? "Account created" : "Your profile"}</p>
      <h1 className="text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl">{welcome ? "Pick your player." : session.username}</h1>
      <p className="mt-3 max-w-lg text-base leading-7 text-zinc-600">{welcome ? "Choose your character, then make your move. You can change it anytime." : "One character for you, wherever you compete."}</p>
      {error && <div role="alert" className="mt-6 rounded-xl bg-red-50 p-4 text-red-700">{error} <button onClick={() => setRetry(n => n + 1)} className="ml-2 underline">Try again</button></div>}
      {!current && !error && <p role="status" className="mt-8">Loading your character…</p>}
      {current && <section className="mt-8 rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm sm:p-8">
        {welcome || editing ? <>
          <CharacterPicker key={session.username} initialAvatar={current.avatar} onSaved={finish} onPendingChange={setPending}
            onSkip={welcome ? () => window.location.assign("/#instructions") : undefined} />
          {!welcome && <button disabled={pending} onClick={() => setEditing(false)} className="mt-4 w-full rounded-lg px-4 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50">Cancel</button>}
        </> : <div className="flex flex-col items-center text-center">
          <div className="h-44 w-44"><CharacterImage username={session.username} avatar={current.avatar} alt="Your selected character" /></div>
          <h2 className="mt-5 text-xl font-semibold">Your character</h2>
          <p className="mt-2 max-w-sm text-sm leading-6 text-zinc-500">Same face on the leaderboard, in Rivals, and on My Bot. Uploading a new bot won’t change it.</p>
          <button onClick={() => { setEditing(true); setSaved(false); }} className="mt-6 rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white hover:bg-blue-700">Change character</button>
          {saved && <p role="status" className="mt-4 text-sm font-medium text-green-700">Character saved. Looking good.</p>}
        </div>}
      </section>}
      {!welcome && <a href="/my-bot" className="mt-6 inline-block text-sm font-semibold text-blue-700">Back to My Bot →</a>}
    </>}
  </main>;
}
