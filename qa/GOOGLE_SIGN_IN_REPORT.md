# Google sign-in implementation check

Branch: codex/google-signin, based on main 2ed9676.

## Implemented

- Continue with Google alongside existing password login.
- Invite-gated Google signup, public username, four existing avatars or custom
  cropped upload. Compact layout follows the approved mockup.
- Returning Google login skips registration; Profile can connect Google to an
  existing password account without moving the user's data.
- CLI browser authorization with explicit human approval, single-use code,
  ten-minute timeout, and independent revocable session.
- Google button stays hidden until both server credentials are configured.
- No live records, invites, bot submissions or infrastructure were changed.

## Evidence

- Server Google/auth suite covers invite rejection/retry, reserved usernames,
  duplicate usernames, ticket consumption, password fallback, link collision,
  CLI approval and token single-use.
- Locally signed RSA ID-token fixtures pass through Google's actual verifier.
  Wrong audience, issuer, expiry, nonce and signature are rejected.
- `qa/google_auth_http.py` builds an isolated web app and temporary API/database.
  It tests actual same-origin web routes, HttpOnly cookies, rejected cross-origin
  writes, callback state binding, invite/signup, returning login, and CLI approval.
  The external Google exchange is mocked in this test only, not in product code.
- CLI tests confirm polling, saving credentials, no password prompt or token
  printing, safe URL requirements, and clean timeout without saving a session.
- Full `npm run qa` regression pipeline and production build run locally.
- Real Google consent completed by the owner on September 8. An isolated local
  database verified Google signup, invite entry, public username, Bear avatar,
  connected status in Profile, CLI approval, authenticated `whoami`, starter
  upload, and 20-hand practice with a downloaded training archive.
- Browser inspection caught a missing account-dialog host on the logged-out
  CLI page. Both signup and CLI now share the homepage backdrop and account
  dialog host. Screenshot checked the restored dimmed/blurred site backdrop.
- Returning real Google login and existing-password-account linking remain to
  be verified. Chrome paused automation because another extension UI was open.
- Synthetic installer tests verify mode-0600 credentials/backups, preservation
  of unrelated invite settings, no printed credentials, and rejection of a
  mismatched Google project without modifying the environment.

## Activation gate

The dedicated Google Cloud OAuth client and local configuration are created.
Remaining: complete real-provider acceptance, production configuration and
provider readiness checks, final regression/CI and coordinated release.
See `docs/GOOGLE_SIGN_IN.md`. Not merged or deployed while this gate is open.
