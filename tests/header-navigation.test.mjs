import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("dojo shares opponent surfaces and keeps leader training out of its cards", async () => {
  const dojo = await readFile(new URL("../app/components/training/DojoWorkspace.tsx", import.meta.url), "utf8");
  const catalog = JSON.parse(await readFile(new URL("../server/alpha_poker/dojo_catalog.json", import.meta.url), "utf8"));
  const workflow = await readFile(new URL("../starter-kit/WORKFLOWS.md", import.meta.url), "utf8");
  assert.equal(catalog.bots.length, 5);
  assert.ok(catalog.bots.every(bot => Number.isInteger(bot.rating) && bot.id !== "leader"));
  assert.deepEqual(catalog.bots.map(bot => bot.rating), catalog.bots.map(bot => bot.rating).sort((a,b) => a-b));
  assert.match(dojo, /OpponentCardSurface/);
  assert.match(dojo, /OPPONENT_PANEL/);
  assert.match(dojo, /Copy training prompt/);
  assert.match(dojo, /self-reported local practice/);
  assert.match(workflow, /leader always runs on the server over WebSocket/);
  assert.match(workflow, /only after approval/);
});

test("community navigation is signed-in-only and grouped in one menu", async () => {
  const [siteHeader, appHeader] = await Promise.all([
    readFile(
      new URL("../app/components/SiteHeader.tsx", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../app/components/app/AppHeader.tsx", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(siteHeader, /useSession/);
  assert.match(
    siteHeader,
    /\? \[GETTING_STARTED, LEADERBOARD, MY_BOT, TRAINING, RIVALS\]\s*: \[GETTING_STARTED, LEADERBOARD\]/,
  );
  assert.match(siteHeader, /\{session && \(/);
  assert.match(siteHeader, /Community <ChevronIcon/);
  assert.match(siteHeader, /COMMUNITY_ITEMS/);
  assert.match(siteHeader, /event\.key !== "Escape"/);
  assert.match(siteHeader, /communityRef\.current\?\.contains/);
  assert.match(appHeader, /useSession/);
  assert.match(appHeader, /session && \(/);
  assert.match(appHeader, />\s*Community/);
  assert.match(appHeader, /setCommunityOpen\(false\)/);
  assert.match(appHeader, /event\.key === "Escape"/);
  assert.match(appHeader, /app-mobile-menu/);
  assert.match(appHeader, /if \(!session\)/);
  assert.match(appHeader, /ref=\{appMenuToggleRef\}/);
  assert.match(appHeader, /id="app-mobile-menu"[\s\S]*?APP_NAV\.map/);
  assert.doesNotMatch(appHeader, /href="\/account"/);
});

test("the app header uses the requested core-game order and real routes", async () => {
  const appHeader = await readFile(
    new URL("../app/components/app/AppHeader.tsx", import.meta.url),
    "utf8",
  );

  // "My Bot" used to open the account dialog; it is a page now.
  assert.match(appHeader, /label: "My Bot",\s*href: "\/my-bot"/);
  assert.doesNotMatch(appHeader, /emit\("open-account"/);
  assert.match(appHeader, /label: "Getting Started",\s*href: "\/#instructions"/);
  assert.match(appHeader, /label: "Training",\s*href: "\/training"/);
  assert.match(appHeader, /label: "Rivals",\s*href: "\/rivals"/);
  assert.match(appHeader, /label: "Leaderboard",\s*href: "\/leaderboard"/);
  const navModel = appHeader.match(/const APP_NAV[\s\S]*?\n\];/)?.[0] ?? "";
  assert.ok(navModel.indexOf('label: "Getting Started"') < navModel.indexOf('label: "Leaderboard"'));
  assert.ok(navModel.indexOf('label: "Leaderboard"') < navModel.indexOf('label: "My Bot"'));
  assert.ok(navModel.indexOf('label: "My Bot"') < navModel.indexOf('label: "Rivals"'));

  // Community stays in its own separated menu, not in APP_NAV.
  assert.doesNotMatch(navModel, /Community/);
  assert.match(appHeader, /border-l border-zinc-200 pl-2/);

  // One nav model, one source of truth for the active underline.
  assert.match(appHeader, /export function AppHeader\(\{ currentPath \}/);
  assert.match(
    appHeader,
    /isActive: \(path\) => path\.startsWith\("\/my-bot"\)/,
  );
  assert.match(
    appHeader,
    /isActive: \(path\) => path\.startsWith\("\/leaderboard"\)/,
  );
  assert.match(
    appHeader,
    /isActive: \(path\) =>\s*path\.startsWith\("\/rivals"\) \|\| path\.startsWith\("\/hands\/"\)/,
  );
  assert.doesNotMatch(appHeader, /aria-current="page"\s*$/m);
  assert.match(appHeader, /const active = item\.isActive\(currentPath\)/);
});

test("every app surface tells the header which route it is on", async () => {
  const [rivals, hands, myBot, leaderboard] = await Promise.all([
    readFile(new URL("../app/rivals/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/hands/[hand_id]/page.tsx", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../app/my-bot/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/leaderboard/page.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(rivals, /<AppHeader currentPath="\/rivals" \/>/);
  assert.match(hands, /<AppHeader currentPath="\/hands\/" \/>/);
  assert.match(myBot, /<AppHeader currentPath="\/my-bot" \/>/);
  assert.match(leaderboard, /<AppHeader currentPath="\/leaderboard" \/>/);
});
