// Local QA against qa/recap_fixture.py. Isolated Chrome on debugging port 9312.
// Timers are real: 2200ms per action, 1040ms per flight. No time mocking.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const site = process.env.RECAP_SITE_URL ?? "http://localhost:3012";
const output = process.env.RECAP_SCREENSHOT_DIR ?? resolve(".wrangler/recap-screenshots");
await mkdir(output, { recursive: true });
const tabs = await fetch("http://localhost:9312/json/list").then(r => r.json());
const ws = new WebSocket(tabs.find(t => t.type === "page").webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener("open", r, { once: true }));
let id = 0;
const pending = new Map();
ws.addEventListener("message", event => {
  const result = JSON.parse(event.data);
  if (result.id) {
    const task = pending.get(result.id);
    pending.delete(result.id);
    if (result.error) task.reject(result.error); else task.resolve(result.result);
  }
});
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const messageId = ++id;
    pending.set(messageId, { resolve, reject });
    ws.send(JSON.stringify({ id: messageId, method, params }));
  });
}
async function evaluate(expression) {
  const result = await call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result.value;
}
const wait = ms => new Promise(r => setTimeout(r, ms));
async function until(expression, timeout = 20000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await wait(30);
  }
  throw new Error(`Timed out: ${expression}`);
}
async function click(selector) {
  await evaluate(`(async()=>{document.querySelector(${JSON.stringify(selector)}).click();await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame)})()`);
}
async function state() {
  return evaluate(`(()=>{const t=document.querySelector('.table-scene'),a=t.querySelector('.seat-active'),f=t.querySelector('.chip-flight');return {
    actor:t.dataset.actorSeat,active:[...t.querySelectorAll('.seat-active')].map(s=>Number(s.dataset.seat)),
    gold:[...t.querySelectorAll('.seat-winner')].map(s=>Number(s.dataset.seat)).sort(),goldResult:!!t.querySelector('.result-action'),
    action:t.querySelector('.table-action').textContent,phase:t.dataset.chipState,pot:t.querySelector('.pot').dataset.pot,
    flights:t.querySelectorAll('.chip-flight').length,ring:a?getComputedStyle(a).boxShadow:null,
    animation:f?getComputedStyle(f).animationName:null,position:f?f.getBoundingClientRect().y:null,
    wagers:[0,1].map(s=>{const v=t.querySelector('[data-wager-seat="'+s+'"]').dataset.wager;return v==='unknown'?null:Number(v)}),
    equity:[0,1].map(s=>{const v=t.querySelector('[data-seat="'+s+'"] .seat-equity').dataset.equity;return v==='unknown'?null:Number(v)}),
    method:t.querySelector('.seat-equity').dataset.method,
    sweepFlights:t.querySelectorAll('.chip-sweep').length,step:Number(t.dataset.stepIndex),hand:t.dataset.handId
  }})()`);
}
async function screenshot(name) {
  const image = await call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  await writeFile(`${output}/${name}.png`, Buffer.from(image.data, "base64"));
}
await call("Page.enable");
await call("Network.enable");
await call("Page.navigate", { url: site + "/rivals" });
await until("location.pathname === '/rivals' && document.readyState === 'complete'");
const status = await evaluate(`fetch('/browser-api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'blueriver',password:'local-recap-qa-only'})}).then(r=>r.status)`);
assert.equal(status, 200, "QA login failed");
await call("Page.navigate", { url: site + "/recaps/challenges/ch_recap_qa?hand=recap_qa_6" });
await until("!!document.querySelector('.table-scene')");
const recap = await evaluate("fetch('/browser-api/challenges/ch_recap_qa/recap').then(r=>r.json())");
const hand = recap.highlights.find(h => h.hand_id === "recap_qa_6");
const handIndex = recap.highlights.indexOf(hand);
const callStep = hand.steps.findIndex(s => s.action_kind === "call" && s.committed_amount > 0);
const sweepStep = hand.steps.findIndex(s => s.table_chips.phase === "sweep");
function assertActor(actual, step) {
  assert.equal(actual.actor, String(step.actor_seat ?? "none"));
  assert.deepEqual(actual.active, step.actor_seat == null ? [] : [step.actor_seat]);
  if (step.street !== "result") {
    assert.equal(actual.action, step.action_label);
    assert.deepEqual(actual.gold, []);
    assert.equal(actual.goldResult, false);
  }
  if (step.actor_seat != null) assert.notEqual(actual.ring, "none");
  assert.deepEqual(actual.equity,step.equity?.percentages ?? [null,null]);
  assert.equal(actual.method,step.equity?.method ?? "unavailable");
}
async function assertFinal(expected = hand) {
  const current = await state();
  assert.equal(current.hand, expected.hand_id);
  assert.equal(current.step, expected.steps.length - 1);
  assertActor(current, expected.steps.at(-1));
  assert.deepEqual(current.gold, expected.players.filter(p=>expected.winners.includes(p.username)).map(p=>p.seat).sort());
  assert.equal(current.goldResult, expected.winners.length > 0);
  assert.equal(current.pot, String(expected.pot));
  assert.equal(current.flights, 0);
  assert.deepEqual(current.wagers,[0,0]);
  const viewer = expected.players.find(p=>p.is_viewer) ?? expected.players[0];
  const summary = await evaluate("document.querySelector('.win-label').textContent");
  if (viewer.profit < 0) assert.ok(summary.includes("lost"));
  if (expected.winners.length === 2) assert.ok(summary.includes("Split pot"));
}
async function assertFlight(index) {
  const current = await state();
  assertActor(current, hand.steps[index]);
  assert.equal(current.step, index);
  assert.equal(current.phase, "flying");
  assert.equal(current.flights, 1);
  assert.equal(current.animation, "recap-chip-flight");
  assert.equal(current.pot, String(hand.steps[index].table_chips.gathered_before));
  assert.deepEqual(current.wagers,hand.steps[index].table_chips.wagers_before);
  return current;
}
async function assertSettled(index) {
  await until("document.querySelector('.table-scene').dataset.chipState === 'settled'");
  const current = await state();
  assertActor(current, hand.steps[index]);
  assert.equal(current.pot, String(hand.steps[index].table_chips.gathered_pot));
  assert.deepEqual(current.wagers,hand.steps[index].table_chips.wagers);
  assert.equal(current.flights, 0);
}
async function waitStep(index) {
  await until(`Number(document.querySelector('.table-scene').dataset.stepIndex) === ${index}`, 45000);
}
for (const [label, width, height] of [["desktop",1600,1000],["mobile",390,844]]) {
  await call("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor:1, mobile:false });
  await evaluate("document.fonts.ready");
  await assertFinal();
  const layout = await evaluate(`(()=>{const s=document.querySelector('.replay-sidebar'),t=document.querySelector('.replay-stage'),h=document.querySelector('h1');return {
    heading:h.textContent,context:document.querySelector('.match-context').textContent,
    controls:s.querySelectorAll('button').length,totalControls:document.querySelectorAll('.replay-page button').length,
    removed:document.querySelectorAll('.playback,.timeline,.recap-events,.action-summary,.sidebar-note,.table-foot').length,
    stageChildren:t.children.length,border:getComputedStyle(s).borderWidth,background:getComputedStyle(s).backgroundColor,
    width:innerWidth,scroll:document.documentElement.scrollWidth,controlBottom:s.querySelector('.hand-playback').getBoundingClientRect().bottom,
    titleBottom:h.getBoundingClientRect().bottom,tableTop:t.getBoundingClientRect().top,tableBottom:t.getBoundingClientRect().bottom
  }})()`);
  assert.equal(layout.heading,hand.label);
  assert.ok(layout.context.includes(`Hand ${hand.hand_number} of ${recap.total_hands}`));
  assert.ok(layout.context.includes(recap.players[0]) && layout.context.includes(recap.players[1]) && layout.context.includes("Direct challenge"));
  assert.equal(layout.controls,4); assert.equal(layout.totalControls,4);
  assert.equal(layout.removed,0); assert.equal(layout.stageChildren,1);
  assert.equal(layout.border,"0px"); assert.equal(layout.background,"rgba(0, 0, 0, 0)");
  assert.equal(layout.width,layout.scroll); assert.ok(layout.controlBottom <= height);
  assert.ok(layout.titleBottom < layout.tableTop);
  if (label === "mobile") { assert.ok(layout.controlBottom < layout.tableTop); assert.ok(layout.tableBottom <= height); }
  assert.equal(await evaluate(`(()=>{const badge=document.querySelector('.bottom-seat .seat-result'),cards=document.querySelector('.hero-cards');if(!badge)return true;const b=badge.getBoundingClientRect(),c=cards.getBoundingClientRect();return b.left>=c.right||b.top>=c.bottom||b.right<=c.left||b.bottom<=c.top})()`),true,"Winner badge must not cover hole cards");
  await screenshot(`codex-recap-wagers-result-${label}`);
  await click('[aria-label="Previous highlight"]');
  await assertFinal(recap.highlights[handIndex - 1]);
  assert.equal(await evaluate("document.querySelector('h1').textContent"), recap.highlights[handIndex - 1].label);
  await click('[aria-label="Next highlight"]');
  await assertFinal();
  assert.equal(await evaluate("location.search.includes('hand=recap_qa_6')"),true);
  // Replay starts the full hand at step 1, with cobalt replacing gold.
  await click('.replay-button');
  await assertFlight(0);
  await wait(1200);
  await click('.replay-button');
  await assertFlight(0);
  await wait(1200);
  assert.equal((await state()).step,0,"Replay on step 1 must reset the full action interval");
  await click('.play-button');
  await assertSettled(0);
  await wait(2300);
  assert.equal((await state()).step,0,"Pause must stop progression");
  await click('.play-button');
  await waitStep(1);
  await assertFlight(1); // other physical actor, including mirrored seats
  await waitStep(callStep);
  await click('.play-button');
  const start = await assertFlight(callStep);
  await wait(150);
  assert.notEqual((await state()).position,start.position);
  await screenshot(`codex-recap-wagers-action-${label}`);
  await assertSettled(callStep);
  const preflopEquity = (await state()).equity;
  await click('.play-button');
  await waitStep(sweepStep);
  await click('.play-button');
  const sweep = await state();
  assertActor(sweep,hand.steps[sweepStep]);
  assert.equal(sweep.phase,"sweeping");
  assert.equal(sweep.sweepFlights,2);
  assert.equal(sweep.pot,String(hand.steps[sweepStep].table_chips.gathered_before));
  assert.deepEqual(sweep.wagers,hand.steps[sweepStep].table_chips.wagers_before);
  await wait(150);
  await screenshot(`codex-recap-wagers-sweep-${label}`);
  await assertSettled(sweepStep);
  assert.deepEqual((await state()).wagers,[0,0]);
  await click('.play-button');
  await waitStep(sweepStep + 1);
  await click('.play-button');
  const flop = await state();
  assertActor(flop,hand.steps[sweepStep + 1]);
  assert.equal(flop.method,"exact");
  assert.notDeepEqual(flop.equity,preflopEquity,"Board arrival must update odds");
  // Restart partway through, then cancel mid-flight with a highlight change.
  await click('.replay-button');
  await assertFlight(0);
  await click('[aria-label="Next highlight"]');
  await wait(2300);
  await assertFinal(recap.highlights[handIndex + 1]); // real viewer loss
  await click('[aria-label="Previous highlight"]');
  await assertFinal();
  await click('.replay-button');
  await assertFlight(0);
  await call("Emulation.setEmulatedMedia",{features:[{name:"prefers-reduced-motion",value:"reduce"}]});
  await click('.play-button');
  await assertSettled(0);
  await click('.replay-button');
  await assertSettled(0);
  // Reduced motion also gathers both wagers immediately, without a flight.
  await waitStep(sweepStep);
  await assertSettled(sweepStep);
  assert.deepEqual((await state()).wagers,[0,0]);
  await click('.play-button');
  await call("Emulation.setEmulatedMedia",{features:[]});
  // Complete the unmodified cadence, checking every action/neutral state.
  await click('.replay-button');
  for (let index=0; index<hand.steps.length; index++) {
    await waitStep(index);
    assertActor(await state(),hand.steps[index]);
  }
  await assertFinal();
  await until("document.querySelector('.play-button').textContent.includes('Play')");
  console.log(`${label}: sidebar-only controls; Replay/Play/Pause; wager payments and street sweeps; exact/estimated odds; full 2200ms cadence; final-only gold; reduced motion; no overflow`);
}
await call("Network.clearBrowserCookies");
await call("Page.reload");
await until("document.body?.innerText.includes('Sign in to view this recap')");
console.log("Signed-out private state clearing verified.");
ws.close();
