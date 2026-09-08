"use client";

import { useEffect, useMemo, useState } from "react";

export type LeaderboardEntry = {
  rank: number;
  username: string;
  bot_name: string;
  elo_rating?: number;
  matchup_wins?: number;
  matchup_losses?: number;
  matchup_draws?: number;
  rating?: number;
  wins?: number;
  losses?: number;
  draws?: number;
  bb_per_100?: number;
  confidence_95?: [number, number];
  hands?: number;
};

type LeaderboardResponse = {
  run_id: string | null;
  updated_at: string | null;
  entries: LeaderboardEntry[];
};

type LeagueResponse = {
  current_run?: { status?: string; error?: string | null } | null;
  queue?: { pending?: boolean; running?: boolean; state?: string; message?: string };
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/v1";
const BOT_NAME_MAX_LENGTH = 64;
const PLAYER_NAME_MAX_LENGTH = 40;
const BOT_NAME_DISPLAY_LENGTH = 18;
const PLAYER_NAME_DISPLAY_LENGTH = 16;
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f-\u009f]/;

function codePointSlice(value: string, maximum: number) {
  return Array.from(value).slice(0, maximum).join("");
}

function displayName(value: string, maximum: number) {
  const points = Array.from(value);
  return points.length > maximum ? `${points.slice(0, maximum - 1).join("")}…` : value;
}

function normalizeEntry(entry: LeaderboardEntry): LeaderboardEntry | null {
  if (typeof entry.bot_name !== "string" || typeof entry.username !== "string") return null;
  const botName = entry.bot_name.trim();
  const username = entry.username.trim();
  if (
    Array.from(botName).length < 2 ||
    Array.from(username).length < 2 ||
    CONTROL_CHARACTERS.test(botName) ||
    CONTROL_CHARACTERS.test(username)
  ) return null;
  return {
    ...entry,
    bot_name: codePointSlice(botName, BOT_NAME_MAX_LENGTH),
    username: codePointSlice(username, PLAYER_NAME_MAX_LENGTH),
  };
}

function eloRating(entry: LeaderboardEntry) {
  return entry.elo_rating ?? entry.rating ?? 1200;
}

function wins(entry: LeaderboardEntry) {
  return entry.matchup_wins ?? entry.wins ?? 0;
}

function losses(entry: LeaderboardEntry) {
  return entry.matchup_losses ?? entry.losses ?? 0;
}

function draws(entry: LeaderboardEntry) {
  return entry.matchup_draws ?? entry.draws ?? 0;
}

function recordLabel(entry: LeaderboardEntry) {
  const winCount = wins(entry);
  const lossCount = losses(entry);
  const drawCount = draws(entry);
  return `${winCount} ${winCount === 1 ? "win" : "wins"}, ${lossCount} ${lossCount === 1 ? "loss" : "losses"}${
    drawCount > 0 ? `, ${drawCount} ${drawCount === 1 ? "draw" : "draws"}` : ""
  }`;
}

function rankBadgeClass(rank: number) {
  if (rank === 1) return "bg-[#FFF3D5] text-[#D99A00]";
  if (rank === 2) return "bg-[#F0F2F4] text-[#66707E]";
  if (rank === 3) return "bg-[#F9E9D9] text-[#B35E1B]";
  return "bg-[#F1F3F5] text-[#66707E]";
}

function RobotAvatar({ rank, thumbnail = false }: { rank: number; thumbnail?: boolean }) {
  const variant = rank === 1 ? "champion" : rank === 2 ? "silver" : rank === 3 ? "bronze" : (["champion", "silver", "bronze"] as const)[(rank - 1) % 3];
  const position = variant === "silver" ? "0% 43%" : variant === "champion" ? "50% 43%" : "100% 43%";
  const ring = rank === 1
    ? "border-[#F4B82E]"
    : rank === 2
      ? "border-[#B8C0CA]"
      : "border-[#E5AF8E]";
  const ringWidth = thumbnail ? "border-2" : rank === 1 ? "border-[5px]" : rank === 3 ? "border-[3px]" : "border-2";

  return (
    <span
      aria-hidden="true"
      data-avatar-variant={variant}
      className={`relative inline-flex aspect-square h-full w-full shrink-0 items-center justify-center overflow-hidden rounded-full bg-[#07172B] ${ringWidth} ${ring} shadow-[0_3px_8px_rgba(15,23,42,0.18)]`}
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

function Crown() {
  return (
    <svg aria-hidden="true" viewBox="0 0 30 24" className="h-full w-full" fill="none">
      <path d="m2.5 6.5 6 4.5L15 3.5l6.5 7.5 6-4.5-2.2 12H4.7l-2.2-12Z" fill="#F2B500" />
      <path d="M5 20.5h20" stroke="#D99A00" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="2.5" cy="5.5" r="2" fill="#F2B500" />
      <circle cx="15" cy="2.5" r="2" fill="#F2B500" />
      <circle cx="27.5" cy="5.5" r="2" fill="#F2B500" />
    </svg>
  );
}

function Trophy() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-full w-full" fill="none">
      <path d="M8 3h8v4.5c0 3.2-1.5 5.2-4 5.2s-4-2-4-5.2V3Z" fill="currentColor" />
      <path d="M8 5H4.5v2.2c0 2.4 1.6 4 4.1 4M16 5h3.5v2.2c0 2.4-1.6 4-4.1 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M12 12.5V17m-4 3h8M9 17h6v3H9z" fill="currentColor" />
    </svg>
  );
}

function Pedestal({ entry }: { entry: LeaderboardEntry }) {
  const leader = entry.rank === 1;
  const placement = leader
    ? "left-[34.19%] z-30 h-[calc(59.66%_+_var(--dy))] w-[calc(30%_+_var(--dx))]"
    : entry.rank === 2
      ? "left-[6.13%] z-20 h-[calc(52.1%_+_var(--dy))] w-[calc(29.03%_+_var(--dx))]"
      : "left-[63.87%] z-10 h-[calc(48.74%_+_var(--dy))] w-[calc(28.06%_+_var(--dx))]";
  const rankColor = leader ? "text-[#E7A500]" : entry.rank === 2 ? "text-[#66707E]" : "text-[#B35E1B]";
  const topFace = leader
    ? "bg-[linear-gradient(145deg,#FFFDF2_0%,#FFE493_52%,#F1BD43_100%)]"
    : entry.rank === 2
      ? "bg-[linear-gradient(145deg,#FFF_0%,#E7EBEF_52%,#C9D0D8_100%)]"
      : "bg-[linear-gradient(145deg,#FFF9F4_0%,#F4D0B5_52%,#DE9E70_100%)]";
  const frontFace = leader
    ? "border-[#E4B438] bg-[linear-gradient(90deg,#FFF5D0_0%,#FFF9E8_70%,#F8E6AC_100%)]"
    : entry.rank === 2
      ? "border-[#C6CDD5] bg-[linear-gradient(90deg,#F3F5F7_0%,#FFF_68%,#E8EBEF_100%)]"
      : "border-[#DEA77F] bg-[linear-gradient(90deg,#FFF0E5_0%,#FFF7F1_68%,#F2D2BC_100%)]";
  const rightFace = leader
    ? "bg-[linear-gradient(90deg,#E6B33C_0%,#D69A18_55%,#EEC761_100%)]"
    : entry.rank === 2
      ? "bg-[linear-gradient(90deg,#B9C1CA_0%,#9FA8B4_55%,#CBD1D8_100%)]"
      : "bg-[linear-gradient(90deg,#D99C70_0%,#C77F4E_55%,#E4B38F_100%)]";
  const shadow = leader ? "bg-amber-950/25" : entry.rank === 2 ? "bg-slate-950/20" : "bg-orange-950/20";
  const silhouette = leader ? "bg-[#C68D12]" : entry.rank === 2 ? "bg-[#929CA8]" : "bg-[#B97447]";

  return (
    <li
      data-podium-block={entry.rank}
      className={`absolute bottom-0 overflow-visible text-center [--dx:clamp(8px,2.5cqi,15px)] [--dy:clamp(5px,1.45cqi,9px)] [perspective:900px] ${placement}`}
    >
      <span data-plane="shadow" aria-hidden="true" className={`absolute -bottom-[3%] left-[4%] right-[-3%] h-[10%] rounded-full blur-sm ${shadow}`} />
      <span aria-hidden="true" className={`absolute inset-0 [clip-path:polygon(0_var(--dy),var(--dx)_0,100%_0,100%_calc(100%_-_var(--dy)),calc(100%_-_var(--dx))_100%,0_100%)] ${silhouette}`} />
      <span data-plane="front" aria-hidden="true" className={`absolute bottom-0 left-0 top-[calc(var(--dy)_-_1px)] w-[calc(100%_-_var(--dx)_+_1px)] overflow-hidden rounded-tl-[clamp(0.45rem,2.4cqi,0.9rem)] border shadow-[inset_1px_0_0_rgba(255,255,255,0.95),inset_0_1px_0_rgba(255,255,255,0.95),0_10px_20px_rgba(15,23,42,0.12)] ${frontFace}`}>
        <span className="absolute inset-x-0 top-0 h-px bg-white/95" />
        <span className="absolute inset-x-0 bottom-0 h-[18%] bg-gradient-to-t from-zinc-950/[0.055] to-transparent" />
      </span>
      <span data-plane="top" aria-hidden="true" className={`absolute left-0 top-0 z-[3] h-[calc(var(--dy)_+_1px)] w-full shadow-[0_3px_5px_rgba(15,23,42,0.14)] [clip-path:polygon(0_100%,var(--dx)_0,100%_0,calc(100%_-_var(--dx))_100%)] ${topFace}`}>
        <span className="absolute left-[var(--dx)] right-0 top-px h-px bg-white/95" />
      </span>
      <span data-plane="right" aria-hidden="true" className={`absolute bottom-0 right-0 top-0 w-[calc(var(--dx)_+_1px)] shadow-[inset_3px_0_5px_rgba(0,0,0,0.14)] [clip-path:polygon(0_var(--dy),100%_0,100%_calc(100%_-_var(--dy)),0_100%)] ${rightFace}`} />

      <div className="absolute bottom-0 left-0 top-[var(--dy)] z-[4] flex w-[calc(100%_-_var(--dx))] flex-col items-center px-[1cqi]">
        <p className={`${leader ? "pt-[7cqi] text-[clamp(1.75rem,9cqi,2.5rem)]" : "pt-[5cqi] text-[clamp(1.35rem,7cqi,2rem)]"} font-bold leading-none tabular-nums ${rankColor}`}>
          {entry.rank}
        </p>
        <p className={`${leader ? "mt-[3.2cqi] text-[clamp(0.72rem,3.9cqi,1.05rem)]" : "mt-[2.5cqi] text-[clamp(0.66rem,3.5cqi,0.95rem)]"} w-full truncate font-bold leading-tight tracking-[-0.025em] text-[#111318]`} title={entry.bot_name}>
          {displayName(entry.bot_name, BOT_NAME_DISPLAY_LENGTH)}
        </p>
        <p className="mt-[1cqi] w-full truncate text-[clamp(0.6rem,3.2cqi,0.82rem)] leading-tight text-[#777E88]" title={entry.username}>{displayName(entry.username, PLAYER_NAME_DISPLAY_LENGTH)}</p>
        <p className="mt-[2.1cqi] text-[clamp(0.68rem,3.7cqi,1rem)] font-semibold leading-tight tabular-nums text-[#08A34A]">{eloRating(entry).toLocaleString()} Elo</p>
        <p className="mt-[1.5cqi] text-[clamp(0.54rem,2.8cqi,0.72rem)] leading-tight tabular-nums text-[#707782]">
          <span className="text-[#08A34A]">{wins(entry)} {wins(entry) === 1 ? "win" : "wins"}</span>,{" "}
          <span className="text-[#F04452]">{losses(entry)} {losses(entry) === 1 ? "loss" : "losses"}</span>
          {draws(entry) > 0 ? <>, <span>{draws(entry)} {draws(entry) === 1 ? "draw" : "draws"}</span></> : null}
        </p>
      </div>
    </li>
  );
}

function Podium({ entries }: { entries: LeaderboardEntry[] }) {
  const leader = entries.find((entry) => entry.rank === 1);
  const second = entries.find((entry) => entry.rank === 2);
  const third = entries.find((entry) => entry.rank === 3);
  const ordered = [leader, second, third].filter((entry): entry is LeaderboardEntry => Boolean(entry));

  return (
    <div className="relative aspect-[310/238] w-full overflow-hidden" aria-label="Top three bots">
      {leader && (
        <>
          <div aria-hidden="true" className="absolute left-[36%] top-[4%] z-[1] h-[33%] w-[28%] text-[#F2C55C]">
            <svg viewBox="0 0 90 80" className="h-full w-full" fill="none">
              <path d="M45 2v11M12 18l9 8M78 18l-9 8M3 46h12M87 46H75M20 5l5 11M70 5l-5 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
          <div className="absolute left-[45.2%] top-0 z-[70] h-[9.25%] w-[9.7%]"><Crown /></div>
          <div className="absolute left-[38.06%] top-[11.34%] z-50 w-[22.26%]">
            <RobotAvatar rank={1} />
          </div>
        </>
      )}
      {second && <div className="absolute left-[9.68%] top-[22.69%] z-[35] w-[19.68%]"><RobotAvatar rank={2} /></div>}
      {third && <div className="absolute left-[68.06%] top-[26.47%] z-[35] w-[19.35%]"><RobotAvatar rank={3} /></div>}
      <ol className="contents">
        {ordered.map((entry) => <Pedestal key={`${entry.rank}-${entry.username}`} entry={entry} />)}
      </ol>
      {leader && (
        <span data-winner-badge className="absolute left-[49.2%] top-[40.3%] z-[70] flex aspect-square w-[clamp(18px,6.2cqi,36px)] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-[3px] border-white bg-[#F2B500] text-white shadow-[0_3px_7px_rgba(120,78,0,0.36),inset_0_0_0_1px_#D99A00]">
          <svg aria-hidden="true" viewBox="0 0 20 20" className="h-[62%] w-[62%]" fill="currentColor">
            <path d="m10 2.2 2.15 4.35 4.8.7-3.48 3.4.82 4.78L10 13.17l-4.29 2.26.82-4.78-3.48-3.4 4.8-.7L10 2.2Z" />
          </svg>
        </span>
      )}
    </div>
  );
}

function StandingsTable({ entries }: { entries: LeaderboardEntry[] }) {
  return (
    <div className="border-t border-[#ECEEF1]">
      <table className="w-full table-fixed border-collapse text-left">
        <colgroup>
          <col className="w-[14%]" />
          <col className="w-[33%]" />
          <col className="w-[20%]" />
          <col className="w-[17%]" />
          <col className="w-[16%]" />
        </colgroup>
        <thead>
          <tr className="h-[clamp(1.8rem,9.35cqi,3rem)] border-b border-[#E9ECEF] text-[clamp(0.42rem,1.95cqi,0.62rem)] font-bold uppercase tracking-[0.04em] text-[#646B76]">
            <th scope="col" className="pl-[4.8cqi] pr-[1cqi]">Rank</th>
            <th scope="col" className="pr-[1cqi]">Bot</th>
            <th scope="col" className="pr-[1cqi]">Player</th>
            <th scope="col" className="whitespace-nowrap pr-[clamp(10px,2.4cqi,15px)] text-right">Elo</th>
            <th scope="col" className="whitespace-nowrap pl-[clamp(10px,2.4cqi,15px)] pr-[clamp(12px,4.5cqi,28px)] text-right min-[480px]:border-l min-[480px]:border-[#EEF0F2]">Record</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={`${entry.rank}-${entry.username}`} className="h-[clamp(2.7rem,13.9cqi,4.6rem)] border-b border-[#EEF0F2] bg-white text-[clamp(0.56rem,2.9cqi,0.82rem)] last:border-b-0">
              <td className="pl-[4.2cqi] pr-[1cqi]">
                <span className={`inline-flex aspect-[24/29] w-[clamp(1.5rem,7.75cqi,2.4rem)] items-center justify-center rounded-[clamp(0.3rem,1.9cqi,0.55rem)] font-bold tabular-nums ${rankBadgeClass(entry.rank)}`}>
                  {entry.rank}
                </span>
              </td>
              <td className="pr-[1cqi]">
                <div className="flex min-w-0 items-center gap-[1.6cqi]">
                  <span className="w-[clamp(1.7rem,8.7cqi,2.8rem)]"><RobotAvatar rank={entry.rank} thumbnail /></span>
                  <span className="min-w-0 truncate font-semibold text-[#17191D]" title={entry.bot_name}>{displayName(entry.bot_name, BOT_NAME_DISPLAY_LENGTH)}</span>
                </div>
              </td>
              <td className="truncate pr-[1cqi] text-[#525862]" title={entry.username}>{displayName(entry.username, PLAYER_NAME_DISPLAY_LENGTH)}</td>
              <td className="whitespace-nowrap pr-[clamp(10px,2.4cqi,15px)] text-right font-semibold text-[#17191D] tabular-nums">{eloRating(entry).toLocaleString()}</td>
              <td className="whitespace-nowrap pl-[clamp(10px,2.4cqi,15px)] pr-[clamp(12px,4.5cqi,28px)] text-right text-[#525862] tabular-nums min-[480px]:border-l min-[480px]:border-[#F0F2F4]" aria-label={recordLabel(entry)}>
                {draws(entry) > 0 ? `${wins(entry)}W ${losses(entry)}L ${draws(entry)}D` : `${wins(entry)}-${losses(entry)}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Leaderboard({ initialEntries }: { initialEntries: LeaderboardEntry[] }) {
  const [data, setData] = useState<LeaderboardResponse>({ run_id: "preview", updated_at: null, entries: initialEntries });
  const [runStatus, setRunStatus] = useState<{ status?: string; error?: string | null } | null>(null);
  const [leagueState, setLeagueState] = useState<{ state?: string; message?: string } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function refresh() {
      try {
        const [boardResponse, leagueResponse] = await Promise.all([
          fetch(`${API_BASE}/leaderboard`, { headers: { Accept: "application/json" }, signal: controller.signal }),
          fetch(`${API_BASE}/league`, { headers: { Accept: "application/json" }, signal: controller.signal }),
        ]);
        if (boardResponse.ok) {
          const next = await boardResponse.json() as LeaderboardResponse;
          if (Array.isArray(next.entries)) setData(next);
        }
        if (leagueResponse.ok) {
          const league = await leagueResponse.json() as LeagueResponse;
          setRunStatus(league.current_run ?? null);
          setLeagueState(league.queue ?? null);
        }
      } catch {
        // Keep the preview visible only while the API is offline. A reachable
        // empty cohort gets the explicit "No official run yet" state.
      }
    }
    void refresh();
    const interval = window.setInterval(refresh, 5000);
    return () => { controller.abort(); window.clearInterval(interval); };
  }, []);

  const entries = useMemo(
    () => [...data.entries]
      .map(normalizeEntry)
      .filter((entry): entry is LeaderboardEntry => entry !== null)
      .sort((a, b) => a.rank - b.rank)
      .slice(0, 20),
    [data.entries],
  );

  if (entries.length === 0) return <p className="mt-10 text-center text-zinc-600">No official run yet.</p>;

  return (
    <>
      <div data-testid="reference-leaderboard" className="mx-auto w-full max-w-[620px] overflow-hidden rounded-[12px] border border-[#E3E6EA] bg-white shadow-[0_1px_3px_rgba(17,24,39,0.04)] [container-type:inline-size]">
        <div className="flex h-[clamp(3.25rem,16.77cqi,4.75rem)] items-center justify-between px-[6.75cqi]">
          <h2 className="text-[clamp(1rem,5.15cqi,1.4rem)] font-bold tracking-[-0.03em] text-[#111318]">Leaderboard</h2>
          <span className="h-[clamp(1.1rem,5.8cqi,1.65rem)] w-[clamp(1.1rem,5.8cqi,1.65rem)] text-[#0B55F5]"><Trophy /></span>
        </div>
        <Podium entries={entries.slice(0, 3)} />
        <StandingsTable entries={entries} />
      </div>

      {(leagueState?.state && !["idle", "completed"].includes(leagueState.state)) && (
        <p role="status" className={`mt-4 text-center text-sm ${leagueState.state === "failed" ? "text-red-600" : "text-blue-700"}`}>
          {leagueState.state === "failed" && runStatus?.error
            ? `${leagueState.message} ${runStatus.error}`
            : leagueState.message}
        </p>
      )}

    </>
  );
}
