# Open-source release audit

Date: September 5, 2026
Release branch: `codex/community-platform`
Repository: `sethusehitch/alpha-poker`

## Result

The repository is safe to make public after the release pull request passes CI.
No credential, private key, participant record, database, Terraform state,
private hand log, or local environment file is present in the release tree or
the existing Git history.

## Scope and evidence

- Reviewed the complete reachable history. Before this release it contained
  one commit, `9e4481d` (`Build Alpha Poker MVP`).
- Scanned every historical text blob and the release worktree for AWS access
  key IDs, GitHub token formats, PEM/OpenSSH private-key headers, and common
  embedded credential assignments. No real secret signature matched.
- Reviewed tracked filenames for environment files, credentials, tokens,
  passwords, private keys, Terraform state/plans, SQLite databases, screenshots,
  and attachments. None are tracked.
- Confirmed `.env*` (except `.env.example`), `*.pem`, `data/`, `*.tfstate*`,
  `*.tfplan`, `*.tfvars` (except examples), `.terraform/`, virtual environments,
  build output, and dependency directories are ignored.
- Reviewed all token/password search hits. They are parameter names,
  environment-variable references, redaction tests, or plainly marked local
  test fixtures.
- Rebuilt the public starter ZIP and verified it contains only the documented
  bot template, agent workflow, API guide, and dependency-free CLI source.
- Ran both `npm audit` and `npm audit --omit=dev`: zero known vulnerabilities.

## Classified non-secret historical value

The original private commit mentioned the local AWS CLI profile label
`hitch-personal`. A profile label is not a credential and grants no access. The
release head replaces it with `default` or `your-profile`; the historical label
does not create a security boundary or require history rewriting.

## Release controls

- MIT license, contributor guide, Code of Conduct, security policy, CODEOWNERS,
  structured issue forms, pull-request template, and least-privilege CI are in
  the release.
- The repository remains private until this branch passes GitHub Actions.
- After publication, `main` must require pull requests, the `qa` status check,
  resolved conversations, and strict up-to-date checks; force pushes and branch
  deletion remain disabled. Only the maintainer account has merge access.
- GitHub private vulnerability reporting and dependency alerts are enabled as
  part of the publication step.

## Exclusions

The untracked local `product-concepts/` directory is unrelated user work. It is
not staged, committed, scanned as release content, or included in containers.
