# Security policy

## Supported version

The latest code on `main` is the only supported version during the prototype.

## Report a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do
not open a public issue and do not include live credentials, participant data,
or private hand logs in a report.

Include a concise description, reproduction steps, affected version or commit,
and the practical impact. A maintainer will acknowledge the report as soon as
possible, investigate it privately, and coordinate a fix before disclosure.

## Scope notes

Alpha Poker runs untrusted bot packages in constrained containers, but this is
a prototype and should not be treated as a hardened multi-tenant execution
platform. See [THREAT_MODEL.md](THREAT_MODEL.md) for the current boundaries.
Poker uses play money only.
