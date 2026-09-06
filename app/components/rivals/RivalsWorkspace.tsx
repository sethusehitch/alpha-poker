"use client";
/* eslint-disable react-hooks/set-state-in-effect, @typescript-eslint/no-unused-expressions */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  rivalsApi,
  type Challenge,
  type Compare,
  type Rival,
  type RivalDetail,
} from "./api";
import { emit, on } from "../uiBus";
import { useSession } from "../useSession";

type Tab = "mine" | "leaderboard" | "challenges" | "records";
const TAB_LABELS: Record<Tab, string> = {
  mine: "My rivals",
  leaderboard: "Leaderboard",
  challenges: "Challenges",
  records: "League records",
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

function Robot({
  name,
  rank,
  className = "",
}: {
  name: string;
  rank?: number;
  className?: string;
}) {
  const hash = Array.from(name).reduce(
    (total, letter) => total + letter.codePointAt(0)!,
    0,
  );
  const position = ["0% 43%", "50% 43%", "100% 43%"][
    Math.abs((rank ?? hash) % 3)
  ];
  return (
    <span
      aria-hidden="true"
      data-robot={name}
      className={`relative grid h-14 w-14 shrink-0 overflow-hidden rounded-2xl bg-gradient-to-br from-blue-100 via-white to-violet-100 shadow-inner ring-1 ring-blue-100 ${className}`}
    >
      <span
        className="absolute inset-0 bg-no-repeat"
        style={{
          backgroundImage: "url('/robot-avatars.png?v=poker-kids-1')",
          backgroundPosition: position,
          backgroundSize: "300% auto",
        }}
      />
    </span>
  );
}

function RivalCard({
  rival,
  onOpen,
}: {
  rival: Rival;
  onOpen: (username: string) => void;
}) {
  return (
    <article className="flex min-h-44 flex-col rounded-2xl border border-zinc-200 bg-white p-4 shadow-[0_8px_28px_rgba(23,35,70,0.04)] transition hover:border-blue-300">
      <div className="flex gap-3">
        <Robot name={rival.username} rank={rival.rank} />
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="truncate font-semibold text-zinc-950">
              {rival.username}
            </h2>
            {rival.is_nemesis && (
              <span className="rounded-full border border-orange-300 bg-orange-50 px-2 py-0.5 text-[10px] font-bold tracking-wide text-orange-700">
                NEMESIS
              </span>
            )}
          </div>
          <p className="truncate text-sm text-zinc-500">{rival.bot_name}</p>
          <p className="mt-2 font-semibold text-zinc-900">
            {rival.elo_rating.toLocaleString()}{" "}
            <span className="text-xs font-medium text-zinc-500">Elo</span>
          </p>
          <p className="mt-1 text-sm text-zinc-600">
            {rival.direct_record.wins} W · {rival.direct_record.losses} L
            {rival.direct_record.draws > 0
              ? ` · ${rival.direct_record.draws} D`
              : ""}
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => onOpen(rival.username)}
        className="mt-auto w-full rounded-lg border border-blue-300 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-blue-600"
      >
        View rival
      </button>
    </article>
  );
}

function ChallengeRow({
  challenge,
  onRecap,
  onOpen,
  viewer,
  highlighted,
}: {
  challenge: Challenge;
  onRecap: (id: string) => void;
  onOpen?: (challenge: Challenge) => void;
  viewer?: string;
  highlighted?: boolean;
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
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-zinc-800">
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
  const [busy, setBusy] = useState(false);
  const [next, setNext] = useState<string | null>(null);
  const [confirmCreate, setConfirmCreate] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const returnFocus = useRef<Element | null>(null);
  const detailRequest = useRef(0);
  const load = useCallback(async () => {
    const request = ++detailRequest.current;
    setError("");
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
      () => panel.current?.querySelector<HTMLElement>("button")?.focus(),
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
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="rival-title"
        className="relative max-h-[100dvh] w-full max-w-2xl overflow-auto rounded-t-2xl bg-white p-5 shadow-2xl sm:max-h-[calc(100dvh-2rem)] sm:rounded-2xl sm:p-7"
        onMouseDown={(event) => event.stopPropagation()}
      >
        {error && (
          <p
            role="alert"
            className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700"
          >
            {error}
          </p>
        )}
        {!detail ? (
          <p className="text-zinc-500">Loading rival…</p>
        ) : (
          <>
            <div className="flex items-start justify-between gap-3">
              <div className="flex gap-4">
                <Robot
                  name={detail.rival.username}
                  rank={detail.rival.rank}
                  className="h-20 w-20 text-4xl"
                />
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h1
                      id="rival-title"
                      className="text-3xl font-bold tracking-tight"
                    >
                      {detail.rival.username}
                    </h1>
                    {detail.is_nemesis && (
                      <span className="rounded-full border border-orange-300 bg-orange-50 px-2.5 py-1 text-xs font-bold text-orange-700">
                        NEMESIS
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-zinc-600">
                    {detail.rival.bot_name} ·{" "}
                    {detail.rival.elo_rating.toLocaleString()} Elo
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close rival"
                className="rounded-lg px-3 py-2 text-xl text-zinc-500 hover:bg-zinc-100"
              >
                ×
              </button>
            </div>
            <div className="mt-6 grid grid-cols-3 gap-2 rounded-xl bg-zinc-50 p-4 text-center">
              <div>
                <strong className="block text-2xl text-blue-700">
                  {detail.direct_record.wins}
                </strong>
                <span className="text-xs text-zinc-500">You</span>
              </div>
              <div>
                <strong className="block text-2xl">
                  {detail.direct_record.draws}
                </strong>
                <span className="text-xs text-zinc-500">Draws</span>
              </div>
              <div>
                <strong className="block text-2xl">
                  {detail.direct_record.losses}
                </strong>
                <span className="text-xs text-zinc-500">
                  {detail.rival.username}
                </span>
              </div>
            </div>
            {detail.is_nemesis && detail.nemesis_explanation && (
              <p className="mt-3 text-sm text-orange-800">
                {detail.nemesis_explanation}
              </p>
            )}
            <div className="mt-5 flex gap-2">
              {status === "pending" && incoming ? (
                <>
                  <button
                    disabled={busy}
                    onClick={() => void action("accept")}
                    className="flex-1 rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    Accept
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => void action("decline")}
                    className="rounded-xl border border-zinc-300 px-4 py-3 font-semibold"
                  >
                    Decline
                  </button>
                </>
              ) : status === "pending" ? (
                <button
                  disabled={busy}
                  onClick={() => void action("cancel")}
                  className="w-full rounded-xl border border-zinc-300 px-4 py-3 font-semibold text-zinc-700 disabled:cursor-not-allowed"
                >
                  Pending · Cancel
                </button>
              ) : status === "queued" || status === "running" ? (
                <button
                  disabled
                  className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 font-semibold text-zinc-600 disabled:cursor-not-allowed"
                >
                  {statusLabel(status)}
                </button>
              ) : status && status !== "completed" ? (
                <button
                  disabled
                  className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 font-semibold text-zinc-600"
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
                  className="w-full rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy
                    ? "Starting…"
                    : status === "completed"
                      ? "Challenge again"
                      : "Challenge"}
                </button>
              )}
            </div>
            {!detail.viewer.has_active_bot && (
              <p className="mt-2 text-xs text-zinc-500">
                Submit an active bot to start a direct challenge.
              </p>
            )}
            <section className="mt-6">
              <div className="flex items-baseline justify-between">
                <h2 className="font-semibold">Recent head-to-head</h2>
                <span className="text-xs text-zinc-500">
                  Direct challenges only
                </span>
              </div>
              <ul className="mt-3 max-h-72 overflow-y-auto rounded-xl border border-zinc-200">
                {detail.history.items.length ? (
                  detail.history.items.map((challenge) => (
                    <ChallengeRow
                      key={challenge.challenge_id}
                      challenge={challenge}
                      onRecap={onRecap}
                      viewer={viewer}
                      highlighted={challenge.challenge_id === highlightedId}
                    />
                  ))
                ) : (
                  <li className="px-4 py-6 text-sm text-zinc-500">
                    No completed direct challenges yet.
                  </li>
                )}
              </ul>
              {next && (
                <button
                  type="button"
                  onClick={() => void more()}
                  className="mt-3 text-sm font-semibold text-blue-700"
                >
                  Load more history
                </button>
              )}
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

function Records({
  people,
  viewer,
  open,
}: {
  people: Rival[];
  viewer?: string;
  open: (username: string) => void;
}) {
  const [a, setA] = useState(viewer ?? "");
  const [b, setB] = useState("");
  const [compare, setCompare] = useState<Compare | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    if (!a || !b || a === b) {
      setCompare(null);
      setError("");
      return;
    }
    setError("");
    void rivalsApi
      .compare(a, b)
      .then((result) => {
        if (!cancelled) setCompare(result);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, [a, b]);
  const names = Array.from(
    new Set([viewer, ...people.map((item) => item.username)].filter(Boolean)),
  ) as string[];
  return (
    <section className="max-w-3xl">
      <p className="mb-5 text-zinc-600">
        Compare completed direct challenges. Official round-robin meetings are
        never included.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {[a, b].map((value, index) => (
          <label key={index} className="text-sm font-medium">
            {index ? "Player B" : "Player A"}
            <input
              list={`players-${index}`}
              value={value}
              onChange={(event) =>
                index ? setB(event.target.value) : setA(event.target.value)
              }
              placeholder="Search a player"
              className="mt-1 block w-full rounded-lg border border-zinc-300 px-3 py-2.5 outline-none focus:border-blue-600"
            />
            <datalist id={`players-${index}`}>
              {names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </label>
        ))}
      </div>
      {error && (
        <p role="alert" className="mt-4 text-sm text-red-700">
          {error}
        </p>
      )}
      {compare && (
        <div className="mt-6 rounded-2xl border border-zinc-200 bg-white p-5">
          <h2 className="font-semibold">Direct challenge record</h2>
          <p className="mt-3 text-3xl font-bold">
            <span className="text-blue-700">
              {compare.direct_record.player_a_wins}
            </span>{" "}
            <span className="text-zinc-400">-</span>{" "}
            {compare.direct_record.player_b_wins}
          </p>
          <p className="mt-1 text-sm text-zinc-500">
            {compare.direct_record.draws} draws · {compare.direct_record.played}{" "}
            completed challenges
          </p>
          {viewer && (a === viewer || b === viewer) && (
            <button
              type="button"
              onClick={() => open(a === viewer ? b : a)}
              className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white"
            >
              Challenge
            </button>
          )}
        </div>
      )}
    </section>
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
    if (
      rawTab === "leaderboard" ||
      rawTab === "challenges" ||
      rawTab === "records"
    )
      setTab(rawTab);
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
      setTab(
        rawTab === "leaderboard" ||
          rawTab === "challenges" ||
          rawTab === "records"
          ? rawTab
          : initialTab,
      );
      setQuery("");
      const href = `${window.location.pathname}${params.size ? `?${params}` : ""}`;
      history.replaceState({}, "", href);
    }
    setStateOwner(viewer ?? null);
    setItems([]);
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
    const source = tab === "leaderboard" ? "leaderboard" : "mine";
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
    if (tab === "records") {
      setBusy(true);
      void Promise.all([rivalsApi.list("mine"), rivalsApi.list("leaderboard")])
        .then(([mine, leaderboard]) => {
          if (stale()) return;
          const unique = new Map<string, Rival>();
          [...mine.items, ...leaderboard.items].forEach((rival) =>
            unique.set(rival.username, rival),
          );
          setItems([...unique.values()]);
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
    <main className="min-h-[calc(100vh-4.5rem)] bg-[radial-gradient(circle_at_12%_0%,#e7efff,transparent_30%),linear-gradient(180deg,#fafbff,#fff)]">
      <div className="mx-auto max-w-[90rem] px-5 py-10 sm:px-8 sm:py-14">
        <div className="max-w-2xl">
          <p className="text-xs font-bold tracking-[0.18em] text-blue-700">
            PLAYFUL PRACTICE ARENA
          </p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight text-zinc-950 sm:text-5xl">
            Choose a rival
          </h1>
          <p className="mt-3 text-zinc-600">
            Practice with a focused, asynchronous heads-up challenge. Every
            matchup uses play chips and leaves public Elo unchanged.
          </p>
        </div>
        <div className="mt-8 border-b border-zinc-200">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs font-medium text-zinc-500 sm:hidden">
              Scroll for more
            </span>
            <nav
              aria-label="Rivals sections, scroll for more"
              tabIndex={0}
              className="min-w-0 flex-1 overflow-x-auto scroll-smooth"
            >
              <div role="tablist" className="flex min-w-max gap-1">
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
        </div>
        {(tab === "mine" || tab === "leaderboard") && (
          <>
            <label className="mt-6 block max-w-md">
              <span className="sr-only">Search players or bots</span>
              <input
                value={query}
                onChange={(event) => {
                  setError("");
                  setQuery(event.target.value);
                }}
                placeholder="Search player or bot"
                className="w-full rounded-xl border border-zinc-300 bg-white px-4 py-3 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
              />
            </label>
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
              <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {items.map((rival) => (
                  <RivalCard key={rival.username} rival={rival} onOpen={open} />
                ))}
              </div>
            ) : (
              <p className="mt-8 rounded-xl border border-zinc-200 bg-white p-5 text-zinc-600">
                No rivals match that search yet.
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
        {tab === "records" && (
          <div className="mt-7">
            <Records key={viewer} people={items} viewer={viewer} open={open} />
          </div>
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
