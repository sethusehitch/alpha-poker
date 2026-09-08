# Alpha Poker workflows for coding agents

Hosted API: `https://alphapoker.io/v1`

This guide is for Claude, ChatGPT, Codex, or another coding agent with terminal
access. Explain the workflow to the participant first, then perform it for them.
Do not ask the participant to copy terminal commands when you can run them.

If this guide came from a download, locate the most recently modified file
matching `alpha-poker-starter*.zip` in the participant's Downloads folder.
Names such as `alpha-poker-starter (1).zip` are normal browser duplicates. Tell
the participant which exact archive you selected, extract it to a new folder,
and verify that it contains `README.md`, `WORKFLOWS.md`, `API.md`, and `cli/`
before continuing. Never silently reuse an older extracted copy.

## What you can do

- Build and locally validate `bot.py` and `bot.json`.
- Register or log in to the participant's Alpha Poker account.
- Train offline against five packaged dojo bots, or face the current leader over WebSocket.
- Inspect downloaded training hands and implement strategy changes the participant requests.
- Submit the best version. Each accepted submission replaces the participant's
  one active bot.
- Check submission validation, league-run status, and the leaderboard.
- Download official run artifacts and training hand logs.
- For Review hands, open saved evidence with `alpha-poker recap PATH --open`,
  or `alpha-poker recap --latest --open` after training. Use `train --recap`
  when the participant asks to train and watch afterward. Without `--open`, the
  command prints a local URL that Codex can open in its browser side panel.
  The same viewer offers highlights and a picker for any retained hand. This
  does not upload evidence, improve the bot, or change Elo. The participant
  inspects the replay and chooses what hypothesis to investigate next.
- Find classmates by player or bot name and explain their public Elo.
- Send a best-of-five Pot-Limit Hold'em challenge after the participant chooses an opponent.
- Check incoming requests and accept or decline after participant approval.
- Wait for a rivalry match, report the game score and total hands, and
  download its recap evidence.
- Read challenge notifications and mark them read after sharing the result.

## Participant-facing opening

After reading this kit, start with a short participant-facing menu before doing
technical work. Show Build, Train, Compete, Challenge someone, Review hands,
and Check progress, with one sentence explaining each and whether it changes
Elo. Fetch `GET /leaderboard` from the hosted API and show at most the current
top three bots with rank, player, Elo, and a plain-language win-loss-draw
record. Add one friendly line inviting the participant to chase the podium.
Never invent standings if the request fails or the league is empty.

Describe Review hands as "Watch your saved hands at the poker table" and Train
as "Choose a dojo opponent or the current leader, then watch the highlights."
After successful training with saved hands, summarize the result and ask,
"Want to watch the highlights?" If the participant already asked to train and
watch, open the local recap immediately. Use the browser side panel when
available, otherwise the default browser or the printed link. Explain the
highlights and individual-hand picker. Do not require the participant to run
commands. Missing replay evidence should be explained, never invented.

Ask what the participant wants to do and wait for the answer. Recommend **Build
my first bot** to a beginner, but let returning participants choose any workflow
immediately. Do not install tools, create an account, edit a bot, train, submit,
or challenge another player before the participant chooses.

For **Build my first bot**, use four visible milestones: Create, Build,
Practice, and Compete. Ask the participant for a name and a simple personality
such as Bold, Patient, Tricky, or Surprise me. Keep technical commands and raw
output out of the participant-facing explanation. Translate practice results
into one strength and one decision worth investigating. Offer the recap, then
ask what hypothesis or strategy change the participant wants to investigate.
Never change strategy automatically or treat watching as permission to edit.
Implement requested changes and validate again. Request explicit approval
directly before the first submission or any later replacement.

## Agent-operated setup

Create a local virtual environment and install the bundled dependency-free CLI
from `./cli`. Use the hosted API above with `--api-url` or set
`ALPHA_POKER_API_URL` only for the current process. Never place a password,
invite code, or session token in bot files, shell history, or source control.
Let the CLI request passwords and any required invite code through its secure
prompts. Omit `--invite-code` during normal agent-operated registration so the
cohort code does not appear in command arguments, tool transcripts, or shell
history.

Run `alpha-poker --help` and the relevant subcommand help before operating.
For a new participant, create and validate the bot locally before account
setup. Connect the account only when hosted leader training, progress sync, competition, or another hosted
workflow needs it. Continue with training, strategy iteration, submission,
status checks, and relevant artifact downloads. Confirm each result for the
participant and continue until the chosen task is complete or a human-only
input is required.

When choosing a destination for training logs, `alpha-poker train --output`
accepts either a directory or an explicit `.zip` filename. If you provide a
directory, the CLI creates a uniquely named training-log ZIP inside it.

## Choosing a training opponent

When the participant chooses Train (including Practice in the beginner path),
run `alpha-poker dojo list --json --api-url https://alphapoker.io/v1`.
Show a compact table: opponent, difficulty, rating, and local or hosted.
The five packaged opponents are Pebble, Spark, Anchor, Mirage, and Summit.
Their **Dojo Elo** is measured in a separate practice pool, not comparable to
public league Elo. All five are unlocked. Use `dojo status --json` to suggest
the first not beaten locally, but let the participant choose any opponent.
Show the current leader as one additional row with its actual bot name, player,
and **public Elo**, fetched live. Never invent a leader or rating. If unavailable,
say so and offer the local opponents. The leader is not a dojo opponent and
never earns a dojo checkmark. Link the dojo at `https://alphapoker.io/training`.

After the participant chooses, operate the appropriate command:

```text
alpha-poker train . --opponent pebble --hands 200
alpha-poker train . --opponent leader --hands 200 --api-url https://alphapoker.io/v1
alpha-poker recap --latest --open
```

Replace `pebble` with the selected packaged opponent ID. Dojo hands must be
even, from 2 to 400. Every pair uses the same cards with player seats swapped.
Only the five dojo bots and public engine are packaged locally. Their source
is inspectable. The leader always runs on the server over WebSocket; never
attempt to download, extract, or distribute another player's bot code.
Neither training path changes public Elo. Both save evidence for the same
local recap viewer. Offer highlights after the result, or open them immediately
if the participant already asked to watch. Do not improve strategy automatically.

A local "beaten" checkmark requires at least 200 mirrored hands, positive net
play chips, and no bot errors. It means **self-reported local practice**, not a
server-verified win. Explain that a single win is not proof of a stronger bot.
Results persist locally. Offer account sync after a run; only after approval,
run `alpha-poker dojo sync RUN_ID --api-url https://alphapoker.io/v1`.
This sends a result summary, not source or hand files. It requires login and
updates private progress on the website. Failed sync never deletes local logs;
retry the same run ID. `dojo status` lists recent run IDs. Viewing a recap does
not sync or change anything. A new opponent version starts a new progress set.

After submitting, run `alpha-poker status` until it reports either a completed
result, a clear wait for another participant, or an actionable failure. Run
`alpha-poker logs --output ./alpha-poker-logs` to download validation output
and the newest official hand-log ZIP when available. The participant can see
the same state by logging in on the website and opening their account.

## Agent-operated rival flow

Rival commands should normally use `--format agent` or `--format json` so results are reliable to parse.
For a completed challenge, agent-format `score` is winner first; `score_order` and `viewer_result` make that perspective explicit.
Present the useful facts conversationally instead of pasting raw JSON.

1. Offer to find a classmate by username or bot name, list prior rivals, or
   browse the leaderboard.
2. Show the selected opponent's bot, Elo, and direct-challenge record. Ask the
   participant whether they want to send the best-of-five challenge.
3. Only after approval, send the challenge with the CLI's `--yes` flag. The
   CLI includes an idempotency key, and the server prevents duplicate open
   challenges.
4. Check requests with `rivals requests`. For an incoming request, explain the
   two current bots before asking whether to accept or decline.
5. Use `rivals status CHALLENGE_ID --wait --format agent` when the participant wants to
   stay for the result. The wait is bounded. If it times out, explain that the
   match continues on the server and repeat the provided check-later command.
6. On completion, use `rivals recap CHALLENGE_ID --output PATH --format agent`. Report
   who won, the game score, and total hands, then offer to inspect selected hands and
   help the participant form a strategy hypothesis.

Useful commands for the coding agent:

```text
alpha-poker rivals list --source leaderboard --json
alpha-poker rivals list --source mine --search maya --json
alpha-poker rivals show maya --json
alpha-poker rivals history maya --limit 20 --json
alpha-poker rivals requests --status incoming --json
alpha-poker rivals challenge maya --yes --json
alpha-poker rivals accept CHALLENGE_ID --yes --json
alpha-poker rivals decline CHALLENGE_ID --yes --json
alpha-poker rivals cancel CHALLENGE_ID --yes --json
alpha-poker rivals status CHALLENGE_ID --wait --format agent
alpha-poker rivals recap CHALLENGE_ID --output ./rival-recaps --format agent
alpha-poker notifications list --unread --json
alpha-poker notifications read NOTIFICATION_ID --json
```

Direct rivalry challenges never change public Elo. Their history contains only
explicit challenges, not the many pairings from official round robins. Do not
promise that a challenge has started merely because it was sent: it remains
pending until the recipient accepts, then moves through queued and running.

## Important behavior

- Training keeps the participant's bot local and does not alter standings.
- Submission uploads only `bot.py` and `bot.json`.
- A successful new submission atomically replaces the participant's prior
  active bot.
- Accepted uploads queue a new official league run. The leaderboard refreshes
  after that run finishes.
- A league needs at least two active bots. With only one, status truthfully says
  it is waiting for another participant rather than claiming a run is active.
- Running leagues show completed and total head-to-head matchups. Every run has
  a server-side deadline; failures remain visible and a later accepted upload
  safely retries the queue.
- Training and official-run artifacts contain the hand logs needed for review.
- Rival challenges use current active bots at acceptance, produce their own
  recap evidence, and do not affect the leaderboard.

The bot input and action contract is in `API.md`. CLI details are in
`cli/README.md`. The hosted REST API reference is available at
`https://alphapoker.io/docs`.
