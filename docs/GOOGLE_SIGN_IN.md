# Google sign-in setup and release gate

Status: implemented, disabled until the Google OAuth client is configured.
This uses the existing Lightsail API and SQLite accounts, not a new auth service.

## Google Cloud setup (project owner)

1. Choose a Google Cloud project owned by the app maintainer. Configure Google
   Auth Platform branding for Alpha Poker, homepage https://alphapoker.io, and
   the required support/contact information. Supply only reviewed, accurate
   privacy/terms URLs if Google requires them; do not invent declarations.
2. Create a Web application OAuth client. Set these exact authorized redirects:
   - https://alphapoker.io/browser-api/auth/google/callback
   - http://localhost:3001/browser-api/auth/google/callback (local development)
   - http://localhost:8080/browser-api/auth/google/callback (optional local Compose)
3. This server flow requests only `openid`, no Gmail/Drive/Calendar access, no
   offline access or refresh token. Use the audience appropriate for the league;
   do not choose Internal unless everyone belongs to that Workspace organization.
   Resolve any Google publishing/branding verification gates before enabling it
   for all participants. School-admin app restrictions may also need approval.
4. Put the client ID and secret in the server's existing protected environment
   configuration, never chat, Git, client bundles, or `NEXT_PUBLIC_*` variables:
   `ALPHA_POKER_GOOGLE_CLIENT_ID`, `ALPHA_POKER_GOOGLE_CLIENT_SECRET`.
   Set `ALPHA_POKER_GOOGLE_REDIRECT_URI` to the exact callback above and
   `ALPHA_POKER_PUBLIC_WEB_URL` to the corresponding site origin.
5. Login must start on the same origin as the configured callback. Use
   alphapoker.io, not www/temporary hostname, for the production sign-in flow.
   Alternate hosts show a link to the main site instead of starting a broken
   cross-origin cookie flow. A canonical redirect can streamline this later.

## User flow

- Existing username/password sign-in stays available when Google is disabled.
- New Google identity: Google -> invite code -> username + avatar/upload.
- Existing Google identity: sign in directly, no repeat invite.
- Existing password user: Profile -> Connect Google while signed in. Never
  silently merge accounts by email. An already-linked Google identity cannot
  be reassigned to a different user. Bots, ratings and avatars stay attached to
  the existing username.
- Google-only accounts have no usable password. CLI: `alpha-poker login
  --browser --no-open --api-url https://alphapoker.io/v1`. The human opens the
  printed URL, enters the code and explicitly approves. CLI polls every 3 seconds
  for up to 10 minutes, saves its own revocable session, and never sees a Google
  password. Existing CLI password login continues to work.
- Custom-image processing still uses the existing sanitized upload pipeline.
  If the avatar upload fails after account creation, retry without creating
  another account, or finish and edit the picture later.

## Security and data

Google code exchange is server-side. State, PKCE and nonce prevent login replay;
Google's maintained library checks ID-token signature, audience, expiry and issuer.
Only immutable Google `sub` is stored. Names, email and Google pictures are not
used to link or publicly identify players. Browser session and onboarding tickets
use HttpOnly cookies. New browser writes enforce same-origin requests. Redirects
are fixed local paths; there is no arbitrary return URL.

Additive tables only: google_identities, google_flows, google_signups,
browser_logins. Existing user and feature-request records are not reset.
Temporary flow records expire after 10 minutes and are pruned on new login starts.
CLI codes are single-use and user approval is required. No permission is granted
to a pending Google identity until the invite and username pass server checks.

## Before enabling production

- Run full QA, verify official Google sign-in with a real configured client.
- Test new/returning users, wrong invite, canceled consent, link collision,
  custom upload, password fallback and Google-backed CLI browser authorization.
- Verify canonical hostname and Secure/HttpOnly cookies behind Caddy.
- Ensure proxies do not log callback authorization codes or cookies.
- Snapshot SQLite; deploy the exact reviewed source using normal release controls.
- Roll back by clearing both Google credential environment values and restoring
  the prior application release if needed. Preserve additive tables and accounts.
  Google-only users will need Google re-enabled to regain access, so communicate
  outages rather than silently creating passwords for them.

Reference: https://developers.google.com/identity/openid-connect/openid-connect
