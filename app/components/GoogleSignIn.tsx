"use client";
import { useEffect, useState } from "react";

export function GoogleSignIn({ link = false }: { link?: boolean }) {
  const [enabled, setEnabled] = useState(false);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [canonical, setCanonical] = useState("");
  useEffect(() => {
    fetch(link ? "/browser-api/auth/google/connection" : "/browser-api/auth/options")
      .then(r => r.ok ? r.json() : null).then(data => {
        setEnabled(Boolean(link ? data?.enabled : data?.google_enabled));
        setConnected(Boolean(data?.connected));
      }).catch(() => undefined);
  }, [link]);
  if (!enabled) return null;
  if (connected) return <p className="mt-5 text-sm text-zinc-600">✓ Google sign-in connected</p>;
  async function start() {
    setBusy(true); setError("");
    try {
      const response = await fetch("/browser-api/auth/google/start", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ link, next: window.location.pathname === "/authorize-cli" ? "cli" : "site" }) });
      const result = await response.json();
      if (result.error?.code === "google_origin") setCanonical(result.error.url);
      if (!response.ok) throw new Error(result.error?.message ?? "Could not start Google sign-in.");
      window.location.assign(result.url);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Try again."); setBusy(false); }
  }
  return <div className="mt-6 w-full">
    <button type="button" disabled={busy} onClick={start} className="flex min-h-11 w-full items-center justify-center gap-3 rounded-lg border border-zinc-300 bg-white px-4 py-3 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-60">
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 48 48"><path fill="#4285F4" d="M43.6 24.5c0-1.4-.1-2.8-.4-4.1H24v7.8h11c-.5 2.5-1.9 4.7-4.1 6.1v5.1h6.6c3.9-3.6 6.1-8.8 6.1-14.9Z"/><path fill="#34A853" d="M24 44c5.5 0 10.1-1.8 13.5-4.9l-6.6-5.1c-1.8 1.2-4.1 1.9-6.9 1.9-5.3 0-9.8-3.6-11.4-8.4H5.8v5.3A20 20 0 0 0 24 44Z"/><path fill="#FBBC05" d="M12.6 27.5a12 12 0 0 1 0-7V15.2H5.8a20 20 0 0 0 0 17.6l6.8-5.3Z"/><path fill="#EA4335" d="M24 12.1c3 0 5.6 1 7.7 3l5.8-5.8A19.3 19.3 0 0 0 24 4 20 20 0 0 0 5.8 15.2l6.8 5.3C14.2 15.7 18.7 12.1 24 12.1Z"/></svg>
      {busy ? "Connecting…" : link ? "Connect Google" : "Continue with Google"}
    </button>
    {error && <p role="alert" className="mt-2 text-sm text-red-600">{error}</p>}
    {canonical && <a href={canonical} className="mt-2 block text-sm font-medium text-blue-700 underline">Open Alpha Poker</a>}
    {!link && <div className="mt-5 flex items-center gap-3 text-xs text-zinc-400"><span className="h-px flex-1 bg-zinc-200"/>or<span className="h-px flex-1 bg-zinc-200"/></div>}
  </div>;
}
