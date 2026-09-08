"use client";
/* eslint-disable react-hooks/set-state-in-effect, @next/next/no-html-link-for-pages, @next/next/no-location-assign-relative-destination */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { AlphaPokerMark } from "../AlphaPokerMark";
import { AuthButton } from "../AuthButton";
import { rivalsApi, type Notification } from "../rivals/api";
import { emit, on } from "../uiBus";
import { useSession } from "../useSession";

function PeopleIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="none">
      <circle cx="7" cy="7" r="2.4" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M2.5 16c0-2.8 2-4.5 4.5-4.5s4.5 1.7 4.5 4.5M13.2 5.4a2.3 2.3 0 0 1 0 4.4M14 11.7c2.1.3 3.5 1.8 3.5 4.3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
function BellIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-5 w-5" fill="none">
      <path
        d="M5 8.6a5 5 0 1 1 10 0c0 4 1.5 4.2 1.5 5H3.5c0-.8 1.5-1 1.5-5ZM8 16.2h4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

type AppNavItem = {
  label: string;
  href: string;
  icon?: ReactNode;
  isActive: (path: string) => boolean;
};

// One nav model drives the desktop bar and the mobile sheet so "My Bot" and
// "Rivals" can never disagree about which surface the participant is on.
const APP_NAV: AppNavItem[] = [
  {
    label: "Getting Started",
    href: "/#instructions",
    isActive: () => false,
  },
  {
    label: "Leaderboard",
    href: "/leaderboard",
    isActive: (path) => path.startsWith("/leaderboard"),
  },
  {
    label: "My Bot",
    href: "/my-bot",
    isActive: (path) => path.startsWith("/my-bot"),
  },
  {
    label: "Rivals",
    href: "/rivals",
    icon: <PeopleIcon />,
    isActive: (path) => path.startsWith("/rivals") || path.startsWith("/hands/"),
  },
];

function notificationTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function AppHeader({ currentPath }: { currentPath: string }) {
  const { session } = useSession();
  const [open, setOpen] = useState(false);
  const [appMenuOpen, setAppMenuOpen] = useState(false);
  const [communityOpen, setCommunityOpen] = useState(false);
  const [notes, setNotes] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const bellRef = useRef<HTMLButtonElement>(null);
  const notificationDialogRef = useRef<HTMLDivElement>(null);
  const restoreBellFocus = useRef(false);
  const communityRef = useRef<HTMLLIElement>(null);
  const appMenuRef = useRef<HTMLDivElement>(null);
  const appMenuToggleRef = useRef<HTMLButtonElement>(null);
  const notificationGeneration = useRef(0);
  const refresh = async (generation = notificationGeneration.current) => {
    try {
      const data = await rivalsApi.notifications();
      if (generation !== notificationGeneration.current) return;
      setNotes(data.items);
      setUnread(data.unread_count);
    } catch {
      /* non-blocking while API is unavailable */
    }
  };
  useEffect(() => {
    const generation = ++notificationGeneration.current;
    if (!session?.username) {
      setOpen(false);
      setNotes([]);
      setUnread(0);
      setCommunityOpen(false);
      setAppMenuOpen(false);
      return;
    }
    void refresh(generation);
    const interval = window.setInterval(() => void refresh(generation), 10_000);
    const focused = () => void refresh(generation);
    window.addEventListener("focus", focused);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", focused);
    };
  }, [session?.username]);
  useEffect(() => {
    setCommunityOpen(false);
  }, [session]);
  useEffect(() => {
    if (open) {
      window.setTimeout(() => {
        const dialog = notificationDialogRef.current;
        const firstItem = dialog?.querySelector<HTMLElement>("button");
        (firstItem ?? dialog)?.focus();
      }, 0);
      return;
    }
    if (restoreBellFocus.current) {
      restoreBellFocus.current = false;
      bellRef.current?.focus();
    }
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const dismiss = () => {
      restoreBellFocus.current = true;
      setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") dismiss();
    };
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        !notificationDialogRef.current?.contains(target) &&
        !bellRef.current?.contains(target)
      )
        dismiss();
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("mousedown", onPointerDown);
    };
  }, [open]);
  useEffect(() => {
    const closeTransientPanels = () => {
      setOpen(false);
      setCommunityOpen(false);
      setAppMenuOpen(false);
    };
    const offPanels = on("close-panels", closeTransientPanels);
    window.addEventListener("popstate", closeTransientPanels);
    window.addEventListener("hashchange", closeTransientPanels);
    return () => {
      offPanels();
      window.removeEventListener("popstate", closeTransientPanels);
      window.removeEventListener("hashchange", closeTransientPanels);
    };
  }, []);
  useEffect(() => {
    if (!communityOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setCommunityOpen(false);
    };
    const onPointerDown = (event: MouseEvent) => {
      if (!communityRef.current?.contains(event.target as Node))
        setCommunityOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("mousedown", onPointerDown);
    };
  }, [communityOpen]);
  useEffect(() => {
    if (!appMenuOpen) return;
    const close = () => setAppMenuOpen(false);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    const onPointerDown = (event: MouseEvent) => {
      if (!appMenuRef.current?.contains(event.target as Node) && !appMenuToggleRef.current?.contains(event.target as Node)) close();
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("mousedown", onPointerDown);
    };
  }, [appMenuOpen]);
  function opponentFrom(note: Notification) {
    return typeof note.payload?.opponent_username === "string"
      ? note.payload.opponent_username
      : null;
  }

  function notificationCopy(note: Notification) {
    const opponent = opponentFrom(note) ?? "Your rival";
    const score =
      note.payload?.series_score &&
      typeof note.payload.series_score === "object"
        ? (note.payload.series_score as Record<string, unknown>)
        : null;
    const viewerScore = session?.username ? Number(score?.[session.username]) : NaN;
    const opponentScore = Number(score?.[opponent]);
    const winnerFirstScore =
      Number.isFinite(viewerScore) && Number.isFinite(opponentScore)
        ? note.type === "challenge_won"
          ? `${viewerScore}-${opponentScore}`
          : `${opponentScore}-${viewerScore}`
        : null;
    if (note.type === "challenge_received") return `${opponent} challenged you`;
    if (note.type === "challenge_won")
      return `You beat ${opponent}${winnerFirstScore ? ` ${winnerFirstScore}` : ""}`;
    if (note.type === "challenge_lost")
      return `${opponent} beat you${winnerFirstScore ? ` ${winnerFirstScore}` : ""}`;
    if (note.type === "challenge_drawn") return `You and ${opponent} tied.`;
    return `Your challenge with ${opponent} could not finish`;
  }

  async function openTarget(note: Notification) {
    const generation = notificationGeneration.current;
    try {
      const challenge = await rivalsApi.challenge(note.challenge_id);
      if (generation !== notificationGeneration.current) return;
      await rivalsApi.readNotification(note.notification_id);
      if (generation !== notificationGeneration.current) return;
      setUnread((count) => Math.max(0, count - (note.read_at ? 0 : 1)));
      const opponent = challenge.opponent_username ?? opponentFrom(note);
      const params = new URLSearchParams();
      if (
        challenge.status === "failed" ||
        challenge.status === "declined" ||
        challenge.status === "cancelled"
      ) {
        params.set("tab", "challenges");
      } else if (opponent) {
        params.set("rival", opponent);
        if (challenge.status === "completed") {
          params.set("result", challenge.challenge_id);
        } else if (
          challenge.status === "pending" &&
          challenge.challenged_username === session?.username
        ) {
          params.set("challenge", challenge.challenge_id);
        } else {
          params.set("challenge", challenge.challenge_id);
        }
      } else {
        params.set("tab", "challenges");
      }
      window.location.assign(`/rivals?${params}`);
    } catch {
      /* leave unread when target could not open */
    }
  }
  if (!session) {
    return (
      <header className="sticky top-0 z-30 border-b border-zinc-200 bg-white">
        <div className="mx-auto flex h-[4.5rem] max-w-[90rem] items-center justify-between px-5 sm:px-8">
          <a
            href="/"
            className="inline-flex items-center gap-2 rounded focus-visible:outline-2 focus-visible:outline-blue-600"
            aria-label="Alpha Poker home"
          >
            <AlphaPokerMark className="h-8 w-10" />
            <span className="hidden text-[1.05rem] font-semibold text-zinc-950 sm:inline">
              Alpha Poker
            </span>
          </a>
          <AuthButton />
        </div>
      </header>
    );
  }
  return (
    <header className="sticky top-0 z-30 border-b border-zinc-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-[4.5rem] max-w-[90rem] items-center justify-between gap-4 px-5 sm:px-8">
        <a
          href="/"
          className="inline-flex shrink-0 items-center gap-2 rounded focus-visible:outline-2 focus-visible:outline-blue-600"
          aria-label="Alpha Poker home"
        >
          <AlphaPokerMark className="h-8 w-10" />
          <span className="hidden text-[1.05rem] font-semibold text-zinc-950 sm:inline">
            Alpha Poker
          </span>
        </a>
        <nav aria-label="App" className="hidden lg:block">
          <ul className="flex h-[4.5rem] items-center gap-1 text-sm font-medium whitespace-nowrap">
            {APP_NAV.map((item) => {
              const active = item.isActive(currentPath);
              return (
                <li key={item.href} className="relative">
                  <a
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`inline-flex h-full items-center gap-1.5 rounded px-3 focus-visible:outline-2 focus-visible:outline-blue-600 ${active ? "text-blue-700" : "text-zinc-600 hover:text-zinc-950"}`}
                  >
                    {item.icon}
                    {item.label}
                  </a>
                  {active && (
                    <span
                      aria-hidden="true"
                      className="absolute inset-x-3 bottom-[-1px] h-0.5 bg-blue-600"
                    />
                  )}
                </li>
              );
            })}
            {session && (
              <li
                ref={communityRef}
                className="relative ml-2 border-l border-zinc-200 pl-2"
              >
                <button
                  type="button"
                  aria-expanded={communityOpen}
                  aria-controls="app-community-menu"
                  onClick={() => setCommunityOpen((value) => !value)}
                  className="inline-flex h-full items-center gap-1 rounded px-3 text-zinc-600 hover:text-zinc-950 focus-visible:outline-2 focus-visible:outline-blue-600"
                >
                  Community
                  <span aria-hidden="true">⌄</span>
                </button>
                {communityOpen && (
                  <div
                    id="app-community-menu"
                    className="absolute left-2 top-[3.75rem] w-44 rounded-xl border border-zinc-200 bg-white p-1.5 shadow-lg"
                  >
                    <a
                      href="/feature-requests"
                      onClick={() => setCommunityOpen(false)}
                      className="block rounded-lg px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
                    >
                      Feature requests
                    </a>
                    <a
                      href="/contribute"
                      onClick={() => setCommunityOpen(false)}
                      className="block rounded-lg px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
                    >
                      Contribute
                    </a>
                  </div>
                )}
              </li>
            )}
          </ul>
        </nav>
        <div className="relative flex shrink-0 items-center gap-2">
          <button
            ref={appMenuToggleRef}
            type="button"
            aria-label={appMenuOpen ? "Close app menu" : "Open app menu"}
            aria-expanded={appMenuOpen}
            aria-controls="app-mobile-menu"
            onClick={() => setAppMenuOpen((value) => !value)}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-zinc-700 hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-blue-600 lg:hidden"
          >
            {appMenuOpen ? "×" : "☰"}
          </button>
          <button
            ref={bellRef}
            type="button"
            aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
            aria-expanded={open}
            onClick={() => {
              if (open) {
                setOpen(false);
                return;
              }
              emit("close-panels", {});
              setOpen(true);
            }}
            className="relative grid h-10 w-10 place-items-center rounded-lg text-zinc-700 hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-blue-600"
          >
            <BellIcon />
            {unread > 0 && (
              <span className="absolute right-1 top-1 min-w-4 rounded-full bg-blue-600 px-1 text-[10px] font-bold leading-4 text-white">
                {unread > 9 ? "9+" : unread}
              </span>
            )}
          </button>
          <AuthButton />
          {open && (
            <div
              ref={notificationDialogRef}
              role="dialog"
              aria-label="Notifications"
              tabIndex={-1}
              className="absolute right-0 top-12 max-h-[calc(100dvh-6rem)] w-80 overflow-y-auto rounded-xl border border-zinc-200 bg-white p-2 shadow-xl"
            >
              <div className="px-3 py-2 font-semibold">Notifications</div>
              {notes.length ? (
                <ul>
                  {notes.map((note) => (
                    <li key={note.notification_id}>
                      <button
                        type="button"
                        onClick={() => void openTarget(note)}
                        className={`w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-zinc-50 ${note.read_at ? "text-zinc-600" : "bg-blue-50 text-zinc-950"}`}
                      >
                        <span className="font-semibold">
                          {notificationCopy(note)}
                        </span>
                        <span className="mt-1 flex items-center gap-2 text-xs font-medium text-zinc-500">
                          <time dateTime={note.created_at}>
                            {notificationTime(note.created_at)}
                          </time>
                          {!note.read_at && (
                            <span
                              className="inline-block h-2 w-2 rounded-full bg-blue-600"
                              aria-label="Unread"
                            />
                          )}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-3 py-4 text-sm text-zinc-500">
                  You&apos;re all caught up.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
      {appMenuOpen && (
        <div
          id="app-mobile-menu"
          ref={appMenuRef}
          className="absolute inset-x-0 top-full z-40 border-b border-zinc-200 bg-white px-5 py-2 shadow-lg lg:hidden"
        >
          <nav aria-label="App">
            {APP_NAV.map((item) => {
              const active = item.isActive(currentPath);
              return (
                <a
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  onClick={() => setAppMenuOpen(false)}
                  className={`flex h-11 items-center rounded-lg px-3 text-sm font-semibold ${active ? "bg-blue-50 text-blue-700" : "text-zinc-700"}`}
                >
                  {item.label}
                </a>
              );
            })}
            <div className="mt-1 border-t border-zinc-100 pt-1">
              <p className="px-3 py-2 text-xs font-bold tracking-wide text-zinc-500">
                COMMUNITY
              </p>
              <a
                href="/feature-requests"
                onClick={() => setAppMenuOpen(false)}
                className="flex h-10 items-center rounded-lg px-3 text-sm font-medium text-zinc-600"
              >
                Feature requests
              </a>
              <a
                href="/contribute"
                onClick={() => setAppMenuOpen(false)}
                className="flex h-10 items-center rounded-lg px-3 text-sm font-medium text-zinc-600"
              >
                Contribute
              </a>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
