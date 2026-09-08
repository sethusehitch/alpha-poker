# Alpha Poker CLI

## Local replay viewer

With the current starter kit installed:

```bash
alpha-poker train ./my-bot --hands 100 --recap
alpha-poker recap --latest --open
alpha-poker recap ./training-results.zip --open
alpha-poker recap ./official-run.zip --open
alpha-poker recap ./hands.jsonl
```

The same animated table used on the website opens locally. Choose Highlights
or any retained hand using the View picker. Archives with several matchups have
a Match picker; their records are never merged into one rivalry. Saved recap-v1
JSON is also supported, but contains only the highlights originally saved.

No website login, internet connection, Node installation, or running Alpha Poker
API is required to **view a saved run**. Training itself still uses the hosted
WebSocket. The CLI prints a loopback URL, and `--open` launches the default
browser. In Codex, ask the agent to open that exact URL in the browser side panel;
other agents can print the link or open your regular browser.

`--latest` uses the last successful training download or explicitly opened recap,
not a scan of your files. A moved/deleted file needs to be opened by its new path.
The local viewer exits after 30 minutes without requests, or eight hours total;
run the command again to reopen it. Its URL is private to this computer and
session, not a share link. No local log is uploaded. Keep the original ZIP to
revisit it later. Limits: 64 MB compressed/uncompressed and 10,000 hand records.
Incomplete hands are skipped with a notice; unknown history does not invent
match-wide lead changes. Only Alpha Poker's JSONL/ZIP/recap-v1 formats are supported.

Repository developers: run `npm ci && npm run build:local-recap` before installing
`./cli` or building the starter kit. Release ZIPs already include the shared
viewer assets and dependency-free recap Python modules.

The CLI has no runtime dependencies beyond Python 3.11. It is designed for a
coding agent such as Claude or Codex to operate on a participant's behalf.
Participants make the poker decisions while the agent handles these technical
commands.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ./cli
alpha-poker register maya
alpha-poker validate ./starter-kit
alpha-poker submit ./starter-kit
alpha-poker train ./starter-kit --hands 400
alpha-poker train ./starter-kit --hands 10 --output ./training-logs
alpha-poker status
alpha-poker logs --output ./alpha-poker-logs
alpha-poker rivals list --source leaderboard
alpha-poker rivals challenge theo --yes
alpha-poker rivals requests --status incoming
alpha-poker rivals accept ch_123 --yes
alpha-poker rivals status ch_123 --wait
alpha-poker rivals recap ch_123 --output ./rival-recaps
alpha-poker notifications list --unread
```

The local API defaults to `http://localhost:8000/v1`. Override it with
`--api-url` or `ALPHA_POKER_API_URL`.

`register` and `login` save a revocable session token in
`${XDG_CONFIG_HOME:-~/.config}/alpha-poker/credentials.json` with mode `0600`.
Set `ALPHA_POKER_CONFIG` to an exact file path when you need a fully isolated
profile. Tokens are scoped to
the API URL and are never included in bot ZIPs. Use `alpha-poker whoami` to
check the account and `alpha-poker logout` to revoke the current token.
If the league uses a cohort code, `register` requests it through a hidden
interactive prompt. This keeps the code out of command arguments and shell
history. `--invite-code CODE` remains available only for controlled automation
where interactive input is impossible.

`status` shows validation, whether the league is waiting or running, matchup
progress, and the latest Elo result. `logs` downloads your validation log and,
after a completed competition, the official ZIP containing hands and summary.
For training, `--output` accepts either a destination directory or an explicit
`.zip` filename. A directory receives a uniquely named training-log ZIP.

For automation, `ALPHA_POKER_TOKEN` overrides the saved token. Do not put that
environment variable in bot code or commit it to source control.

## Rival challenges

Rival challenges are asynchronous, play-money, best-of-five heads-up Pot-Limit Hold'em tournament series. Each game starts both bots at 10,000 chips, carries stacks between hands, escalates blinds, and ends when one bot is bankrupt. The first bot to win three games wins the challenge.
They are separate from official round robins and do not change public Elo.
Only direct challenges appear in rival history.

Use `alpha-poker rivals list --source leaderboard` to find an opponent, or
`--source mine` to return people previously challenged. `rivals show USERNAME`
summarizes the selected bot, Elo, direct-challenge record, and Nemesis status.
`rivals history USERNAME` returns only the direct series between those two
participants.

Sending, accepting, declining, and cancelling are confirmation-protected. An
agent should show the participant the opponent, current bots, and fixed format
before using `--yes`. Creation and state-changing requests carry an
`Idempotency-Key`, and the server rejects a duplicate open challenge.

`rivals status CHALLENGE_ID --wait` polls with bounded backoff for at most five
minutes by default. Use `--timeout SECONDS` to choose a bound from 1 to 3600.
It exits when the challenge is completed, declined, cancelled, or failed. If the wait bound expires, the command exits normally with a message explaining that the server is still working and provides the exact check-later command.
`rivals recap` prints the result; with `--output`, it downloads the evidence
archive when available, otherwise it saves recap JSON.

Completed challenges expose the same highlighted replay in the browser and CLI:

```bash
alpha-poker rivals requests --status finished
alpha-poker rivals history theo
alpha-poker rivals status ch_123
alpha-poker rivals recap ch_123 --url
alpha-poker rivals recap ch_123 --open --site-url http://localhost:3002
alpha-poker matches list
alpha-poker matches list --run run_123
alpha-poker matches recap run_123 run_123_match_1 --open
```

`rivals recap CHALLENGE_ID` always prints a stable `View recap` URL after
authenticating and fetching the completed recap. `--url` prints only that URL;
`--open` also opens it. `--json` includes the URL alongside the full normalized
highlight payload. Existing `--output` evidence downloads still work.
`matches list` discovers pairings in the latest completed official run (or the
exact run supplied with `--run`); `matches recap RUN_ID MATCHUP_ID` requests only
that pairing. These commands authenticate using the existing API profile.

The web origin defaults to `http://localhost:3002` for a local API, otherwise
the API's origin. Set `ALPHA_POKER_SITE_URL` or `--site-url` when web and API
origins differ. Run the normal web app and API locally to view a local recap;
there is no second file renderer or token bridge. Sign in to the web app
separately. Session tokens are never embedded in URLs or handed to the browser.

Recaps select at most five distinct retained hands, ordered chronologically.
Highlights use net chip profit, mirrored-seat mapping, and complete-match
cumulative scores. Partial history never claims a match-wide comeback or lead
change. Play steps through recorded actions; it does not rerun either bot.

Notifications tell the participant when a challenge arrives, completes, or
fails. Use `notifications list --unread` and `notifications read ID`.

Rivals result commands support `--format human|agent|json`; `--json` remains a backwards-compatible alias. Human output is concise prose, agent output uses stable `key=value` facts, and JSON writes one object to stdout. A completed agent result reports `score` in winner-loser order, names that order explicitly, and includes the viewer's win/loss result. Progress goes to stderr for machine-readable modes, and credentials are never printed.
