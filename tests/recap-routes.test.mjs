import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import ts from "typescript";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

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

test("highlight heading and all controls are above or beside the table, without duplicate controls", async () => {
  const source = await readFile(new URL("../app/components/recaps/MatchRecap.tsx", import.meta.url), "utf8");
  const css = await readFile(new URL("../app/components/recaps/recap.css", import.meta.url), "utf8");
  assert.match(source, /<h1>\{hand.label\}<\/h1>/);
  assert.match(source, /Hand \{hand.hand_number\} of \{data.total_hands\}/);
  const sidebar = source.match(/<aside[\s\S]*?<\/aside>/)[0];
  for (const control of ["Previous highlight", "Next highlight", "replay-button", "play-button"]) assert.ok(sidebar.includes(control));
  const tableSection = source.match(/<section className="replay-stage"[\s\S]*?<\/section>/)[0];
  assert.doesNotMatch(tableSection, /<button|<details|action-summary|timeline|playback/);
  assert.doesNotMatch(source, /className="(?:playback|timeline|recap-events|action-summary|sidebar-note|table-foot)"/);
  assert.match(source, /function replayHand\(\) \{\s*setPlaying\(true\);\s*setStepIndex\(0\);\s*setVisit/);
  assert.ok(source.includes('[playing, hand, stepIndex, visit]'), "Replay visit resets the action timer even on the same step");
  assert.doesNotMatch(css.match(/\.replay-sidebar \{[^}]+/)[0], /border|background|radius/);
});

test("recorded winner, loss, split, unknown and action states render honest gold accents", async () => {
  // Execute the actual view component with only its avatar/session leaf imports
  // stubbed. No duplicate result renderer or gold-state helper in this test.
  let source = await readFile(new URL("../app/components/recaps/MatchRecap.tsx", import.meta.url), "utf8");
  source = source.replace(/import \{ BotAvatar \}[^;]+;/, 'const BotAvatar = () => null;')
    .replace(/import \{ AlphaPokerMark \}[^;]+;/, 'const AlphaPokerMark = () => null;')
    .replace(/import \{ useSession \}[^;]+;/, 'const useSession = () => ({session:null, loaded:true});')
    .replace('import "./recap.css";', '');
  let code = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  const require = createRequire(import.meta.url);
  code = code.replace(/from "(react(?:\/jsx-runtime)?)"/g, (_, name) => `from "${pathToFileURL(require.resolve(name))}"`);
  const { RecapView } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
  for (const [winners, street, actor, expected] of [
    [["alice"], "result", null, [0]], [["bob"], "result", null, [1]],
    [["alice", "bob"], "result", null, [0, 1]], [[], "result", null, []],
    [["alice"], "preflop", 1, []], [["alice"], "flop", null, []],
  ]) {
    const hand = { hand_id:"h", hand_number:6, label:"Largest single-hand swing", labels:[], dealer:0,
      winners, outcome:winners.length === 2 ? "Split pot" : winners.length ? `${winners[0]} wins after a fold` : "Result details unavailable",
      players:["alice","bob"].map((username,seat)=>({username,seat,is_viewer:seat===0,starting_stack:100,final_stack:100,profit:0,hole_cards:[]})),
      steps:[{street,actor_seat:actor,action_kind:actor===null?null:"check",committed_amount:0,summary:"bob checks",action_label:"bob checks",board:[],hole_cards:[[],[]],pot:20,stacks:[90,90]}] };
    const data = { source:"direct_challenge",players:["alice","bob"],highlights:[hand],total_hands:8,complete_history:true };
    const html = renderToStaticMarkup(createElement(RecapView,{data}));
    const goldSeats = [...html.matchAll(/data-seat="(\d)" class="[^"]*seat-winner/g)].map(match=>Number(match[1])).sort();
    assert.deepEqual(goldSeats, expected);
    assert.equal(html.includes("result-action"), expected.length > 0);
    if (winners.length === 2 && street === "result") assert.match(html, />Split pot</);
    if (actor !== null) assert.match(html, /data-seat="1" class="[^"]*seat-active/);
    assert.equal((html.match(/class="replay-button"/g)??[]).length,1);
  }
});
