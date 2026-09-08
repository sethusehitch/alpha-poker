# Competition E2E Friction Pass 13

## Result: PASS

Date: 2026-09-07 (America/Los_Angeles)

## Black-box scope

- Tested the running homepage and API only.
- Did not inspect product source or prior QA reports.
- Used an isolated, logged-out in-app browser session for the homepage smoke and current download-link discovery.
- Used a new temporary directory, fresh archive, fresh extraction, isolated CLI environment, and isolated CLI profiles.

## Safe evidence

### Homepage and starter kit

- `http://127.0.0.1:3019/` opened normally with the expected Alpha Poker title, leaderboard, instructions, and starter-kit control.
- The page's current starter-kit link was clickable and was used as the exact download URL.
- Fresh archive size: 29,068 bytes.
- SHA-256: `8c4ee0c5ea2c2bbfeebd02c53860034a272a9a970b516d2ec244f6a70ff62e62`
- Fresh extraction opened normally and contained `README.md`, `WORKFLOWS.md`, `API.md`, `bot.py`, `bot.json`, and the bundled CLI files.
- The bundled CLI installed successfully in a fresh virtual environment, and its top-level and relevant rivals help commands opened normally.

### Pending challenge status wording

- Created two fresh disposable test participants and submitted two simple bots.
- Both bots reached accepted, active status.
- Created a direct challenge and intentionally left it pending without recipient acceptance.
- Ran the human command `rivals status <pending challenge> --wait --timeout 1` once for the primary assertion, then repeated it three more times while the challenge remained pending.
- All four runs exited successfully.
- Every run reported `Still pending after 1 seconds.`
- Every run explained that the challenge was `waiting for the other player to respond.`
- `Still running` appeared zero times across all runs.

## Release gate

PASS. The pending challenge timeout is described as pending and waiting for the other player, never as still running. The homepage and freshly downloaded starter kit also passed smoke validation.
