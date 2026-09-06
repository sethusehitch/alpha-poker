import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("the dedicated leaderboard shows the top five and an out-of-cut viewer", async () => {
  const [page, workspace, proxy, api] = await Promise.all([
    readFile(new URL("../app/leaderboard/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/components/leaderboard/StandingsWorkspace.tsx", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../app/browser-api/leaderboard/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/components/rivals/api.ts", import.meta.url), "utf8"),
  ]);

  assert.match(page, /<AppHeader currentPath="\/leaderboard" \/>/);
  assert.match(page, /<StandingsWorkspace \/>/);
  assert.match(proxy, /proxyApi\(request, "leaderboard"\)/);
  assert.match(api, /top_entries/);
  assert.match(api, /viewer_entry/);
  assert.match(workspace, /const TOP_COUNT = 5/);
  assert.match(workspace, /entries\.slice\(0, TOP_COUNT\)/);
  assert.match(workspace, /data-standings-separator="true"/);
  assert.match(workspace, /<StandingRow entry=\{viewerEntry\} you \/>/);
  assert.match(workspace, /data-viewer-row=\{you \? "true" : undefined\}/);
});

test("Rivals no longer treats leaderboard as an internal tab", async () => {
  const [page, workspace] = await Promise.all([
    readFile(new URL("../app/rivals/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/components/rivals/RivalsWorkspace.tsx", import.meta.url),
      "utf8",
    ),
  ]);

  assert.doesNotMatch(page, /params\.tab === "leaderboard"/);
  assert.doesNotMatch(workspace, /type Tab = [^\n]*leaderboard/);
  assert.doesNotMatch(workspace, /League records/);
});
