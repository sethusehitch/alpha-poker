import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("Rivals keeps the browser contract and direct-challenge rules explicit", async () => {
  const [workspace, api, header, feedback, handReplay, handProxy, proxy] =
    await Promise.all([
      readFile(
        new URL(
          "../app/components/rivals/RivalsWorkspace.tsx",
          import.meta.url,
        ),
        "utf8",
      ),
      readFile(
        new URL("../app/components/rivals/api.ts", import.meta.url),
        "utf8",
      ),
      readFile(
        new URL("../app/components/app/AppHeader.tsx", import.meta.url),
        "utf8",
      ),
      readFile(
        new URL("../app/components/FeedbackWidget.tsx", import.meta.url),
        "utf8",
      ),
      readFile(
        new URL("../app/components/rivals/HandReplay.tsx", import.meta.url),
        "utf8",
      ),
      readFile(
        new URL("../app/browser-api/hands/[hand_id]/route.ts", import.meta.url),
        "utf8",
      ),
      readFile(
        new URL("../app/browser-api/_proxy.ts", import.meta.url),
        "utf8",
      ),
    ]);
  assert.match(workspace, /My rivals/);
  assert.match(workspace, /League records/);
  assert.match(workspace, /Direct challenges only/);
  assert.match(workspace, /event\.key === "Escape"/);
  assert.match(workspace, /document\.body\.style\.overflow = "hidden"/);
  assert.match(workspace, /history\.pushState/);
  assert.match(workspace, /Confirm challenge/);
  assert.match(workspace, /setConfirmCreate\(true\)/);
  assert.match(workspace, /viewer=\{viewer\}/);
  assert.match(workspace, /outcome === "draw"/);
  assert.match(workspace, /challenge\.recap_url/);
  assert.match(workspace, /robot-avatars\.png/);
  assert.match(workspace, /direct_record\.draws > 0/);
  assert.match(workspace, /const result = fromUrl\.get\("result"\)/);
  assert.match(workspace, /fromUrl\.get\("challenge"\) \?\? result/);
  assert.match(
    workspace,
    /if \(result && found\.recap_url\) setRecap\(found\.challenge_id\)/,
  );
  assert.match(workspace, /onOpen=\{openChallenge\}/);
  assert.match(workspace, /challenge\.opponent_username/);
  assert.match(workspace, /status === "queued" \|\| status === "running"/);
  assert.match(workspace, /window\.setInterval\(\(\) => void load\(\), 5000\)/);
  assert.match(
    workspace,
    /Promise\.all\(\[rivalsApi\.list\("mine"\), rivalsApi\.list\("leaderboard"\)\]\)/,
  );
  assert.match(workspace, /dateStyle: "medium",\s*timeStyle: "short"/);
  assert.doesNotMatch(workspace, /timeZone: "UTC"/);
  assert.match(workspace, /Scroll for more/);
  assert.match(workspace, /highlightedId=\{recap\}/);
  assert.match(workspace, /z-50 flex items-end/);
  assert.match(workspace, /emit\("open-account"/);
  assert.match(workspace, /workspaceGeneration/);
  assert.match(workspace, /useRef<string \| null \| undefined>\(undefined\)/);
  assert.match(workspace, /sessionOwner\.current !== undefined && sessionOwner\.current !== nextOwner/);
  assert.match(workspace, /if \(!loaded\) return;/);
  assert.match(workspace, /if \(changedOwner\) \{[\s\S]*setQuery\(""\);/);
  assert.match(workspace, /\? rawTab\s*:\s*initialTab/);
  assert.match(workspace, /<Records key=\{viewer\}/);
  assert.match(workspace, /let cancelled = false/);
  assert.match(workspace, /const stale = \(\) => cancelled \|\| generation !== workspaceGeneration\.current/);
  assert.match(workspace, /return \(\) => \{\s*cancelled = true;/);
  assert.match(
    workspace,
    /generation !== workspaceGeneration\.current \|\| requestUrl !== window\.location\.href/,
  );
  assert.match(workspace, /rivalsOverlay: pushed === "overlay"/);
  assert.match(workspace, /rivalsRecap: pushed === "recap"/);
  assert.match(workspace, /overlayWasPushed\.current = Boolean\(state\?\.rivalsOverlay\)/);
  assert.match(workspace, /let cancelled = false/);
  assert.match(workspace, /on\("close-panels", \(\) => \{/);
  assert.match(workspace, /emit\("rivals-dialog-changed", \{ open: Boolean\(selected \|\| recap\) \}\)/);
  assert.match(workspace, /return \(\) => emit\("rivals-dialog-changed", \{ open: false \}\)/);
  assert.match(workspace, /workspaceGeneration\.current \+= 1;/);
  assert.match(workspace, /history\.replaceState\(\{\}, "", href\)/);
  assert.match(api, /Idempotency-Key/);
  assert.match(api, /rivalries\/compare/);
  assert.match(header, /10_000/);
  assert.match(header, /window\.addEventListener\("focus"/);
  assert.match(header, /You beat \$\{opponent\} by \$\{margin\} play chips/);
  assert.match(header, /\$\{opponent\} challenged you/);
  assert.match(header, /You and \$\{opponent\} tied\./);
  assert.match(header, /params\.set\("result", challenge\.challenge_id\)/);
  assert.match(header, /params\.set\("challenge", challenge\.challenge_id\)/);
  assert.match(header, /AuthButton/);
  assert.match(header, /#instructions/);
  assert.match(header, /if \(!session\) \{/);
  assert.match(header, /setNotes\(\[\]\)/);
  assert.match(header, /setUnread\(0\)/);
  assert.match(header, /notificationGeneration/);
  assert.match(header, /generation !== notificationGeneration\.current/);
  assert.match(header, /challenge\.status === "completed"/);
  assert.match(header, /challenge\.challenged_username === session\?\.username/);
  assert.match(header, /challenge\.status === "failed"/);
  assert.match(header, /params\.set\("tab", "challenges"\)/);
  assert.match(header, /notificationDialogRef/);
  assert.match(header, /event\.key === "Escape"/);
  assert.match(header, /!notificationDialogRef\.current\?\.contains\(target\)/);
  assert.match(header, /bellRef\.current\?\.focus\(\)/);
  assert.match(header, /max-h-\[calc\(100dvh-6rem\)\] .*overflow-y-auto/);
  assert.match(header, /function notificationTime\(value: string\)/);
  assert.match(header, /<time dateTime=\{note\.created_at\}>/);
  assert.match(header, /month: "short",\s*day: "numeric",\s*hour: "numeric"/);
  assert.match(header, /app-mobile-menu/);
  assert.match(header, /lg:hidden/);
  assert.match(header, /appMenuToggleRef\.current\?\.contains/);
  assert.match(header, /on\("close-panels", closeTransientPanels\)/);
  assert.match(feedback, /emit\("close-panels", \{\}\)/);
  assert.match(feedback, /on\("rivals-dialog-changed", \(\{ open \}\) => \{/);
  assert.match(feedback, /setRivalsDialogOpen\(open\);\s*if \(open\) setOpen\(false\);/);
  assert.match(feedback, /accountOpen \|\| suggestOpen \|\| rivalsDialogOpen/);
  assert.match(proxy, /Idempotency-Key/);
  assert.match(api, /history\?limit=20/);
  assert.match(api, /challenge_drawn/);
  assert.match(handReplay, /seat_to_bot/);
  assert.match(handReplay, /hand\.events/);
  assert.match(handReplay, /eventCopy/);
  assert.match(handReplay, /eventLabel/);
  assert.doesNotMatch(handReplay, /event\.type\.replaceAll/);
  assert.match(handReplay, /Sign in to view this replay/);
  assert.match(workspace, /hand\.winner \? \(/);
  assert.match(workspace, /Hand \{hand\.hand_number\} tied/);
  assert.match(handProxy, /hands\/\$\{encodeURIComponent\(hand_id\)\}/);
});
