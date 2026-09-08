"use client";
import { useState } from "react";
import { useSession } from "./useSession";
import { emit } from "./uiBus";

export default function AuthorizeCli() {
  const { session, loaded } = useSession();
  const [code, setCode] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <main className="relative z-40 flex min-h-dvh items-center justify-center bg-black/20 px-4 py-6 backdrop-blur-[3px]"><section className="w-full max-w-lg rounded-2xl border border-zinc-200 bg-white p-8 shadow-xl">
    <h1 className="text-2xl font-semibold">{done ? "Your agent is connected" : "Connect your coding agent"}</h1>
    {done ? <p className="mt-4 text-zinc-600">Return to your terminal or coding agent. You can close this page.</p> : <>
      <p className="mt-4 text-zinc-600">Enter the code shown by Alpha Poker in your terminal or coding agent.</p>
      <p className="mt-3 text-sm text-zinc-500">Only approve a login you started. This lets that agent train, upload bots, and act on your account.</p>
      {!loaded ? <p className="mt-6">Checking account…</p> : !session ? <button onClick={() => emit("open-account", {})} className="mt-6 w-full rounded-lg bg-blue-600 p-3 font-semibold text-white">Log in to continue</button> : <form className="mt-6" onSubmit={async e => {
        e.preventDefault(); setBusy(true); setError("");
        try {
          const response = await fetch("/browser-api/auth/browser/approve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_code: code.toUpperCase() }) });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error?.message ?? "Could not connect.");
          setDone(true);
        } catch (cause) { setError(cause instanceof Error ? cause.message : "Try again."); }
        finally { setBusy(false); }
      }}>
        <p className="mb-4 text-sm">Connecting as <strong>{session.username}</strong></p>
        <label className="block text-sm font-medium">Code<input required autoComplete="off" placeholder="AB12-CD34" maxLength={9} pattern="[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}" value={code} onChange={e => setCode(e.target.value)} className="mt-2 w-full rounded-lg border border-zinc-300 p-3 font-mono uppercase tracking-widest" /></label>
        <button disabled={busy} className="mt-5 w-full rounded-lg bg-blue-600 p-3 font-semibold text-white disabled:opacity-60">{busy ? "Connecting…" : "Approve connection"}</button>
      </form>}
      {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}
    </>}
  </section></main>;
}
