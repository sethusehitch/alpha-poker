"use client";
/* eslint-disable react-hooks/set-state-in-effect, @next/next/no-html-link-for-pages */

import { useEffect, useId, useRef, useState } from "react";
import { AlphaPokerMark } from "./AlphaPokerMark";
import { AuthButton } from "./AuthButton";
import { on } from "./uiBus";
import { useSession } from "./useSession";

type NavItem = {
  label: string;
  href: string;
  isActive: (path: string) => boolean;
};
const GETTING_STARTED: NavItem = {
  label: "Getting Started",
  href: "/#instructions",
  isActive: () => false,
};
const LEADERBOARD: NavItem = {
  label: "Leaderboard",
  href: "/leaderboard",
  isActive: (path) => path.startsWith("/leaderboard"),
};
const MY_BOT: NavItem = {
  label: "My Bot",
  href: "/my-bot",
  isActive: (path) => path.startsWith("/my-bot"),
};
const RIVALS: NavItem = {
  label: "Rivals",
  href: "/rivals",
  isActive: (path) => path.startsWith("/rivals") || path.startsWith("/hands/"),
};
const TRAINING: NavItem = { label: "Training", href: "/training", isActive: path => path.startsWith("/training") };
const COMMUNITY_ITEMS: NavItem[] = [
  {
    label: "Feature requests",
    href: "/feature-requests",
    isActive: (path) => path.startsWith("/feature-requests"),
  },
  {
    label: "Contribute",
    href: "/contribute",
    isActive: (path) => path.startsWith("/contribute"),
  },
];

function MenuIcon({ open }: { open: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-5 w-5" fill="none">
      {open ? (
        <path
          d="M5 5l10 10M15 5 5 15"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
        />
      ) : (
        <path
          d="M3 5.5h14M3 10h14M3 14.5h14"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}
function ChevronIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 14 14"
      className="h-3.5 w-3.5"
      fill="none"
    >
      <path
        d="M3.5 5.25 7 8.75l3.5-3.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SiteHeader({
  currentPath,
  sticky = true,
}: {
  currentPath: string;
  sticky?: boolean;
}) {
  const { session } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);
  const [communityOpen, setCommunityOpen] = useState(false);
  const [mobileCommunityOpen, setMobileCommunityOpen] = useState(false);
  const panelId = useId();
  const communityId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);
  const firstLinkRef = useRef<HTMLAnchorElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const communityRef = useRef<HTMLLIElement>(null);
  const communityButtonRef = useRef<HTMLButtonElement>(null);
  const coreItems = session
    ? [GETTING_STARTED, LEADERBOARD, MY_BOT, TRAINING, RIVALS]
    : [GETTING_STARTED, LEADERBOARD];

  const closeMenus = () => {
    setMenuOpen(false);
    setCommunityOpen(false);
    setMobileCommunityOpen(false);
  };
  useEffect(() => on("close-panels", closeMenus), []);
  useEffect(() => {
    closeMenus();
  }, [session]);
  useEffect(() => {
    if (!menuOpen && !communityOpen) return;
    if (menuOpen) firstLinkRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const wasCommunity = communityOpen;
      closeMenus();
      (wasCommunity ? communityButtonRef.current : toggleRef.current)?.focus();
    };
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        panelRef.current?.contains(target) ||
        toggleRef.current?.contains(target) ||
        communityRef.current?.contains(target)
      )
        return;
      closeMenus();
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("mousedown", onPointerDown);
    };
  }, [menuOpen, communityOpen]);

  function DesktopItem({ item }: { item: NavItem }) {
    const active = item.isActive(currentPath);
    return (
      <li className="relative h-[4.5rem]">
        <a
          href={item.href}
          aria-current={active ? "page" : undefined}
          className={`inline-flex h-full items-center rounded-[5px] px-1 text-[0.9375rem] font-medium tracking-[-0.01em] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600 ${active ? "text-blue-700" : "text-zinc-600 hover:text-zinc-950"}`}
        >
          {item.label}
        </a>
        {active && (
          <span
            aria-hidden="true"
            className="absolute inset-x-0 bottom-[-1px] h-0.5 bg-blue-600"
          />
        )}
      </li>
    );
  }

  return (
    <header
      className={`border-b border-zinc-200/80 bg-white ${sticky ? "sticky top-0 z-30" : "relative"}`}
    >
      <div className="mx-auto flex h-[4.5rem] max-w-[90rem] items-center justify-between px-5 sm:px-8">
        <a
          href="/"
          className="group inline-flex shrink-0 items-center gap-2 rounded-[5px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-600 sm:gap-2.5"
          aria-label="Alpha Poker home"
        >
          <AlphaPokerMark className="h-8 w-10 shrink-0 transition-transform duration-200 group-hover:-rotate-2" />
          <span className="whitespace-nowrap text-[1.05rem] font-semibold tracking-[-0.025em] text-zinc-950">
            Alpha Poker
          </span>
        </a>
        <nav
          aria-label="Main"
          className="absolute left-1/2 hidden -translate-x-1/2 lg:flex"
        >
          <ul className="flex items-center gap-8">
            {coreItems.map((item) => (
              <DesktopItem key={item.href} item={item} />
            ))}
            {session && (
              <li ref={communityRef} className="relative">
                <button
                  ref={communityButtonRef}
                  type="button"
                  aria-expanded={communityOpen}
                  aria-controls={communityId}
                  onClick={() => setCommunityOpen((value) => !value)}
                  className="inline-flex h-10 items-center gap-1 rounded-[5px] px-1 text-[0.9375rem] font-medium text-zinc-600 hover:text-zinc-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
                >
                  Community <ChevronIcon />
                </button>
                {communityOpen && (
                  <div
                    id={communityId}
                    className="absolute left-0 top-12 w-44 rounded-xl border border-zinc-200 bg-white p-1.5 shadow-lg"
                  >
                    <ul>
                      {COMMUNITY_ITEMS.map((item) => (
                        <li key={item.href}>
                          <a
                            href={item.href}
                            onClick={closeMenus}
                            className="block rounded-lg px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 hover:text-zinc-950"
                          >
                            {item.label}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            )}
          </ul>
        </nav>
        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          <button
            ref={toggleRef}
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-[5px] text-zinc-700 hover:bg-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 lg:hidden"
            aria-label={menuOpen ? "Close menu" : "Menu"}
            aria-expanded={menuOpen}
            aria-controls={panelId}
            onClick={() => setMenuOpen((value) => !value)}
          >
            <MenuIcon open={menuOpen} />
          </button>
          <AuthButton />
        </div>
      </div>
      {menuOpen && (
        <div
          id={panelId}
          ref={panelRef}
          className="absolute inset-x-0 top-full z-35 border-b border-zinc-200 bg-white px-5 py-2 shadow-[0_8px_24px_rgba(9,9,11,0.10)] motion-safe:animate-[fade-in_150ms_ease-out]"
        >
          <nav aria-label="Main">
            <ul>
              {coreItems.map((item, index) => {
                const active = item.isActive(currentPath);
                return (
                  <li key={item.href}>
                    <a
                      ref={index === 0 ? firstLinkRef : undefined}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      onClick={closeMenus}
                      className={`flex h-12 items-center rounded-[5px] pl-3 text-[1.0625rem] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600 ${active ? "border-l-2 border-blue-600 bg-blue-50/60 font-semibold text-blue-700" : "text-zinc-700"}`}
                    >
                      {item.label}
                    </a>
                  </li>
                );
              })}
              {session && (
                <li className="mt-1 border-t border-zinc-100 pt-1">
                  <button
                    type="button"
                    aria-expanded={mobileCommunityOpen}
                    onClick={() => setMobileCommunityOpen((value) => !value)}
                    className="flex h-12 w-full items-center justify-between rounded-[5px] pl-3 text-left text-[1.0625rem] font-medium text-zinc-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
                  >
                    Community <ChevronIcon />
                  </button>
                  {mobileCommunityOpen && (
                    <ul className="ml-3 border-l border-zinc-200">
                      {COMMUNITY_ITEMS.map((item) => (
                        <li key={item.href}>
                          <a
                            href={item.href}
                            onClick={closeMenus}
                            className="flex h-11 items-center pl-4 text-sm font-medium text-zinc-600 hover:text-zinc-950"
                          >
                            {item.label}
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              )}
            </ul>
          </nav>
        </div>
      )}
    </header>
  );
}
