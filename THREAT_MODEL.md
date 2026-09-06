# Alpha Poker local threat model

## Intended use

The current build is for a small, invited cohort on one operator-controlled
machine. Poker is play money only. Accounts identify participants and prevent
accidental cross-user submissions. They are not an internet-scale identity
system.

The landing page, standings, completed run metadata, and hand artifacts are
intentionally readable without an account in this prototype. "Private league"
means only registered cohort members can submit, train, or mutate state. Gate
the entire site before launch if standings themselves must be confidential.

## Controls implemented

- Passwords use salted scrypt hashes and are never logged.
- Session tokens are random, stored server-side only as SHA-256 digests, expire
  after 30 days, and can be revoked.
- The browser receives its token in an HTTP-only, same-site cookie.
- The CLI stores tokens in a mode-`0600` file scoped to the API URL.
- Training WebSocket URLs contain a separate, short-lived capability token.
  Uvicorn request access logging is disabled so that token is not copied into
  local or container logs. Startup and error logging remains enabled.
- Submission and training resources enforce account ownership.
- An optional shared cohort invite code gates new registration.
- Manual league runs require a separate operator token when authentication is
  enabled, preventing cohort accounts from scheduling unbounded work.
- ZIP paths, expanded size, manifest shape, action shape, and output size are
  validated.
- Each hosted bot runs in a separate Python isolated-mode subprocess with a
  clean environment and private empty working directory.
- The runner blocks filesystem access outside the Python runtime, filesystem
  writes, network sockets, shell commands, process creation, directory
  enumeration, and common dynamic-library escape paths.
- The runner applies CPU, address-space, file-size, file-descriptor, stack, and
  Linux process-count limits where the host supports them.
- Decision IPC has a hard deadline. A timeout kills the bot subprocess and
  forfeits the hand.
- League work is serialized, restart-recoverable, and bounded by hand-log
  retention.
- Inactive and rejected upload ZIPs are pruned while preserving the active bots,
  the published leader, and packages frozen into live training sessions.
- Feature-request titles, details, and feedback messages are treated as
  untrusted content: rejected outright if they contain C0/C1 control
  characters, and otherwise stripped of bidi-override/isolate and zero-width
  formatting characters before storage, matching the leaderboard's existing
  untrusted-name handling. They are always rendered as text, never as HTML.
- Feature-request creation and voting require an authenticated session.
  Feedback may be anonymous, is rate-limited by client IP, stores only a
  coarse browser/device category, and is automatically deleted after the
  configured retention window (90 days by default).
- Feature-request moderation (status change, hide/restore) requires an
  authenticated session whose username is in `ALPHA_POKER_OPERATOR_USERNAMES`.
  Those names are reserved at registration unless the server-only operator
  token is supplied directly to the API.
  Promotion to a GitHub issue additionally requires the exact
  `ALPHA_POKER_OPERATOR_TOKEN` value, mirroring `/v1/admin/runs`'s existing
  operator-token gate, and is idempotent so a retried or repeated request
  cannot create duplicate GitHub issues.
- The optional `GITHUB_TOKEN` used for `/contribute` reads and promotion is
  read only from the server process environment. No browser route accepts,
  forwards, or echoes either `GITHUB_TOKEN` or the operator token; the
  same-origin `/browser-api/*` proxy only ever forwards the visitor's own
  session cookie as a bearer token.
- Every GitHub-sourced issue URL is validated against the configured
  `https://github.com/{owner}/{repo}/...` prefix before being rendered as a
  link; GitHub-supplied label colors and any other styling are mapped through
  a fixed local table, never used directly, so a compromised or malicious
  upstream label cannot inject arbitrary styling or an off-repo link.

## Remaining trust assumptions

Python audit hooks and resource limits are defense in depth, not a security
boundary against deliberately hostile native-code attackers. All bot processes
still share the host kernel and API container user. There are no per-person
per-person invitations, password recovery, multi-factor authentication, or
security event alerts yet. Login attempts are bounded per client IP and failed
attempts are also bounded per normalized account.

Before public access, execute each bot in an ephemeral container or microVM with
no network namespace, read-only root filesystem, seccomp or equivalent syscall
filtering, strict cgroups, a disposable user namespace, and a hard outer
deadline. Add invitations, rate limits, audit events, secret rotation, and
off-host encrypted backups.

## Data classification

Store only usernames, password hashes, session digests, bot source packages,
play-money results, and hand logs. Do not collect real names, payment data,
financial account data, or real-money poker records in this prototype.
