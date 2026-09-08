"use client";

import { useEffect, useState } from "react";
import { BotAvatar } from "../BotAvatar";
import {
  rivalsApi,
  type LeaderboardStanding,
  type LeaderboardStandings,
} from "../rivals/api";
import { useSession } from "../useSession";
import { RoundRobinRecaps } from "../recaps/RoundRobinRecaps";

// The dedicated standings page shows the real league result, so it never falls
// back to the landing page's illustrative preview data.
const TOP_COUNT = 5;

function elo(entry: LeaderboardStanding) {
  return (entry.elo_rating ?? 1200).toLocaleString();
}
function record(entry: LeaderboardStanding) {
  const wins = entry.matchup_wins ?? 0;
  const losses = entry.matchup_losses ?? 0;
  const draws = entry.matchup_draws ?? 0;
  return draws > 0
    ? `${wins}W · ${losses}L · ${draws}D`
    : `${wins}W · ${losses}L`;
}
function recordLabel(entry: LeaderboardStanding) {
  const wins = entry.matchup_wins ?? 0;
  const losses = entry.matchup_losses ?? 0;
  const draws = entry.matchup_draws ?? 0;
  return `${wins} ${wins === 1 ? "win" : "wins"}, ${losses} ${losses === 1 ? "loss" : "losses"}${
    draws > 0 ? `, ${draws} ${draws === 1 ? "draw" : "draws"}` : ""
  }`;
}
function rankTone(rank: number) {
  return rank === 1
    ? "bg-amber-100 text-amber-700"
    : rank === 2
      ? "bg-zinc-100 text-zinc-600"
      : rank === 3
        ? "bg-orange-100 text-orange-700"
        : "bg-zinc-100 text-zinc-500";
}
function updatedLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function StandingRow({
  entry,
  you,
}: {
  entry: LeaderboardStanding;
  you: boolean;
}) {
  return (
    <tr
      data-viewer-row={you ? "true" : undefined}
      className={`border-b border-zinc-100 last:border-b-0 ${you ? "bg-blue-50/70" : "bg-white"}`}
    >
      <td className="py-3 pl-4 pr-2 sm:pl-6">
        <span
          className={`inline-grid h-8 w-8 place-items-center rounded-lg text-sm font-bold tabular-nums ${rankTone(entry.rank)}`}
        >
          {entry.rank}
        </span>
      </td>
      <td className="py-3 pr-2">
        <div className="flex min-w-0 items-center gap-3">
          <BotAvatar
            name={entry.username}
            rank={entry.rank}
            circle
            className="h-10 w-10"
          />
          <div className="min-w-0">
            <p
              className="flex min-w-0 items-center gap-2 font-semibold text-zinc-950"
              title={entry.bot_name}
            >
              <span className="truncate">{entry.bot_name}</span>
              {you && (
                <span className="shrink-0 rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-bold tracking-wide text-white">
                  YOU
                </span>
              )}
            </p>
            <p className="truncate text-sm text-zinc-500" title={entry.username}>
              {entry.username}
            </p>
            <p className="mt-0.5 text-xs tabular-nums text-zinc-500 sm:hidden">
              {record(entry)}
            </p>
          </div>
        </div>
      </td>
      <td className="py-3 pr-4 text-right font-semibold tabular-nums text-zinc-950 sm:pr-6">
        {elo(entry)}
      </td>
      <td
        className="hidden py-3 pr-6 text-right tabular-nums text-zinc-600 sm:table-cell"
        aria-label={recordLabel(entry)}
      >
        {record(entry)}
      </td>
    </tr>
  );
}

export function StandingsWorkspace() {
  const { session, loaded } = useSession();
  const [board, setBoard] = useState<LeaderboardStandings | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const viewer = session?.username;
  useEffect(() => {
    if (!loaded) return;
    let cancelled = false;
    // Standings already on screen stay put while a refresh is in flight, so
    // this never flashes the loading copy after the first load.
    void rivalsApi
      .leaderboard()
      .then((data) => {
        if (cancelled) return;
        setBoard(data);
        setError("");
        setBusy(false);
      })
      .catch((reason) => {
        if (cancelled) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Could not load the leaderboard.",
        );
        setBusy(false);
      });
    return () => {
      cancelled = true;
    };
    // Standings are public, but the caller's own row depends on the session.
  }, [loaded, viewer]);
  const entries = board?.entries ?? [];
  const top = (board?.top_entries ?? entries.slice(0, TOP_COUNT)).slice(
    0,
    TOP_COUNT,
  );
  // The API only fills `viewer_entry` when the caller ranks below the cut, so
  // the separator row appears exactly when a rank is being skipped.
  const viewerEntry = board?.viewer_entry ?? null;
  return (
    <main className="min-h-[calc(100dvh-4.5rem)] bg-[#f6f8fc]">
      <div className="mx-auto w-full max-w-3xl px-5 py-10 sm:px-8 sm:py-14">
        <h1 className="text-4xl font-bold tracking-tight text-zinc-950 sm:text-5xl">
          Leaderboard
        </h1>
        <p className="mt-3 text-zinc-600">
          The top five bots from the latest official league run.
        </p>
        {error ? (
          <p
            role="alert"
            className="mt-8 rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-800"
          >
            {error}
          </p>
        ) : busy ? (
          <p className="mt-8 text-sm text-zinc-500">Loading standings…</p>
        ) : top.length ? (
          <>
            <div className="mt-8 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-[0_8px_28px_rgba(23,35,70,0.04)]">
              <table className="w-full border-collapse text-left">
                <caption className="sr-only">
                  Top {top.length} league standings
                  {viewerEntry ? ", followed by your own rank" : ""}
                </caption>
                <thead>
                  <tr className="border-b border-zinc-200 text-xs font-bold uppercase tracking-wide text-zinc-500">
                    <th scope="col" className="py-3 pl-4 pr-2 sm:pl-6">
                      Rank
                    </th>
                    <th scope="col" className="py-3 pr-2">
                      Bot
                    </th>
                    <th
                      scope="col"
                      className="py-3 pr-4 text-right sm:pr-6"
                    >
                      Elo
                    </th>
                    <th
                      scope="col"
                      className="hidden py-3 pr-6 text-right sm:table-cell"
                    >
                      Record
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {top.map((entry) => (
                    <StandingRow
                      key={`${entry.rank}-${entry.username}`}
                      entry={entry}
                      you={entry.username === viewer}
                    />
                  ))}
                  {viewerEntry && (
                    <>
                      <tr data-standings-separator="true">
                        <td
                          colSpan={4}
                          className="border-b border-zinc-100 bg-zinc-50 py-2 text-center text-sm font-bold tracking-[0.3em] text-zinc-400"
                        >
                          <span aria-hidden="true">···</span>
                          <span className="sr-only">
                            Ranks 6 to {viewerEntry.rank - 1} are not shown
                          </span>
                        </td>
                      </tr>
                      <StandingRow entry={viewerEntry} you />
                    </>
                  )}
                </tbody>
              </table>
            </div>
            {board?.updated_at && (
              <p className="mt-4 text-xs text-zinc-500">
                Updated{" "}
                <time dateTime={board.updated_at}>
                  {updatedLabel(board.updated_at)}
                </time>
              </p>
            )}
            {board?.run_id && <RoundRobinRecaps runId={board.run_id} />}
          </>
        ) : (
          <p className="mt-8 rounded-2xl border border-zinc-200 bg-white p-5 text-zinc-600">
            No official run has finished yet.
          </p>
        )}
      </div>
    </main>
  );
}
