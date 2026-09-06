"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { emit, on } from "./uiBus";

const USERNAME_CHIP_DISPLAY_LENGTH = 16;

function displayUsername(value: string) {
  const points = Array.from(value);
  return points.length > USERNAME_CHIP_DISPLAY_LENGTH
    ? `${points.slice(0, USERNAME_CHIP_DISPLAY_LENGTH - 1).join("")}…`
    : value;
}

function PersonIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4 shrink-0 text-zinc-500" fill="none">
      <circle cx="8" cy="5.25" r="2.75" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.75 13.25c0-2.9 2.35-4.75 5.25-4.75s5.25 1.85 5.25 4.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 14 14" className="h-3.5 w-3.5 shrink-0 text-zinc-400" fill="none">
      <path d="M3.5 5.25 7 8.75l3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type Session = { username: string };

export function AuthButton() {
  const [session, setSession] = useState<Session | null>(null);
  const [open, setOpen] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const resetAuthForm = useCallback(() => {
    setRegistering(false);
    setUsername("");
    setPassword("");
    setConfirmation("");
    setInviteCode("");
    setError("");
  }, []);

  const closeDialog = useCallback(() => {
    resetAuthForm();
    setOpen(false);
  }, [resetAuthForm]);

  useEffect(() => {
    fetch("/browser-api/auth/me")
      .then(async (response) => {
        if (!response.ok) return;
        const result = await response.json();
        if (typeof result.username === "string") {
          setSession({ username: result.username });
          emit("session-changed", { username: result.username, isOperator: Boolean(result.is_operator) });
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => on("open-account", () => setOpen(true)), []);

  useEffect(() => {
    emit("account-dialog-changed", { open });
    if (open) emit("close-panels", {});
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeDialog();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, closeDialog]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (registering && password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`/browser-api/auth/${registering ? "register" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, ...(registering && inviteCode ? { invite_code: inviteCode } : {}) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error?.message ?? "Could not log in");
      const next = { username: result.username };
      setSession(next);
      closeDialog();
      const me = await fetch("/browser-api/auth/me").then((r) => (r.ok ? r.json() : null)).catch(() => null);
      emit("session-changed", { username: result.username, isOperator: Boolean(me?.is_operator) });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not log in");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    if (session) {
      await fetch("/browser-api/auth/logout", { method: "POST" }).catch(() => undefined);
    }
    setSession(null);
    closeDialog();
    emit("session-changed", { username: null, isOperator: false });
  }

  return (
    <>
      <button
        type="button"
        data-testid="account-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
        className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-[8px] border border-zinc-300 bg-white px-2.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 min-[380px]:gap-2 min-[380px]:px-3.5"
      >
        <PersonIcon />
        {session ? (
          <>
            {/* Narrower cap below 380px so the lockup, menu toggle, and chip
                all fit a 320px header row without wrapping. */}
            <span className="max-w-[4.5rem] truncate min-[380px]:max-w-[6.5rem] sm:max-w-[9rem]" title={session.username}>
              {displayUsername(session.username)}
            </span>
            <ChevronDownIcon />
          </>
        ) : (
          <span>Log in</span>
        )}
      </button>

      {open && (
        // The overlay itself scrolls and the panel caps at the dynamic viewport
        // height, so a short phone in landscape — or the register form with the
        // invite field — can never clip the submit button off screen.
        <div
          className="fixed inset-0 z-50 overflow-y-auto overscroll-contain bg-black/20 px-4 py-6 sm:px-5"
          onMouseDown={closeDialog}
        >
          <div className="flex min-h-full items-center justify-center">
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="account-title"
              className="max-h-[calc(100dvh-3rem)] w-full max-w-sm overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-5 shadow-xl sm:p-6"
              onMouseDown={(event) => event.stopPropagation()}
            >
              {session ? (
                <>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h2 id="account-title" className="text-xl font-bold text-zinc-900">Account</h2>
                      <p className="mt-1 text-sm text-zinc-500">You are signed in.</p>
                    </div>
                    <button type="button" aria-label="Close" onClick={closeDialog} className="-mr-1 -mt-1 rounded-lg px-2 py-1 text-xl leading-none text-zinc-500 hover:bg-zinc-100">×</button>
                  </div>
                  {/* Identity and sign-out only — bot status lives on /my-bot. */}
                  <div className="mt-5 flex items-center gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-4">
                    <span aria-hidden="true" className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-blue-600 text-base font-bold text-white">
                      {Array.from(session.username)[0]?.toUpperCase() ?? "?"}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-zinc-950" title={session.username}>{session.username}</p>
                      <p className="text-xs text-zinc-500">Same account as the Alpha Poker CLI.</p>
                    </div>
                  </div>
                  <button type="button" onClick={logout} className="mt-5 w-full rounded-lg border border-zinc-300 px-4 py-2.5 font-semibold text-zinc-900 hover:bg-zinc-50">
                    Log out
                  </button>
                </>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 id="account-title" className="text-xl font-bold text-zinc-900">{registering ? "Create account" : "Log in"}</h2>
                      <p className="mt-1 text-sm text-zinc-500">Use the same account in the Alpha Poker CLI.</p>
                    </div>
                    <button type="button" aria-label="Close" onClick={closeDialog} className="-mr-1 -mt-1 rounded-lg px-2 py-1 text-xl leading-none text-zinc-500 hover:bg-zinc-100">×</button>
                  </div>
                  <form onSubmit={submit} className="mt-6 space-y-4">
                    <label className="block text-sm font-medium text-zinc-800">
                      Username
                      <input autoFocus autoComplete="username" required minLength={2} maxLength={40} value={username} onChange={(event) => setUsername(event.target.value)} className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2.5 font-normal outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
                    </label>
                    <label className="block text-sm font-medium text-zinc-800">
                      Password
                      <input type="password" autoComplete={registering ? "new-password" : "current-password"} required minLength={8} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2.5 font-normal outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
                    </label>
                    {registering && (
                      <>
                        <label className="block text-sm font-medium text-zinc-800">
                          Confirm password
                          <input type="password" autoComplete="new-password" required minLength={8} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2.5 font-normal outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
                        </label>
                      <label className="block text-sm font-medium text-zinc-800">
                        Invite code <span className="font-normal text-zinc-500">(required)</span>
                          <input type="password" autoComplete="off" required maxLength={128} value={inviteCode} onChange={(event) => setInviteCode(event.target.value)} className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2.5 font-normal outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
                          <span className="mt-1.5 block font-normal text-zinc-500">Provided by your cohort organizer. Ask them if you do not have one.</span>
                        </label>
                      </>
                    )}
                    {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
                    <button disabled={busy} className="w-full rounded-lg bg-blue-600 px-4 py-2.5 font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
                      {busy ? "Working…" : registering ? "Create account" : "Log in"}
                    </button>
                  </form>
                  <button type="button" onClick={() => {
                    setRegistering(!registering);
                    setPassword("");
                    setConfirmation("");
                    setInviteCode("");
                    setError("");
                  }} className="mt-4 w-full text-sm font-medium text-blue-700">
                    {registering ? "Already have an account? Log in" : "New here? Create an account"}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
