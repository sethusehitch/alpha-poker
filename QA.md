# Alpha Poker QA record

Date: September 5, 2026

## Automated suite

Run from the project root:

```bash
npm run qa
```

Verified:

- Production vinext build succeeds.
- Ten rendered-page tests pass.
- Twenty-four community-surface tests pass, covering `/feature-requests`,
  `/contribute`, the six-stage lifecycle, anonymous feedback, responsive and
  accessible controls, exact GitHub URL validation, draft recovery, and
  deterministic server/browser date rendering.
- Four single-box container configuration tests pass.
- ESLint passes with zero warnings.
- 109 poker engine, auth, queue, isolation, retention, migration, community, and
  FastAPI tests pass.
- Seventeen CLI tests pass.
- Python compilation passes for the CLI, benchmark, starter kit, and server.
- The public starter ZIP rebuild is byte-deterministic and contains the bot
  template, API and agent-workflow guides, plus the dependency-free CLI source.
- Duplicate browser downloads are safe: the copied prompt and starter workflow
  select the newest `alpha-poker-starter*.zip`, verify its contents, and report
  the exact selected file before operating.
- Participant status distinguishes validation, waiting for another bot, queued,
  running with matchup progress, completed with Elo and artifacts, and failed
  with an actionable message. Regression coverage verifies the single-bot wait
  is never described as an active run.
- Official runs store start and heartbeat timestamps, completed and total
  matchups, and an enforced run deadline with a durable failure reason.
- The CLI waits for upload validation, exposes `status`, and downloads both
  validation output and official hand logs through `logs`.
- Training `--output` accepts a directory or an explicit ZIP filename; the
  directory case that previously lost a completed session's download has direct
  regression coverage.
- The starter guide never asks the participant to open a terminal or manually
  run the submission command. Claude, ChatGPT, or Codex operates the bundled
  CLI after the participant pastes the website prompt.
- A real API test accepts 20 active bot packages, completes all 190 mirrored
  pairings, and returns a 20-row leaderboard with contiguous ranks and correct
  per-player hand totals.
- Both the production-only and complete dependency audits report zero known
  vulnerabilities. The Vinext, Vite, Wrangler, and Cloudflare packages were
  upgraded and the unused Drizzle/D1 starter scaffolding was removed.

Two upstream deprecation warnings remain in FastAPI's current Starlette test
client dependencies. They do not affect runtime behavior.

## Browser QA baseline

The previously deployed functional baseline was tested through the in-app
browser against the live API:

- Desktop page order is hero, leaderboard, then instructions.
- Both hero buttons scroll to the correct section.
- The current leader and rows are replaced with live API data.
- The copy-to-agent button copies and displays its accessible confirmation.
- At 390 by 844 pixels the leaderboard becomes a compact list.
- Mobile document width equals viewport width, with no horizontal overflow.
- Browser console contains no warnings or errors.
- The starter ZIP URL returns successfully.
- Registration, logout, failed login, returning login, and session persistence
  across a reload work through the HTTP-only browser session cookie.
- The browser auth response never returns the raw API token to JavaScript.

The selected logo, refined hero typography, podium, instructions, and account
status panel have completed build, rendered-page, container, and browser QA.

## Live three-player league

Three different users submitted active packages through the real CLI:

| User | Bot |
| --- | --- |
| `leo` | `PressureBot` |
| `maya` | `SteadyCaller` |
| `sam` | `TightFold` |

An official run used seed `424242`, 200 mirrored hands per pairing, and 600
total hands. Results were:

| Rank | Bot | bb/100 | 95% interval | Hands |
| ---: | --- | ---: | ---: | ---: |
| 1 | PressureBot | +17.25 | [0.40, 34.10] | 400 |
| 2 | SteadyCaller | +14.50 | [-2.03, 31.03] | 400 |
| 3 | TightFold | -31.75 | [-38.51, -24.99] | 400 |

Scores sum to zero, as required in a closed heads-up league. A second run with
the same seed, packages, rules, and hand count produced identical standings,
intervals, and hand records.

The artifact ZIP contained 600 JSONL hand records plus PHH, CSV, manifest, and
plain-language summary files. The interval crossing zero for SteadyCaller is
intentional and shows the site does not pretend a small sample is conclusive.

## Training WebSocket

The real CLI played four hands against the frozen current leader and downloaded
a ZIP containing `summary.json`, `events.jsonl`, and `hands.jsonl`.

Additional tests cover:

- 250 ms deadline reporting
- direct hand forfeits for timeout and illegal actions
- legal action conversion
- stale-turn rejection
- idempotent action retries
- sequence-based reconnection and replay
- freezing the exact first-place submission
- downloadable training artifacts

## Engine verification

- 1,000 randomized hands preserved chip conservation and JSON serialization.
- 3,000 evaluated hands and 10,000 pairwise comparisons matched the independent
  `treys` evaluator.
- Duplicate deals reverse seats while retaining the same deck.
- Confidence intervals cluster each mirrored pair together.

## Community surfaces: feature requests, feedback, and contribute

Backend (FastAPI/SQLite) test coverage for `/v1/feature-requests`,
`/v1/feedback`, `/v1/github/issues`, and `/v1/config`:

- Reading the feature-request list and submitting feedback are public;
  creating and voting require the same authenticated session as the rest of
  the API. Signed-in feedback is attributed to the account and signed-out
  feedback is stored anonymously.
- A new feature request always starts `submitted`; status updates accept all
  six lifecycle values (`submitted`, `under_review`, `planned`, `in_progress`,
  `shipped`, `declined`); a status value that is not one of these six (for
  example, written by a hypothetically newer release) is served back as
  `submitted` rather than a raw string.
- The Top, New, and Planned tabs sort correctly, an unrecognized `tab` value
  falls back to Top, and Planned includes exactly `planned`, `in_progress`,
  and `shipped` requests, ordered planned-first.
- Voting is idempotent per request/user pair: upvote, switch to downvote, and
  clear all update the score correctly and are reflected in both the voter's
  and an anonymous viewer's view of `my_vote`.
- Title and details are rejected outright on C0/C1 control characters and
  otherwise stripped of bidi-override and zero-width formatting before
  storage; duplicate titles are rejected with `409 duplicate_request`.
- Status changes and hide/restore are operator-username-gated and return
  `403` for a non-operator; promotion to a GitHub issue additionally requires
  the exact operator token, is idempotent (a second promotion call returns the
  original issue instead of creating a duplicate), and returns
  `503 github_not_configured` without a server-side `GITHUB_TOKEN`.
- The GitHub issue/PR summary is cached in SQLite for 10 minutes, a fetch
  failure with an existing cache serves it with `"stale": true`, and a fetch
  failure with no cache returns `503 api_unavailable`. Issue URLs returned to
  the client are always rebuilt from the configured repository, never trusted
  from the upstream API response.
- Per-account/IP rate limits on feature-request creation, voting, feedback,
  registration, and login return `429 rate_limited` once exceeded. Failed
  login attempts are also limited by normalized account across source IPs.
- `GET /v1/config` is public and unauthenticated, and reports
  `auth_required` truthfully for both local and hosted configurations.
- Re-running schema initialization against an already-migrated database
  preserves existing feature requests and votes without data loss.

Frontend (rendered-HTML/static-contract) coverage:

- `/feature-requests` and `/contribute` render their hero, tabs, GitHub-outage
  fallback copy, and accessibility landmarks with no FastAPI instance
  reachable, and never leak a raw `error.code` or status string.
- Deep-linking `?tab=new` and `?tab=planned` selects the right tab.
- Neither page renders any excluded content: `bb/100`, confidence intervals,
  Discord links, or feature-request comment counts.
- `StatusChip` implements exactly the six lifecycle statuses (no `open` or
  `not_planned` remnants) and falls back unknown values to `submitted`.
- The feedback widget accepts signed-out submissions with explicit anonymous
  copy. Its unsent draft survives full-page navigation in tab-scoped
  `sessionStorage`, clears after success, and never uses `localStorage`.
- Feature-request dates use a fixed UTC formatter so SSR and browser hydration
  match in every client time zone.
- No browser-facing `/browser-api/*` route accepts, forwards, or otherwise
  handles the operator token or `GITHUB_TOKEN`; there is no browser route for
  promotion.
- The feedback FAB and the account chip mount on `/`, `/feature-requests`, and
  `/contribute`; the shared header stays 72px and is sticky only on the two
  community pages.

## Automatic upload-to-league behavior

An accepted upload queues a league automatically once two active bots exist.
Only one league worker runs at a time. Uploads accepted during a run increment a
durable SQLite generation, which coalesces them into one follow-up league instead
of launching overlapping tournaments. Tests cover queue persistence, recovery
after a restart, cancellation, and automatic two-player league completion.

## Bot isolation and bounded storage

- Every uploaded bot runs in a separate Python process with a decision deadline,
  256 MB address-space limit, bounded output, restricted environment and working
  directory, and blocked network, subprocess, mutation, and host-file access.
- Tests verify safe standard-library imports while rejecting socket access,
  shell commands, directory listing, host reads, excessive output, and infinite
  loops. Worker processes are checked for cleanup after the suite.
- The newest two official runs retain detailed SQLite hands. The newest 30 run
  artifacts remain downloadable. Tests verify old hand rows and artifacts are
  pruned without changing historical standings.
- Inactive and rejected upload ZIPs are removed after it is safe to do so. The
  active packages and the exact currently published leader remain available,
  including while a nonexpired training session has them frozen.
- A real 20-bot benchmark completed 190 pairings and 3,800 hands in 19.1 seconds,
  about 199 hands per second, using a 15.2 MB database and 0.27 MB artifact.
  Reproduce it with `npm run benchmark:20`.

## Containers

All three production images were built in a 4 GB Colima VM. The exact Compose
topology was started from scratch with an isolated project, health-gated, and
smoke-tested through Caddy. Caddy's configuration is baked into its image so
the stack does not depend on a host bind mount. Verified through Caddy:

- Homepage
- Health endpoint
- Leaderboard proxy
- `/api/v1` prefix rewrite
- Real WebSocket upgrade and events
- Persistent SQLite volume
- Registration and bearer-authenticated upload
- Browser-cookie participant status and binary validation/official-log downloads
- Automatic league execution in isolated bot subprocesses
- Truthful one-bot waiting state and two-bot completion state
- Run summary and five-file artifact download
- Public Swagger/OpenAPI routing

The isolated QA stack and its named test volume were removed after the pass.

## Hosted AWS verification

The Terraform-managed Lightsail deployment at `https://alphapoker.io`, with
the sslip.io transition hostname retained as a fallback, is verified end to end:

- Terraform validate and format checks pass, followed by a zero-change drift plan.
- The 4 GB Ubuntu instance is running on its attached static IP.
- Ports 80 and 443 are public; SSH is restricted to the operator IP and the
  Lightsail browser-console network.
- Automatic daily snapshots are enabled for 10:00 UTC.
- Caddy serves a trusted Let's Encrypt certificate and the security headers.
- Caddy, web, and API containers report healthy with about 2.8 GB memory
  available after deployment; the 2 GB swap file is active.
- External homepage, API health, league metadata, account, HTTPS, and training
  WebSocket smoke checks pass.
- Public `/docs`, `/redoc`, and `/openapi.json` are routed to FastAPI on both the
  apex and `www` domains. Deploys force-recreate services so Caddy's immutable
  release-directory bind mount cannot remain attached to stale configuration.
- The HTTPS proxy regression test verifies that training sessions return a
  `wss://` endpoint.

## Final independent production acceptance

Four independent, clean-slate participant agents tested production without
repository, server, database, AWS, or operator access. The first two passes
found and reproduced a retained registration-form secret, official-league lock
contention during training, shared CLI credentials that ignored
`XDG_CONFIG_HOME`, a logged-out copy flash, missing draw records, and a dead-end
404. Each issue received a regression test and was fixed through protected pull
request 3 before acceptance restarted.

Two new independent agents then repeated the journey with fresh accounts,
download directories, bots, and isolated CLI homes. Both passed registration,
reload persistence, logout/reopen field clearing, copied instructions, local
validation, exactly ten hosted training hands, readable logs, accepted upload,
truthful league progress, feature submission and voting, feedback, Contribute,
mobile layout, API documentation, branded 404s, and returning login. A separate
ten-hand training session also completed in seven seconds while a 10-bot,
45-matchup official league was running, proving that training no longer waits
behind the league lock.

The final agents exposed two narrow CLI presentation defects: status omitted
draws, and password prompting without a TTY surfaced a Python EOF traceback.
The final release prints draws when present and turns noninteractive password
input into a concise, actionable error. Both behaviors have direct regression
coverage. QA-only public standings and request artifacts are hidden after a
recoverable production database backup; the disposable accounts are retained
privately for auditability.

## Final deployment audit

After the two consecutive passes, a read-only completion audit confirmed:

- Terraform formatting and validation pass, and the live Lightsail plan reports
  no changes or infrastructure drift.
- The apex and `www` hostnames both return HTTP/2 200 over HTTPS.
- The production homepage, health endpoints, API proxy, Swagger HTML, CSP,
  OpenAPI account-status route, and a real authenticated training WebSocket pass
  the release smoke suite.
- The Caddy, web, and API containers are all running and healthy.
- The final 10-bot acceptance league completed all 45 matchups before QA data
  cleanup; the queue has no pending generation and no running worker.
- The deployed OpenAPI document contains 25 paths, including
  `/v1/account/status`.

The final local suite for this release passed the build, lint, compilation,
starter-kit rebuild, 109 server tests, 17 CLI tests, 10 rendered-page tests, 24
community-surface tests, and four container-configuration tests.

## Completion matrix

| Requirement | Release evidence |
| --- | --- |
| Clear invite-only account creation | Required organizer-provided invite copy, auth regression tests, and two new live registrations |
| Duplicate-safe starter download | Newest-match prompt and workflow checks, regression coverage, and two double-download live passes |
| Copy prompt to a coding agent | Render/copy coverage and both independent passes using the copied prompt as their sole guide |
| Build and validate | Contract and isolation tests plus two distinct live bots validated from fresh kits |
| Hosted leader training | WebSocket protocol tests, release smoke, and two exact ten-hand participant sessions |
| Readable training logs | Both passes verified summary, events, and exact JSONL hand counts before revising their bot |
| Agent-operated submission | Copied prompt assigns CLI operation to the coding agent; both black-box agents submitted end to end |
| Truthful progress and failures | Account-status API/UI/CLI regression tests; passes observed incremental matchup progress |
| Bounded competition | Durable heartbeat/deadline tests; final leagues completed 6/6 and 10/10 well within the limit |
| Refreshed Elo leaderboard | Account, CLI, and public leaderboard rank/Elo/record agreed, including explicit draw counts |
| Official results and hand logs | Validation plus five-file official artifacts downloaded and counts reconciled in both passes |
| Working API documentation | Proxy/CSP tests, release smoke, and rendered Swagger with zero console errors in both passes |
| Logout and returning login | Browser and CLI session tests plus successful final logout/login in both passes |
| No silently stuck worker | Deadline and heartbeat regression coverage; final live queue completed, idle, and not pending |
| Isolated QA data | Fresh accounts/directories per pass; public QA artifacts hidden only after a recoverable database backup |

## Deliberate prototype limits

- Username/password auth is intended for a small, trusted private cohort.
  Registration and login are rate-limited, but there is no password reset,
  email verification, or MFA yet.
- Bot process isolation is defense in depth, not a hardened multi-tenant sandbox
  for hostile public code.
- One league and one serialized match worker
- Lightweight PHH summaries rather than fully replayable action streams
- No remote Terraform state or automated off-instance application-data backup yet

Do not expose the current build to untrusted public participants. A stronger
container or microVM sandbox, request rate limits, secrets management, and
production monitoring remain gates for that phase.
