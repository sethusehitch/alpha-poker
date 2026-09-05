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

## Remaining trust assumptions

Python audit hooks and resource limits are defense in depth, not a security
boundary against deliberately hostile native-code attackers. All bot processes
still share the host kernel and API container user. There are no per-person
invitations, password recovery, multi-factor authentication, login rate limits,
or security event alerts yet.

Before public access, execute each bot in an ephemeral container or microVM with
no network namespace, read-only root filesystem, seccomp or equivalent syscall
filtering, strict cgroups, a disposable user namespace, and a hard outer
deadline. Add invitations, rate limits, audit events, secret rotation, and
off-host encrypted backups.

## Data classification

Store only usernames, password hashes, session digests, bot source packages,
play-money results, and hand logs. Do not collect real names, payment data,
financial account data, or real-money poker records in this prototype.
