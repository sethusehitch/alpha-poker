# Summit strengthening, resumed September 8

Goal remains active. No policy in this research directory is installed or accepted.
The complete raw evidence lives at the path in `CHECKPOINT.json`; this directory
keeps compact evidence and the exact experimental sources in Git.

## Findings

- v16 replaces fixed action thresholds with sampled opponent ranges and expected
  values for several legal bet sizes. It won 80/110 matched reference series,
  versus 70/110 for the original range prototype. No individual drop exceeded
  two wins. It failed fresh Mirage acceptance at 16/20 in both batches.
- v17: increased sampling. v18: separate card inference from fixed style priors.
  v19: one additional re-raise response layer. v20: stronger style priors guided
  by public aggression. v21: preflop realization penalty. v22: higher sampling
  with the v20 model. v23: noisy-equity threshold likelihood. v24: cross-hand
  Bayesian style evidence. None established acceptance.
- v20 won 82/110 matched references and 19/20 against both Mirage and Spark in
  the matched development screen, but failed fresh acceptance at 17/20 twice.
- v25-v27 replace linear chip value with concave utility, a tournament heuristic
  that values retaining chips for future play. Powers 0.6, 0.4, and 0.8 were
  declared as a small development grid. v26 won 20/20 against both Mirage and
  Spark in that screen; it is frozen for acceptance and reference checks.
- v28 is a separate multi-street rollout prototype, reusing the public hand
  state machine with entirely synthetic deals. It is not the nominated v26.

These are approximate models, not GTO solvers or universal-strength claims.
Risk-sensitive utility approximates ties through equity and does not explicitly
solve the future tournament. A favorable tuning batch does not certify strength.

## Local integration preparation

`codex/dojo-recovery` includes origin/main through 8f0b017, preserving Google
sign-in changes and both auth and dojo QA hooks. The starter ZIP was rebuilt
from merged sources. Website build, 8 focused navigation/auth tests, and 33
API auth/dojo tests passed. No deployment occurred.

After a candidate passes every gate, update only Summit, assign it a distinct
opponent version, preserve prior opponents' progress, recalibrate or mark its
rating pending, regenerate both server/CLI assets, and run full local QA.
