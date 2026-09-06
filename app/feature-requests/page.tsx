import type { Metadata } from "next";
import { headers } from "next/headers";
import { authorizationFromCookieHeader, serverFetchJson } from "../browser-api/_proxy";
import { SiteHeader } from "../components/SiteHeader";
import { FeatureRequestList, type FeatureRequest, type FeatureTab } from "../components/FeatureRequestList";

export const metadata: Metadata = {
  title: "Feature requests — Alpha Poker",
  description: "Vote on ideas from the Alpha Poker community.",
};

function resolveTab(value: string | string[] | undefined): FeatureTab {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw === "new" || raw === "planned" ? raw : "top";
}

export default async function FeatureRequestsPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string | string[] }>;
}) {
  const params = await searchParams;
  const tab = resolveTab(params.tab);

  const requestHeaders = await headers();
  const authorization = authorizationFromCookieHeader(requestHeaders.get("cookie"));
  const initialData = await serverFetchJson(`feature-requests?tab=${tab}`, authorization);
  const initialItems: FeatureRequest[] = Array.isArray(initialData?.items) ? initialData.items : [];
  const initialNextCursor: string | null = initialData?.next_cursor ?? null;
  const initialError = initialData === null;

  return (
    <>
      <SiteHeader currentPath="/feature-requests" sticky />
      <main>
        <div className="mx-auto w-full max-w-[76rem] px-5 pt-14 pb-10 text-center sm:px-8 sm:pt-20 sm:pb-12">
          <h1 className="mx-auto max-w-[24ch] text-[clamp(2.5rem,5vw,4rem)] font-[680] leading-[1.06] tracking-[-0.045em] text-zinc-950">
            What should we build next?
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-[1.08rem] leading-[1.6] tracking-[-0.018em] text-zinc-600 sm:text-[1.25rem]">
            Vote on ideas from the Alpha Poker community.
          </p>
        </div>
        <FeatureRequestList tab={tab} initialItems={initialItems} initialNextCursor={initialNextCursor} initialError={initialError} />
      </main>
    </>
  );
}
