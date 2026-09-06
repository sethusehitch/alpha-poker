"use client";

import { useEffect, useId, useRef, useState } from "react";
import { AlphaPokerMark } from "./AlphaPokerMark";
import { AuthButton } from "./AuthButton";
import { on } from "./uiBus";

type NavItem = { label: string; href: string; isActive: (path: string) => boolean };

const NAV_ITEMS: NavItem[] = [
  { label: "Leaderboard", href: "/#leaderboard", isActive: (path) => path === "/" },
  { label: "Feature requests", href: "/feature-requests", isActive: (path) => path.startsWith("/feature-requests") },
  { label: "Contribute", href: "/contribute", isActive: (path) => path.startsWith("/contribute") },
];

function MenuIcon({ open }: { open: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-5 w-5" fill="none">
      {open ? (
        <path d="M5 5l10 10M15 5 5 15" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      ) : (
        <path d="M3 5.5h14M3 10h14M3 14.5h14" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      )}
    </svg>
  );
}

export function SiteHeader({ currentPath, sticky = false }: { currentPath: string; sticky?: boolean }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const panelId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);
  const firstLinkRef = useRef<HTMLAnchorElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => on("close-panels", () => setMenuOpen(false)), []);

  useEffect(() => {
    if (!menuOpen) return;
    firstLinkRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        toggleRef.current?.focus();
      }
    };
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (panelRef.current?.contains(target) || toggleRef.current?.contains(target)) return;
      setMenuOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("mousedown", onPointerDown);
    };
  }, [menuOpen]);

  return (
    <header className={`relative border-b border-zinc-200/80 bg-white ${sticky ? "sticky top-0 z-30" : ""}`}>
      <div className="mx-auto flex h-[4.5rem] max-w-[90rem] items-center justify-between px-5 sm:px-8">
        {/* The lockup never wraps or shrinks: at 320px the tighter gap plus the
            account chip's narrower small-screen padding keeps the whole row on
            one 72px line. */}
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- vinext's worker routing has no next/link support; every internal link in this codebase is a plain <a>. */}
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

        <nav aria-label="Main" className="absolute left-1/2 hidden -translate-x-1/2 lg:flex">
          <ul className="flex items-center gap-8">
            {NAV_ITEMS.map((item) => {
              const active = item.isActive(currentPath);
              return (
                <li key={item.href} className="relative h-[4.5rem]">
                  <a
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`inline-flex h-full items-center rounded-[5px] px-1 text-[0.9375rem] font-medium tracking-[-0.01em] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600 ${
                      active ? "text-blue-700" : "text-zinc-600 hover:text-zinc-950"
                    }`}
                  >
                    {item.label}
                  </a>
                  {active && <span aria-hidden="true" className="absolute inset-x-0 bottom-[-1px] h-0.5 bg-blue-600" />}
                </li>
              );
            })}
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
          {/* The disclosure carries the Main landmark below 1024px, where the
              centered nav above is display:none and therefore absent from the
              accessibility tree (spec 7.4). */}
          <nav aria-label="Main">
            <ul>
              {NAV_ITEMS.map((item, index) => {
                const active = item.isActive(currentPath);
                return (
                  <li key={item.href}>
                    <a
                      ref={index === 0 ? firstLinkRef : undefined}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      onClick={() => setMenuOpen(false)}
                      className={`flex h-12 items-center rounded-[5px] pl-3 text-[1.0625rem] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600 ${
                        active
                          ? "border-l-2 border-blue-600 bg-blue-50/60 font-semibold text-blue-700"
                          : "text-zinc-700"
                      }`}
                    >
                      {item.label}
                    </a>
                  </li>
                );
              })}
            </ul>
          </nav>
        </div>
      )}
    </header>
  );
}
