# Single-box hosting

The prototype is deployed as one Linux box running Caddy, the web app,
FastAPI, the match worker, and SQLite through Docker Compose. Terraform owns
the Lightsail instance, static IP, firewall, automatic snapshot setting, and
the Route 53 records for `alphapoker.io` and `www.alphapoker.io`.

Primary URL:

`https://alphapoker.io`

Transition/fallback URL:

`https://alpha-poker.32.186.80.108.sslip.io`

## Recommended first host

Use one Amazon Lightsail `Medium-4GB` Linux instance with public IPv4:

- 2 vCPUs
- 4 GB memory
- 80 GB SSD
- 4 TB included transfer in most regions
- $24 USD per month

AWS lists the current bundle details in its
[Lightsail instance documentation](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html).
The IPv6-only version is $20 per month, but the $24 public IPv4 plan is the
simpler prototype choice.

Keep SQLite and uploaded ZIPs on the instance volume. Caddy terminates HTTPS
once a domain is attached. Do not add a managed database, load balancer, or
separate container service for this scale.

## Expected bill for 20 participants

Assuming 20 people each upload once per day:

| Item | Expected monthly cost |
| --- | ---: |
| Lightsail 4 GB instance | $24 |
| Incremental snapshots | about $1 to $4 |
| DNS in Lightsail | $0 |
| Domain registration | typically about $1 to $2 monthly when annualized |
| Expected total | about $26 to $30 per month |

Lightsail snapshots cost $0.05 per stored GB-month, with successive snapshots
billed primarily for changed blocks. See the
[AWS snapshot pricing explanation](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html).
The 4 TB transfer allowance should be far above this prototype's expected web,
ZIP, WebSocket, and artifact traffic.

## Match and storage budget

With 20 active bots there are 190 unique head-to-head pairings. One full league
therefore runs:

`190 pairings × hands per pairing`

With isolated subprocess execution enabled, the local QA machine completed a
20-bot, 190-pairing run of 3,800 real hands in 19.1 seconds, about 199 hands per
second. It produced a 15.2 MB live database and a 0.27 MB compressed artifact.
Hosted bots and a burstable server will vary, so budget conservatively and keep
match concurrency at one on the first box. Re-run this check with
`npm run benchmark:20`.

Running a complete league after every one of 20 daily uploads multiplies both
compute and logs by 20. At 2,000 hands per pairing, that is 7.6 million hands
per day. The bounded live-hand and compressed-artifact retention prevents
unlimited disk growth, but a run at that sample size may take hours on the
first box. The recommended prototype policy is:

1. Run 200 hands per pairing while validating the product.
2. Coalesce uploads arriving within a short window into one run.
3. Keep the current run and one prior run's detailed hands in SQLite. This is
   implemented and configurable with `ALPHA_POKER_RETAINED_HAND_RUNS`.
4. Preserve the newest 30 compressed run artifacts. This bound is implemented
   with `ALPHA_POKER_RETAINED_ARTIFACT_RUNS` and can be lowered if disk pressure
   appears.
5. Remove rejected and inactive submission ZIPs after no current league,
   published leader, or live training session needs them. This is implemented.
6. Raise the hand count toward 2,000 or more when participants want narrower
   confidence intervals.

The leaderboard always shows its 95% interval, so a small early run is clearly
marked as uncertain rather than presented as conclusive.

## Deploy and operate

AWS CLI and Terraform use the `hitch-personal` profile by default. The apply
script creates a dedicated local deployment key at
`~/.ssh/alpha-poker-lightsail`, detects the current public IP for restricted
SSH, validates the Terraform, and applies a saved plan:

```bash
AWS_PROFILE=hitch-personal ./ops/aws/apply-infra.sh
AWS_PROFILE=hitch-personal ./ops/aws/deploy.sh
```

The deployment command keeps application state in Docker volumes, creates the
cohort invite and operator token only on the server, retains three source
releases, waits for healthy containers, and runs HTTPS plus WebSocket smoke
tests. Retrieve the credentials only when needed:

```bash
./ops/aws/show-access.sh
```

This command is for the league operator, not participants. It uses the local
deployment SSH key to read two values that are generated and stored only in the
server's private environment file:

- `ALPHA_POKER_INVITE_CODE` is shared with invited participants when they need
  to create an account.
- `ALPHA_POKER_OPERATOR_TOKEN` authorizes manual administrative league runs.
  Normal participants and automatic upload-triggered runs do not need it.

Keeping both values off the public site and out of source control prevents
visitors from enrolling themselves or invoking operator-only actions. Running
`show-access.sh` does not rotate or change either value; it only displays them
on the operator's Mac when they need to be copied.

Terraform state is local and intentionally ignored. Keep
`infra/aws/lightsail/terraform.tfstate` backed up privately until state is
moved to a remote backend. To inspect a destroy plan without applying it:

```bash
terraform -chdir=infra/aws/lightsail plan -destroy
```

Route 53 points the apex and `www` hostnames at the Lightsail static IP. Caddy
serves those names plus the sslip.io fallback and obtains certificates
automatically. Before inviting untrusted public users, replace the cohort-grade
subprocess boundary with an ephemeral container or microVM sandbox.

If sustained league runs saturate CPU, move the worker first. The landing page,
API, and SQLite do not justify a larger architecture at 20 users.
