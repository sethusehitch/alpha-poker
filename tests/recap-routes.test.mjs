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

test("recap playback uses recorded actor/payment metadata and isolated step presentations", async () => {
  const component = await readFile(new URL("../app/components/recaps/MatchRecap.tsx", import.meta.url), "utf8");
  const css = await readFile(new URL("../app/components/recaps/recap.css", import.meta.url), "utf8");
  const types = await readFile(new URL("../app/components/recaps/types.ts", import.meta.url), "utf8");
  assert.match(component, /key=\{`\$\{hand.hand_id\}:\$\{stepIndex\}:\$\{visit\}`\}/);
  assert.match(component, /aria-label="Previous action".*selectStep\(stepIndex - 1\)/);
  assert.match(component, /aria-label="Next action".*selectStep\(stepIndex \+ 1\)/);
  assert.match(component, /actor === top.seat \? "seat-active"/);
  assert.match(component, /actor === bottom.seat \? "seat-active"/);
  assert.match(component, /flying \? step.pot_before : step.pot/);
  assert.match(component, /onAnimationEnd=.*setArrived\(true\)/);
  assert.match(component, /matchMedia\("\(prefers-reduced-motion: reduce\)"\)/);
  assert.match(component, /motion.removeEventListener/);
  assert.match(component, /window.clearTimeout\(timer\)/);
  assert.match(component, /const STEP_INTERVAL_MS = 2200/);
  assert.match(css, /recap-chip-flight 1040ms/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /\.seat\.seat-active/);
  for (const field of ["actor_seat", "action_kind", "committed_amount", "pot_before", "action_label"]) assert.ok(types.includes(`${field}?:`));
});
