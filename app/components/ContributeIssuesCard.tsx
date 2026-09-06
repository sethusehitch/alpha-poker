"use client";

import { useState } from "react";
import { GITHUB_REPO_URL, displayText, isRepoIssueUrl, safeDisplayText } from "./textSafety";

export type ContributeIssue = {
  number: number;
  title: string;
  url: string;
  labels: string[];
  assignee: string | null;
  comments: number;
};

export type ContributeSummary = {
  good_first_issues: ContributeIssue[];
  open_issue_count: number;
  open_pr_count: number;
  stale: boolean;
};

const LABEL_STYLE: Record<string, string> = {
  "good first issue": "bg-violet-50 text-violet-700",
  frontend: "bg-blue-50 text-blue-700",
  docs: "bg-green-50 text-green-700",
  bug: "bg-red-50 text-red-700",
};

function labelClass(name: string) {
  return LABEL_STYLE[name] ?? "bg-zinc-100 text-zinc-700";
}

function commentsLabel(count: number) {
  return count >= 1000 ? "999+" : String(count);
}

function IssueRow({ issue }: { issue: ContributeIssue }) {
  const title = safeDisplayText(issue.title) ?? "(untitled issue)";
  // Exact match against this repo's own issue URL for this issue number:
  // another repository, a pull-request URL, or a mismatched number all fall
  // back to non-interactive text (spec 5.8 "URL safety").
  const safeUrl = isRepoIssueUrl(issue.url, issue.number) ? issue.url : null;
  const assignee = issue.assignee ? safeDisplayText(issue.assignee) : null;

  const content = (
    <>
      <span aria-hidden="true" className="h-4 w-4 shrink-0 text-green-600">
        <svg viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6.25" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="8" cy="8" r="2" fill="currentColor" />
        </svg>
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[0.9375rem] font-medium text-zinc-950" title={title}>
          {displayText(title, 90)}
        </span>
        {Number.isInteger(issue.number) && issue.number > 0 && (
          <span className="mt-0.5 block font-mono text-[0.75rem] text-zinc-500">#{issue.number}</span>
        )}
      </span>
      <span className="hidden shrink-0 gap-1.5 md:flex">
        {issue.labels.slice(0, 2).map((label) => (
          <span key={label} className={`h-6 shrink-0 rounded-[6px] px-2 text-[0.75rem] font-medium leading-6 ${labelClass(label)}`}>
            {displayText(label, 22)}
          </span>
        ))}
      </span>
      <span className="hidden shrink-0 text-[0.8125rem] text-zinc-500 lg:inline">
        {assignee ? `@${displayText(assignee, 14)}` : "No assignee"}
      </span>
      <span className="hidden shrink-0 items-center gap-1 text-[0.8125rem] tabular-nums text-zinc-500 sm:flex">
        <svg aria-hidden="true" viewBox="0 0 14 14" className="h-3.5 w-3.5" fill="none">
          <path d="M2 3.5h10v6H6l-2.5 2.5V9.5H2v-6Z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
        </svg>
        {commentsLabel(issue.comments)}
      </span>
    </>
  );

  if (!safeUrl) {
    return <div className="flex min-h-16 items-center gap-3 px-5 py-3.5">{content}</div>;
  }
  return (
    <a
      href={safeUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="flex min-h-16 items-center gap-3 px-5 py-3.5 transition-colors hover:bg-zinc-50 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600"
    >
      {content}
    </a>
  );
}

export function ContributeIssuesCard({ initialData }: { initialData: ContributeSummary | null }) {
  const [data, setData] = useState<ContributeSummary | null>(initialData);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(initialData === null);

  async function retry() {
    setLoading(true);
    try {
      const response = await fetch("/browser-api/github/issues", { cache: "no-store" });
      if (!response.ok) throw new Error("unavailable");
      setData(await response.json());
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-[10px] border border-zinc-200 bg-white">
      <div className="p-5 pb-4">
        <h2 className="text-[1.375rem] font-[680] tracking-[-0.03em] text-zinc-950 sm:text-[1.5rem]">Good first issues</h2>
      </div>
      {loading ? (
        <>
        <p className="sr-only" role="status">Loading issues…</p>
        <ul className="divide-y divide-zinc-200/80 border-t border-zinc-200/80" aria-busy="true">
          {/* Mirrors IssueRow geometry at every breakpoint (spec 3.5, 5.8):
              same paddings, same responsive visibility for labels, assignee,
              and comment count, so nothing shifts when content arrives. */}
          {Array.from({ length: 3 }, (_, index) => (
            <li key={index} aria-hidden="true" className="flex min-h-16 items-center gap-3 px-5 py-3.5">
              <span className="h-4 w-4 shrink-0 animate-pulse rounded-full bg-zinc-100 motion-reduce:animate-none" />
              <span className="min-w-0 flex-1">
                <span className="block h-3.5 w-[55%] animate-pulse rounded-[4px] bg-zinc-100 motion-reduce:animate-none" />
                <span className="mt-1.5 block h-3 w-10 animate-pulse rounded-[4px] bg-zinc-100 motion-reduce:animate-none" />
              </span>
              <span className="hidden shrink-0 gap-1.5 md:flex">
                <span className="h-6 w-[5.625rem] animate-pulse rounded-[6px] bg-zinc-100 motion-reduce:animate-none" />
                <span className="h-6 w-[5.625rem] animate-pulse rounded-[6px] bg-zinc-100 motion-reduce:animate-none" />
              </span>
              <span className="hidden h-3 w-16 shrink-0 animate-pulse rounded-[4px] bg-zinc-100 motion-reduce:animate-none lg:block" />
              <span className="hidden h-3.5 w-8 shrink-0 animate-pulse rounded-[4px] bg-zinc-100 motion-reduce:animate-none sm:block" />
            </li>
          ))}
        </ul>
        </>
      ) : failed ? (
        <div role="status" className="px-5 py-10 text-center">
          <h3 className="text-base font-semibold text-zinc-950">Couldn&rsquo;t load issues from GitHub.</h3>
          <p className="mt-1.5 text-[0.9375rem] text-zinc-600">The full list still works.</p>
          <button
            type="button"
            onClick={retry}
            className="mt-4 inline-flex h-11 items-center justify-center rounded-[5px] border border-zinc-200 bg-white px-4 text-sm font-semibold text-zinc-700 transition-colors hover:bg-zinc-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            Try again
          </button>
        </div>
      ) : data && data.good_first_issues.length === 0 ? (
        <div className="px-5 py-10 text-center">
          <h3 className="text-base font-semibold text-zinc-950">No good first issues right now.</h3>
          <p className="mt-1.5 text-[0.9375rem] text-zinc-600">Check the full issue list — there&rsquo;s plenty of other ways to help.</p>
        </div>
      ) : (
        <ul className="divide-y divide-zinc-200/80 border-t border-zinc-200/80">
          {data?.good_first_issues.map((issue) => (
            <li key={issue.number}>
              <IssueRow issue={issue} />
            </li>
          ))}
        </ul>
      )}
      <div className="border-t border-zinc-200/80 p-5">
        <a
          href={`${GITHUB_REPO_URL}/issues`}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-[5px] text-sm font-semibold text-blue-700 transition-colors hover:text-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          View all open issues <span aria-hidden="true">→</span>
          <span className="sr-only"> (opens in a new tab)</span>
        </a>
      </div>
    </div>
  );
}
