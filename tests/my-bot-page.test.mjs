import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(path) {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${path}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${path}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) },
    },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

const workspaceSource = () =>
  readFile(
    new URL("../app/components/mybot/MyBotWorkspace.tsx", import.meta.url),
    "utf8",
  );

test("/my-bot is a real route, not a dialog", async () => {
  const response = await render("/my-bot");
  assert.equal(response.status, 200);

  const body = await response.text();
  assert.match(body, /<title>My Bot — Alpha Poker<\/title>/);
  assert.match(body, /MY BOT/);
  // The session is unknown until the browser checks it, so the server paints
  // the calm loading plate rather than guessing at a bot.
  assert.match(body, /Dealing you in…/);
  assert.match(body, /data-testid="account-trigger"/);

  const page = await readFile(
    new URL("../app/my-bot/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(page, /<AppHeader currentPath="\/my-bot" \/>/);
  assert.match(page, /<MyBotWorkspace \/>/);
});

test("the empty state offers the starter kit and the agent instructions", async () => {
  const source = await workspaceSource();

  assert.match(source, /Your seat is open/);
  assert.match(source, /Download starter kit/);
  assert.match(source, /label="Copy agent instructions"/);
  assert.match(source, /href=\{`\/\$\{STARTER_KIT_FILENAME\}`\}/);
  assert.match(source, /text=\{BUILD_BOT_PROMPT\}/);
  // One identity slot renders in both states: the dashed empty seat and the
  // portrait that replaces it.
  assert.match(source, /border-dashed border-blue-200/);
  assert.match(source, /<BotAvatar name=\{submission\.bot_name\}/);
});

test("the submitted state stays on facts /browser-api/account/status returns", async () => {
  const source = await workspaceSource();

  assert.match(source, /"\/browser-api\/account\/status"/);
  assert.match(source, /\{submission\.bot_name\}/);
  assert.match(source, /STATUS_LABEL\[chip\]/);
  assert.match(source, /label="ELO"/);
  assert.match(source, /label="W–L"/);
  assert.match(source, /label="RANK"/);
  assert.match(source, /result\.elo_rating\.toLocaleString\(\)/);
  assert.match(source, /\$\{record\.wins\}–\$\{record\.losses\}/);
  assert.match(
    source,
    /\/browser-api\/runs\/\$\{encodeURIComponent\(result\.id\)\}\/artifacts/,
  );
  assert.match(
    source,
    /\/browser-api\/submissions\/\$\{encodeURIComponent\(submission\.submission_id\)\}\/logs/,
  );

  // The page reports; it never offers an automatic "improve my bot" action.
  assert.doesNotMatch(source, /Improve/i);
});

test("the page renders exactly one of loading, signed-out, error, or bot", async () => {
  const source = await workspaceSource();

  assert.match(
    source,
    /if \(!loaded \|\| \(session && visibleState\.loading && !visibleStatus\)\)/,
  );
  assert.match(source, /if \(!session\) \{/);
  assert.match(source, /if \(!visibleStatus\) \{/);
  assert.match(source, /Sign in to see your bot/);
  assert.match(source, /emit\("open-account", \{\}\)/);
  assert.match(source, /onClick=\{\(\) => void refresh\(session\.username\)\}[\s\S]{0,320}Retry/);
  // Polling stops once the submission reaches a resting state.
  assert.match(source, /function isSettled/);
  assert.match(source, /loadState\.owner === session\.username/);
  assert.match(source, /if \(!session \|\| isSettled\(visibleStatus\)\) return;/);
});

test("the starter kit filename and agent prompt have a single definition", async () => {
  const [landing, prompt] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/components/agentPrompt.ts", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(prompt, /export const STARTER_KIT_FILENAME = /);
  assert.match(prompt, /export const BUILD_BOT_PROMPT = /);
  assert.match(
    landing,
    /import \{ BUILD_BOT_PROMPT, STARTER_KIT_FILENAME \} from "\.\/components\/agentPrompt"/,
  );
  assert.doesNotMatch(landing, /^const BUILD_BOT_PROMPT/m);
  assert.doesNotMatch(landing, /^const STARTER_KIT_FILENAME/m);
});

test("the shared agent prompt opens with a choice-driven rookie experience", async () => {
  const prompt = await readFile(
    new URL("../app/components/agentPrompt.ts", import.meta.url),
    "utf8",
  );

  for (const capability of [
    "Build a bot",
    "Train",
    "Compete",
    "Challenge someone",
    "Review hands",
    "Check progress",
  ]) {
    assert.match(prompt, new RegExp(capability));
  }
  assert.match(prompt, /Changes your Elo\?/);
  assert.match(prompt, /Fetch the current public leaderboard/);
  assert.match(prompt, /top three/);
  assert.match(prompt, /rank, bot, player, Elo/);
  assert.match(prompt, /Think your bot can knock one of them off the podium\?/);
  assert.match(prompt, /Build my first bot/);
  assert.match(prompt, /Create, Build, Practice, and Compete/);
  assert.match(prompt, /Stop and wait for my choice/);
  assert.match(prompt, /explicit approval immediately before submitting/);
  assert.match(prompt, /Never invent standings/);
  assert.doesNotMatch(prompt, /First, give me a short overview of every available workflow/);
});

test("the copy control reports both success and failure", async () => {
  const source = await readFile(
    new URL("../app/components/CopyPromptButton.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /navigator\.clipboard\.writeText\(text\)/);
  assert.match(source, /document\.execCommand\("copy"\)/);
  assert.match(source, /Copy failed\. Try again/);
  assert.match(source, /Could not copy the prompt\. Try again\./);
  assert.match(source, /Prompt copied to clipboard/);
});
