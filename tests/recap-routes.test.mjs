import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("both stable recap routes server-render loading and the real navigation shell", async () => {
  const { default: worker } = await import("../dist/server/index.js");
  for (const path of ["/recaps/challenges/ch_123", "/recaps/runs/run_123/matches/match_456"]) {
    const response = await worker.fetch(new Request(`http://localhost${path}`, { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
    assert.equal(response.status, 200);
    const html = await response.text();
    assert.match(html, /Loading recap/);
    assert.match(html, /Alpha Poker home/);
    assert.doesNotMatch(html, /BlueRiver|RedAce|seth-preview/);
  }
});

test("discovery links use stable exact challenge and pairing IDs", async () => {
  const read = path => readFile(new URL(`../${path}`, import.meta.url), "utf8");
  const [rivals, header, standings, matches, challengeProxy, pairingProxy] = await Promise.all([
    read("app/components/rivals/RivalsWorkspace.tsx"), read("app/components/app/AppHeader.tsx"),
    read("app/components/leaderboard/StandingsWorkspace.tsx"), read("app/components/recaps/RoundRobinRecaps.tsx"),
    read("app/browser-api/challenges/[id]/recap/route.ts"), read("app/browser-api/runs/[runId]/matchups/[matchupId]/recap/route.ts"),
  ]);
  assert.match(rivals, /\/recaps\/challenges\/\$\{encodeURIComponent\(challenge.challenge_id\)\}/);
  assert.match(header, /\/recaps\/challenges\/\$\{encodeURIComponent\(challenge.challenge_id\)\}/);
  assert.match(standings, /RoundRobinRecaps runId=\{board.run_id\}/);
  assert.match(matches, /encodeURIComponent\(runId\).*encodeURIComponent\(match.matchup_id\)/);
  assert.match(challengeProxy, /proxyApi\(request/);
  assert.match(pairingProxy, /proxyApi\(request/);
});
