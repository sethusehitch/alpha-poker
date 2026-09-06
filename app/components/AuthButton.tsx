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
type AccountStatus = {
  participant_state: string;
  participant_message: string;
  submission: { submission_id: string; bot_name: string; status: string; error?: string | null } | null;
  league: { queue: { state: string; message: string }; current_run?: { progress?: { matchups_completed?: number; matchups_total?: number } } | null };
  result: { id: string; rank: number; elo_rating: number; record: { wins: number; losses: number; draws: number } } | null;
};

function recordLabel(count: number, singular: string, plural: string) {
  return `${count} ${count === 1 ? singular : plural}`;
}

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
  const [accountStatus, setAccountStatus] = useState<AccountStatus | null>(null);
  const [statusBusy, setStatusBusy] = useState(false);
  const [sessionChecked, setSessionChecked] = useState(false);

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
      .catch(() => undefined)
      .finally(() => setSessionChecked(true));
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

  useEffect(() => {
    if (!open || !session) return;
    let cancelled = false;
    async function refreshStatus() {
      setStatusBusy(true);
      try {
        const response = await fetch("/browser-api/account/status", { cache: "no-store" });
        if (!response.ok) return;
        const result = await response.json() as AccountStatus;
        if (!cancelled) setAccountStatus(result);
      } finally {
        if (!cancelled) setStatusBusy(false);
      }
    }
    void refreshStatus();
    const interval = window.setInterval(refreshStatus, 5000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [open, session]);

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
        ) : sessionChecked ? (
          <span>Log in</span>
        ) : (
          <span>Account</span>
        )}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 px-5" onMouseDown={closeDialog}>
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="account-title"
            className="w-full max-w-sm rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            {session ? (
              <>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 id="account-title" className="text-xl font-bold text-zinc-900">Your bot</h2>
                    <p className="mt-1 text-sm text-zinc-500">Logged in as <strong>{session.username}</strong></p>
                  </div>
                  <button type="button" aria-label="Close" onClick={closeDialog} className="text-xl leading-none text-zinc-500">×</button>
                </div>
                <div className="mt-5 rounded-xl border border-zinc-200 bg-zinc-50 p-4">
                  {statusBusy && !accountStatus ? (
                    <p className="text-sm text-zinc-500">Checking your bot…</p>
                  ) : !accountStatus?.submission ? (
                    <p className="text-sm text-zinc-600">No bot submitted yet. Download the starter kit and give its prompt to your coding agent.</p>
                  ) : (
                    <>
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate font-semibold text-zinc-950" title={accountStatus.submission.bot_name}>{accountStatus.submission.bot_name}</p>
                        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold capitalize text-zinc-600 ring-1 ring-zinc-200">{accountStatus.submission.status}</span>
                      </div>
                      {accountStatus.submission.error ? <p role="alert" className="mt-3 text-sm text-red-600">{accountStatus.submission.error}</p> : null}
                      <p className={`mt-3 text-sm ${["failed", "rejected"].includes(accountStatus.participant_state) ? "text-red-600" : "text-zinc-600"}`}>
                        {accountStatus.participant_message}
                      </p>
                      {accountStatus.league.queue.state === "running" && accountStatus.league.current_run?.progress ? (
                        <p className="mt-1 text-xs text-zinc-500">
                          {accountStatus.league.current_run.progress.matchups_completed ?? 0} of {accountStatus.league.current_run.progress.matchups_total ?? 0} matchups complete
                        </p>
                      ) : null}
                      {accountStatus.result ? (
                        <div className="mt-4 border-t border-zinc-200 pt-4">
                          <p className="font-semibold text-zinc-950">Rank #{accountStatus.result.rank} · {accountStatus.result.elo_rating.toLocaleString()} Elo</p>
                          <p className="mt-1 text-sm text-zinc-600">
                            {recordLabel(accountStatus.result.record.wins, "win", "wins")}, {recordLabel(accountStatus.result.record.losses, "loss", "losses")}
                            {accountStatus.result.record.draws > 0 ? `, ${recordLabel(accountStatus.result.record.draws, "draw", "draws")}` : ""}
                          </p>
                          <a className="mt-3 inline-flex text-sm font-semibold text-blue-700 hover:text-blue-800" href={`/browser-api/runs/${encodeURIComponent(accountStatus.result.id)}/artifacts`} download>
                            Download official hand logs
                          </a>
                        </div>
                      ) : null}
                      <a className="mt-3 inline-flex text-sm font-semibold text-blue-700 hover:text-blue-800" href={`/browser-api/submissions/${encodeURIComponent(accountStatus.submission.submission_id)}/logs`} download>
                        Download validation log
                      </a>
                    </>
                  )}
                </div>
                <button type="button" onClick={logout} className="mt-6 w-full rounded-lg border border-zinc-300 px-4 py-2.5 font-semibold text-zinc-900 hover:bg-zinc-50">
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
                  <button type="button" aria-label="Close" onClick={closeDialog} className="text-xl leading-none text-zinc-500">×</button>
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
                        Invite code
                        <input type="password" autoComplete="off" required maxLength={128} value={inviteCode} onChange={(event) => setInviteCode(event.target.value)} className="mt-1.5 w-full rounded-lg border border-zinc-300 px-3 py-2.5 font-normal outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
                        <span className="mt-1.5 block font-normal text-zinc-500">Provided by your cohort organizer.</span>
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
      )}
    </>
  );
}
