# Alpha Poker production deployment report

Date: September 5, 2026

## Release

- Public repository: `sethusehitch/alpha-poker`
- Production: `https://alphapoker.io` and `https://www.alphapoker.io`
- Hosting: one Terraform-managed AWS Lightsail 4 GB Ubuntu instance with a
  static IP, Caddy, the web service, API service, and a persistent SQLite volume
- Delivery: protected pull requests with the required `qa` check, followed by
  the timestamped release deploy script and automatic HTTP, API, OpenAPI, and
  WebSocket smoke tests

`main` requires a pull request, an up-to-date passing `qa` check, resolved
conversations, and squash merge. Force pushes and branch deletion are disabled.
The repository is public, while production invite, operator, session, and AWS
credentials remain server-side and untracked.

## Verification

- Full local gate: production build, 10 landing-page tests, 26 community tests,
  4 container tests, zero-warning lint, 109 API/engine tests, 17 CLI tests,
  compilation, and deterministic starter-kit generation
- Dependency gate: production and full npm audits report zero known
  vulnerabilities; the published pytest advisory is fixed
- Container gate: a clean, isolated three-service Compose stack built, became
  healthy, passed homepage, API, docs, authenticated upload, and WebSocket
  checks, and was removed with its test volume
- Infrastructure gate: Terraform format and validation pass; the authenticated
  production plan reports no drift
- Production gate: apex and `www` HTTPS, health, API proxy, Swagger/OpenAPI,
  GitHub cache, social preview asset, branded 404, and all three container health
  checks pass
- Concurrency gate: a ten-hand participant training session completed in seven
  seconds while the 10-bot official round robin was actively running

## Independent acceptance and remediations

Four clean-slate agents used the deployed product like participants without
source or operator access. Early passes found retained invite input, training
lock contention, CLI credential-home leakage between local testers, missing draw
copy, an auth-state flash, and a dead-end 404. Protected pull request 3 fixed
them with regression coverage. Two new independent passes then completed the
website, starter kit, validation, training, submission, league, logs, community,
mobile, documentation, and session journeys. The last CLI-only follow-up adds
draws to `status` and converts non-TTY password EOF into a friendly error.

QA-created public entries are hidden only after a timestamped SQLite backup.
Accounts and historical rows are retained for auditability. No participant
secret or hand-log content is included in this report.

## Deliberate limits

The server-side GitHub token is intentionally unset, so the Contribute page can
read public issues and pull requests but operator promotion returns the safe
`github_not_configured` response. Enabling promotion later requires a
fine-grained, Issues-write token on the server; no browser route accepts it.

This remains a trusted-cohort prototype. Bot isolation is defense in depth, not
a hardened hostile-code boundary. Rollback uses the prior timestamped release
and its database backup; daily Lightsail snapshots provide instance recovery.
