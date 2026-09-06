"use client";

import { useEffect, useRef, useState } from "react";
import { StatusChip, normalizeStatus, statusLabel, type FeatureStatus } from "./StatusChip";
import { showToast } from "./toastBus";
import { emit, on } from "./uiBus";
import { useSession } from "./useSession";
import { SuggestFeatureDialog } from "./SuggestFeatureDialog";
import { codePointSlice, displayText, safeDisplayText } from "./textSafety";

export type FeatureRequest = {
  id: string;
  title: string;
  details: string | null;
  status: string;
  score: number;
  my_vote: "up" | "down" | null;
  author: string;
  created_at: string;
};

export type FeatureTab = "top" | "new" | "planned";

const TITLE_DISPLAY_LENGTH = 80;
const USERNAME_DISPLAY_LENGTH = 20;
const AVATAR_COLORS = ["#155DFC", "#00A63E", "#F54A00", "#9810FA", "#D08700", "#0092B8"];
const OPERATOR_STATUS_ORDER: FeatureStatus[] = [
  "submitted",
  "under_review",
  "planned",
  "in_progress",
  "shipped",
  "declined",
];

const VOTE_ERROR_COPY = "Couldn't save your vote.";
const DETAILS_DESKTOP_TITLE_ID = "feature-request-details-desktop-title";
const DETAILS_MOBILE_TITLE_ID = "feature-request-details-mobile-title";
const LIST_ERROR_COPY: Record<string, string> = {
  api_unavailable: "Ideas are offline right now. Try again in a moment.",
};

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

function dateLabel(iso: string): string {
  try {
    // SSR and the browser can run in different time zones. Pinning the label
    // to UTC keeps hydration deterministic while <time dateTime> retains the
    // exact instant for assistive technology and machines.
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    }).format(new Date(iso));
  } catch {
    return "";
  }
}

function avatarInitialAndColor(username: string) {
  const points = Array.from(username);
  const first = points[0] ?? "?";
  const initial = /[\p{L}\p{N}]/u.test(first) ? first.toUpperCase() : "?";
  const sum = points.reduce((total, point) => total + point.codePointAt(0)!, 0);
  return { initial, color: AVATAR_COLORS[sum % AVATAR_COLORS.length] };
}

function sanitizeItem(item: FeatureRequest): FeatureRequest | null {
  const title = safeDisplayText(item.title);
  const author = safeDisplayText(item.author);
  if (title === null || author === null) return null;
  const details = item.details ? safeDisplayText(item.details) : null;
  return { ...item, title: codePointSlice(title, TITLE_DISPLAY_LENGTH), author, details };
}

function voteNumber(vote: "up" | "down" | null): number {
  return vote === "up" ? 1 : vote === "down" ? -1 : 0;
}

async function fetchPage(tab: FeatureTab, cursor: string | null) {
  const query = new URLSearchParams({ tab });
  if (cursor) query.set("cursor", cursor);
  const response = await fetch(`/browser-api/feature-requests?${query.toString()}`, { cache: "no-store" });
  if (!response.ok) throw new Error("list_unavailable");
  return (await response.json()) as { items: FeatureRequest[]; next_cursor: string | null };
}

function AuthorAvatar({ username }: { username: string }) {
  const { initial, color } = avatarInitialAndColor(username);
  return (
    <span
      aria-hidden="true"
      style={{ backgroundColor: color }}
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[0.6875rem] font-semibold text-white"
    >
      {initial}
    </span>
  );
}

function VoteArrows({
  item,
  disabled,
  onVote,
}: {
  item: FeatureRequest;
  disabled: boolean;
  onVote: (direction: "up" | "down") => void;
}) {
  return (
    <div
      className={`flex w-12 shrink-0 flex-col items-center justify-center gap-0.5 py-3 sm:w-16 sm:border-r sm:border-zinc-200/80 ${
        disabled ? "pointer-events-none opacity-60" : ""
      }`}
    >
      <button
        type="button"
        aria-label={`Upvote: ${item.title}`}
        aria-pressed={item.my_vote === "up"}
        onClick={() => onVote("up")}
        className={`inline-flex h-10 w-10 items-center justify-center rounded-[5px] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 sm:h-9 sm:w-9 ${
          item.my_vote === "up" ? "bg-blue-50 text-blue-600" : "text-zinc-400 hover:bg-blue-50 hover:text-blue-600"
        }`}
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4" fill="none">
          <path d="M8 13.5v-10m0 0 4 4m-4-4-4 4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      <span className={`my-0.5 text-[1.0625rem] font-semibold tabular-nums ${item.my_vote === "up" ? "text-blue-700" : item.score < 0 ? "text-zinc-500" : "text-zinc-900"}`}>
        {item.score}
      </span>
      <button
        type="button"
        aria-label={`Downvote: ${item.title}`}
        aria-pressed={item.my_vote === "down"}
        onClick={() => onVote("down")}
        className={`inline-flex h-10 w-10 items-center justify-center rounded-[5px] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 sm:h-9 sm:w-9 ${
          item.my_vote === "down" ? "bg-zinc-100 text-zinc-700" : "text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
        }`}
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4" fill="none">
          <path d="M8 2.5v10m0 0 4-4m-4 4-4-4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </div>
  );
}

function FeatureDetailsContent({
  item,
  headingId,
  closeButtonRef,
  voting,
  onClose,
  onVote,
}: {
  item: FeatureRequest;
  headingId: string;
  closeButtonRef: React.RefObject<HTMLButtonElement | null>;
  voting: boolean;
  onClose: () => void;
  onVote: (direction: "up" | "down") => void;
}) {
  return (
    <div className="flex h-full max-h-full min-w-0 flex-col overflow-y-auto p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] sm:p-6 lg:p-5">
      <div className="flex items-start justify-between gap-4">
        <StatusChip status={item.status} />
        <button
          ref={closeButtonRef}
          type="button"
          aria-label={`Close details for ${item.title}`}
          onClick={onClose}
          className="-mr-1 -mt-1 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[5px] text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4" fill="none">
            <path d="m3.5 3.5 9 9m0-9-9 9" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <h2
        id={headingId}
        className="mt-4 break-words text-[1.375rem] font-[680] leading-[1.25] tracking-[-0.03em] text-zinc-950 [overflow-wrap:anywhere]"
      >
        {item.title}
      </h2>
      <p className="mt-3 whitespace-pre-wrap break-words text-[0.9375rem] leading-[1.65] text-zinc-700 [overflow-wrap:anywhere]">
        {item.details}
      </p>

      <div className="mt-5 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1.5 border-t border-zinc-200/80 pt-4 text-[0.8125rem] text-zinc-500">
        <AuthorAvatar username={item.author} />
        <span className="max-w-full break-words [overflow-wrap:anywhere]" title={item.author}>
          {displayText(item.author, USERNAME_DISPLAY_LENGTH)}
        </span>
        <span aria-hidden="true">·</span>
        <time dateTime={item.created_at}>{dateLabel(item.created_at)}</time>
      </div>

      <div className="mt-5 flex items-center rounded-[8px] border border-zinc-200 bg-zinc-50/60">
        <VoteArrows item={item} disabled={voting} onVote={onVote} />
        <p className="min-w-0 px-3 text-sm leading-5 text-zinc-600">Vote on this idea</p>
      </div>
    </div>
  );
}

function OperatorStatusMenu({
  item,
  onChangeStatus,
  onHide,
}: {
  item: FeatureRequest;
  onChangeStatus: (status: FeatureStatus) => void;
  onHide: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [confirmingHide, setConfirmingHide] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const confirmTimeoutRef = useRef<number | null>(null);
  const current = normalizeStatus(item.status);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (menuRef.current?.contains(target) || buttonRef.current?.contains(target)) return;
      setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        buttonRef.current?.focus();
      }
    }
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => () => {
    if (confirmTimeoutRef.current !== null) window.clearTimeout(confirmTimeoutRef.current);
  }, []);

  return (
    <div className="relative" data-operator="true">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-7 items-center gap-1 rounded-[6px] bg-zinc-100 px-2.5 pl-2.5 text-[0.75rem] font-semibold text-zinc-700 transition-[filter] hover:brightness-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        <StatusChip status={item.status} />
        <svg aria-hidden="true" viewBox="0 0 12 12" className="h-3 w-3" fill="none">
          <path d="M3 4.5 6 7.5l3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div
          ref={menuRef}
          role="menu"
          className="absolute right-0 z-10 mt-1 w-[13rem] rounded-[10px] border border-zinc-200 bg-white p-1 shadow-[0_8px_24px_rgba(9,9,11,0.10)]"
        >
          {OPERATOR_STATUS_ORDER.map((status) => (
            <button
              key={status}
              type="button"
              role="menuitemradio"
              aria-checked={status === current}
              onClick={() => {
                onChangeStatus(status);
                setOpen(false);
                buttonRef.current?.focus();
              }}
              className="flex h-8 w-full items-center gap-2 rounded-[5px] px-2 text-left text-[0.8125rem] text-zinc-700 transition-colors hover:bg-zinc-50 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600"
            >
              <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full bg-current opacity-50" />
              <span className="flex-1">{statusLabel(status)}</span>
              {status === current && (
                <svg aria-hidden="true" viewBox="0 0 14 14" className="h-3.5 w-3.5 shrink-0 text-blue-600" fill="none">
                  <path d="M3 7.3 5.8 10 11 4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          ))}
          <div className="my-1 border-t border-zinc-200" />
          <button
            type="button"
            onClick={() => {
              if (!confirmingHide) {
                setConfirmingHide(true);
                confirmTimeoutRef.current = window.setTimeout(() => setConfirmingHide(false), 4000);
                return;
              }
              if (confirmTimeoutRef.current !== null) window.clearTimeout(confirmTimeoutRef.current);
              setConfirmingHide(false);
              setOpen(false);
              onHide();
            }}
            className={`flex h-8 w-full items-center rounded-[5px] px-2 text-left text-[0.8125rem] text-red-600 transition-colors hover:bg-red-50 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600 ${confirmingHide ? "font-semibold" : ""}`}
          >
            {confirmingHide ? "Confirm hide" : "Hide request"}
          </button>
        </div>
      )}
    </div>
  );
}

function EmptyState({ tab, onSuggest }: { tab: FeatureTab; onSuggest: () => void }) {
  if (tab === "planned") {
    return (
      <div className="rounded-[10px] border border-dashed border-zinc-300 py-14 text-center">
        <span aria-hidden="true" className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-zinc-100">
          <svg viewBox="0 0 20 20" className="h-5 w-5 text-zinc-500" fill="none">
            <path d="M4 6h12M4 10h12M4 14h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </span>
        <h2 className="mt-4 text-lg font-semibold text-zinc-950">Nothing planned yet.</h2>
        <p className="mx-auto mt-1.5 max-w-sm text-[0.9375rem] text-zinc-600">Ideas we decide to build will show up here.</p>
        <a
          href="/feature-requests"
          className="mt-6 inline-flex rounded-[5px] text-sm font-semibold text-blue-700 transition-colors hover:text-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          See all ideas
        </a>
      </div>
    );
  }
  return (
    <div className="rounded-[10px] border border-dashed border-zinc-300 py-14 text-center">
      <span aria-hidden="true" className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-blue-50">
        <svg viewBox="0 0 20 20" className="h-5 w-5 text-blue-600" fill="none">
          <path d="M10 2.5c-2.6 0-4.5 1.9-4.5 4.4 0 1.7 1 3 2.2 3.9-.1.8-.4 1.4-1 2h6.6c-.6-.6-.9-1.2-1-2 1.2-.9 2.2-2.2 2.2-3.9 0-2.5-1.9-4.4-4.5-4.4Z" stroke="currentColor" strokeWidth="1.5" />
          <path d="M8 16.5h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </span>
      <h2 className="mt-4 text-lg font-semibold text-zinc-950">No ideas yet.</h2>
      <p className="mx-auto mt-1.5 max-w-sm text-[0.9375rem] text-zinc-600">Be the first to suggest what we should build next.</p>
      <button
        type="button"
        onClick={onSuggest}
        className="mt-6 inline-flex h-11 items-center justify-center rounded-[5px] bg-blue-600 px-5 text-sm font-semibold text-white shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        Suggest a feature
      </button>
    </div>
  );
}

// Mirrors the real row at both breakpoints (spec 3.5): the 48px undivided vote
// rail and inline status chip below 640px, the 64px divided rail and chip
// column above it, and the same vote-button box heights, so swapping skeletons
// for content shifts nothing.
function RowSkeleton() {
  return (
    <li aria-hidden="true" className="flex min-h-[5.5rem] items-stretch rounded-[10px] border border-zinc-200 bg-white">
      <div className="flex w-12 shrink-0 flex-col items-center justify-center gap-0.5 py-3 sm:w-16 sm:border-r sm:border-zinc-200/80">
        <div className="flex h-10 w-10 items-center justify-center sm:h-9 sm:w-9">
          <div className="h-4 w-4 animate-pulse rounded-[4px] bg-zinc-100 motion-reduce:animate-none" />
        </div>
        <div className="my-0.5 h-3 w-6 animate-pulse rounded-[4px] bg-zinc-100 motion-reduce:animate-none" />
        <div className="flex h-10 w-10 items-center justify-center sm:h-9 sm:w-9">
          <div className="h-4 w-4 animate-pulse rounded-[4px] bg-zinc-100 motion-reduce:animate-none" />
        </div>
      </div>
      <div className="min-w-0 flex-1 px-4 py-3.5 sm:px-5 sm:py-4">
        <div className="h-4 w-3/5 animate-pulse rounded-[4px] bg-zinc-100 motion-reduce:animate-none" />
        <div className="mt-2 h-3 w-[85%] animate-pulse rounded-[4px] bg-zinc-100 motion-reduce:animate-none" />
        <div className="mt-2.5 flex items-center gap-2">
          <div className="h-2.5 w-[30%] animate-pulse rounded-[4px] bg-zinc-100 motion-reduce:animate-none" />
          <div className="h-7 w-[5.25rem] animate-pulse rounded-[6px] bg-zinc-100 motion-reduce:animate-none sm:hidden" />
        </div>
      </div>
      <div className="hidden shrink-0 items-center pr-4 sm:flex sm:pr-5">
        <div className="h-7 w-[5.25rem] animate-pulse rounded-[6px] bg-zinc-100 motion-reduce:animate-none" />
      </div>
    </li>
  );
}

// Icon wells carry a semantic line icon (pencil / two people / clipboard with a
// check) rather than repeating the step number that already prefixes the title
// (spec 4.10).
const HOW_IDEAS_WORK = [
  {
    title: "Suggest",
    body: "Share an idea that would make Alpha Poker better.",
    icon: (
      <>
        <path d="M3.5 16.5h3l8-8a2.12 2.12 0 0 0-3-3l-8 8v3Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M11.5 5.5l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </>
    ),
  },
  {
    title: "Community votes",
    body: "Upvote the ideas you want most. The best ones rise to the top.",
    icon: (
      <>
        <circle cx="7.75" cy="6.5" r="2.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M3 16c0-2.5 2.1-4.25 4.75-4.25S12.5 13.5 12.5 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M13 4.4a2.5 2.5 0 0 1 0 4.2M14.4 11.9c1.6.6 2.6 2.05 2.6 4.1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </>
    ),
  },
  {
    title: "We review",
    body: "We read the top ideas and build what helps most.",
    icon: (
      <>
        <path d="M7 4H5.5A1.5 1.5 0 0 0 4 5.5v10A1.5 1.5 0 0 0 5.5 17h9a1.5 1.5 0 0 0 1.5-1.5v-10A1.5 1.5 0 0 0 14.5 4H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <rect x="7" y="2.5" width="6" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <path d="M7.25 11.25 9 13l3.75-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
];

function HowIdeasWorkRail() {
  return (
    <aside className="mt-10 rounded-[10px] border border-zinc-200 bg-white p-5 lg:sticky lg:top-[5.5rem] lg:mt-0">
      <h2 className="text-[1.375rem] font-[680] tracking-[-0.03em] text-zinc-950 sm:text-[1.5rem]">How ideas work</h2>
      <ol className="mt-4">
        {HOW_IDEAS_WORK.map((step, index) => (
          <li key={step.title} className={`flex gap-3.5 ${index > 0 ? "mt-4 border-t border-zinc-200/70 pt-4" : ""}`}>
            <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-600">
              <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none">
                {step.icon}
              </svg>
            </span>
            <div>
              <h3 className="text-[1rem] font-semibold text-zinc-950">
                {index + 1}. {step.title}
              </h3>
              <p className="mt-0.5 text-[0.8125rem] text-zinc-600">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="mt-4 border-t border-zinc-200/70 pt-4">
        <p className="text-[0.8125rem] text-zinc-600">Have a question?</p>
        <button
          type="button"
          onClick={() => emit("open-feedback-panel", { focusTextarea: true })}
          className="mt-1 rounded-[5px] text-[0.8125rem] font-semibold text-blue-700 transition-colors hover:text-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Use the feedback button in the corner
        </button>
      </div>
    </aside>
  );
}

export function FeatureRequestList({
  tab,
  initialItems,
  initialNextCursor,
  initialError,
}: {
  tab: FeatureTab;
  initialItems: FeatureRequest[];
  initialNextCursor: string | null;
  initialError: boolean;
}) {
  const { session, loaded: sessionLoaded } = useSession();
  const [activeTab, setActiveTab] = useState<FeatureTab>(tab);
  const [items, setItems] = useState<FeatureRequest[]>(initialItems);
  const [nextCursor, setNextCursor] = useState<string | null>(initialNextCursor);
  const [loadingMore, setLoadingMore] = useState(false);
  const [listError, setListError] = useState(initialError ? "api_unavailable" : "");
  const [retrying, setRetrying] = useState(false);
  const [votingIds, setVotingIds] = useState<Set<string>>(new Set());
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const pendingSuggestAfterLoginRef = useRef(false);
  const rowRefs = useRef(new Map<string, HTMLLIElement>());
  const detailTriggerRefs = useRef(new Map<string, HTMLButtonElement>());
  const restoreDetailFocusIdRef = useRef<string | null>(null);
  const desktopCloseRef = useRef<HTMLButtonElement>(null);
  const mobileCloseRef = useRef<HTMLButtonElement>(null);
  const mobileDialogRef = useRef<HTMLDialogElement>(null);
  const hiddenRowsRef = useRef(new Map<string, { item: FeatureRequest; index: number }>());
  const isOperator = Boolean(session?.isOperator);

  useEffect(() => {
    return on("session-changed", ({ username }) => {
      if (username && pendingSuggestAfterLoginRef.current) {
        pendingSuggestAfterLoginRef.current = false;
        setSuggestOpen(true);
      }
    });
  }, []);

  useEffect(() => {
    if (!highlightId) return;
    const node = rowRefs.current.get(highlightId);
    // Reduced motion jumps straight to the new row instead of animating the
    // scroll; the 2s highlight still holds either way (spec 1.7).
    node?.scrollIntoView({ block: "center", behavior: prefersReducedMotion() ? "auto" : "smooth" });
    const timeout = window.setTimeout(() => setHighlightId(null), 2000);
    return () => window.clearTimeout(timeout);
  }, [highlightId]);

  useEffect(() => {
    if (!selectedId) {
      const triggerId = restoreDetailFocusIdRef.current;
      restoreDetailFocusIdRef.current = null;
      if (triggerId) window.requestAnimationFrame(() => detailTriggerRefs.current.get(triggerId)?.focus());
      return;
    }

    const dialog = mobileDialogRef.current;
    const desktopQuery = window.matchMedia("(min-width: 1024px)");
    const previousBodyOverflow = document.body.style.overflow;

    function syncPresentation() {
      if (desktopQuery.matches) {
        if (dialog?.open) dialog.close();
        document.body.style.overflow = previousBodyOverflow;
        window.requestAnimationFrame(() => desktopCloseRef.current?.focus());
      } else {
        document.body.style.overflow = "hidden";
        if (dialog && !dialog.open) dialog.showModal();
        window.requestAnimationFrame(() => mobileCloseRef.current?.focus());
      }
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (!desktopQuery.matches && dialog?.open) {
        event.preventDefault();
        setSelectedId(null);
        return;
      }
      if (desktopQuery.matches) {
        if (document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')) return;
        event.preventDefault();
        setSelectedId(null);
      }
    }

    syncPresentation();
    desktopQuery.addEventListener("change", syncPresentation);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      desktopQuery.removeEventListener("change", syncPresentation);
      window.removeEventListener("keydown", closeOnEscape);
      if (dialog?.open) dialog.close();
      document.body.style.overflow = previousBodyOverflow;
    };
  }, [selectedId]);

  function openSuggest() {
    if (!session) {
      pendingSuggestAfterLoginRef.current = true;
      emit("open-account", {});
      return;
    }
    setSuggestOpen(true);
  }

  async function retryList() {
    setListError("");
    setRetrying(true);
    try {
      const page = await fetchPage(activeTab, null);
      replaceItems(page.items);
      setNextCursor(page.next_cursor);
    } catch {
      setListError("api_unavailable");
    } finally {
      setRetrying(false);
    }
  }

  async function loadMore() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await fetchPage(activeTab, nextCursor);
      setItems((current) => [...current, ...page.items]);
      setNextCursor(page.next_cursor);
      setAnnouncement(`${page.items.length} more ideas loaded.`);
    } catch {
      showToast({ message: "Couldn't load more ideas.", kind: "error" });
    } finally {
      setLoadingMore(false);
    }
  }

  async function handlePosted(result: { id: string; title: string; details: string }) {
    setSuggestOpen(false);
    try {
      const page = await fetchPage("new", null);
      replaceItems(page.items);
      setNextCursor(page.next_cursor);
      setActiveTab("new");
    } catch {
      setItems((current) => [
        { id: result.id, title: result.title, details: result.details || null, status: "submitted", score: 0, my_vote: null, author: session?.username ?? "local", created_at: new Date().toISOString() },
        ...current,
      ]);
      setActiveTab("new");
    }
    setHighlightId(result.id);
    showToast({ message: "Idea posted. Thanks!", kind: "success" });
  }

  async function handleVote(item: FeatureRequest, direction: "up" | "down") {
    if (!session) {
      emit("open-account", {});
      return;
    }
    if (votingIds.has(item.id)) return;
    const previousVote = item.my_vote;
    const previousScore = item.score;
    const newVote = previousVote === direction ? null : direction;
    const newScore = previousScore - voteNumber(previousVote) + voteNumber(newVote);

    setVotingIds((current) => new Set(current).add(item.id));
    setItems((current) => current.map((row) => (row.id === item.id ? { ...row, my_vote: newVote, score: newScore } : row)));

    try {
      const response = await fetch(`/browser-api/feature-requests/${encodeURIComponent(item.id)}/vote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: newVote === "up" ? 1 : newVote === "down" ? -1 : 0 }),
      });
      if (!response.ok) throw new Error("vote_failed");
      const result = await response.json();
      setItems((current) => current.map((row) => (row.id === item.id ? { ...row, score: result.score, my_vote: result.my_vote } : row)));
      setAnnouncement(`${item.title}, score ${result.score}`);
    } catch {
      setItems((current) => current.map((row) => (row.id === item.id ? { ...row, my_vote: previousVote, score: previousScore } : row)));
      showToast({ message: VOTE_ERROR_COPY, kind: "error" });
    } finally {
      setVotingIds((current) => {
        const next = new Set(current);
        next.delete(item.id);
        return next;
      });
    }
  }

  async function handleStatusChange(item: FeatureRequest, status: FeatureStatus) {
    const previous = item.status;
    setItems((current) => current.map((row) => (row.id === item.id ? { ...row, status } : row)));
    try {
      const response = await fetch(`/browser-api/feature-requests/${encodeURIComponent(item.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!response.ok) throw new Error("status_failed");
    } catch {
      setItems((current) => current.map((row) => (row.id === item.id ? { ...row, status: previous } : row)));
      showToast({ message: "Couldn't update status.", kind: "error" });
    }
  }

  async function handleHide(item: FeatureRequest) {
    const index = items.findIndex((row) => row.id === item.id);
    hiddenRowsRef.current.set(item.id, { item, index });
    if (selectedId === item.id) setSelectedId(null);
    setItems((current) => current.filter((row) => row.id !== item.id));
    try {
      const response = await fetch(`/browser-api/feature-requests/${encodeURIComponent(item.id)}/hide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hidden: true }),
      });
      if (!response.ok) throw new Error("hide_failed");
      showToast({
        message: "Request hidden.",
        kind: "success",
        actionLabel: "Undo",
        onAction: () => undoHide(item.id),
      });
    } catch {
      undoHide(item.id);
      showToast({ message: "Couldn't hide that request.", kind: "error" });
    }
  }

  function undoHide(id: string) {
    const entry = hiddenRowsRef.current.get(id);
    if (!entry) return;
    hiddenRowsRef.current.delete(id);
    setItems((current) => {
      const next = [...current];
      next.splice(Math.min(entry.index, next.length), 0, entry.item);
      return next;
    });
    fetch(`/browser-api/feature-requests/${encodeURIComponent(id)}/hide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hidden: false }),
    }).catch(() => undefined);
  }

  function replaceItems(nextItems: FeatureRequest[]) {
    setItems(nextItems);
    setSelectedId((current) => (
      current && !nextItems.some((item) => item.id === current && sanitizeItem(item) !== null) ? null : current
    ));
  }

  const visibleItems = items.map(sanitizeItem).filter((row): row is FeatureRequest => row !== null);
  const selectedItem = selectedId ? visibleItems.find((item) => item.id === selectedId) ?? null : null;

  function openDetails(itemId: string) {
    restoreDetailFocusIdRef.current = itemId;
    setSelectedId(itemId);
  }

  function closeDetails() {
    setSelectedId(null);
  }

  return (
    <div className="mx-auto w-full max-w-[76rem] px-5 pb-24 sm:px-8 sm:pb-20">
      <div aria-live="polite" className="sr-only" role="status">
        {announcement}
      </div>

      {/* The toolbar lives inside the list column so its left and right edges
          line up with the rows beneath it on desktop instead of stretching
          across the rail (spec 4.2/4.4). */}
      <div
        className={`mt-8 grid gap-8 lg:items-start ${
          selectedItem
            ? "lg:grid-cols-[minmax(0,1.2fr)_minmax(24rem,0.8fr)] xl:grid-cols-[minmax(0,1.1fr)_minmax(27rem,0.9fr)]"
            : "lg:grid-cols-[minmax(0,1fr)_20rem]"
        }`}
      >
        <div className="min-w-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
            <nav
              aria-label="Filter feature requests"
              className="grid grid-cols-3 rounded-[7px] border border-zinc-200 bg-white p-0.5 sm:inline-flex"
            >
              {([
                { key: "top", label: "Top", href: "/feature-requests" },
                { key: "new", label: "New", href: "/feature-requests?tab=new" },
                { key: "planned", label: "Planned", href: "/feature-requests?tab=planned" },
              ] as const).map((entry) => (
                <a
                  key={entry.key}
                  href={entry.href}
                  aria-current={activeTab === entry.key ? "page" : undefined}
                  className={`flex h-10 items-center justify-center rounded-[5px] px-2 text-center text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600 sm:h-9 sm:px-4 ${
                    activeTab === entry.key ? "bg-blue-50 text-blue-700" : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950"
                  }`}
                >
                  {entry.label}
                </a>
              ))}
            </nav>
            <button
              type="button"
              onClick={openSuggest}
              className="inline-flex h-11 w-full shrink-0 items-center justify-center rounded-[5px] bg-blue-600 px-5 text-sm font-semibold text-white shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 sm:w-auto"
            >
              Suggest a feature
            </button>
          </div>
          {sessionLoaded && !session && <p className="mt-3 text-[0.8125rem] text-zinc-500">Log in to vote and suggest features.</p>}

          <div className="mt-6">
          {retrying ? (
            <>
              <p className="sr-only" role="status">Loading ideas…</p>
              <ul role="list" aria-busy="true" className="space-y-2.5">
                {Array.from({ length: 5 }, (_, index) => <RowSkeleton key={index} />)}
              </ul>
            </>
          ) : listError ? (
            <div role="alert" className="rounded-[10px] border border-red-200 bg-red-50/60 p-6 text-center">
              <h2 className="text-base font-semibold text-red-700">Couldn&rsquo;t load ideas.</h2>
              <p className="mt-1 text-[0.9375rem] text-red-700/80">{LIST_ERROR_COPY[listError] ?? "Something went wrong on our side."}</p>
              <button
                type="button"
                onClick={retryList}
                className="mt-4 inline-flex h-11 items-center justify-center rounded-[5px] border border-zinc-200 bg-white px-4 text-sm font-semibold text-zinc-700 transition-colors hover:bg-zinc-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                Try again
              </button>
            </div>
          ) : visibleItems.length === 0 ? (
            <EmptyState tab={activeTab} onSuggest={openSuggest} />
          ) : (
            <ul role="list" className="space-y-2.5">
              {visibleItems.map((item, index) => {
                const highlighted = activeTab === "top" && index === 0;
                const isNew = item.id === highlightId;
                return (
                  <li
                    key={item.id}
                    ref={(node) => {
                      if (node) rowRefs.current.set(item.id, node);
                      else rowRefs.current.delete(item.id);
                    }}
                    className={`flex min-h-[5.5rem] items-stretch rounded-[10px] border transition-colors ${
                      selectedId === item.id
                        ? "border-blue-300 bg-blue-50/30"
                        : isNew
                          ? "border-blue-200 bg-blue-50/60"
                          : highlighted
                            ? "border-blue-200 bg-blue-50/40"
                            : "border-zinc-200 bg-white hover:border-zinc-300"
                    }`}
                  >
                    <VoteArrows item={item} disabled={votingIds.has(item.id)} onVote={(direction) => handleVote(item, direction)} />
                    <div className="min-w-0 flex-1 px-4 py-3.5 sm:px-5 sm:py-4">
                      <p className="line-clamp-2 break-words text-[1.0625rem] font-semibold leading-[1.35] tracking-[-0.02em] text-zinc-950" title={item.title}>
                        {item.title}
                      </p>
                      {item.details && (
                        <p className="mt-1 line-clamp-2 break-words text-[0.9375rem] leading-[1.6] text-zinc-600" title={item.details}>
                          {item.details}
                        </p>
                      )}
                      <div className="mt-2.5 flex flex-col gap-2 text-[0.8125rem] text-zinc-500 sm:flex-row sm:items-center">
                        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1.5">
                          <AuthorAvatar username={item.author} />
                          <span className="truncate" title={item.author}>{displayText(item.author, USERNAME_DISPLAY_LENGTH)}</span>
                          <span aria-hidden="true">·</span>
                          <time dateTime={item.created_at}>{dateLabel(item.created_at)}</time>
                        </div>
                        <div className="flex shrink-0 items-center justify-end gap-2 self-end sm:self-auto">
                          {item.details && (
                            <button
                              ref={(node) => {
                                if (node) detailTriggerRefs.current.set(item.id, node);
                                else detailTriggerRefs.current.delete(item.id);
                              }}
                              type="button"
                              aria-label={`View details for ${item.title}`}
                              aria-controls="feature-request-details feature-request-details-mobile"
                              aria-expanded={selectedId === item.id}
                              onClick={() => openDetails(item.id)}
                              className="inline-flex h-8 items-center rounded-[5px] px-1 font-semibold text-blue-700 transition-colors hover:text-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                            >
                              Details <span aria-hidden="true" className="ml-1">→</span>
                            </button>
                          )}
                          <span className="sm:hidden">
                          {isOperator ? (
                            <OperatorStatusMenu item={item} onChangeStatus={(status) => handleStatusChange(item, status)} onHide={() => handleHide(item)} />
                          ) : (
                            <StatusChip status={item.status} />
                          )}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="hidden shrink-0 items-center pr-4 sm:flex sm:pr-5">
                      {isOperator ? (
                        <OperatorStatusMenu item={item} onChangeStatus={(status) => handleStatusChange(item, status)} onHide={() => handleHide(item)} />
                      ) : (
                        <StatusChip status={item.status} />
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {!listError && visibleItems.length > 0 && nextCursor && (
            <button
              type="button"
              onClick={loadMore}
              disabled={loadingMore}
              className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-[5px] border border-zinc-200 bg-white text-sm font-semibold text-zinc-700 transition-colors hover:bg-zinc-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-60"
            >
              {loadingMore && (
                <span aria-hidden="true" className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600 motion-reduce:animate-none" />
              )}
              {loadingMore ? "Loading…" : "Show more ideas"}
            </button>
          )}
          </div>
        </div>

        {selectedItem ? (
          <aside
            id="feature-request-details"
            aria-labelledby={DETAILS_DESKTOP_TITLE_ID}
            className="hidden h-[calc(100vh-6.5rem)] min-w-0 overflow-hidden rounded-[10px] border border-blue-200 bg-white shadow-[0_8px_24px_rgba(9,9,11,0.08)] lg:sticky lg:top-[5.5rem] lg:block"
          >
            <FeatureDetailsContent
              item={selectedItem}
              headingId={DETAILS_DESKTOP_TITLE_ID}
              closeButtonRef={desktopCloseRef}
              voting={votingIds.has(selectedItem.id)}
              onClose={closeDetails}
              onVote={(direction) => handleVote(selectedItem, direction)}
            />
          </aside>
        ) : (
          <HowIdeasWorkRail />
        )}
      </div>

      <dialog
        id="feature-request-details-mobile"
        ref={mobileDialogRef}
        aria-labelledby={DETAILS_MOBILE_TITLE_ID}
        onCancel={(event) => {
          event.preventDefault();
          closeDetails();
        }}
        className="fixed inset-x-0 bottom-0 top-auto m-0 h-[min(85dvh,46rem)] w-full max-w-none overflow-hidden rounded-t-[14px] border border-zinc-200 bg-white p-0 shadow-[0_-12px_40px_rgba(9,9,11,0.18)] backdrop:bg-zinc-950/45 lg:hidden"
      >
        {selectedItem && (
          <FeatureDetailsContent
            item={selectedItem}
            headingId={DETAILS_MOBILE_TITLE_ID}
            closeButtonRef={mobileCloseRef}
            voting={votingIds.has(selectedItem.id)}
            onClose={closeDetails}
            onVote={(direction) => handleVote(selectedItem, direction)}
          />
        )}
      </dialog>

      <SuggestFeatureDialog
        open={suggestOpen}
        isSignedIn={Boolean(session)}
        onClose={() => setSuggestOpen(false)}
        onPosted={handlePosted}
      />
    </div>
  );
}

export { RowSkeleton };
