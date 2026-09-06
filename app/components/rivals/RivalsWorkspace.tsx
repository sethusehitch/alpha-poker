"use client";
/* eslint-disable react-hooks/set-state-in-effect, @typescript-eslint/no-unused-expressions */

import { useCallback, useEffect, useRef, useState } from "react";
import { rivalsApi, type Challenge, type Rival, type RivalDetail } from "./api";
import { BotAvatar } from "../BotAvatar";
import { emit, on } from "../uiBus";
import { useSession } from "../useSession";

// Rivals is only the people surface now: league standings live on /leaderboard.
type Tab = "mine" | "challenges";
const TAB_LABELS: Record<Tab, string> = {
  mine: "My rivals",
  challenges: "Challenges",
};
function time(value?: string | null) {
  return value
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "Recently";
}
function statusLabel(status: Challenge["status"]) {
  return status === "pending"
    ? "Pending"
    : status === "queued"
      ? "Queued"
      : status === "running"
        ? "Running"
        : status === "completed"
          ? "Challenge again"
          : status === "declined"
            ? "Declined"
            : status === "cancelled"
              ? "Cancelled"
              : "Needs attention";
}

function NemesisBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full border border-orange-300 bg-orange-50 px-2 py-0.5 text-[10px] font-bold tracking-wide text-orange-700 ${className}`}
    >
      <svg aria-hidden="true" viewBox="0 0 12 12" className="h-3 w-3" fill="none">
        <circle cx="6" cy="6" r="4.4" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="6" cy="6" r="1.3" fill="currentColor" />
      </svg>
      NEMESIS
    </span>
  );
}

function BoltIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4" fill="currentColor">
      <path d="M9.1 1.2 3.4 9h3.3l-.8 5.8L12.6 7H9.3l-.2-5.8Z" />
    </svg>
  );
}

/**
 * Challenge readiness, not live presence: a rival is "Online" exactly when they
 * have an active bot the viewer can play against.
 */
function ChallengeStatus({
  online,
  className = "",
}: {
  online: boolean;
  className?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      {online ? "Online" : "Offline"}
      <span
        aria-hidden="true"
        className={`h-2 w-2 rounded-full ${online ? "bg-emerald-500" : "bg-zinc-300"}`}
      />
    </span>
  );
}

function isOnline(rival: { has_active_bot?: boolean; bot_name: string | null }) {
  return rival.has_active_bot ?? Boolean(rival.bot_name);
}

function Portrait({
  name,
  rank,
  className,
}: {
  name: string;
  rank?: number | null;
  className: string;
}) {
  return (
    <span className="relative inline-flex shrink-0">
      <span
        aria-hidden="true"
        className="absolute -inset-1.5 rounded-full bg-[radial-gradient(circle_at_35%_30%,#e0ecff,transparent_70%)]"
      />
      <BotAvatar
        name={name}
        rank={rank ?? undefined}
        circle
        className={`relative ${className}`}
      />
    </span>
  );
}

function RivalCard({
  rival,
  onOpen,
  selected = false,
}: {
  rival: Rival;
  onOpen: (username: string) => void;
  selected?: boolean;
}) {
  return (
    <article
      className={`flex h-[16.8125rem] min-h-0 w-full max-w-[20.5625rem] flex-col justify-between overflow-hidden rounded-2xl border bg-white p-4 shadow-[0_8px_28px_rgba(23,35,70,0.04)] transition hover:shadow-[0_12px_32px_rgba(23,35,70,0.08)] ${selected ? "border-blue-500 ring-1 ring-blue-500/20" : "border-zinc-200 hover:border-blue-300"}`}
    >
      {/* min-h-0 + overflow-hidden keep long names or five-digit Elo values
          from stretching the card beyond its fixed compact height. */}
      <div className="flex min-h-0 flex-1 items-start gap-3.5 overflow-hidden">
        <div className="mt-1.5 shrink-0">
          <Portrait
            name={rival.username}
            rank={rival.rank}
            className="h-28 w-28"
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h2
              className="min-w-0 max-w-full truncate text-lg font-bold tracking-tight text-zinc-950"
              title={rival.username}
            >
              {rival.username}
            </h2>
            {rival.is_nemesis && <NemesisBadge />}
          </div>
          <p
            className="truncate text-sm text-zinc-500"
            title={rival.bot_name ?? undefined}
          >
            {rival.bot_name ?? "No active bot"}
          </p>
          <p className="mt-2 text-xl font-bold leading-none tabular-nums text-zinc-950">
            {rival.elo_rating.toLocaleString()}
          </p>
          <p className="mt-1 text-[0.65rem] font-bold leading-none tracking-[0.14em] text-zinc-500">
            ELO
          </p>
          <p className="mt-2 text-base font-semibold leading-tight tabular-nums text-zinc-900">
            {rival.direct_record.wins} – {rival.direct_record.losses}
          </p>
          <p className="text-xs text-zinc-500">vs you</p>
          <p className="mt-1 text-xs font-medium text-zinc-600">
            <ChallengeStatus online={isOnline(rival)} />
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => onOpen(rival.username)}
        className={`mt-3 w-full shrink-0 rounded-xl border px-3 py-2 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${selected ? "border-blue-600 bg-blue-600 text-white hover:bg-blue-700" : "border-blue-200 text-blue-700 hover:bg-blue-50"}`}
      >
        View rival
      </button>
    </article>
  );
}

function RivalGrid({
  items,
  onOpen,
  selected,
}: {
  items: Rival[];
  onOpen: (username: string) => void;
  selected?: string | null;
}) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(17.25rem,20.5625rem))] justify-center gap-4 sm:justify-start">
      {items.map((rival) => (
        <RivalCard
          key={rival.username}
          rival={rival}
          onOpen={onOpen}
          selected={selected === rival.username}
        />
      ))}
    </div>
  );
}

function ChallengeRow({
  challenge,
  onRecap,
  onOpen,
  viewer,
  highlighted,
  portraits,
}: {
  challenge: Challenge;
  onRecap: (id: string) => void;
  onOpen?: (challenge: Challenge) => void;
  viewer?: string;
  highlighted?: boolean;
  /** The overlay history shows both faces; the flat list stays text-only. */
  portraits?: boolean;
}) {
  const outcome =
    challenge.status !== "completed"
      ? null
      : !challenge.winner_username
        ? "draw"
        : viewer === challenge.winner_username
          ? "win"
          : "loss";
  const outcomeClass =
    outcome === "win"
      ? "bg-emerald-100 text-emerald-700"
      : outcome === "loss"
        ? "bg-red-100 text-red-700"
        : outcome === "draw"
          ? "bg-zinc-100 text-zinc-700"
          : "bg-blue-100 text-blue-700";
  return (
    <li
      className={`flex items-center gap-3 border-b border-zinc-100 px-4 py-3 last:border-0 ${highlighted ? "bg-blue-50 ring-1 ring-inset ring-blue-200" : ""}`}
    >
      <span
        className={`grid h-6 w-6 place-items-center rounded-full text-xs font-bold ${outcomeClass}`}
      >
        {outcome === "win"
          ? "✓"
          : outcome === "loss"
            ? "×"
            : outcome === "draw"
              ? "="
              : "…"}
      </span>
      {portraits && (
        <span className="hidden items-center gap-1 sm:flex">
          <BotAvatar
            name={challenge.challenger_username}
            className="h-7 w-7"
            circle
          />
          <span className="text-[10px] font-semibold text-zinc-400">vs</span>
          <BotAvatar
            name={challenge.challenged_username}
            className="h-7 w-7"
            circle
          />
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-bold tracking-wide text-zinc-800 uppercase">
          {outcome === "win"
            ? "Win"
            : outcome === "loss"
              ? "Loss"
              : outcome === "draw"
                ? "Draw"
                : statusLabel(challenge.status)}
        </p>
        <p className="truncate text-xs text-zinc-500">
          {challenge.opponent_username ??
            `${challenge.challenger_username} vs ${challenge.challenged_username}`}{" "}
          · {time(challenge.completed_at ?? challenge.created_at)} ·{" "}
          {challenge.hand_count} hands
        </p>
      </div>
      {challenge.margin_play_chips !== null &&
        challenge.margin_play_chips !== undefined && (
          <span
            className={`hidden text-xs font-semibold sm:inline ${outcome === "win" ? "text-emerald-700" : outcome === "loss" ? "text-red-600" : "text-zinc-600"}`}
          >
            {outcome === "win" ? "+" : ""}
            {challenge.margin_play_chips.toLocaleString()} play chips
          </span>
        )}
      {onOpen ? (
        <button
          onClick={() => onOpen(challenge)}
          type="button"
          className="rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"
        >
          Open
        </button>
      ) : challenge.status === "completed" && challenge.recap_url ? (
        <button
          onClick={() => onRecap(challenge.challenge_id)}
          type="button"
          className="rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"
        >
          View recap
        </button>
      ) : null}
    </li>
  );
}

function RecapDrawer({ id, close }: { id: string; close: () => void }) {
  const [data, setData] = useState<Awaited<
    ReturnType<typeof rivalsApi.recap>
  > | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError("");
    void rivalsApi
      .recap(id)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);
  return (
    <aside
      aria-label="Challenge recap"
      className="fixed inset-x-0 bottom-0 z-60 mx-auto max-h-[78vh] w-full max-w-3xl overflow-auto rounded-t-2xl border border-zinc-200 bg-white p-5 shadow-2xl sm:bottom-5 sm:rounded-2xl"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-bold tracking-widest text-blue-700">
            DIRECT CHALLENGE
          </p>
          <h2 className="mt-1 text-xl font-bold">Match recap</h2>
        </div>
        <button
          type="button"
          onClick={close}
          className="rounded-lg px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-100"
        >
          Close
        </button>
      </div>
      {error ? (
        <p role="alert" className="mt-5 text-sm text-red-700">
          {error}
        </p>
      ) : !data ? (
        <p className="mt-5 text-sm text-zinc-500">Loading recap…</p>
      ) : (
        <>
          <p className="mt-4 text-sm text-zinc-600">
            {data.challenge.challenger_username} and{" "}
            {data.challenge.challenged_username} played{" "}
            {data.challenge.hand_count} deterministic, unranked hands. Public
            Elo was unchanged.
          </p>
          {data.challenge.completed_at && (
            <p className="mt-2 text-xs text-zinc-500">
              Completed {time(data.challenge.completed_at)}
            </p>
          )}
          <h3 className="mt-6 font-semibold">Focused hand replay</h3>
          <ul className="mt-2 divide-y rounded-xl border border-zinc-200">
            {data.best_hands.map((hand) => (
              <li key={hand.hand_id}>
                <a
                  href={`/hands/${encodeURIComponent(hand.hand_id)}?rival=${encodeURIComponent(data.challenge.opponent_username ?? data.challenge.challenger_username)}&result=${encodeURIComponent(data.challenge.challenge_id)}`}
                  className="flex items-center justify-between px-4 py-3 text-sm hover:bg-blue-50"
                >
                  <span>
                    {hand.winner ? (
                      <>
                        Hand {hand.hand_number}{" "}
                        <span className="text-zinc-500">
                          won by {hand.winner}
                        </span>
                      </>
                    ) : (
                      <span className="text-zinc-600">
                        Hand {hand.hand_number} tied
                      </span>
                    )}
                  </span>
                  <span className="font-semibold text-blue-700">
                    Open replay
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}

function RivalOverlay({
  username,
  onClose,
  onRecap,
  viewer,
  highlightedId,
}: {
  username: string;
  onClose: () => void;
  onRecap: (id: string) => void;
  viewer?: string;
  highlightedId?: string | null;
}) {
  const [detail, setDetail] = useState<RivalDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [next, setNext] = useState<string | null>(null);
  const [confirmCreate, setConfirmCreate] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const returnFocus = useRef<Element | null>(null);
  const detailRequest = useRef(0);
  const load = useCallback(async () => {
    const request = ++detailRequest.current;
    setError("");
    setLoading(true);
    try {
      const result = await rivalsApi.detail(username);
      if (request !== detailRequest.current) return;
      setDetail(result);
      setNext(result.history.next_cursor);
    } catch (reason) {
      if (request !== detailRequest.current) return;
      setError(
        reason instanceof Error ? reason.message : "Could not load this rival.",
      );
    } finally {
      if (request === detailRequest.current) setLoading(false);
    }
  }, [username]);
  useEffect(
    () => () => {
      detailRequest.current += 1;
    },
    [],
  );
  const pollingStatus = detail?.current_challenge?.status;
  useEffect(() => {
    returnFocus.current = document.activeElement;
    document.body.style.overflow = "hidden";
    void load();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab" && panel.current) {
        const items = panel.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, [tabindex]:not([tabindex="-1"])',
        );
        const first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", key);
    window.setTimeout(
      () =>
        (
          panel.current?.querySelector<HTMLElement>("button") ?? panel.current
        )?.focus(),
      0,
    );
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", key);
      (returnFocus.current as HTMLElement | null)?.focus?.();
    };
  }, [load, onClose]);
  useEffect(() => {
    if (!["queued", "running"].includes(pollingStatus ?? "")) return;
    const interval = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(interval);
  }, [pollingStatus, load]);
  async function action(action?: "accept" | "decline" | "cancel") {
    if (!detail) return;
    setError("");
    setBusy(true);
    try {
      if (action && detail.current_challenge)
        await rivalsApi.transition(
          detail.current_challenge.challenge_id,
          action,
        );
      else await rivalsApi.create(detail.rival.username);
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not update this challenge.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function more() {
    if (!next) return;
    const request = ++detailRequest.current;
    setError("");
    try {
      const page = await rivalsApi.history(username, next);
      if (request !== detailRequest.current) return;
      setDetail((current) =>
        current
          ? {
              ...current,
              history: {
                items: [...current.history.items, ...page.items],
                next_cursor: page.next_cursor,
              },
            }
          : current,
      );
      setNext(page.next_cursor);
    } catch (reason) {
      if (request !== detailRequest.current) return;
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not load more history.",
      );
    }
  }
  const status = pollingStatus;
  const incoming =
    detail?.current_challenge?.challenger_username === detail?.rival.username;
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-end bg-zinc-950/25 p-0 sm:p-4"
      role="presentation"
      onMouseDown={onClose}
    >
      {/* Fixed near-viewport height: the panel no longer grows or shrinks with
          the history length, so opening rivals back to back does not make the
          overlay jump around. The history list absorbs the slack instead. */}
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="rival-title"
        tabIndex={-1}
        className="relative flex h-[92dvh] max-h-[100dvh] w-full max-w-[29rem] flex-col overflow-hidden rounded-t-2xl bg-white p-5 shadow-2xl outline-none sm:h-[calc(100dvh-2rem)] sm:max-h-[calc(100dvh-2rem)] sm:rounded-2xl sm:p-7"
        onMouseDown={(event) => event.stopPropagation()}
      >
        {/* Exactly one of loading, error, or detail is on screen. A failed
            first load used to leave the skeleton copy underneath the alert,
            which read as "Rival not found. Loading rival…". */}
        {!detail && loading ? (
          <div
            role="status"
            aria-live="polite"
            className="flex min-h-72 flex-1 flex-col items-center justify-center gap-4 py-10"
          >
            <span
              aria-hidden="true"
              className="h-9 w-9 rounded-full border-2 border-zinc-200 border-t-blue-600 motion-safe:animate-spin"
            />
            <p id="rival-title" className="text-sm text-zinc-500">
              Loading rival…
            </p>
          </div>
        ) : !detail ? (
          <div
            role="alert"
            className="flex min-h-72 flex-1 flex-col items-center justify-center px-4 py-10 text-center"
          >
            <span
              aria-hidden="true"
              className="grid h-12 w-12 place-items-center rounded-full bg-red-50 text-xl font-bold text-red-600"
            >
              !
            </span>
            <h1 id="rival-title" className="mt-4 text-xl font-bold text-zinc-950">
              Could not open this rival
            </h1>
            <p className="mt-2 max-w-sm text-sm leading-6 text-zinc-600">
              {error || "Could not load this rival."}
            </p>
            <div className="mt-6 flex w-full max-w-xs flex-col gap-2 sm:flex-row sm:justify-center">
              <button
                type="button"
                onClick={() => void load()}
                className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                Retry
              </button>
              <button
                type="button"
                onClick={onClose}
                className="rounded-xl border border-zinc-300 px-5 py-2.5 text-sm font-semibold text-zinc-700 hover:bg-zinc-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                Close
              </button>
            </div>
          </div>
        ) : (
          <>
            {error && (
              <p
                role="alert"
                className="mb-4 shrink-0 rounded-lg bg-red-50 p-3 text-sm text-red-700"
              >
                {error}
              </p>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close rival"
              className="absolute right-3 top-3 grid h-10 w-10 place-items-center rounded-lg text-xl text-zinc-500 hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-blue-600"
            >
              ×
            </button>
            <div className="flex shrink-0 flex-col items-center gap-5 text-center sm:flex-row sm:items-start sm:text-left">
              <div className="mt-1 shrink-0 sm:mt-3">
                <Portrait
                  name={detail.rival.username}
                  rank={detail.rival.rank}
                  className="h-32 w-32 sm:h-44 sm:w-44"
                />
              </div>
              <div className="min-w-0 w-full flex-1">
                <div className="flex flex-wrap items-center justify-center gap-2 pr-10 sm:translate-x-3 sm:justify-start">
                  <h1
                    id="rival-title"
                    className="min-w-0 max-w-full truncate text-3xl font-bold tracking-tight"
                    title={detail.rival.username}
                  >
                    {detail.rival.username}
                  </h1>
                  {detail.is_nemesis && <NemesisBadge className="text-[11px]" />}
                </div>
                <p className="mt-1 flex flex-wrap items-center justify-center gap-x-2 text-sm text-zinc-600 sm:translate-x-3 sm:justify-start">
                  <span
                    className="max-w-full truncate"
                    title={detail.rival.bot_name ?? undefined}
                  >
                    {detail.rival.bot_name ?? "No active bot"}
                  </span>
                  <span aria-hidden="true" className="text-zinc-300">
                    •
                  </span>
                  <ChallengeStatus online={detail.rival.has_active_bot} />
                </p>
                {detail.is_nemesis && detail.nemesis_explanation && (
                  <p className="mt-1.5 text-sm text-orange-800">
                    {detail.nemesis_explanation}
                  </p>
                )}
                {/* Auto-width columns instead of 1fr keep the two numbers
                    reading as one scoreline rather than drifting to the edges. */}
                <div className="mt-4 flex -translate-x-2 items-end justify-center gap-4 sm:-translate-x-3">
                  <div className="min-w-0 max-w-[9rem] text-center">
                    <p className="text-sm font-semibold text-blue-700">You</p>
                    <p className="text-4xl font-bold leading-none tabular-nums text-blue-700 sm:text-5xl">
                      {detail.direct_record.wins}
                    </p>
                  </div>
                  <span
                    aria-hidden="true"
                    className="mb-3 h-1 w-7 rounded-full bg-zinc-600"
                  />
                  <div className="min-w-0 max-w-[9rem] text-center">
                    <p
                      className="truncate text-sm font-semibold text-zinc-700"
                      title={detail.rival.username}
                    >
                      {detail.rival.username}
                    </p>
                    <p className="text-4xl font-bold leading-none tabular-nums text-zinc-950 sm:text-5xl">
                      {detail.direct_record.losses}
                    </p>
                  </div>
                </div>
                {detail.direct_record.draws > 0 && (
                  <p className="mt-1.5 text-center text-xs text-zinc-500">
                    {detail.direct_record.draws} drawn
                  </p>
                )}
                <div className="mt-5 flex -translate-x-2 flex-wrap justify-center gap-2 sm:-translate-x-3">
                  {status === "pending" && incoming ? (
                    <>
                      <button
                        disabled={busy}
                        onClick={() => void action("accept")}
                        className="rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50"
                      >
                        Accept
                      </button>
                      <button
                        disabled={busy}
                        onClick={() => void action("decline")}
                        className="rounded-xl border border-zinc-300 px-6 py-2.5 text-sm font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
                      >
                        Decline
                      </button>
                    </>
                  ) : status === "pending" ? (
                    <button
                      disabled={busy}
                      onClick={() => void action("cancel")}
                      className="rounded-xl border border-zinc-300 px-6 py-2.5 text-sm font-semibold text-zinc-700 hover:bg-zinc-50 disabled:cursor-not-allowed"
                    >
                      Pending · Cancel
                    </button>
                  ) : status && status !== "completed" ? (
                    <button
                      disabled
                      className="rounded-xl border border-zinc-200 bg-zinc-50 px-6 py-2.5 text-sm font-semibold text-zinc-600 disabled:cursor-not-allowed"
                    >
                      {statusLabel(status)}
                    </button>
                  ) : (
                    <button
                      disabled={
                        busy ||
                        !detail.viewer.has_active_bot ||
                        !detail.rival.has_active_bot
                      }
                      onClick={() => setConfirmCreate(true)}
                      className="inline-flex min-w-44 max-w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-8 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {busy ? (
                        "Starting…"
                      ) : (
                        <>
                          <BoltIcon />
                          <span className="min-w-0 truncate">
                            Challenge {detail.rival.username}
                            {status === "completed" ? " again" : ""}
                          </span>
                        </>
                      )}
                    </button>
                  )}
                </div>
                {!detail.viewer.has_active_bot && (
                  <p className="mt-2 text-center text-xs text-zinc-500">
                    Submit an active bot to start a direct challenge.
                  </p>
                )}
                {detail.viewer.has_active_bot &&
                  !detail.rival.has_active_bot && (
                    <p className="mt-2 text-center text-xs text-zinc-500">
                      You can view this rival now. Challenges unlock when they
                      submit an active bot.
                    </p>
                  )}
              </div>
            </div>
            {/* Nothing follows the history: the overlay is identity, one
                action, and a head-to-head list that takes whatever height is
                left over and scrolls inside itself. */}
            <section className="mt-6 flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-zinc-200">
              <div className="flex shrink-0 items-baseline border-b border-zinc-200 px-4 py-3">
                <h2 className="font-semibold">Recent head-to-head</h2>
              </div>
              <ul className="min-h-0 flex-1 overflow-y-auto">
                {detail.history.items.length ? (
                  detail.history.items.map((challenge) => (
                    <ChallengeRow
                      key={challenge.challenge_id}
                      challenge={challenge}
                      onRecap={onRecap}
                      viewer={viewer}
                      highlighted={challenge.challenge_id === highlightedId}
                      portraits
                    />
                  ))
                ) : (
                  <li className="px-4 py-6 text-sm text-zinc-500">
                    No completed direct challenges yet.
                  </li>
                )}
                {next && (
                  <li className="border-t border-zinc-100 px-4 py-3">
                    <button
                      type="button"
                      onClick={() => void more()}
                      className="text-sm font-semibold text-blue-700 hover:underline"
                    >
                      Load more history
                    </button>
                  </li>
                )}
              </ul>
            </section>
            {confirmCreate && (
              <div className="absolute inset-0 z-10 flex items-center justify-center rounded-2xl bg-zinc-950/25 p-5">
                <div
                  role="alertdialog"
                  aria-modal="true"
                  aria-labelledby="challenge-confirmation"
                  className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl"
                >
                  <h2 id="challenge-confirmation" className="text-lg font-bold">
                    Challenge {detail.rival.username}?
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-zinc-600">
                    This starts an asynchronous, unranked 200-hand direct
                    challenge. Public Elo will not change.
                  </p>
                  <div className="mt-5 flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setConfirmCreate(false)}
                      className="rounded-lg px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-100"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        setConfirmCreate(false);
                        void action();
                      }}
                      className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      Confirm challenge
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function RivalsWorkspace({ initialTab = "mine" }: { initialTab?: Tab }) {
  const { session, loaded } = useSession();
  const workspaceGeneration = useRef(0);
  // `undefined` is deliberately distinct from a resolved signed-out session.
  // The first authenticated hydration must retain an exact rival/result link.
  const sessionOwner = useRef<string | null | undefined>(undefined);
  const overlayWasPushed = useRef(false);
  const recapWasPushed = useRef(false);
  const [tab, setTab] = useState<Tab>(initialTab);
  const [items, setItems] = useState<Rival[]>([]);
  // The API only offers suggestions when "mine" comes back empty and unfiltered.
  const [suggested, setSuggested] = useState<Rival[]>([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [recap, setRecap] = useState<string | null>(null);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const viewer = session?.username;
  const [stateOwner, setStateOwner] = useState<string | null>(viewer ?? null);
  const accountChanged = stateOwner !== (viewer ?? null);
  const updateUrl = (
    params: URLSearchParams,
    replace = false,
    pushed?: "overlay" | "recap",
  ) => {
    const href = `${window.location.pathname}${params.size ? `?${params}` : ""}`;
    if (href === `${window.location.pathname}${window.location.search}`)
      return false;
    const state = pushed
      ? {
          ...(history.state ?? {}),
          rivalsOverlay: pushed === "overlay",
          rivalsRecap: pushed === "recap",
        }
      : {};
    replace
      ? history.replaceState(state, "", href)
      : history.pushState(state, "", href);
    return true;
  };
  const open = (username: string) => {
    setSelected(username);
    setRecap(null);
    const params = new URLSearchParams(window.location.search);
    params.set("rival", username);
    params.delete("challenge");
    params.delete("result");
    overlayWasPushed.current = updateUrl(params, false, "overlay");
  };
  const openChallenge = (challenge: Challenge) => {
    if (!challenge.opponent_username) return;
    setSelected(challenge.opponent_username);
    const params = new URLSearchParams(window.location.search);
    params.set("rival", challenge.opponent_username);
    if (challenge.status === "completed" && challenge.recap_url) {
      params.set("result", challenge.challenge_id);
      params.delete("challenge");
      setRecap(challenge.challenge_id);
    } else {
      params.set("challenge", challenge.challenge_id);
      params.delete("result");
      setRecap(null);
    }
    overlayWasPushed.current = updateUrl(params, false, "overlay");
  };
  const openRecap = (challengeId: string) => {
    setRecap(challengeId);
    const params = new URLSearchParams(window.location.search);
    if (params.get("result") === challengeId) return;
    params.set("result", challengeId);
    recapWasPushed.current = updateUrl(params, false, "recap");
  };
  const closeRecap = () => {
    setRecap(null);
    if (recapWasPushed.current) {
      recapWasPushed.current = false;
      history.back();
      return;
    }
    const params = new URLSearchParams(window.location.search);
    params.delete("result");
    updateUrl(params, true);
  };
  const close = () => {
    setSelected(null);
    setRecap(null);
    if (overlayWasPushed.current) {
      overlayWasPushed.current = false;
      recapWasPushed.current = false;
      history.back();
      return;
    }
    const params = new URLSearchParams(window.location.search);
    params.delete("rival");
    params.delete("challenge");
    params.delete("result");
    updateUrl(params, true);
  };
  const syncFromLocation = useCallback(() => {
    const generation = workspaceGeneration.current;
    const requestUrl = window.location.href;
    const state = history.state as {
      rivalsOverlay?: boolean;
      rivalsRecap?: boolean;
    } | null;
    overlayWasPushed.current = Boolean(state?.rivalsOverlay);
    recapWasPushed.current = Boolean(state?.rivalsRecap);
    const fromUrl = new URLSearchParams(window.location.search);
    const rawTab = fromUrl.get("tab");
    if (rawTab === "challenges") setTab(rawTab);
    setSelected(fromUrl.get("rival"));
    const result = fromUrl.get("result");
    const challenge = fromUrl.get("challenge") ?? result;
    if (!result) setRecap(null);
    if (challenge && session) {
      void rivalsApi
        .challenge(challenge)
        .then((found) => {
          if (generation !== workspaceGeneration.current || requestUrl !== window.location.href) return;
          if (found.opponent_username) setSelected(found.opponent_username);
          if (result && found.recap_url) setRecap(found.challenge_id);
        })
        .catch(() => undefined);
    }
  }, [session]);
  useEffect(() => {
    emit("rivals-dialog-changed", { open: Boolean(selected || recap) });
  }, [selected, recap]);
  useEffect(() => {
    return () => emit("rivals-dialog-changed", { open: false });
  }, []);
  useEffect(() => {
    if (!loaded) return;
    const nextOwner = viewer ?? null;
    const changedOwner =
      sessionOwner.current !== undefined && sessionOwner.current !== nextOwner;
    sessionOwner.current = nextOwner;
    workspaceGeneration.current += 1;
    if (changedOwner) {
      const params = new URLSearchParams(window.location.search);
      params.delete("rival");
      params.delete("challenge");
      params.delete("result");
      const rawTab = params.get("tab");
      setTab(rawTab === "challenges" ? rawTab : initialTab);
      setQuery("");
      const href = `${window.location.pathname}${params.size ? `?${params}` : ""}`;
      history.replaceState({}, "", href);
    }
    setStateOwner(viewer ?? null);
    setItems([]);
    setSuggested([]);
    setChallenges([]);
    setSelected(null);
    setRecap(null);
    setError("");
    setBusy(Boolean(viewer));
    overlayWasPushed.current = false;
    recapWasPushed.current = false;
  }, [initialTab, loaded, viewer]);
  useEffect(() => {
    syncFromLocation();
    const pop = () => syncFromLocation();
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, [syncFromLocation]);
  useEffect(() => {
    return on("close-panels", () => {
      // Other global overlays (account, feedback, notifications) own the
      // interaction now. Replace the URL instead of walking history so an
      // older challenge result is not revealed behind the new overlay.
      workspaceGeneration.current += 1;
      overlayWasPushed.current = false;
      recapWasPushed.current = false;
      setSelected(null);
      setRecap(null);
      const params = new URLSearchParams(window.location.search);
      params.delete("rival");
      params.delete("challenge");
      params.delete("result");
      const href = `${window.location.pathname}${params.size ? `?${params}` : ""}`;
      history.replaceState({}, "", href);
    });
  }, []);
  useEffect(() => {
    if (!loaded || session) return;
    const timer = window.setTimeout(() => emit("open-account", {}), 0);
    return () => window.clearTimeout(timer);
  }, [loaded, session]);
  useEffect(() => {
    if (!loaded || !session) return;
    const generation = workspaceGeneration.current;
    let cancelled = false;
    const stale = () => cancelled || generation !== workspaceGeneration.current;
    // Unsearched, the list is the people you have actually played. A search
    // widens to every cohort candidate so new rivals stay discoverable.
    const source = query ? "leaderboard" : "mine";
    setError("");
    if (tab === "challenges") {
      setBusy(true);
      void Promise.all([
        rivalsApi.challenges("incoming"),
        rivalsApi.challenges("running"),
        rivalsApi.challenges("finished"),
      ])
        .then((sets) => {
          if (stale()) return;
          setChallenges(sets.flatMap((set) => set.items));
          setBusy(false);
        })
        .catch((reason) => {
          if (stale()) return;
          setError(reason.message);
          setBusy(false);
        });
      return () => {
        cancelled = true;
      };
    }
    setBusy(true);
    const timer = window.setTimeout(
      () => {
        void rivalsApi
          .list(source, query)
          .then((data) => {
            if (stale()) return;
            setItems(data.items);
            setSuggested(data.suggested_items ?? []);
            setBusy(false);
          })
          .catch((reason) => {
            if (stale()) return;
            setError(reason.message);
            setBusy(false);
          });
      },
      query ? 200 : 0,
    );
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [loaded, session, tab, query]);
  function choose(next: Tab) {
    setTab(next);
    setError("");
    const params = new URLSearchParams(window.location.search);
    if (next === "mine") params.delete("tab");
    else params.set("tab", next);
    updateUrl(params);
  }
  if (loaded && !session) {
    return (
      <main className="grid min-h-[calc(100vh-4.5rem)] place-items-center bg-zinc-50 px-5 text-center">
        <div>
          <h1 className="text-2xl font-bold">Sign in to use Rivals</h1>
          <p className="mt-2 text-zinc-600">
            Your account dialog is open. Sign in to view direct challenges.
          </p>
        </div>
      </main>
    );
  }
  return (
    <main className="min-h-[calc(100vh-4.5rem)] bg-[#f6f8fc]">
      <div className="mx-auto max-w-[90rem] px-5 py-10 sm:px-8 sm:py-14">
        {/* The title leads. No eyebrow, no explainer: the search field is the
            next thing a participant needs. */}
        <h1 className="text-4xl font-bold tracking-tight text-zinc-950 sm:text-5xl">
          Choose a rival
        </h1>
        <label className="mt-6 block max-w-md">
          <span className="sr-only">Search players or bots</span>
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setError("");
              // A search is always a search for people, so it answers on the
              // rivals list rather than silently filtering nothing.
              if (event.target.value && tab !== "mine") choose("mine");
              setQuery(event.target.value);
            }}
            placeholder="Search player or bot"
            className="w-full rounded-xl border border-zinc-300 bg-white px-4 py-3 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
          />
        </label>
        <div className="mt-6 border-b border-zinc-200">
          <nav aria-label="Rivals sections">
            <div role="tablist" className="flex gap-1">
              {(Object.keys(TAB_LABELS) as Tab[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={tab === key}
                  onClick={() => choose(key)}
                  className={`relative px-4 py-3 text-sm font-semibold ${tab === key ? "text-blue-700" : "text-zinc-600 hover:text-zinc-950"}`}
                >
                  {TAB_LABELS[key]}
                  {tab === key && (
                    <span className="absolute inset-x-4 bottom-[-1px] h-0.5 bg-blue-600" />
                  )}
                </button>
              ))}
            </div>
          </nav>
        </div>
        {tab === "mine" && (
          <>
            {accountChanged || error ? (
              <p
                role="alert"
                className={`mt-8 rounded-xl border p-4 text-sm ${accountChanged ? "border-zinc-200 bg-white text-zinc-600" : "border-red-200 bg-red-50 text-red-800"}`}
              >
                {accountChanged ? "Loading your Rivals workspace…" : error}
              </p>
            ) : busy ? (
              <p className="mt-8 text-sm text-zinc-500">Loading rivals…</p>
            ) : items.length ? (
              <div className="mt-7">
                <RivalGrid items={items} onOpen={open} selected={selected} />
              </div>
            ) : suggested.length ? (
              <section className="mt-7">
                <h2 className="text-xl font-bold tracking-tight text-zinc-950">
                  Suggested
                </h2>
                <div className="mt-4">
                  <RivalGrid items={suggested} onOpen={open} selected={selected} />
                </div>
              </section>
            ) : (
              <p className="mt-8 rounded-xl border border-zinc-200 bg-white p-5 text-zinc-600">
                {query
                  ? "No rivals match that search yet."
                  : "No rivals yet. Search for a player to start a direct challenge."}
              </p>
            )}
          </>
        )}
        {tab === "challenges" && (
          <section className="mt-7 max-w-3xl">
            <h2 className="text-xl font-bold">Your challenges</h2>
            {accountChanged || error ? (
              <p
                role="alert"
                className={`mt-4 ${accountChanged ? "text-zinc-600" : "text-red-700"}`}
              >
                {accountChanged ? "Loading your Rivals workspace…" : error}
              </p>
            ) : busy ? (
              <p className="mt-4 text-zinc-500">Loading challenges…</p>
            ) : (
              <ul className="mt-4 rounded-xl border border-zinc-200 bg-white">
                {challenges.length ? (
                  challenges.map((challenge) => (
                    <ChallengeRow
                      key={challenge.challenge_id}
                      challenge={challenge}
                      onRecap={openRecap}
                      onOpen={openChallenge}
                      viewer={viewer}
                    />
                  ))
                ) : (
                  <li className="p-5 text-sm text-zinc-500">
                    No direct challenges yet.
                  </li>
                )}
              </ul>
            )}
          </section>
        )}
      </div>
      {!accountChanged && selected && (
        <RivalOverlay
          key={`${viewer ?? "signed-out"}:${selected}`}
          username={selected}
          onClose={close}
          onRecap={openRecap}
          viewer={viewer}
          highlightedId={recap}
        />
      )}{" "}
      {!accountChanged && recap && (
        <RecapDrawer
          key={`${viewer ?? "signed-out"}:${recap}`}
          id={recap}
          close={closeRecap}
        />
      )}
    </main>
  );
}
