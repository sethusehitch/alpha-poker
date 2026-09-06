# Alpha Poker MVP Black-Box QA

## Test scope

- Environment: `https://alphapoker.io`
- Method: fresh agent with no repository or source-code access
- Perspective: first-time participant using only the public website and downloaded starter kit
- Test identity: disposable account prefixed `qa_e2e_`
- Test bot: `QA E2E SafeCaller`
- Tested: account creation, login persistence, starter download, copied prompt, local validation, hosted training, training logs, submission, competition status, leaderboard, official logs, API documentation, and logout

No invite codes, passwords, API tokens, operator credentials, or private hand-log contents are recorded here.

## Results

| Journey | Result | Evidence |
| --- | --- | --- |
| Understand landing page and navigation | Pass | Instructions and leaderboard were discoverable and navigation worked. |
| Create account and log in | Pass with copy defect | Registration worked, but the invite field said “if required” even though an invite is required. |
| Persist and restore browser session | Pass | Reload preserved the session; logout and repeat login worked. |
| Download starter kit | Pass with stale-file risk | ZIP was valid, but a repeated download was renamed by the browser while the copied prompt referenced one exact filename. |
| Copy agent prompt | Pass with stale-file risk | Copy action worked; prompt must locate the newest matching download. |
| Build and locally validate bot | Pass | Three validation checks passed. |
| Train through hosted WebSocket | Pass | Ten hosted hands completed against the current leader. |
| Download training logs | Pass | Archive contained summary, event, and hand logs. |
| Submit bot | Pass | Submission was accepted. |
| Track submission and competition | Fail | Website exposed no participant submission page, run progress, actionable status, or errors. |
| Complete official competition | Blocked | UI displayed “run in progress” for more than ten minutes, but production inspection showed it was waiting for a second active bot. |
| Appear on leaderboard | Blocked | No official run occurred because only one active participant bot existed. |
| Download official logs | Blocked | No official run occurred, and the advertised CLI commands were absent. |
| Open API documentation | Fail | `/docs` returned 404 through the production reverse proxy. |

## Defects and remediation criteria

### P0: No participant-facing status or official-log workflow

The starter documentation promises submission status, run status, and artifact downloads, but CLI version 0.1.0 does not provide `status` or `logs` commands. The website account area only shows the username and logout.

Acceptance criteria:

- Authenticated participants can see their current submission, validation state, validation errors, league state, latest included run, and official artifact availability.
- CLI provides documented status and log-download commands.
- Website and CLI use the same API semantics and actionable language.

### P0: API documentation is not routed in production

FastAPI provides documentation internally, but the public reverse proxy sends `/docs` to the web application, which returns 404.

Acceptance criteria:

- `/docs`, `/openapi.json`, and `/redoc` reach the API service over HTTPS.
- Production smoke tests validate the documentation page and OpenAPI document.

### P0: Competition state is misleading and can appear permanently stuck

Verified production state after submission:

- Queue generation requested: 1
- Queue generation completed: 0
- Worker running flag: false
- Active participant submissions: 1

The worker intentionally waits until at least two active bots exist. The public API only exposes `pending`, and the UI maps both pending and running to “A league run is in progress.”

Acceptance criteria:

- League state distinguishes idle, waiting for players, running, completed, and failed.
- Waiting state states the minimum and current active-bot counts.
- Running state exposes measurable progress and timestamps.
- Failures expose a safe, actionable error.
- Runs have a deadline and cannot remain silently running without heartbeat or progress.

### P1: Duplicate downloads can make the agent use a stale starter kit

Browsers rename repeated downloads, for example `alpha-poker-starter (1).zip`, while the copied prompt names only `alpha-poker-starter.zip`.

Acceptance criteria:

- Prompt tells the coding agent to find the newest matching Alpha Poker starter ZIP in Downloads.
- Agent verifies expected files before proceeding and reports the selected path.
- Regression test covers a suffixed duplicate filename.

### P1: Invite requirement is ambiguous

The registration field says “Invite code (if required),” while production requires an invite.

Acceptance criteria:

- Field says “Invite code.”
- Supporting copy says it is provided by the cohort organizer.

## Full end-to-end completion standard

A clean-slate pass succeeds only when a first-time tester, without repository access:

1. Creates and restores an account session.
2. Downloads the newest starter kit and copies the agent prompt.
3. Builds and validates a fresh bot.
4. Trains it against the hosted leader and receives readable logs.
5. Submits it through the agent-driven workflow.
6. Sees accurate waiting, running, failure, and completion states.
7. Completes an official round-robin heads-up league within the documented timeout once enough bots are active.
8. Appears on the refreshed Elo leaderboard.
9. Downloads official results and hand logs.
10. Opens working live API documentation.
11. Logs out and back in.

Release acceptance requires local tests, container smoke tests, live smoke tests, then two consecutive independent production passes using new accounts, new download directories, new bots, and no source access. QA data must use the `qa_e2e_` prefix and be removed or explicitly isolated after verification.

## Independent production pass 1

The first post-fix clean-slate pass completed every participant step except the
interactive API reference. `/docs` returned HTTP 200, but its page was blank
because the global Content Security Policy blocked Swagger UI's CDN script.
The browser reported `SwaggerUIBundle is not defined`. The pass also found
misleading validation-log copy claiming an optional validator was unavailable,
even though archive checks and isolated smoke execution had completed.

Remediation:

- Permit FastAPI's pinned Swagger UI CDN assets in the proxy policy while
  retaining the existing framing, connection, and default-source restrictions.
- Make deployment smoke tests load and inspect the rendered Swagger interface,
  rather than accepting HTTP 200 alone.
- Replace the misleading optional-validator line with an explicit confirmation
  that isolated smoke validation completed and the package was accepted.

All other pass-1 stages succeeded, including duplicate download handling,
training, submission, automatic official competition, visible Elo result,
validation and official artifacts, session persistence, logout, and login.

## Independent production pass 2

The next clean-slate tester completed the entire participant journey using only
the public website, copied instructions, and downloaded starter kit. The tester
created a new isolated account, preserved its session across reload, selected
the newest of multiple browser-renamed ZIP downloads, installed the bundled CLI
in a fresh environment, validated a distinct bot, trained for exactly ten hosted
hands, used the downloaded logs to revise it, submitted it, watched truthful
matchup progress, and received a completed official result. The live account
panel and leaderboard agreed on rank, Elo, and record. Both validation and
official artifacts downloaded successfully and contained the documented files;
the official JSONL contained the expected 600 hands for three matchups. Swagger
rendered the account-status operation with no browser-console errors, and logout
plus returning login succeeded.

One low-severity copy defect remained: the account panel displayed `1 wins`
instead of `1 win`. The shared record formatter now handles singular and plural
win/loss labels, with a rendered-source regression test. The first correction
exposed the irregular plural edge case `losss` in the next clean-slate test and
was replaced with explicit `win`/`wins` and `loss`/`losses` forms. Because
production changed after these passes, they are recorded as successful
diagnostic evidence but do not count toward the final two consecutive
release-acceptance passes.

The next attempted clean-slate pass found that `train --output` treated a
directory as a file and crashed after the hosted hands had successfully
completed. The CLI now accepts either a directory or an explicit `.zip` path,
uses consistent behavior with `logs --output`, documents both forms, and has
regression coverage for existing and new destination directories. CLI status
copy now uses the same correct singular/plural win-loss labels as the website.
This changed production behavior, so the consecutive acceptance counter resets.

## Final release acceptance

The exact production build deployed after the directory-output correction then
passed two consecutive independent black-box journeys. Neither tester had
repository, source, database, server, AWS, or operator access. Each used a new
`qa_e2e_` account, a fresh download and work tree, an isolated CLI home, and a
new bot. No code or deployment changed between the two passes.

### Consecutive pass A

- Registration, reload persistence, duplicate downloads, newest-ZIP selection,
  copied instructions, and all starter-kit documentation passed.
- The isolated bundled CLI built and validated a fresh bot, authenticated the
  participant, and completed exactly ten hosted training hands with `--output`
  targeting a directory. The training ZIP had the documented files and exactly
  ten JSONL hands.
- After log-driven bot revision and revalidation, submission succeeded. The
  official four-player league displayed truthful progress and completed all six
  matchups in about eleven seconds.
- CLI status, account UI, and leaderboard agreed on rank, Elo, and a correctly
  pluralized 2-win, 1-loss record.
- Validation logs and the five-file official artifact downloaded successfully;
  JSONL, CSV, PHH, and manifest counts agreed on 1,200 hands.
- Swagger rendered `GET /v1/account/status` with zero console errors. Browser
  logout and returning login succeeded.

### Consecutive pass B

- A second new participant independently repeated account creation, persistence,
  duplicate-safe starter selection, copied-agent workflow, isolated CLI setup,
  build, validation, authentication, and exactly ten hosted training hands to a
  destination directory.
- Training artifacts contained exactly ten hands. The tester reviewed them,
  revised and revalidated the bot, submitted it, and observed truthful official
  progress through all ten matchups of a five-player league within the timeout.
- CLI, account UI, and leaderboard agreed on rank, Elo, and a grammatically
  correct 3-win, 1-loss record.
- Validation output and all five official files downloaded. JSONL, CSV, PHH,
  and manifest counts agreed on 2,000 hands at 200 hands for each pairing.
- Swagger rendered the account-status operation with zero console errors, and
  both browser and CLI logout/login flows succeeded.

The invite handoff files were deleted after registration. Disposable accounts
remain clearly isolated by their `qa_e2e_` prefix so no real participant data
was changed during verification.

## Agent-led rookie tutorial, isolated pass 1

A fresh agent received only the production-style local website, its copied
prompt, downloaded starter kit, a local API override, and disposable cohort
inputs. It did not read source or contact production. The agent showed the six
capabilities and their Elo effects, fetched the real seeded top three, invited
the participant to chase the podium, and stopped before taking action. After a
simulated **Build my first bot** choice, it completed Create, Build, a ten-hand
Practice session, log-driven improvement, revalidation, approval-gated
submission, and truthful waiting-for-players status without exposing commands
or secrets to the participant.

The pass found three onboarding risks:

- The landing page briefly showed preview standings before hydration replaced
  them with the local league. The server now fetches initial standings from the
  API and uses preview data only when the API is unavailable.
- Clipboard automation could fail silently before the browser clipboard was
  initialized. The existing fallback remains, and the button now exposes a
  visible, accessible failure state with a retry action when neither path works.
- Registration accepted the cohort invite only as a command argument. The CLI
  now discovers whether an invite is required and requests it through a hidden
  interactive prompt by default. The flag remains for controlled automation.

The prompt also now states that local creation and validation precede account
setup, and that an accepted bot waiting for more players is active while its
Elo remains unchanged. A second fresh pass is required after these changes.

## Agent-led rookie tutorial, isolated pass 2

A second clean-slate agent used only a fresh localhost website, its downloaded
starter kit, and disposable cohort inputs. It did not inspect the repository,
containers, database, or production. The landing page's first render matched
the live local top three, and the Copy instructions control succeeded on its
first click with visible status feedback. The opening followed the required
order, showed the six-capability table and current podium, invited the student
to compete, and stopped before any setup or bot changes.

After the simulated **Build my first bot** choice, the agent completed Create,
Build, Practice, and Compete. It validated a unique bot, registered using
hidden password and invite prompts without an invite argument, completed a
200-hand practice match, found a specific post-flop leak in the hand evidence,
improved and revalidated the bot, and stopped for explicit approval before
submission. Once approval was simulated, the bot was accepted. The API and
public leaderboard correctly remained in a waiting state with no Elo change.
No commands, raw output, or secrets appeared in participant-facing prose.

The pass identified two remaining low-scope product issues. CLI status exposed
the correct accepted and waiting facts but did not explain their meaning, so it
now says that the official run has not started and that Elo is unchanged or not
yet assigned. The signed-out header briefly rendered **Account** before
changing to **Log in**, so its server and first client render now use **Log in**.
The workflow documentation was also aligned with the prompt's local-first
ordering. The tester's local-API override is an intentional QA-only condition;
the public starter kit continues to target the hosted service.
