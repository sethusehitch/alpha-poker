import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("browser API proxy preserves Caddy's client address and safe user-agent context", async () => {
  const source = await readFile(new URL("../app/browser-api/_proxy.ts", import.meta.url), "utf8");
  assert.match(source, /request\.headers\.get\("x-forwarded-for"\)/);
  assert.match(source, /headers\.set\("X-Forwarded-For"/);
  assert.match(source, /headers\.set\("User-Agent"/);
  assert.doesNotMatch(source, /X-Alpha-Operator/);
});

async function render(path) {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${path}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${path}`, { headers: { accept: "text/html" } }),
    {
      ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) },
    },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

async function html(path) {
  const response = await render(path);
  assert.equal(response.status, 200);
  return response.text();
}

test("/feature-requests renders the community header, hero, and offline-safe list", async () => {
  const body = await html("/feature-requests");

  assert.match(body, /<title>Feature requests — Alpha Poker<\/title>/);
  assert.match(body, /Vote on ideas from the Alpha Poker community\./);
  assert.match(body, /What should we build next\?/);
  assert.match(body, /aria-label="Main"/);
  assert.match(body, /aria-current="page"[^>]*>Feature requests/);
  assert.match(body, /aria-current="page"[^>]*>Top/);
  assert.match(body, /aria-label="Filter feature requests"/);
  assert.match(body, /Suggest a feature/);
  assert.doesNotMatch(body, /Log in to vote and suggest features\./);
  assert.match(body, /How ideas work/);
  assert.match(body, /Use the feedback button in the corner/);

  // No FastAPI instance is reachable during the static test build, so the
  // list must degrade to the documented offline error copy, never a raw
  // status code or error.code string (COMMUNITY_DESIGN_SPEC.md section 7.1.5).
  assert.match(body, /Couldn.t load ideas\./);
  assert.doesNotMatch(body, /api_unavailable/);
  assert.doesNotMatch(body, /"error":\s*\{/);
});

test("authenticated-only copy waits until the session check completes", async () => {
  const source = await readFile(new URL("../app/components/FeatureRequestList.tsx", import.meta.url), "utf8");
  assert.match(source, /sessionLoaded && !session/);
});

test("unknown routes provide a useful path back to the arena", async () => {
  const response = await render("/definitely-not-a-page");
  assert.equal(response.status, 404);
  const body = await response.text();
  assert.match(body, /That page isn.t in the deck\./);
  assert.match(body, /Back to Alpha Poker/);
  assert.match(body, /aria-label="Alpha Poker home"/);
});

test("/feature-requests?tab=new and ?tab=planned deep-link to the right tab", async () => {
  const newTab = await html("/feature-requests?tab=new");
  assert.match(newTab, /aria-current="page"[^>]*>New/);

  const plannedTab = await html("/feature-requests?tab=planned");
  assert.match(plannedTab, /aria-current="page"[^>]*>Planned/);
});

test("feature request dates hydrate identically across server and browser time zones", async () => {
  const source = await readFile(new URL("../app/components/FeatureRequestList.tsx", import.meta.url), "utf8");
  assert.match(source, /timeZone: "UTC"/);

  const script = `process.stdout.write(new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", year: "numeric", timeZone: "UTC"
  }).format(new Date("2026-09-06T04:47:17.810787Z")))`;
  const labels = ["UTC", "America/Los_Angeles", "Pacific/Kiritimati"].map((TZ) => {
    const result = spawnSync(process.execPath, ["-e", script], {
      encoding: "utf8",
      env: { ...process.env, TZ },
    });
    assert.equal(result.status, 0, result.stderr);
    return result.stdout;
  });
  assert.deepEqual(labels, ["Sep 6, 2026", "Sep 6, 2026", "Sep 6, 2026"]);
});

test("/feature-requests never renders excluded community content", async () => {
  const body = await html("/feature-requests");

  assert.doesNotMatch(body, /bb\/100/);
  assert.doesNotMatch(body, /95% range/i);
  assert.doesNotMatch(body, /Discord/i);
  assert.doesNotMatch(body, /join our (community|server)/i);
  assert.doesNotMatch(body, /💬/);
});

test("/contribute renders the hero, four-step guide, and offline-safe issues card", async () => {
  const body = await html("/contribute");

  assert.match(body, /<title>Contribute — Alpha Poker<\/title>/);
  assert.match(body, /Pick an issue, improve the arena, and send a pull request\./);
  assert.match(body, /OPEN SOURCE/);
  assert.match(body, /Help build Alpha Poker\./);
  assert.match(body, /Pick an issue/);
  assert.match(body, /Fork and build/);
  assert.match(body, /Run the tests/);
  assert.match(body, /Open a pull request/);
  assert.match(body, /Good first issues/);
  assert.match(body, /Before you start/);
  assert.match(body, /You propose\. Maintainers review\. Nothing merges automatically\./);
  assert.match(body, /target="_blank" rel="noopener noreferrer"/);
  assert.match(body, /\(opens in a new tab\)/);

  // GitHub is unreachable during the static test build; the page must keep
  // working (hero, steps, rail, closing strip) instead of blanking.
  assert.match(body, /Couldn.t load issues from GitHub\./);
  assert.match(body, /The full list still works\./);
});

test("/contribute never shows decorative casino imagery or a Discord link", async () => {
  const body = await html("/contribute");

  assert.doesNotMatch(body, /Discord/i);
  assert.doesNotMatch(body, /felt|playing-card|casino/i);
});

test("global feedback widget and account chip mount on every community page", async () => {
  for (const path of ["/", "/feature-requests", "/contribute"]) {
    const body = await html(path);
    assert.match(body, /aria-label="Send feedback"/, `${path} is missing the feedback FAB`);
    assert.match(body, /data-testid="account-trigger"/, `${path} is missing the account chip`);
  }
});

test("account dialog clears private registration fields whenever it closes", async () => {
  const source = await readFile(new URL("../app/components/AuthButton.tsx", import.meta.url), "utf8");

  assert.match(source, /resetAuthForm = useCallback\(\(\) => \{[\s\S]*setInviteCode\(""\)/);
  assert.match(source, /closeDialog = useCallback\(\(\) => \{[\s\S]*resetAuthForm\(\)[\s\S]*setOpen\(false\)/);
  assert.doesNotMatch(source, /aria-label="Close" onClick=\{\(\) => setOpen\(false\)\}/);
  assert.match(source, /onMouseDown=\{closeDialog\}/);
  assert.match(source, /if \(event\.key === "Escape"\) closeDialog\(\)/);
});

test("status chip supports exactly the six-stage lifecycle", async () => {
  const source = await readFile(new URL("../app/components/StatusChip.tsx", import.meta.url), "utf8");

  for (const status of ["submitted", "under_review", "planned", "in_progress", "shipped", "declined"]) {
    assert.match(source, new RegExp(status), `StatusChip is missing "${status}"`);
  }
  assert.doesNotMatch(source, /\bopen\b/);
  assert.doesNotMatch(source, /not_planned/);
  assert.match(source, /"submitted"/, "unknown statuses must safely fall back to submitted");
});

test("feedback accepts signed-out visitors and keeps optional username context", async () => {
  const source = await readFile(new URL("../app/components/FeedbackWidget.tsx", import.meta.url), "utf8");

  // The API attaches the username server-side when a session cookie exists and
  // accepts the post without one, so the widget must not gate submission.
  assert.doesNotMatch(source, /mustLogIn/);
  assert.doesNotMatch(source, /authRequired/);
  assert.doesNotMatch(source, /Log in to send feedback/);
  assert.match(source, /Sent with your username and this page\./);
  assert.match(source, /Sent anonymously with this page address\./);
  // A 401 still offers an inline log-in without discarding the draft.
  assert.match(source, /session_expired/);
  assert.match(source, /emit\("open-account", \{\}\)/);
});

test("feedback draft survives a full route navigation and clears after a successful send", async () => {
  const source = await readFile(new URL("../app/components/FeedbackWidget.tsx", import.meta.url), "utf8");

  // Every navigation in this app is a full document load, so component state
  // alone loses the draft. sessionStorage is tab-scoped (unlike localStorage,
  // which would leak a draft to the next user of a shared machine).
  assert.match(source, /"alpha-poker:feedback-draft"/, "draft key must be narrow and project-specific");
  assert.match(source, /window\.sessionStorage\.getItem\(DRAFT_STORAGE_KEY\)/);
  assert.match(source, /window\.sessionStorage\.setItem\(DRAFT_STORAGE_KEY/);
  assert.match(source, /window\.sessionStorage\.removeItem\(DRAFT_STORAGE_KEY\)/);
  assert.doesNotMatch(source, /window\.localStorage/);

  // Both the message and the selected type persist, and the draft is cleared
  // on success so the next visitor never sees the last one.
  assert.match(source, /JSON\.stringify\(draft\)/);
  assert.match(source, /writeDraft\(\{ type, message \}\)|writeDraft\(message === "" \? null : \{ type, message \}\)/);
  assert.match(source, /setType\("idea"\);\s*\n\s*writeDraft\(null\);/);
});

test("mobile disclosure links sit inside a Main nav landmark", async () => {
  const source = await readFile(new URL("../app/components/SiteHeader.tsx", import.meta.url), "utf8");

  // Below 1024px the centered nav is display:none and therefore absent from
  // the accessibility tree, so the disclosure panel has to carry the landmark.
  const panel = source.slice(source.indexOf("{menuOpen && ("));
  assert.match(panel, /<nav aria-label="Main">/, "the mobile panel is missing the Main landmark");
  assert.match(panel, /<ul>/, "the mobile nav links must be a real list");
});

test("only this repository's own issue URL is ever rendered as an href", async () => {
  const safety = await readFile(new URL("../app/components/textSafety.ts", import.meta.url), "utf8");
  const card = await readFile(new URL("../app/components/ContributeIssuesCard.tsx", import.meta.url), "utf8");

  // The owner/repo are pinned to a build-time constant that mirrors
  // GITHUB_OWNER/GITHUB_REPO in server/alpha_poker_api/github.py.
  assert.match(safety, /GITHUB_REPO_URL = "https:\/\/github\.com\/sethusehitch\/alpha-poker"/);
  assert.match(safety, /\$\{GITHUB_REPO_URL\}\/issues\/\$\{issueNumber\}/);

  // Validation is exact string equality against the URL this repo would build
  // for that issue number, so no wildcard owner/repo segment and no `pull`
  // path can slip through the way the old prefix regex allowed.
  assert.match(safety, /return expected !== null && typeof value === "string" && value === expected;/);
  assert.doesNotMatch(safety, /\[\^\/\]\+/);
  assert.doesNotMatch(safety, /issues\|pull/);
  assert.doesNotMatch(safety, /isSafeRepoUrl/);

  // A URL that fails the check renders as plain text, never as an anchor.
  assert.match(card, /isRepoIssueUrl\(issue\.url, issue\.number\)/);
  assert.match(card, /if \(!safeUrl\) \{\s*\n\s*return <div/);
});

function mainContent(body) {
  const start = body.indexOf("<main");
  const end = body.indexOf("</main>", start);
  assert.ok(start !== -1 && end > start, "page is missing a <main> landmark");
  return body.slice(start, end);
}

function svgBodies(markup) {
  return [...markup.matchAll(/<svg[^>]*>([\s\S]*?)<\/svg>/g)].map((match) => match[1]);
}

test("the feature-request toolbar shares the list column and is usable at narrow widths", async () => {
  const body = await html("/feature-requests");

  // The toolbar renders inside the two-column grid, so its edges line up with
  // the rows beneath it instead of stretching across the rail.
  const gridIndex = body.indexOf("lg:grid-cols-[minmax(0,1fr)_20rem]");
  const tabsIndex = body.indexOf('aria-label="Filter feature requests"');
  assert.ok(gridIndex !== -1, "the two-column grid is missing");
  assert.ok(tabsIndex > gridIndex, "the toolbar must sit inside the list column, not above the grid");

  // 3-up full-width tabs with 40px touch targets below 640px, segmented
  // control above it; primary CTA full width below 640px.
  assert.match(body, /aria-label="Filter feature requests" class="grid grid-cols-3[^"]*sm:inline-flex"/);
  assert.match(body, /class="flex h-10 items-center justify-center[^"]*sm:h-9 sm:px-4[^"]*"[^>]*>Top</);
  assert.match(body, /class="inline-flex h-11 w-full[^"]*sm:w-auto">Suggest a feature<\/button>/);
});

test("every interactive control on the community surfaces has a cobalt focus ring", async () => {
  for (const path of ["/feature-requests", "/contribute"]) {
    const body = await html(path);
    const controls = mainContent(body).match(/<(?:a|button)\b[^>]*>/g) ?? [];
    assert.ok(controls.length >= 4, `${path} rendered no interactive controls to check`);
    for (const control of controls) {
      assert.match(control, /focus-visible:outline-blue-600/, `${path}: missing focus ring on ${control}`);
    }

    // Global chrome: nav links, the mobile toggle, the account chip, and the
    // feedback FAB all live outside <main>.
    assert.match(body, /aria-label="Menu"[\s\S]{0,400}?focus-visible:outline-blue-600|focus-visible:outline-blue-600[^>]*aria-label="Menu"/);
    assert.match(body, /data-testid="account-trigger"[\s\S]{0,400}?focus-visible:outline-blue-600/);
    assert.match(body, /aria-label="Send feedback"[\s\S]{0,600}?focus-visible:outline-blue-600/);
  }
});

test("the wordmark never wraps and the page clears the feedback FAB at 320px", async () => {
  for (const path of ["/feature-requests", "/contribute"]) {
    const body = await html(path);
    assert.match(body, /class="whitespace-nowrap[^"]*">Alpha Poker<\/span>/, `${path}: the wordmark can wrap`);
    // 96px of bottom padding below 640px keeps content clear of the 56px FAB.
    assert.match(body, /max-w-\[76rem\][^"]*pb-24[^"]*sm:pb-20/, `${path}: page bottom padding does not clear the FAB`);
  }

  const header = await readFile(new URL("../app/components/SiteHeader.tsx", import.meta.url), "utf8");
  const chip = await readFile(new URL("../app/components/AuthButton.tsx", import.meta.url), "utf8");
  assert.match(header, /shrink-0 items-center gap-2 rounded-\[5px\]/, "the lockup must not shrink or re-gap");
  assert.match(chip, /min-\[380px\]:px-3\.5/, "the account chip must tighten below 380px so the 320px row fits");
  assert.match(chip, /max-w-\[4\.5rem\] truncate min-\[380px\]:max-w-\[6\.5rem\]/);
});

test("posted-row scrolling and list skeletons respect reduced motion and real geometry", async () => {
  const source = await readFile(new URL("../app/components/FeatureRequestList.tsx", import.meta.url), "utf8");

  // Reduced motion jumps to the new row instead of animating the scroll.
  assert.match(source, /prefers-reduced-motion: reduce/);
  assert.match(source, /behavior: prefersReducedMotion\(\) \? "auto" : "smooth"/);

  // The skeleton mirrors the row it replaces at both breakpoints: 48px
  // undivided vote rail and inline chip below 640px, 64px divided rail and
  // chip column above it.
  const skeleton = source.slice(source.indexOf("function RowSkeleton()"), source.indexOf("const HOW_IDEAS_WORK"));
  assert.match(skeleton, /w-12 shrink-0[^"]*sm:w-16 sm:border-r/);
  assert.match(skeleton, /rounded-\[6px\] bg-zinc-100 motion-reduce:animate-none sm:hidden/);
  assert.match(skeleton, /hidden shrink-0 items-center pr-4 sm:flex sm:pr-5/);
  assert.match(skeleton, /h-10 w-10 items-center justify-center sm:h-9 sm:w-9/);
});

test("feature request cards expose compact previews and open a live detail view", async () => {
  const source = await readFile(new URL("../app/components/FeatureRequestList.tsx", import.meta.url), "utf8");

  assert.match(source, /line-clamp-2 break-words text-\[1\.0625rem\]/, "titles must stay at two lines");
  assert.match(source, /mt-1 line-clamp-2 break-words text-\[0\.9375rem\]/, "descriptions must stay at two lines");
  assert.match(source, /\{item\.details && \([\s\S]*Details <span aria-hidden="true" className="ml-1">→<\/span>/, "requests with descriptions need a Details trigger");
  assert.match(source, /aria-label=\{`View details for \$\{item\.title\}`\}/);
  assert.match(source, /aria-expanded=\{selectedId === item\.id\}/);
  assert.match(source, /const selectedItem = selectedId \? visibleItems\.find/, "detail content must derive from live list state");
  assert.match(source, /function replaceItems\([\s\S]*!nextItems\.some\(\(item\) => item\.id === current && sanitizeItem\(item\) !== null\) \? null : current/, "replacing the list must close details if its item disappears");
  assert.match(source, /if \(selectedId === item\.id\) setSelectedId\(null\)/, "hiding the selected item must close its details");
  assert.match(source, /selectedId === item\.id[\s\S]*border-blue-300 bg-blue-50\/30/, "the selected row needs a subtle highlight");
});

test("feature request details use accessible desktop and modal mobile presentations", async () => {
  const source = await readFile(new URL("../app/components/FeatureRequestList.tsx", import.meta.url), "utf8");

  assert.match(source, /<aside[\s\S]*aria-labelledby=\{DETAILS_DESKTOP_TITLE_ID\}/, "desktop details need a labelled complementary landmark");
  assert.match(source, /<dialog[\s\S]*aria-labelledby=\{DETAILS_MOBILE_TITLE_ID\}/, "mobile details need a labelled native dialog");
  assert.doesNotMatch(source, /useId\(/, "detail labels must hydrate with page-stable ids");
  assert.match(source, /dialog\.showModal\(\)/, "the mobile sheet must make the page behind it inert");
  assert.match(source, /document\.body\.style\.overflow = "hidden"/, "the mobile sheet must block background scrolling");
  assert.match(source, /h-\[min\(85dvh,46rem\)\]/, "the mobile sheet needs a definite dynamic-viewport scroll boundary");
  assert.match(source, /safe-area-inset-bottom/, "the mobile sheet must clear the device safe area");
  assert.match(source, /onCancel=\{\(event\) => \{[\s\S]*event\.preventDefault\(\);[\s\S]*closeDetails\(\)/, "Escape must close the mobile dialog through its cancel event");
  assert.match(source, /!desktopQuery\.matches && dialog\?\.open[\s\S]*setSelectedId\(null\)/, "mobile Escape must not depend only on native cancel behavior");
  assert.match(source, /event\.key === "Escape"[\s\S]*setSelectedId\(null\)/, "Escape must close desktop details");
  assert.match(source, /detailTriggerRefs\.current\.get\(triggerId\)\?\.focus\(\)/, "closing must restore trigger focus");
  assert.match(source, /aria-label=\{`Close details for \$\{item\.title\}`\}/);
  assert.match(source, /document\.querySelector\('dialog\[open\], \[role="dialog"\]\[aria-modal="true"\]'\)/, "another active modal must own Escape");
  assert.match(source, /whitespace-pre-wrap break-words[^"]*\[overflow-wrap:anywhere\]/, "long detail content must wrap");
});

test("contribute skeleton rows mirror the issue rows they replace", async () => {
  const source = await readFile(new URL("../app/components/ContributeIssuesCard.tsx", import.meta.url), "utf8");
  const skeleton = source.slice(source.indexOf("{loading ? ("), source.indexOf(") : failed ?"));

  assert.match(skeleton, /min-h-16 items-center gap-3 px-5 py-3\.5/);
  assert.match(skeleton, /hidden shrink-0 gap-1\.5 md:flex/, "label blocks must be hidden below md, like the real labels");
  assert.match(skeleton, /lg:block/, "the assignee block must be hidden below lg");
  assert.match(skeleton, /sm:block/, "the comment-count block must be hidden below sm");
  assert.match(skeleton, /Loading issues…/);
});

test("step and rail icons are semantic and never duplicated", async () => {
  const contribute = await html("/contribute");

  const steps = contribute.slice(contribute.indexOf("<ol"), contribute.indexOf("</ol>"));
  const stepIcons = svgBodies(steps);
  assert.equal(stepIcons.length, 4, "each of the four steps needs its own icon");
  assert.equal(new Set(stepIcons).size, 4, "the four step icons must be distinct");

  const rail = contribute.slice(contribute.indexOf("Before you start"), contribute.indexOf("Open CONTRIBUTING.md"));
  const railIcons = svgBodies(rail);
  assert.equal(railIcons.length, 3, "each Before you start item needs its own icon");
  assert.equal(new Set(railIcons).size, 3, "the three rail icons must be distinct");

  const requests = await html("/feature-requests");
  const howItWorks = requests.slice(requests.indexOf("How ideas work"), requests.indexOf("Have a question?"));
  const howIcons = svgBodies(howItWorks);
  assert.equal(new Set(howIcons).size, 3, "the three How ideas work icons must be distinct");
  // The step number appears once, in the title — never again inside the well.
  assert.match(howItWorks, /rounded-full bg-blue-50 text-blue-600"><svg/);
  assert.doesNotMatch(howItWorks, /bg-blue-50 text-blue-600">1</);
  assert.match(howItWorks, /<h3[^>]*>1(?:<!-- -->)?\.\s*(?:<!-- -->)?Suggest<\/h3>/);
});

test("promotion and the GitHub token never reach a browser-facing route", async () => {
  const proxySource = await readFile(new URL("../app/browser-api/_proxy.ts", import.meta.url), "utf8");
  assert.doesNotMatch(proxySource, /x-alpha-operator/i);
  assert.doesNotMatch(proxySource, /GITHUB_TOKEN/);

  const idRouteSource = await readFile(
    new URL("../app/browser-api/feature-requests/[id]/route.ts", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(idRouteSource, /promote/);
});

test("header stays 72px and only the community pages request a sticky header", async () => {
  const home = await html("/");
  assert.doesNotMatch(home, /sticky top-0 z-30/);
  assert.match(home, /h-\[4\.5rem\]/);

  const featureRequests = await html("/feature-requests");
  assert.match(featureRequests, /sticky top-0 z-30/);
  assert.match(featureRequests, /h-\[4\.5rem\]/);

  const contribute = await html("/contribute");
  assert.match(contribute, /sticky top-0 z-30/);
});
