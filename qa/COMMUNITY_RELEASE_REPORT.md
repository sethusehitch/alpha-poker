# Community feature release report

Date: September 5, 2026

## Shipped behavior

- `/feature-requests` publicly lists ideas with Top, New, and Planned views.
  Logged-in users can submit one idea, upvote or downvote once, switch their
  vote, and clear it.
- The lifecycle is `submitted`, `under_review`, `planned`, `in_progress`,
  `shipped`, or `declined`. Reserved operator accounts can moderate status and
  visibility.
- Approved requests can be deliberately promoted to GitHub Issues by an
  operator-only API. Promotion is single-flight and persisted as `creating`,
  `needs_reconciliation`, or `promoted`, so a process crash fails closed instead
  of silently creating duplicate issues.
- The global feedback widget accepts signed-in or anonymous notes. It retains
  only the page path without query/fragment and a coarse browser/device class.
  Feedback expires after 90 days by default. An unsent draft is tab-scoped and
  cleared after success.
- `/contribute` links to the public repository, explains the four-step pull
  request workflow, and shows a server-cached list of open issues and pull
  requests. GitHub URLs are reconstructed and exact-match validated for this
  repository before becoming browser links.

## Security and reliability

- Registration and login are IP-limited; failed login is also account-limited
  across IPs. Feature posting, voting, and feedback have scoped limits.
- Operator usernames cannot be claimed through normal registration. Initial
  operator registration requires the server-only operator token.
- GitHub credentials are optional, server-only, and never accepted or forwarded
  by a browser-facing route.
- GitHub reads use a ten-minute SQLite cache, one in-process refresh, and stale
  fallback. Mutations never happen from the public Contribute page.
- Text rejects control characters and removes bidi overrides and invisible
  formatting before storage. Display names are bounded in API and UI.
- Schema initialization migrates existing SQLite data in place. Deploys retain
  an online database backup, and rollback restores the prior release plus the
  matching database backup when a one-way migration must be reversed.

## Verification completed before publication

- Full local gate: production build, 10 landing-page render tests, 24 community
  render/contract tests, 4 container configuration tests, ESLint, 108 backend
  tests, 17 CLI tests, Python compilation, and deterministic starter-kit build.
- Dependency audit: zero known production or development vulnerabilities.
- Isolated Compose gate: rebuilt Caddy, web, and API images; all services became
  healthy; homepage, health, Swagger/OpenAPI, authenticated account status,
  training WebSocket, feature creation, voting, listing, and anonymous feedback
  passed through Caddy. The isolated volume and network were removed afterward.
- Browser gate at desktop and 390 by 844: account creation/logout, feature
  submission/voting, feedback draft recovery across navigation, anonymous
  feedback, mobile navigation landmark, no horizontal overflow, and visual
  layouts passed.
- Browser QA found and fixed a UTC/local date hydration mismatch. A clean-tab
  retest produced zero console errors and a cross-time-zone regression test now
  covers the boundary.

Production deployment, the acceptance findings they uncovered, their fixes,
and the final clean-slate passes are recorded in `qa/DEPLOYMENT_REPORT.md`.
