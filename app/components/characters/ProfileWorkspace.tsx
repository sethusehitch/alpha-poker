"use client";
/* eslint-disable react-hooks/set-state-in-effect, @next/next/no-location-assign-relative-destination */
import { useEffect, useState } from "react";
import { useSession } from "../useSession";
import { emit } from "../uiBus";
import { CharacterPicker } from "./CharacterPicker";
import { CharacterImage } from "./CharacterImage";
import { type Avatar } from "./avatar";
import { GoogleSignIn } from "../GoogleSignIn";

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
  const welcomeDestination = () => new URLSearchParams(window.location.search).get("next") === "cli" ? "/authorize-cli" : "/#instructions";
  useEffect(() => {
    setWelcome(new URLSearchParams(window.location.search).get("welcome") === "1");
  }, []);
  useEffect(() => {
    if (!username) return;
    let active = true;
    fetch("/browser-api/account/avatar").then(async response => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.error?.message ?? "Could not load your profile.");
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
    if (welcome) window.location.assign(welcomeDestination());
  }
  const current = data?.username === session?.username ? data : null;
  const pickerOpen = Boolean(current && (welcome || editing));
  useEffect(() => {
    emit("character-picker-changed", { open: pickerOpen });
    return () => emit("character-picker-changed", { open: false });
  }, [pickerOpen]);
  return <main className="mx-auto min-h-[calc(100dvh-4.5rem)] max-w-3xl px-4 py-10 sm:px-6 sm:py-16">
    {!loaded ? <p role="status">Loading your profile…</p> : !session ? <section className="rounded-3xl border border-zinc-200 bg-white p-8 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">Your profile</h1>
      <p className="mt-3 text-zinc-600">Log in to view and edit your profile.</p>
      <button onClick={() => emit("open-account", {})} className="mt-6 rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white">Log in</button>
    </section> : <>
      {(welcome || editing) && <>
        <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-blue-600">{welcome ? "Account created" : "Your profile"}</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl">{welcome ? "Set up your profile" : session.username}</h1>
      </>}
      {welcome && <p className="mt-3 max-w-lg text-base leading-7 text-zinc-600">Add a profile picture. You can change it anytime.</p>}
      {error && <div role="alert" className="mt-6 rounded-xl bg-red-50 p-4 text-red-700">{error} <button onClick={() => setRetry(n => n + 1)} className="ml-2 underline">Try again</button></div>}
      {!current && !error && <p role="status" className="mt-8">Loading your profile…</p>}
      {current && <section className={welcome || editing ? "mt-8 rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm sm:p-8" : "mx-auto flex max-w-sm flex-col items-center py-10 sm:py-16"}>
        {welcome || editing ? <>
          <CharacterPicker key={session.username} initialAvatar={current.avatar} onSaved={finish} onPendingChange={setPending}
            onSkip={welcome ? () => window.location.assign(welcomeDestination()) : undefined} />
          {!welcome && <button disabled={pending} onClick={() => setEditing(false)} className="mt-4 w-full rounded-lg px-4 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50">Cancel</button>}
        </> : <div className="flex flex-col items-center text-center">
          <div className="relative h-36 w-36">
            <CharacterImage username={session.username} avatar={current.avatar} alt="Your profile picture" />
            <button aria-label="Change picture" title="Change picture" onClick={() => { setEditing(true); setSaved(false); }} className="absolute -right-1 -top-1 grid h-9 w-9 place-items-center rounded-full border border-zinc-200 bg-white text-zinc-700 shadow-sm hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">
              <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4"><path d="m12.5 4.5 3 3M3.5 16.5l3.7-.8 9-9a2.1 2.1 0 0 0-3-3l-9 9-.7 3.8Z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>
          </div>
          <h1 className="mt-6 max-w-full break-all text-3xl font-semibold tracking-tight text-zinc-950">{session.username}</h1>
          {saved && <p role="status" className="mt-4 text-sm font-medium text-green-700">Saved.</p>}
          <a href="/my-bot" className="mt-6 text-sm font-semibold text-blue-700 hover:underline">My Bot →</a>
          <GoogleSignIn link />
        </div>}
      </section>}
    </>}
  </main>;
}
