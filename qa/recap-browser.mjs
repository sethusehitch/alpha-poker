// Local browser QA against qa/recap_fixture.py. Uses an isolated Chrome profile.
// Start Chrome with --headless=new --remote-debugging-port=9312 and a profile
// beneath .wrangler, then run node qa/recap-browser.mjs. No tokens are printed.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const site = process.env.RECAP_SITE_URL ?? "http://localhost:3012";
const output = process.env.RECAP_SCREENSHOT_DIR ?? resolve(".wrangler/recap-screenshots");
await mkdir(output, { recursive: true });
const tabs = await fetch("http://localhost:9312/json/list").then(r => r.json());
const tab = tabs.find(t => t.type === "page");
const ws = new WebSocket(tab.webSocketDebuggerUrl);
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
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}
async function until(expression) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await new Promise(r => setTimeout(r, 30));
  }
  throw new Error(`Timed out: ${expression}`);
}
await call("Page.enable");
await call("Network.enable");
await call("Page.navigate", { url: site + "/rivals" });
await until("location.pathname === '/rivals' && document.readyState === 'complete'");
const status = await evaluate(`fetch('/browser-api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'blueriver',password:'local-recap-qa-only'})}).then(r=>r.status)`);
assert.equal(status, 200, "QA login failed");
await call("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
await call("Page.navigate", { url: site + "/recaps/challenges/ch_recap_qa?hand=recap_qa_6" });
await until("document.querySelector('.board .playing-card') && document.body.innerText.includes('ace-high straight')");
assert.equal(await evaluate("document.querySelector('.win-label').innerText.includes('+840')"), true);
assert.equal(await evaluate("document.querySelector('.pot').innerText.includes('1,680')"), true);
const recap = await evaluate("fetch('/browser-api/challenges/ch_recap_qa/recap').then(r=>r.json())");
const hand = recap.highlights.find(h => h.hand_id === "recap_qa_6");
const handIndex = recap.highlights.indexOf(hand);
const firstPayment = hand.steps.findIndex(s => s.committed_amount > 0);
const callStep = hand.steps.findIndex(s => s.action_kind === "call" && s.committed_amount > 0);
const checkStep = hand.steps.findLastIndex(s => s.action_kind === "check");
const boardStep = hand.steps.findIndex(s => !s.actor_seat && s.action_kind === null && s.street === "flop");
const wait = ms => new Promise(r => setTimeout(r, ms));
async function click(selector) {
  await evaluate(`(async()=>{document.querySelector(${JSON.stringify(selector)}).click();await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame)})()`);
}
const selectStep = index => click(`.recap-events li:nth-child(${index + 1}) button`);
const selectHand = index => click(`.timeline button:nth-child(${index + 1})`);
async function state() {
  return evaluate(`(()=>{const t=document.querySelector('.table-scene'),a=t.querySelector('.seat-active'),f=t.querySelector('.chip-flight');return {
    actor:t.dataset.actorSeat,active:[...t.querySelectorAll('.seat-active')].map(s=>Number(s.dataset.seat)),
    action:t.querySelector('.table-action').textContent,phase:t.dataset.chipState,pot:t.querySelector('.pot').dataset.pot,
    flights:t.querySelectorAll('.chip-flight').length,ring:a?getComputedStyle(a).boxShadow:null,
    animation:f?getComputedStyle(f).animationName:null,position:f?f.getBoundingClientRect().y:null,
    destination:!!t.querySelector('.chip-arrived'),step:[...document.querySelectorAll('.recap-events li button')].findIndex(b=>b.getAttribute('aria-current')==='step')
  }})()`);
}
function assertActor(actual, step) {
  assert.equal(actual.actor, String(step.actor_seat ?? "none"));
  assert.deepEqual(actual.active, step.actor_seat == null ? [] : [step.actor_seat]);
  assert.equal(actual.action, step.street === "result" ? "Hand complete" : step.action_label);
  if (step.actor_seat != null) assert.notEqual(actual.ring, "none");
}
async function assertFlight(index) {
  const current = await state();
  assertActor(current, hand.steps[index]);
  assert.equal(current.step, index);
  assert.equal(current.phase, "flying");
  assert.equal(current.flights, 1);
  assert.equal(current.animation, "recap-chip-flight");
  assert.equal(current.pot, String(hand.steps[index].pot_before));
  return current;
}
async function assertSettled(index) {
  await until("document.querySelector('.table-scene').dataset.chipState === 'settled'");
  const current = await state();
  assertActor(current, hand.steps[index]);
  assert.equal(current.pot, String(hand.steps[index].pot));
  assert.equal(current.flights, 0);
  assert.equal(current.destination, true);
}
async function screenshot(name) {
  const image = await call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  await writeFile(`${output}/${name}.png`, Buffer.from(image.data, "base64"));
}
for (const [label, width, height] of [["desktop", 1600, 1000], ["mobile", 390, 844]]) {
  await call("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
  await evaluate("document.fonts.ready");
  await selectStep(hand.steps.length - 1);
  assertActor(await state(), hand.steps.at(-1));
  // Play and manual stepping visit identical recorded states. Pausing during a
  // flight lets that single payment settle, without scheduling another action.
  await click(".play-button");
  await assertFlight(firstPayment);
  await click(".play-button");
  await assertSettled(firstPayment);
  await wait(1150);
  assert.equal((await state()).step, firstPayment);
  await click('[aria-label="Next action"]');
  await assertFlight(firstPayment + 1);
  await assertSettled(firstPayment + 1);
  await click('[aria-label="Previous action"]');
  await assertFlight(firstPayment);
  await assertSettled(firstPayment);
  await click(".play-button");
  await until("document.querySelectorAll('.recap-events li button')[1].getAttribute('aria-current') === 'step'");
  await assertFlight(firstPayment + 1);
  await click(".play-button");
  await assertSettled(firstPayment + 1);
  // Neutral board steps and player checks never fly chips.
  for (const index of [boardStep, checkStep]) {
    await selectStep(index);
    const current = await state();
    assertActor(current, hand.steps[index]);
    assert.equal(current.phase, "none");
    assert.equal(current.flights, 0);
    assert.equal(current.pot, String(hand.steps[index].pot));
  }
  await screenshot(`codex-recap-actions-${label}`);
  // Back/forward replay of a paid raise/call, sampled in flight.
  await selectStep(callStep - 1);
  await click('[aria-label="Next action"]');
  const start = await assertFlight(callStep);
  await wait(100);
  const moving = await state();
  assert.notEqual(moving.position, start.position, "chip must travel toward the pot");
  await screenshot(`codex-recap-chip-flight-${label}`);
  await assertSettled(callStep);
  await click('[aria-label="Previous action"]');
  await assertFlight(callStep - 1);
  await click('[aria-label="Next action"]');
  await assertFlight(callStep);
  // Switching highlights cancels the old presentation even mid-flight.
  await selectHand(0);
  await wait(1200);
  const switched = await state();
  assertActor(switched, recap.highlights[0].steps.at(-1));
  assert.equal(switched.flights, 0);
  assert.equal(switched.pot, String(recap.highlights[0].pot));
  await selectHand(handIndex);
  assert.equal(await evaluate("location.search.includes('hand=recap_qa_6')"), true);
  // Motion preference changes during a flight settle immediately, and future
  // steps show the destination without ever mounting a flight.
  await selectStep(callStep);
  await assertFlight(callStep);
  await call("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
  await assertSettled(callStep);
  await selectStep(firstPayment);
  await assertSettled(firstPayment);
  await selectStep(callStep);
  await assertSettled(callStep);
  await screenshot(`codex-recap-reduced-motion-${label}`);
  await call("Emulation.setEmulatedMedia", { features: [] });
  await selectStep(hand.steps.length - 1);
  assertActor(await state(), hand.steps.at(-1));
  const geometry = await evaluate("({width:innerWidth,scroll:document.documentElement.scrollWidth,controls:document.querySelector('.playback').getBoundingClientRect().bottom})");
  assert.equal(geometry.width, geometry.scroll, `${label} has horizontal overflow`);
  assert.ok(geometry.controls <= height, `${label} controls are outside the viewport`);
  await screenshot(`codex-recap-actions-result-${label}`);
  console.log(`${label}: ${width}x${height}; actors, chip movement, synchronized pots, manual/Play/Pause, cancelled flights, reduced motion, neutral results, no overflow, controls visible`);
}
await call("Network.clearBrowserCookies");
await call("Page.reload");
await until("document.body?.innerText.includes('Sign in to view this recap')");
console.log("Private recap clears after sign-out. Previous / Play / Pause / Next verified.");
ws.close();
