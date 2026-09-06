import type { Metadata } from "next";
import { SiteHeader } from "./components/SiteHeader";

export const metadata: Metadata = {
  title: "Page not found — Alpha Poker",
};

export default function NotFound() {
  return (
    <>
      <SiteHeader currentPath="/not-found" />
      <main className="mx-auto flex min-h-[calc(100vh-4.5rem)] max-w-2xl flex-col items-center justify-center px-5 py-20 text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-blue-600">404</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-[-0.04em] text-zinc-950 sm:text-5xl">That page isn&rsquo;t in the deck.</h1>
        <p className="mt-5 max-w-md text-lg leading-8 text-zinc-600">Head back to the arena and keep building your bot.</p>
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- vinext worker routing requires a plain internal anchor. */}
        <a
          href="/"
          className="mt-8 inline-flex h-11 items-center justify-center rounded-[7px] bg-blue-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Back to Alpha Poker
        </a>
      </main>
    </>
  );
}
