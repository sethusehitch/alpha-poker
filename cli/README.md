# Alpha Poker CLI

The CLI has no runtime dependencies beyond Python 3.11.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ./cli
alpha-poker register maya
alpha-poker validate ./starter-kit
alpha-poker submit ./starter-kit
alpha-poker train ./starter-kit --hands 5000
alpha-poker train ./starter-kit --hands 10 --output ./training-logs
alpha-poker status
alpha-poker logs --output ./alpha-poker-logs
```

The local API defaults to `http://localhost:8000/v1`. Override it with
`--api-url` or `ALPHA_POKER_API_URL`.

`register` and `login` save a revocable session token in
`${XDG_CONFIG_HOME:-~/.config}/alpha-poker/credentials.json` with mode `0600`.
Set `ALPHA_POKER_CONFIG` to an exact file path when you need a fully isolated
profile. Tokens are scoped to
the API URL and are never included in bot ZIPs. Use `alpha-poker whoami` to
check the account and `alpha-poker logout` to revoke the current token.
If the league uses a cohort code, add `--invite-code CODE` when registering.

`status` shows validation, whether the league is waiting or running, matchup
progress, and the latest Elo result. `logs` downloads your validation log and,
after a completed competition, the official ZIP containing hands and summary.
For training, `--output` accepts either a destination directory or an explicit
`.zip` filename. A directory receives a uniquely named training-log ZIP.

For automation, `ALPHA_POKER_TOKEN` overrides the saved token. Do not put that
environment variable in bot code or commit it to source control.
