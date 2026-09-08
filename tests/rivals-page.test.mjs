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
  assert.match(workspace, /challenges: "Challenges"/);
  assert.doesNotMatch(workspace, /League records/);
  assert.doesNotMatch(workspace, /leaderboard: "Leaderboard"/);
  assert.doesNotMatch(workspace, /Direct challenges only/);
  assert.match(workspace, /event\.key === "Escape"/);
  assert.match(workspace, /document\.body\.style\.overflow = "hidden"/);
  assert.match(workspace, /history\.pushState/);
  assert.match(workspace, /Confirm challenge/);
  assert.match(workspace, /setConfirmCreate\(true\)/);
  assert.match(workspace, />\s*Challenge\s*</);
  assert.match(workspace, /Create a bot first to send a challenge\./);
  assert.match(workspace, /aria-disabled=\{!canChallenge\}/);
  assert.match(workspace, /viewerHasActiveBot=\{viewerHasActiveBot\}/);
  assert.match(
    workspace,
    /startWithConfirmation=\{challengeTarget === selected\}/,
  );
  assert.match(
    workspace,
    /const challengeIntent = useRef\(startWithConfirmation\)/,
  );
  assert.match(workspace, /line-clamp-2 min-w-0 text-center leading-tight/);
  assert.doesNotMatch(
    workspace,
    /<span className="min-w-0 truncate">\s*Challenge \{detail\.rival\.username\}/,
  );
  assert.match(workspace, /viewer=\{viewer\}/);
  assert.match(workspace, /outcome === "draw"/);
  assert.match(workspace, /challenge\.recap_url/);
  assert.match(workspace, /<BotAvatar/);
  assert.match(workspace, /direct_record\.draws > 0/);
  assert.match(workspace, /const result = fromUrl\.get\("result"\)/);
  assert.match(workspace, /fromUrl\.get\("challenge"\) \?\? result/);
  assert.match(
    workspace,
    /if \(result && found\.recap_url\) setRecap\(found\.challenge_id\)/,
  );
  assert.match(workspace, /onOpen=\{openChallenge\}/);
  assert.match(workspace, /challenge\.opponent_username/);
  assert.match(workspace, /window\.setInterval\(\(\) => void load\(\), 5000\)/);
  assert.match(workspace, /suggested_items/);
  assert.match(workspace, /setSuggested\(data\.suggested_items \?\? \[\]\)/);
  assert.match(workspace, /dateStyle: "medium",\s*timeStyle: "short"/);
  assert.doesNotMatch(workspace, /timeZone: "UTC"/);
  assert.match(workspace, /highlightedId=\{recap\}/);
  assert.match(workspace, /z-50 flex items-end/);
  assert.doesNotMatch(workspace, /<aside\s+ref=\{panel\}\s+role="dialog"/);
  assert.match(handReplay, /event\.hands/);
  assert.match(handReplay, /shown\.hole_cards/);
  assert.match(handReplay, /shown\.category/);
  assert.match(workspace, /emit\("open-account"/);
  assert.match(workspace, /workspaceGeneration/);
  assert.match(workspace, /useRef<string \| null \| undefined>\(undefined\)/);
  assert.match(
    workspace,
    /sessionOwner\.current !== undefined && sessionOwner\.current !== nextOwner/,
  );
  assert.match(workspace, /if \(!loaded\) return;/);
  assert.match(workspace, /if \(changedOwner\) \{[\s\S]*setQuery\(""\);/);
  assert.match(workspace, /rawTab === "challenges" \? rawTab : initialTab/);
  assert.doesNotMatch(workspace, /<Records key=\{viewer\}/);
  assert.match(workspace, /let cancelled = false/);
  assert.match(
    workspace,
    /const stale = \(\) => cancelled \|\| generation !== workspaceGeneration\.current/,
  );
  assert.match(workspace, /return \(\) => \{\s*cancelled = true;/);
  assert.match(
    workspace,
    /generation !== workspaceGeneration\.current \|\|\s*requestUrl !== window\.location\.href/,
  );
  assert.match(workspace, /rivalsOverlay: pushed === "overlay"/);
  assert.match(workspace, /rivalsRecap: pushed === "recap"/);
  assert.match(
    workspace,
    /overlayWasPushed\.current = Boolean\(state\?\.rivalsOverlay\)/,
  );
  assert.match(workspace, /let cancelled = false/);
  assert.match(workspace, /on\("close-panels", \(\) => \{/);
  assert.match(
    workspace,
    /emit\("rivals-dialog-changed", \{ open: Boolean\(selected \|\| recap\) \}\)/,
  );
  assert.match(
    workspace,
    /return \(\) => emit\("rivals-dialog-changed", \{ open: false \}\)/,
  );
  assert.match(workspace, /workspaceGeneration\.current \+= 1;/);
  assert.match(workspace, /history\.replaceState\(\{\}, "", href\)/);
  assert.match(api, /Idempotency-Key/);
  assert.match(api, /rivalries\/compare/);
  assert.match(header, /10_000/);
  assert.match(header, /window\.addEventListener\("focus"/);
  assert.match(header, /You beat \$\{opponent\}\$\{winnerFirstScore/);
  assert.match(header, /\$\{opponent\} beat you\$\{winnerFirstScore/);
  assert.doesNotMatch(header, /by \$\{margin\} play chips/);
  assert.match(header, /\$\{opponent\} challenged you/);
  assert.match(header, /You and \$\{opponent\} tied\./);
  assert.match(header, /params\.set\("result", challenge\.challenge_id\)/);
  assert.match(header, /params\.set\("challenge", challenge\.challenge_id\)/);
  assert.match(header, /AuthButton/);
  assert.match(header, /#instructions/);
  assert.match(header, /currentPath/);
  assert.match(header, /if \(!session\) \{/);
  assert.match(header, /setNotes\(\[\]\)/);
  assert.match(header, /setUnread\(0\)/);
  assert.match(header, /notificationGeneration/);
  assert.match(header, /generation !== notificationGeneration\.current/);
  assert.match(header, /challenge\.status === "completed"/);
  assert.match(
    header,
    /challenge\.challenged_username === session\?\.username/,
  );
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
  assert.match(
    feedback,
    /setRivalsDialogOpen\(open\);\s*if \(open\) setOpen\(false\);/,
  );
  assert.match(feedback, /accountOpen \|\| suggestOpen \|\| rivalsDialogOpen/);
  assert.match(proxy, /Idempotency-Key/);
  assert.match(api, /history\?limit=20/);
  assert.match(api, /challenge_drawn/);
  assert.match(api, /challenges\$\{status \? `\?status=\$\{status\}` : ""\}/);
  assert.match(workspace, /rivalsApi\s*\.challenges\(\)/);
  assert.match(workspace, /setChallenges\(result\.items\)/);
  assert.match(handReplay, /seat_to_bot/);
  assert.match(handReplay, /hand\.events/);
  assert.match(handReplay, /eventCopy/);
  assert.match(handReplay, /eventLabel/);
  assert.match(handReplay, /Small blind/);
  assert.match(handReplay, /Big blind/);
  assert.doesNotMatch(handReplay, /event\.type\.replaceAll/);
  assert.match(handReplay, /Sign in to view this replay/);
  assert.doesNotMatch(workspace, /function RecapDrawer|<RecapDrawer|Match recap/);
  assert.match(workspace, /rival-recap-button/);
  assert.match(handProxy, /hands\/\$\{encodeURIComponent\(hand_id\)\}/);
});

test("the rival overlay shows exactly one of loading, error, or detail", async () => {
  const [workspace, avatar] = await Promise.all([
    readFile(
      new URL("../app/components/rivals/RivalsWorkspace.tsx", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../app/components/BotAvatar.tsx", import.meta.url),
      "utf8",
    ),
  ]);

  // A failed first load used to stack "Rival not found" on top of the
  // "Loading rival…" placeholder.
  assert.match(workspace, /\{!detail && loading \? \(/);
  assert.match(workspace, /\) : !detail \? \(/);
  assert.match(workspace, /const \[loading, setLoading\] = useState\(true\)/);
  assert.match(workspace, /setLoading\(true\);/);
  assert.match(
    workspace,
    /if \(request === detailRequest\.current\) setLoading\(false\);/,
  );
  assert.match(workspace, /Could not open this rival/);
  assert.match(
    workspace,
    /onClick=\{\(\) => void load\(\)\}[\s\S]{0,320}Retry/,
  );
  assert.match(
    workspace,
    /Could not open this rival[\s\S]*?Retry[\s\S]*?>\s*Close\s*</,
  );
  // The action-level banner still renders, but only alongside a loaded rival.
  assert.match(workspace, /\) : \(\s*<>\s*\{error && \(\s*<p\s*role="alert"/);
  // The API contract keeps this history direct-only without extra UI copy.
  assert.doesNotMatch(workspace, /Direct challenges only/);
  assert.match(workspace, /No completed direct challenges yet\./);
  assert.match(
    workspace,
    /Challenges unlock when they\s+submit an active bot\./,
  );
  assert.match(workspace, /h-\[18\.5rem\]/);
  assert.match(workspace, /max-w-\[20\.5625rem\]/);
  assert.match(workspace, /min-h-0 flex-1 items-start[^\n]*overflow-hidden/);
  assert.match(workspace, /className="h-28 w-28"/);
  assert.match(workspace, /h-\[92dvh\]/);
  assert.match(workspace, /sm:h-\[calc\(100dvh-2rem\)\]/);
  assert.match(workspace, /h-1 w-7 rounded-full bg-zinc-600/);
  assert.match(workspace, /mt-6 flex min-h-0 flex-1 flex-col overflow-hidden/);
  assert.match(workspace, /circle/);
  assert.match(
    workspace,
    /direct_record\.wins\} – \{rival\.direct_record\.losses/,
  );
  assert.match(workspace, />\s*Suggested\s*</);

  // All surfaces use the same account-owned character renderer.
  assert.match(avatar, /<CharacterImage username=\{name\} avatar=\{avatar\}/);
  assert.doesNotMatch(workspace, /robot-avatars\.png/);
});
