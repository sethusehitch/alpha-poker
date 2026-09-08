# Alpha Poker Rivals MVP

## Product boundary

- Keep the public landing page unchanged. Rivals starts after login.
- Add one authenticated `/rivals` workspace and one focused `/hands/:hand_id` replay route.
- Use the approved rival-gallery visual direction in:
  `/Users/sethsaperstein/Documents/AlphaSchool/alpha-poker-app/product-concepts/playful-experience-v6/images/03-rival-gallery-overlay.png`.
- The signed-in header includes My Bot, Training, Rivals (people icon and blue active underline), Leaderboard, a notification bell with unread count, and account/avatar.
- Keep all play-money language. No gambling, purchases, loot boxes, or automatic “Improve my bot” action.

## One-page UI

The `/rivals` page has in-place tabs for My rivals, Leaderboard, Challenges, and League records. Selecting a person opens one reusable overlay, not a new page. The overlay contains only:

1. Opponent identity, bot, Elo, head-to-head score, and `NEMESIS` when earned.
2. One contextual action: Challenge, Accept/Decline, Running, Pending, or Challenge again.
3. A fixed-height, scrollable, paginated head-to-head history.

History rows can open an in-page recap drawer. The drawer links individual hands to `/hands/:hand_id`. Query parameters drive deep links and browser Back closes overlays naturally.

League records is an in-page comparison with two searchable player selectors. If the signed-in user is one participant, show Challenge. Otherwise it is read-only.

## Critical data rule

Head-to-head scores, rivalry history, League-record comparisons, and Nemesis use **completed direct rivalry challenges only**. Never include official round-robin meetings. Direct challenges never update public Elo.

Nemesis is the opponent with the caller's most direct-challenge losses, requiring at least three completed direct challenges. Tie break by total direct challenges, then most recent completion.

## Challenge lifecycle

- A challenge is always an asynchronous, unranked, deterministic best-of-five heads-up Pot-Limit Hold'em tournament series.
- States: `pending -> queued -> running -> completed`; alternatives: `declined`, `cancelled`, `failed`.
- Creation and acceptance use `Idempotency-Key`.
- Reject self-challenges, missing active bots, duplicate open challenges, and unauthorized transitions.
- Snapshot both active submissions when accepted and protect them from pruning while queued/running.
- Store the match as one non-official `runs` row and one matchup using existing hands/artifacts.
- Determine winner by aggregate play-chip profit. Elo is unchanged.
- Recover stale work safely after process restart.

## Notifications

Types: challenge_received, challenge_won, challenge_lost, challenge_drawn, challenge_failed. Poll every 10 seconds and on focus. Notification clicks deep-link into the exact rival/challenge or result recap and become read only after the target opens successfully. Logging out immediately clears notification content and unread state from the browser shell.

Feature requests and Contribute are signed-in navigation destinations. They live under a visually separate Community menu, while Rivals and Leaderboard remain core game navigation.

## API

- `GET /v1/rivals?source=mine|leaderboard&q=`
- `GET /v1/rivals/{username}`
- `GET /v1/rivals/{username}/history?cursor=&limit=`
- `GET /v1/rivalries/compare?player_a=&player_b=&cursor=&limit=`
- `POST /v1/challenges`
- `GET /v1/challenges?status=incoming|running|finished`
- `GET /v1/challenges/{id}`
- `POST /v1/challenges/{id}/accept|decline|cancel`
- `GET /v1/challenges/{id}/recap`
- `GET /v1/notifications?cursor=&limit=`
- `POST /v1/notifications/{id}/read`
- `POST /v1/notifications/read-all`

## CLI

Support dependency-light, agent-friendly `rivals` commands for list, show, history, requests, challenge, accept, decline, cancel, status (including bounded `--wait`), and recap, plus notification list/read. Read commands support stable `--json`. Mutations preview the action, support confirmation and `--yes`, and never expose credentials. The student asks Claude or Codex in chat; the coding agent performs all technical commands.

## Acceptance

- Auth, validation, races, pagination, deterministic output, restart recovery, retention, notification fan-out, and unchanged Elo have automated coverage.
- Desktop/mobile browser QA covers tabs, overlay accessibility, challenge lifecycle with two accounts, notifications, recap, and hand replay.
- Container, restart, and concurrency checks pass.
- A fresh independent agent with no inherited context receives only the local URL, starter prompt, and disposable credentials. It must use the product as a user without reading source first. Defects are fixed and the clean-slate pass repeats until successful.
