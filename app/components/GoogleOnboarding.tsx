"use client";
import { useEffect, useState } from "react";
import { CharacterPicker, type CharacterAvatar } from "./characters/CharacterPicker";
import { DEFAULT_AVATAR } from "./characters/avatar";
import { emit } from "./uiBus";

export function GoogleOnboarding() {
  const [stage, setStage] = useState<"loading" | "invite" | "profile" | "expired">("loading");
  const [invite, setInvite] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(false);
  const destination = () => new URLSearchParams(window.location.search).get("next") === "cli" ? "/authorize-cli" : "/#instructions";
  useEffect(() => {
    fetch("/browser-api/auth/google/pending").then(async r => {
      if (!r.ok) { setStage("expired"); return; }
      const data = await r.json(); setStage(data.invite_required ? "invite" : "profile");
    }).catch(() => { setError("Could not reach Alpha Poker. Refresh to try again."); });
  }, []);
  async function post(path: string, body: unknown, method = "POST") {
    const response = await fetch(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message ?? "Something went wrong. Please try again.");
    return data;
  }
  async function save(avatar: CharacterAvatar) {
    if (!created) {
      if (!/^[A-Za-z0-9_-]{2,40}$/.test(username.trim())) throw new Error("Choose a username with 2 to 40 letters, numbers, underscores, or hyphens.");
      const data = await post("/browser-api/auth/google/complete", { username, invite_code: invite, preset: avatar.id === "custom" ? "elephant" : avatar.id });
      setCreated(true);
      emit("session-changed", { username: data.username, isOperator: false });
    }
    if (avatar.url.startsWith("data:") || created) {
      try { return (await post("/browser-api/account/avatar", avatar.url.startsWith("data:") ? { image_data: avatar.url } : { preset: avatar.id }, "PUT")).avatar; }
      catch { throw new Error("Your account is ready, but the picture did not save. Try again, or continue and change it from Profile."); }
    }
    return avatar;
  }
  return <main className="mx-auto flex min-h-[80dvh] max-w-2xl items-center px-4 py-10">
    <section className="w-full rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm sm:p-10">
      {stage === "loading" && <p role="status">Checking your sign-in…</p>}
      {stage === "expired" && <><h1 className="text-2xl font-semibold">Let’s try that again</h1><p className="mt-3 text-zinc-600">Your Google sign-in expired. Continue with Google again to finish joining.</p><button onClick={() => emit("open-account", {})} className="mt-6 rounded-lg bg-blue-600 px-5 py-3 font-semibold text-white">Log in</button></>}
      {stage === "invite" && <>
        <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500">Join Alpha Poker</p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight">Got an invite?</h1>
        <p className="mt-3 text-zinc-600">Enter your invite code to join the league.</p>
        <p className="mt-6 rounded-lg bg-zinc-50 p-3 text-sm text-zinc-600">✓ Google account connected</p>
        <form className="mt-6" onSubmit={async e => {
          e.preventDefault(); setBusy(true); setError("");
          try { await post("/browser-api/auth/google/invite", { invite_code: invite }); setStage("profile"); }
          catch (cause) { setError(cause instanceof Error ? cause.message : "Try again."); }
          finally { setBusy(false); }
        }}>
          <label className="block text-sm font-medium">Invite code<input required autoComplete="off" maxLength={128} value={invite} onChange={e => setInvite(e.target.value)} placeholder="Enter your code" className="mt-2 w-full rounded-lg border border-zinc-300 p-3 outline-blue-600" /></label>
          <button disabled={busy} className="mt-5 w-full rounded-lg bg-blue-600 p-3 font-semibold text-white disabled:opacity-60">{busy ? "Checking…" : "Continue"}</button>
        </form>
        <p className="mt-4 text-sm text-zinc-500">Ask your teacher or league organizer for a code.</p>
        <button onClick={() => emit("open-account", {})} className="mt-6 text-sm font-medium text-blue-700">Use a different Google account</button>
      </>}
      {stage === "profile" && <>
        <h1 className="text-3xl font-semibold tracking-tight">Make it yours</h1>
        <p className="mt-3 text-zinc-600">Choose how you appear in the league.</p>
        <label className="mt-6 block text-sm font-medium">Username<input disabled={created} required minLength={2} maxLength={40} pattern="[A-Za-z0-9_-]{2,40}" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} className="mt-2 w-full rounded-lg border border-zinc-300 p-3 outline-blue-600" placeholder="Choose a username" /></label>
        <p className="mb-6 mt-2 text-sm text-zinc-500">Your Google name and photo stay private.</p>
        <CharacterPicker compact initialAvatar={DEFAULT_AVATAR} saveDraft={save} saveLabel="Join the league" onSaved={() => window.location.assign(destination())} />
        {created && <button onClick={() => window.location.assign(destination())} className="mt-4 text-sm text-blue-700">Continue to Alpha Poker</button>}
      </>}
      {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}
      {(stage === "invite" || stage === "profile") && !created && <p className="mt-6 border-t border-zinc-100 pt-4 text-sm text-zinc-500">Already have an account? <a href="/profile" className="font-medium text-blue-700 underline">Log in and connect Google from Profile.</a></p>}
    </section>
  </main>;
}
