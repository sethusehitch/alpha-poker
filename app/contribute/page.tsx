import type { Metadata } from "next";
import { serverFetchJson } from "../browser-api/_proxy";
import { SiteHeader } from "../components/SiteHeader";
import { ContributeIssuesCard, type ContributeSummary } from "../components/ContributeIssuesCard";
import { GITHUB_REPO_URL } from "../components/textSafety";

export const metadata: Metadata = {
  title: "Contribute — Alpha Poker",
  description: "Pick an issue, improve the arena, and send a pull request.",
};

const REPO_URL = GITHUB_REPO_URL;

// Each step and rail item carries the icon the spec names for it (5.4, 5.6);
// a shared placeholder glyph would make four different actions look identical.
const STEPS = [
  {
    title: "Pick an issue",
    body: 'Browse open issues and find one labeled "good first issue".',
    icon: (
      <>
        <circle cx="8.75" cy="8.75" r="5.25" stroke="currentColor" strokeWidth="1.5" />
        <path d="m12.75 12.75 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </>
    ),
  },
  {
    title: "Fork and build",
    body: "Fork the repo, create a branch, and make your change.",
    icon: (
      <>
        <circle cx="5.5" cy="4.5" r="2" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="14.5" cy="4.5" r="2" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="10" cy="15.5" r="2" stroke="currentColor" strokeWidth="1.5" />
        <path d="M5.5 6.5v1.75c0 1.4 1.1 2.5 2.5 2.5h4c1.4 0 2.5-1.1 2.5-2.5V6.5M10 10.75v2.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </>
    ),
  },
  {
    title: "Run the tests",
    body: "Run the test suite locally and make sure every check passes.",
    icon: (
      <>
        <rect x="2.5" y="3.5" width="15" height="13" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <path d="m6 8 2.25 2.25L6 12.5M10.75 12.5H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
  {
    title: "Open a pull request",
    body: "Push your branch and open a pull request with a clear description.",
    icon: (
      <>
        <circle cx="5.5" cy="5" r="2" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="5.5" cy="15" r="2" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="14.5" cy="15" r="2" stroke="currentColor" strokeWidth="1.5" />
        <path d="M5.5 7v6M14.5 13V7.5A2.5 2.5 0 0 0 12 5h-2.25m0 0 1.75-1.75M9.75 5l1.75 1.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
];

const BEFORE_YOU_START = [
  {
    title: "Read CONTRIBUTING.md",
    body: "Understand the project, setup, and guidelines.",
    icon: (
      <>
        <path d="M4 4h5a2 2 0 0 1 2 2v10a1.5 1.5 0 0 0-1.5-1.5H4V4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M16 4h-5a2 2 0 0 0-2 2v10a1.5 1.5 0 0 1 1.5-1.5H16V4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      </>
    ),
  },
  {
    title: "Keep changes focused",
    body: "Small, targeted changes are easier to review and merge.",
    icon: (
      <>
        <circle cx="10" cy="10" r="6.75" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="10" cy="10" r="3.25" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="10" cy="10" r="0.9" fill="currentColor" />
      </>
    ),
  },
  {
    title: "All checks must pass",
    body: "CI must be green before your PR can be merged.",
    icon: (
      <>
        <circle cx="10" cy="10" r="6.75" stroke="currentColor" strokeWidth="1.5" />
        <path d="m6.75 10.25 2.25 2.25 4.25-4.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
];

export default async function ContributePage() {
  const initialData = await serverFetchJson("github/issues", null);
  const summary: ContributeSummary | null = initialData
    ? {
        good_first_issues: Array.isArray(initialData.good_first_issues) ? initialData.good_first_issues : [],
        open_issue_count: Number(initialData.open_issue_count) || 0,
        open_pr_count: Number(initialData.open_pr_count) || 0,
        stale: Boolean(initialData.stale),
      }
    : null;

  return (
    <>
      <SiteHeader currentPath="/contribute" sticky />
      <main>
        <div className="mx-auto w-full max-w-[76rem] px-5 pb-12 pt-14 text-center sm:px-8 sm:pb-16 sm:pt-20">
          <span aria-hidden="true" className="mb-3 inline-flex text-blue-600">
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none">
              <path d="M9 6 3 12l6 6M15 6l6 6-6 6" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <p className="text-[0.6875rem] font-bold uppercase tracking-[0.25em] text-blue-700 sm:text-xs">OPEN SOURCE</p>
          <h1 className="mx-auto mt-4 max-w-[24ch] text-[clamp(2.5rem,5vw,4rem)] font-[680] leading-[1.06] tracking-[-0.045em] text-zinc-950">
            Help build Alpha Poker.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-[1.08rem] leading-[1.6] tracking-[-0.018em] text-zinc-600 sm:text-[1.25rem]">
            Pick an issue, improve the arena, and send a pull request.
          </p>
          <div className="mx-auto mt-9 flex max-w-md flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
            <a
              href={`${REPO_URL}/issues`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-[5px] bg-blue-600 px-7 text-base font-semibold text-white shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-blue-600"
            >
              View open issues <span aria-hidden="true">→</span>
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
            <a
              href={`${REPO_URL}/pulls`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-[5px] border border-zinc-900 bg-white px-7 text-base font-semibold text-zinc-950 transition-colors hover:bg-zinc-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-blue-600"
            >
              View pull requests <span aria-hidden="true">→</span>
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          </div>
        </div>

        <div className="mx-auto w-full max-w-[76rem] px-5 sm:px-8">
          <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, index) => (
              <li
                key={step.title}
                className={`relative rounded-[10px] border border-zinc-200 bg-white p-5 text-center shadow-[0_1px_2px_rgba(0,0,0,0.03)] ${
                  index < 3 ? "lg:after:absolute lg:after:right-[-1.15rem] lg:after:top-1/2 lg:after:h-px lg:after:w-[1.2rem] lg:after:border-t lg:after:border-dashed lg:after:border-zinc-300" : ""
                }`}
              >
                <div className="flex items-center justify-center gap-2.5">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-50 text-xs font-bold text-blue-700">{index + 1}</span>
                  <span aria-hidden="true" className="text-zinc-700">
                    <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none">
                      {step.icon}
                    </svg>
                  </span>
                </div>
                <h3 className="mt-4 text-[1rem] font-semibold text-zinc-950">{step.title}</h3>
                <p className="mt-2 text-balance text-[0.9375rem] text-zinc-600">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>

        {/* 96px of bottom padding below 640px keeps the closing strip clear of
            the 56px feedback FAB at 320px (spec 1.3). */}
        <div className="mx-auto mt-8 w-full max-w-[76rem] px-5 pb-24 sm:px-8 sm:pb-20">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
            <ContributeIssuesCard initialData={summary} />

            <aside className="rounded-[10px] border border-zinc-200 bg-white p-5 lg:sticky lg:top-[5.5rem]">
              <h2 className="text-[1.375rem] font-[680] tracking-[-0.03em] text-zinc-950 sm:text-[1.5rem]">Before you start</h2>
              <div className="mt-4 space-y-4">
                {BEFORE_YOU_START.map((item) => (
                  <div key={item.title} className="flex gap-3.5">
                    <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-zinc-50 text-zinc-700">
                      <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none">
                        {item.icon}
                      </svg>
                    </span>
                    <div>
                      <h3 className="text-[1rem] font-semibold text-zinc-950">{item.title}</h3>
                      <p className="mt-0.5 text-[0.8125rem] text-zinc-600">{item.body}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-5 border-t border-zinc-200/70 pt-4">
                <a
                  href={`${REPO_URL}/blob/main/CONTRIBUTING.md`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-[5px] text-sm font-semibold text-blue-700 transition-colors hover:text-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                >
                  Open CONTRIBUTING.md <span aria-hidden="true">→</span>
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
              </div>
            </aside>
          </div>

          <div className="mt-12 flex flex-col items-center justify-center gap-3 border-t border-zinc-200 py-8 text-center min-[480px]:flex-row">
            <span aria-hidden="true" className="h-5 w-5 shrink-0 text-zinc-400">
              <svg viewBox="0 0 20 20" fill="none">
                <path d="M2 8.5 5 6l3 2 2-2 3 2 3-2.5M2 12l3-2 3 2 2-2 3 2 3-2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <p className="text-[0.9375rem] text-zinc-600">You propose. Maintainers review. Nothing merges automatically.</p>
          </div>
        </div>
      </main>
    </>
  );
}
