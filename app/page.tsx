import { BUILD_BOT_PROMPT, STARTER_KIT_FILENAME, STARTER_KIT_URL } from "./components/agentPrompt";
import { CopyPromptButton } from "./components/CopyPromptButton";
import { Leaderboard, type LeaderboardEntry } from "./components/Leaderboard";
import { SiteHeader } from "./components/SiteHeader";
import { serverFetchJson } from "./browser-api/_proxy";

const previewLeaderboard: LeaderboardEntry[] = [
  {
    rank: 1,
    bot_name: "RiverRat",
    username: "Maya",
    elo_rating: 1264,
    matchup_wins: 4,
    matchup_losses: 0,
    bb_per_100: 8.42,
    confidence_95: [4.1, 12.74],
    hands: 152000,
  },
  {
    rank: 2,
    bot_name: "DeepStack",
    username: "Leo",
    elo_rating: 1232,
    matchup_wins: 3,
    matchup_losses: 1,
    bb_per_100: 3.17,
    confidence_95: [-0.82, 7.16],
    hands: 152000,
  },
  {
    rank: 3,
    bot_name: "FoldEquity",
    username: "Sam",
    elo_rating: 1200,
    matchup_wins: 2,
    matchup_losses: 2,
    bb_per_100: -1.04,
    confidence_95: [-5.22, 3.14],
    hands: 152000,
  },
  {
    rank: 4,
    bot_name: "RangeFinder",
    username: "Noor",
    elo_rating: 1168,
    matchup_wins: 1,
    matchup_losses: 3,
    bb_per_100: -3.88,
    confidence_95: [-8.11, 0.35],
    hands: 152000,
  },
  {
    rank: 5,
    bot_name: "ValueSeeker",
    username: "Jules",
    elo_rating: 1136,
    matchup_wins: 0,
    matchup_losses: 4,
    bb_per_100: -6.67,
    confidence_95: [-10.92, -2.42],
    hands: 152000,
  },
];

export default async function Home() {
  const liveLeaderboard = await serverFetchJson("leaderboard", null);
  const initialLeaderboard = liveLeaderboard === null
    ? previewLeaderboard
    : Array.isArray(liveLeaderboard.entries)
      ? liveLeaderboard.entries as LeaderboardEntry[]
      : [];

  return (
    <>
      <SiteHeader currentPath="/" />

      <main>
        <section
          id="top"
          className="flex min-h-[calc(100svh-4.5rem)] scroll-mt-20 items-center justify-center px-5 py-16 text-center sm:px-8 sm:py-20"
        >
          <div className="mx-auto w-full max-w-6xl -translate-y-[2vh]">
            <p className="text-[0.68rem] font-bold tracking-[0.28em] text-zinc-500 sm:text-xs">
              PRIVATE BOT LEAGUE
            </p>
            <h1 className="mx-auto mt-6 max-w-6xl text-[clamp(1.75rem,8.6vw,2.75rem)] font-[650] leading-[1.08] tracking-[-0.05em] text-zinc-950 sm:mt-7 sm:text-[clamp(3.35rem,6.2vw,6.5rem)] sm:leading-[1.09]">
              <span className="block whitespace-nowrap">Build a poker bot.</span>
              <span className="block whitespace-nowrap">
                Prove it&rsquo;s the best.
              </span>
            </h1>
            <p className="mx-auto mt-7 max-w-xl text-[1.08rem] leading-7 tracking-[-0.018em] text-zinc-600 sm:text-xl">
              A private arena for testing autonomous poker agents.
            </p>
            <div className="mt-10 flex flex-col items-stretch justify-center gap-3 px-4 sm:flex-row sm:items-center sm:px-0">
              <a
                href="#instructions"
                className="group inline-flex min-h-12 items-center justify-center gap-3 rounded-[5px] bg-blue-600 px-7 py-3 text-base font-semibold tracking-[-0.01em] text-white shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-blue-600"
              >
                Instructions
                <svg aria-hidden="true" className="h-4 w-4 transition-transform group-hover:translate-y-0.5" viewBox="0 0 16 16" fill="none">
                  <path d="M8 2.5v10m0 0 4-4m-4 4-4-4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </a>
              <a
                href="#leaderboard"
                className="group inline-flex min-h-12 items-center justify-center gap-3 rounded-[5px] border border-zinc-900 bg-white px-7 py-3 text-base font-semibold tracking-[-0.01em] text-zinc-950 transition-colors hover:bg-zinc-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-blue-600"
              >
                Leaderboard
                <svg aria-hidden="true" className="h-4 w-4 transition-transform group-hover:translate-y-0.5" viewBox="0 0 16 16" fill="none">
                  <path d="M8 2.5v10m0 0 4-4m-4 4-4-4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </a>
            </div>
          </div>
        </section>

        <section
          id="leaderboard"
          className="scroll-mt-0 border-t border-zinc-200 bg-zinc-50/60 px-3 py-20 sm:px-8 sm:py-24"
        >
          <div className="mx-auto max-w-5xl">
            <Leaderboard initialEntries={initialLeaderboard} />
          </div>
        </section>

        <section
          id="instructions"
          className="flex min-h-[100svh] scroll-mt-0 items-center border-t border-zinc-200 px-5 py-16 sm:px-8 sm:py-20"
        >
          <div className="mx-auto w-full max-w-6xl">
            <p className="text-center text-[0.68rem] font-bold tracking-[0.25em] text-blue-700">
              ENTER THE ARENA
            </p>
            <h2 className="mt-4 text-center text-4xl font-[720] tracking-[-0.045em] text-zinc-950 sm:text-5xl">
              Instructions
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-center leading-7 text-zinc-600">
              Download the kit, hand it to your coding agent, and start competing.
            </p>

            <ol className="mt-10 grid gap-4 lg:grid-cols-3">
              <li className="flex flex-col rounded-[10px] border border-zinc-200 bg-white p-6 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
                <p className="text-xs font-bold tracking-[0.2em] text-blue-700">STEP 1</p>
                <h3 className="mt-3 text-2xl font-[680] tracking-[-0.025em] text-zinc-950">
                  Download the starter kit
                </h3>
                <p className="mt-3 flex-1 leading-6 text-zinc-600">
                  Save <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-sm">{STARTER_KIT_FILENAME}</code> to your Downloads folder.
                </p>
                <a
                  href={STARTER_KIT_URL}
                  download
                  className="mt-6 inline-flex min-h-11 items-center justify-center gap-2.5 rounded-[5px] border border-blue-600 bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-colors hover:border-blue-700 hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-blue-600"
                >
                  Download starter kit
                  <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 16 16" fill="none">
                    <path d="M8 2.25v7.5m0 0 3-3m-3 3-3-3M3 12.75h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </a>
              </li>

              <li className="rounded-[10px] border border-blue-200 bg-blue-50/40 p-6 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
                <p className="text-xs font-bold tracking-[0.2em] text-blue-700">STEP 2</p>
                <h3 className="mt-3 text-2xl font-[680] tracking-[-0.025em] text-zinc-950">
                  Give it to your agent
                </h3>
                <ol className="mt-5 space-y-4">
                  <li className="flex items-start gap-3">
                    <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">1</span>
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-zinc-950">Copy the agent instructions</p>
                      <div className="mt-3">
                        <CopyPromptButton text={BUILD_BOT_PROMPT} label="Copy instructions" />
                      </div>
                    </div>
                  </li>
                  <li className="flex items-start gap-3 border-t border-blue-200/70 pt-4">
                    <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">2</span>
                    <div>
                      <p className="font-semibold text-zinc-950">Paste them into your coding agent</p>
                      <p className="mt-1 text-sm leading-6 text-zinc-600">Use Claude, ChatGPT, or Codex. The prompt tells it exactly where to find the downloaded kit.</p>
                    </div>
                  </li>
                </ol>
              </li>

              <li className="flex flex-col rounded-[10px] border border-zinc-200 bg-white p-6 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
                <p className="text-xs font-bold tracking-[0.2em] text-zinc-600">STEP 3</p>
                <h3 className="mt-3 text-2xl font-[680] tracking-[-0.025em] text-zinc-950">
                  Enter the arena
                </h3>
                <p className="mt-3 leading-6 text-zinc-600">
                  Your agent builds, trains, and submits your bot.
                </p>
                <p className="mt-4 border-t border-zinc-200 pt-4 text-sm font-semibold leading-6 text-zinc-900">
                  Beat the field. Take the crown.
                </p>
              </li>
            </ol>
          </div>
        </section>
      </main>
    </>
  );
}
