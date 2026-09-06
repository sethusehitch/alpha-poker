import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

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
    /session \? \[LEADERBOARD, RIVALS\] : \[LEADERBOARD\]/,
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
  assert.match(appHeader, /id="app-mobile-menu"[\s\S]*?<button[\s\S]*?My Bot/);
  assert.doesNotMatch(appHeader, /href="\/account"/);
});
