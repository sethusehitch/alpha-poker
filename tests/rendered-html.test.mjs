import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const templateRoot = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the Alpha Poker landing page", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Alpha Poker/i);
  assert.match(html, /Build a poker bot\./);
  // The mobile headline scales with the viewport so both written lines stay on
  // one line each instead of stacking into four words-per-line rows.
  assert.match(
    html,
    /text-\[clamp\(1\.75rem,8\.6vw,2\.75rem\)\].*sm:text-\[clamp\(3\.35rem,6\.2vw,6\.5rem\)\]/,
  );
  assert.match(html, /<span class="block whitespace-nowrap">Build a poker bot\.<\/span>/);
  assert.match(html, /<span class="block whitespace-nowrap">\s*Prove it.{1,2}s the best\./);
  assert.match(html, /Prove it.{1,2}s the best\./);
  assert.match(html, /A private arena for testing autonomous poker agents\./);
  assert.match(html, /PRIVATE BOT LEAGUE/);
  assert.match(html, /Claude, ChatGPT, or Codex/);
  assert.match(html, /alpha-poker-preview-v2\.png/);
  assert.match(html, /property="og:image:width" content="1200"/);
  assert.match(html, /property="og:image:height" content="630"/);
  assert.match(html, /name="twitter:card" content="summary_large_image"/);
  assert.doesNotMatch(html, /react-loading-skeleton/);
});

test("orders hero, leaderboard, and instructions sections", async () => {
  const response = await render();
  const html = await response.text();

  const heroIndex = html.indexOf("PRIVATE BOT LEAGUE");
  const leaderboardIndex = html.indexOf('id="leaderboard"');
  const instructionsIndex = html.indexOf('id="instructions"');

  assert.ok(heroIndex >= 0, "hero section missing");
  assert.ok(leaderboardIndex > heroIndex, "leaderboard should follow hero");
  assert.ok(
    instructionsIndex > leaderboardIndex,
    "instructions should follow leaderboard",
  );
});

test("features RiverRat as the current leader with one private league", async () => {
  const response = await render();
  const html = await response.text();

  assert.match(html, /RiverRat/);
  assert.match(html, /1,264(<!-- -->)? Elo/);
  assert.match(html, /4(<!-- -->)? wins/);
  assert.match(html, /0(<!-- -->)? losses/);
  assert.ok((html.match(/RiverRat/g) ?? []).length >= 2, "leader should appear on the podium and in the table");
  assert.doesNotMatch(html, /join.{0,20}room/i);
  assert.doesNotMatch(html, /create.{0,20}room/i);
});

test("renders the selected podium and keeps the hero to the first viewport", async () => {
  const response = await render();
  const html = await response.text();

  assert.match(html, /aria-label="Top three bots"/);
  assert.match(html, /data-testid="reference-leaderboard"/);
  assert.match(html, /robot-avatars\.png/);
  assert.match(html, /data-avatar-variant="champion"/);
  assert.match(html, /data-avatar-variant="silver"/);
  assert.match(html, /data-avatar-variant="bronze"/);
  assert.match(html, /data-podium-block="1"/);
  assert.match(html, /data-plane="top"/);
  assert.match(html, /data-plane="front"/);
  assert.match(html, /data-plane="right"/);
  assert.match(html, /data-winner-badge/);
  assert.match(html, /max-w-\[620px\]/);
  assert.match(html, /aspect-\[310\/238\]/);
  assert.match(html, />Rank<\/th>/);
  assert.match(html, />Bot<\/th>/);
  assert.match(html, />Player<\/th>/);
  assert.match(html, />Elo<\/th>/);
  assert.match(html, />Record<\/th>/);
  assert.doesNotMatch(html, />BB\/100<\/th>/);
  assert.doesNotMatch(html, />Hands<\/th>/);
  assert.doesNotMatch(html, /Duplicate deals/);
  assert.doesNotMatch(html, /How scoring works/);
  assert.match(html, /w-\[33%\]/);
  assert.doesNotMatch(html, /FULL STANDINGS/);
  assert.match(html, /min-h-\[calc\(100svh-4\.5rem\)\]/);
  assert.match(html, /aria-label="Alpha Poker home"/);
});

test("renders working account entry and hero links to real sections", async () => {
  const response = await render();
  const html = await response.text();

  assert.match(html, /data-testid="account-trigger"/);
  assert.match(html, /<span>Account<\/span>/);
  const authSource = await readFile(new URL("../app/components/AuthButton.tsx", import.meta.url), "utf8");
  assert.match(authSource, /sessionChecked \? \([\s\S]*<span>Log in<\/span>/);
  assert.doesNotMatch(html, /aria-disabled="true"[^>]*>\s*Log in/);
  assert.match(html, /href="#instructions"/);
  assert.match(html, /href="#leaderboard"/);
});

test("bot record copy lives on /my-bot and pluralizes draws", async () => {
  const source = await readFile(
    new URL("../app/components/mybot/MyBotWorkspace.tsx", import.meta.url),
    "utf8",
  );

  // The record reads as a compact W–L tile, so the only prose count left is
  // the draws footnote and it must not render "1 draws".
  assert.match(source, /record\.draws === 1 \? "draw" : "draws"/);
  assert.doesNotMatch(source, /record\.draws\} draws/);
  assert.doesNotMatch(source, /losss/);
});

test("instructions download the kit and hand the complete workflow to a coding agent", async () => {
  const response = await render();
  const html = await response.text();

  assert.match(html, /href="\/alpha-poker-starter\.zip"/);
  assert.match(html, /download/);
  assert.match(html, /alpha-poker-starter\.zip/g);
  assert.match(html, /most recently modified file matching alpha-poker-starter\*\.zip/);
  assert.match(html, /alpha-poker-starter \(1\)\.zip/);
  assert.match(html, /Enter the arena/);
  assert.match(html, /Your agent builds, trains, and submits your bot\./);
  assert.match(html, /Beat the field\. Take the crown\./);
  assert.match(html, /Copy the agent instructions/);
  assert.match(html, /Copy instructions/);
  assert.match(html, /Paste them into your coding agent/);
  assert.match(html, /min-h-\[100svh\]/);
  assert.match(html, /one active bot/);
  assert.match(html, /download all available hand and training artifacts/i);
  assert.match(html, /bundled cli folder/i);
  assert.match(html, /Do not ask me to run Alpha Poker terminal commands myself/i);
  assert.doesNotMatch(html, /alpha-poker submit \./);
  assert.doesNotMatch(html, /font-mono text-sm leading-6 text-zinc-700/);
});

test("bot status and log downloads live on /my-bot, not the account dialog", async () => {
  const [auth, myBot] = await Promise.all([
    readFile(new URL("app/components/AuthButton.tsx", templateRoot), "utf8"),
    readFile(new URL("app/components/mybot/MyBotWorkspace.tsx", templateRoot), "utf8"),
  ]);

  assert.match(myBot, /browser-api\/account\/status/);
  assert.match(myBot, /Validation log/);
  assert.match(myBot, /Latest result logs/);
  assert.match(myBot, /participant_message/);

  // The dialog is identity and sign-out only now.
  assert.doesNotMatch(auth, /browser-api\/account\/status/);
  assert.doesNotMatch(auth, /validation log/i);
  assert.doesNotMatch(auth, /hand logs/i);
  assert.match(auth, /Log out/);
  assert.match(auth, /Provided by your cohort organizer/);
  assert.doesNotMatch(auth, /if required/);
});

test("the account dialog stays inside short viewports", async () => {
  const source = await readFile(
    new URL("app/components/AuthButton.tsx", templateRoot),
    "utf8",
  );

  // The scroll container is the overlay, so the register form cannot push its
  // submit button past the bottom of a short screen.
  assert.match(source, /fixed inset-0 z-50 overflow-y-auto overscroll-contain/);
  assert.match(source, /flex min-h-full items-center justify-center/);
  assert.match(source, /max-h-\[calc\(100dvh-3rem\)\][^"]*overflow-y-auto/);
});

test("private-league registration makes the invite requirement visible", async () => {
  const auth = await readFile(
    new URL("../app/components/AuthButton.tsx", import.meta.url),
    "utf8",
  );
  assert.match(auth, /Invite code[\s\S]{0,100}\(required\)/);
  assert.match(auth, /Provided by your cohort organizer\. Ask them if you do not have one\./);
});

test("removes the starter preview scaffolding", async () => {
  await access(new URL("public/robot-avatars.png", templateRoot));
  await assert.rejects(
    access(new URL("app/_sites-preview", templateRoot)),
  );
  const packageJson = await readFile(
    new URL("package.json", templateRoot),
    "utf8",
  );
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.match(packageJson, /vinext dev --port 3001/);
});

test("leaderboard constrains untrusted names at the UI boundary", async () => {
  const source = await readFile(
    new URL("app/components/Leaderboard.tsx", templateRoot),
    "utf8",
  );

  assert.match(source, /BOT_NAME_DISPLAY_LENGTH = 18/);
  assert.match(source, /PLAYER_NAME_DISPLAY_LENGTH = 16/);
  assert.match(source, /CONTROL_CHARACTERS\.test\(botName\)/);
  assert.match(source, /CONTROL_CHARACTERS\.test\(username\)/);
  assert.match(source, /\.map\(normalizeEntry\)/);
});
