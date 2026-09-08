"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { BotAvatar } from "../BotAvatar";
import { CopyPromptButton } from "../CopyPromptButton";
import { BUILD_BOT_PROMPT, STARTER_KIT_URL } from "../agentPrompt";
import { emit } from "../uiBus";
import { useSession } from "../useSession";

type SubmissionStatus = "queued" | "validating" | "accepted" | "rejected";

type AccountStatus = {
  avatar?: { id: string; url: string };
  participant_state: string;
  participant_message: string;
  submission: {
    submission_id: string;
    bot_name: string;
    status: string;
    error?: string | null;
    updated_at?: string | null;
  } | null;
  league: {
    queue: { state: string; message: string };
    current_run?: {
      progress?: { matchups_completed?: number; matchups_total?: number };
    } | null;
  };
  result: {
    id: string;
    rank: number;
    elo_rating: number;
    record: { wins: number; losses: number; draws: number };
    completed_at?: string | null;
  } | null;
};

const STATUS_TONE: Record<SubmissionStatus, string> = {
  queued: "bg-blue-50 text-blue-700 ring-blue-200",
  validating: "bg-blue-50 text-blue-700 ring-blue-200",
  accepted: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  rejected: "bg-red-50 text-red-700 ring-red-200",
};
const STATUS_LABEL: Record<SubmissionStatus, string> = {
  queued: "Queued",
  validating: "Checking",
  accepted: "Accepted",
  rejected: "Rejected",
};

function PictureEdit() {
  return <a href="/profile" aria-label="Change picture" title="Change picture" className="absolute -right-1 -top-1 grid h-9 w-9 place-items-center rounded-full border border-zinc-200 bg-white text-zinc-700 shadow-sm hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4"><path d="m12.5 4.5 3 3M3.5 16.5l3.7-.8 9-9a2.1 2.1 0 0 0-3-3l-9 9-.7 3.8Z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
  </a>;
}

function submissionStatus(value: string): SubmissionStatus {
  return value === "validating" || value === "accepted" || value === "rejected"
    ? value
    : "queued";
}

// Acceptance is not the end of a queued/running league evaluation.
function isSettled(status: AccountStatus | null) {
  const state = status?.submission?.status;
  return state === "rejected" || (state === "accepted" &&
    !["queued", "running", "awaiting_first_run", "waiting_for_players"].includes(status?.participant_state ?? ""));
}

function Plate({ children }: { children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded-3xl border border-zinc-200 bg-[radial-gradient(130%_120%_at_50%_-10%,#eff6ff_0%,#ffffff_58%)] shadow-[0_16px_44px_rgba(23,35,70,0.06)]">
      {children}
    </section>
  );
}

function Suits() {
  return (
    <p
      aria-hidden="true"
      className="select-none text-lg tracking-[0.5em] text-blue-200"
    >
      ♠♥♦♣
    </p>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white px-4 py-4 text-center">
      <p className="text-2xl font-bold tabular-nums tracking-tight text-zinc-950 sm:text-3xl">
        {value}
      </p>
      <p className="mt-1 text-[0.7rem] font-bold tracking-[0.16em] text-zinc-500">
        {label}
      </p>
    </div>
  );
}

function LogLink({ href, children }: { href: string; children: string }) {
  return (
    <a
      href={href}
      download
      className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 text-sm font-semibold text-blue-700 hover:border-blue-300 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
    >
      <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4" fill="none">
        <path
          d="M8 2.25v7.5m0 0 3-3m-3 3-3-3M3 12.75h10"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {children}
    </a>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto min-h-[calc(100dvh-4.5rem)] w-full max-w-3xl px-5 py-10 sm:px-8 sm:py-14">
      <h1 className="text-[0.7rem] font-bold tracking-[0.22em] text-blue-700">
        MY BOT
      </h1>
      <div className="mt-5">{children}</div>
    </main>
  );
}

export function MyBotWorkspace() {
  const { session, loaded } = useSession();
  const requestGeneration = useRef(0);
  const [loadState, setLoadState] = useState<{
    owner: string;
    status: AccountStatus | null;
    error: string;
    loading: boolean;
  }>({ owner: "", status: null, error: "", loading: true });

  const refresh = useCallback(async (owner: string) => {
    const request = ++requestGeneration.current;
    setLoadState({ owner, status: null, error: "", loading: true });
    try {
      const response = await fetch("/browser-api/account/status", {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      const body = await response.json().catch(() => null);
      if (!response.ok)
        throw new Error(
          body?.error?.message ?? "Could not reach your bot right now.",
        );
      if (request !== requestGeneration.current) return;
      setLoadState({
        owner,
        status: body as AccountStatus,
        error: "",
        loading: false,
      });
    } catch (reason) {
      if (request !== requestGeneration.current) return;
      setLoadState({
        owner,
        status: null,
        error:
          reason instanceof Error
            ? reason.message
            : "Could not reach your bot right now.",
        loading: false,
      });
    }
  }, []);

  useEffect(() => {
    if (!loaded || !session) {
      requestGeneration.current += 1;
      return;
    }
    const username = session.username;
    const timer = window.setTimeout(() => void refresh(username), 0);
    return () => window.clearTimeout(timer);
  }, [loaded, session, refresh]);

  const visibleState =
    session && loadState.owner === session.username
      ? loadState
      : { owner: session?.username ?? "", status: null, error: "", loading: true };
  const visibleStatus = visibleState.status;

  useEffect(() => {
    if (!session || isSettled(visibleStatus)) return;
    const username = session.username;
    const interval = window.setInterval(() => void refresh(username), 10_000);
    return () => window.clearInterval(interval);
  }, [session, visibleStatus, refresh]);

  if (!loaded || (session && visibleState.loading && !visibleStatus)) {
    return (
      <Shell>
        <Plate>
          <div
            role="status"
            aria-live="polite"
            className="flex min-h-72 flex-col items-center justify-center gap-4 p-10"
          >
            <span
              aria-hidden="true"
              className="h-9 w-9 rounded-full border-2 border-zinc-200 border-t-blue-600 motion-safe:animate-spin"
            />
            <p className="text-sm text-zinc-500">Dealing you in…</p>
          </div>
        </Plate>
      </Shell>
    );
  }

  if (!session) {
    return (
      <Shell>
        <Plate>
          <div className="flex min-h-72 flex-col items-center justify-center gap-5 p-10 text-center">
            <Suits />
            <p className="text-2xl font-bold tracking-tight text-zinc-950">
              Sign in to see your bot
            </p>
            <button
              type="button"
              onClick={() => emit("open-account", {})}
              className="min-h-11 rounded-xl bg-blue-600 px-6 text-sm font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              Log in
            </button>
          </div>
        </Plate>
      </Shell>
    );
  }

  if (!visibleStatus) {
    return (
      <Shell>
        <Plate>
          <div
            role="alert"
            className="flex min-h-72 flex-col items-center justify-center gap-4 p-10 text-center"
          >
            <span
              aria-hidden="true"
              className="grid h-12 w-12 place-items-center rounded-full bg-red-50 text-xl font-bold text-red-600"
            >
              !
            </span>
            <p className="max-w-sm text-sm leading-6 text-zinc-600">
              {visibleState.error || "Could not reach your bot right now."}
            </p>
            <button
              type="button"
              onClick={() => void refresh(session.username)}
              className="min-h-11 rounded-xl bg-blue-600 px-6 text-sm font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              Retry
            </button>
          </div>
        </Plate>
      </Shell>
    );
  }

  const submission = visibleStatus.submission;

  if (!submission) {
    return (
      <Shell>
        <Plate>
          <div className="flex flex-col items-center gap-6 px-5 py-12 text-center sm:px-10">
            <div className="relative"><BotAvatar name={session.username} avatar={visibleStatus.avatar} circle className="h-28 w-28" /><PictureEdit /></div>
            <div>
              <p className="text-3xl font-bold tracking-tight text-zinc-950">
                No bot uploaded yet
              </p>
              <p className="mt-2 text-zinc-600">
                Two steps and your agent builds the bot.
              </p>
            </div>
            <Suits />
            <div className="flex w-full max-w-md flex-col gap-3 sm:flex-row sm:justify-center">
              <a
                href={STARTER_KIT_URL}
                download
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                Download starter kit
                <svg
                  aria-hidden="true"
                  viewBox="0 0 16 16"
                  className="h-4 w-4"
                  fill="none"
                >
                  <path
                    d="M8 2.25v7.5m0 0 3-3m-3 3-3-3M3 12.75h10"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </a>
              <CopyPromptButton
                text={BUILD_BOT_PROMPT}
                label="Copy agent instructions"
              />
            </div>
          </div>
        </Plate>
      </Shell>
    );
  }

  const chip = submissionStatus(submission.status);
  const result = visibleStatus.result;
  const record = result?.record;
  const state = visibleStatus.participant_state;
  const statusLabel = ({
    waiting_for_players: "Pending opponent",
    queued: "Waiting to play",
    running: "Playing matches",
    validating: "Checking bot",
    awaiting_first_run: "Waiting to play",
    automation_paused: "Matches paused",
    rejected: "Needs changes",
    failed: "Run failed",
    completed: "In the league",
  } as Record<string, string>)[state] ?? STATUS_LABEL[chip];
  const pending = ["waiting_for_players", "queued", "running", "validating", "awaiting_first_run"].includes(state);

  return (
    <Shell>
      <Plate>
        <div className="flex flex-col items-center gap-4 px-5 pt-10 pb-8 text-center sm:px-10">
          <div className="relative"><BotAvatar name={session.username} avatar={visibleStatus.avatar} circle className="h-28 w-28" /><PictureEdit /></div>
          <div className="min-w-0">
            <p className="truncate text-3xl font-bold tracking-tight text-zinc-950 sm:text-4xl">
              {submission.bot_name}
            </p>
            <span
              role="status"
              className={`mt-3 inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold ring-1 ${pending ? "bg-blue-50 text-blue-700 ring-blue-200" : STATUS_TONE[chip]}`}
            >
              {statusLabel}
              {pending && <span aria-hidden="true" className="h-3.5 w-3.5 rounded-full border-2 border-current border-r-transparent motion-safe:animate-spin" />}
            </span>
          </div>
        </div>

        {result && <div className="grid grid-cols-3 gap-3 border-t border-zinc-200/80 bg-white/60 p-4 sm:p-5">
          <Stat
            label="ELO"
            value={result ? result.elo_rating.toLocaleString() : "—"}
          />
          <Stat
            label="W–L"
            value={record ? `${record.wins}–${record.losses}` : "—"}
          />
          <Stat label="RANK" value={result ? `#${result.rank}` : "—"} />
        </div>}
      </Plate>

      {record && record.draws > 0 && (
        <p className="mt-3 text-center text-xs text-zinc-500">
          {record.draws} {record.draws === 1 ? "draw" : "draws"}
        </p>
      )}

      <div className="mt-5 flex flex-wrap justify-center gap-3">
        {result && (
          <LogLink
            href={`/browser-api/runs/${encodeURIComponent(result.id)}/artifacts`}
          >
            Latest result logs
          </LogLink>
        )}
      </div>
    </Shell>
  );
}
