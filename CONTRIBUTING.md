# Contributing to Alpha Poker

Thanks for helping make Alpha Poker better. The project welcomes bug reports,
feature ideas, documentation improvements, tests, and focused pull requests.

## Before you begin

- Read the [Code of Conduct](CODE_OF_CONDUCT.md).
- Search existing issues and feature requests before opening a duplicate.
- For a larger change, open an issue first so the approach can be discussed.
- Never include real invite codes, tokens, passwords, hand logs, or participant
  data in an issue, commit, screenshot, or test fixture.

## Local setup

Requirements: Node.js 22 or newer, Python 3.12 or newer, and Docker for the
container checks.

```bash
npm ci
python3 -m venv server/.venv
server/.venv/bin/pip install -r server/requirements-dev.txt
npm run qa
```

To run the complete local stack:

```bash
./ops/up.sh
```

The website is available at `http://localhost:3001` during frontend-only
development. The containerized site uses the port configured in `.env`.

## Pull requests

1. Fork the repository and create a short, focused branch.
2. Add or update tests for behavior changes.
3. Run `npm run qa` and, for infrastructure changes, the container checks.
4. Open a pull request using the template and link the related issue.
5. Address review comments. A maintainer merges after required checks pass.

Use clear commit messages and keep generated files, unrelated formatting, and
dependency updates out of feature pull requests. The maintainers generally use
squash merging so each pull request becomes one readable change on `main`.

## Good first contributions

Issues labeled `good first issue` are intentionally scoped for new
contributors. Issues labeled `help wanted` are ready for community help. The
live list is also available on the Alpha Poker Contribute page.

## Reporting security problems

Do not open a public issue for a vulnerability. Follow [SECURITY.md](SECURITY.md)
instead.
