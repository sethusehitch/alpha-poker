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
    await new Promise(r => setTimeout(r, 300));
  }
  throw new Error(`Timed out: ${expression}`);
}
await call("Page.enable");
await call("Network.enable");
await call("Page.navigate", { url: site + "/rivals" });
await until("document.readyState === 'complete'");
const status = await evaluate(`fetch('/browser-api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'blueriver',password:'local-recap-qa-only'})}).then(r=>r.status)`);
assert.equal(status, 200, "QA login failed");
await call("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
await call("Page.navigate", { url: site + "/recaps/challenges/ch_recap_qa?hand=recap_qa_6" });
await until("document.querySelector('.board .playing-card') && document.body.innerText.includes('ace-high straight')");
assert.equal(await evaluate("document.querySelector('.win-label').innerText.includes('+840')"), true);
assert.equal(await evaluate("document.querySelector('.pot').innerText.includes('1,680')"), true);
await evaluate("document.querySelector('.playback-buttons button').click()");
assert.equal(await evaluate("location.search.includes('hand=recap_qa_6')"), false);
await evaluate("document.querySelector('.playback-buttons button:last-child').click()");
assert.equal(await evaluate("location.search.includes('hand=recap_qa_6')"), true);
await evaluate("document.querySelector('.play-button').click()");
await until("document.querySelector('.play-button').innerText.includes('Pause')");
assert.equal(await evaluate("document.querySelectorAll('.board .playing-card').length"), 0);
await evaluate("document.querySelector('.play-button').click(); document.querySelector('.recap-events li:last-child button').click()");
await until("document.querySelectorAll('.board .playing-card').length === 5");
for (const [label, width, height] of [["desktop", 1600, 1000], ["mobile", 390, 844]]) {
  await call("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
  await evaluate("document.fonts.ready");
  await new Promise(r => setTimeout(r, 600));
  const geometry = await evaluate("({width:innerWidth,scroll:document.documentElement.scrollWidth,controls:document.querySelector('.playback').getBoundingClientRect().bottom})");
  assert.equal(geometry.width, geometry.scroll, `${label} has horizontal overflow`);
  assert.ok(geometry.controls <= height, `${label} controls are outside the viewport`);
  const image = await call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  await writeFile(`${output}/codex-recap-light-${label}.png`, Buffer.from(image.data, "base64"));
  console.log(`${label}: ${width}x${height}, no horizontal overflow, controls visible`);
}
await call("Network.clearBrowserCookies");
await call("Page.reload");
await until("document.body.innerText.includes('Sign in to view this recap')");
console.log("Private recap clears after sign-out. Previous / Play / Pause / Next verified.");
ws.close();
