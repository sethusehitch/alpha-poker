# Current continuation

Summit v27 has passed the tournament acceptance gates and is integrated locally
as `summit-v2`. The 40,000-hand local rating calibration and full application/CLI/recap QA passed.
The goal is complete locally; no deployment occurred. See
`qa/summit-research-2026-09-08/README.md` for the continuation evidence.
The remainder of this file is the original recovery snapshot.

# Dojo recovery, September 8, 2026

Recovered from the interrupted Codex task **Poker Site Ideas**
(`01a07402-1c93-75d0-baf0-6a29d575072a`). This checkout preserves commit
`606e861a5246a88e724f12b595609dfbbad71afc` on `codex/dojo-recovery`.
The original `codex/training-dojo` checkout remains untouched.

## Working feature

- `server/alpha_poker/dojo.py`: five packaged strategies.
- `cli/alpha_poker_cli/dojo.py`: fully local practice, evidence, and progress.
- `app/components/training/DojoWorkspace.tsx`: five opponent cards.
- `qa/training-dojo.md`: implementation and earlier QA record.

The feature is not merged or published. Current main has subsequent changes;
reconcile those before eventual integration. The local practice format uses
200 mirrored hands; the strengthening experiment uses tournament best-of-five
series. Their results and ratings must not be conflated.

## Active strategy work

All experiment files are under:
`/Users/sethsaperstein/Documents/AlphaSchool/summit-strengthening-2026-09-08`.
Earlier work is in sibling `dojo-calibration-2026-09-08`,
`dojo-calibration-round2-2026-09-08`, and `dojo-elo-expanded-2026-09-08`.

Read `PROTOCOL.md` and `INTEGRATION.md` in the strengthening directory.
Seth approved improving Summit from the strongest research candidate, keeping
Mirage fixed. Acceptance requires at least 18/20 tournament series against
Mirage in EACH of two fresh batches, lower-opponent gates, reference regressions,
and runtime checks. No candidate has met all gates. Do not weaken Mirage or
promote based on a favorable development batch.

## Recovery evidence

- `recovery-confirm-v13/result.json`: frozen v13 won 15/20 and 17/20 against
  Mirage on fresh confirmation deals, zero errors. Both gates failed.
  These deals are now used evidence and cannot be future holdouts.
- `resume.py`: restores missing series from a saved development manifest;
  verifies source hashes and retained results, preserves completed results,
  and refuses to overwrite an existing summary.
- `builder/v15-screen`: recovered all 120 series (90 resumed), 463 games,
  10,193 hands, zero errors, unchanged source hashes. Wins out of 20:
  Mirage 14, old Summit 15, Spark 20, smallpressure 17, hard-a 12, middle-a 6.
  This version does not meet the Mirage gate and remains vulnerable to middle-a.
- Six CLI dojo tests and twenty API dojo tests passed in this recovery.
- `audit/recovery-v13-isolation.json`: 282 decisions, zero mismatches, no
  shared default memory mutation.
- `audit/recovery-v13-short-stack.json`: 100 premium short-stack all-in
  decisions, zero errors.

## Next development step

Use v13 as the better-supported baseline, preserving its frozen source.
Inspect losing public decision traces and create a new version for substantive
range/betting-policy changes. v15's extra equity calculation is an experiment,
not an established improvement. Compare new changes on matched development
schedules and the existing attacker pool before spending fresh acceptance
seeds. Only run the full integration checklist after all strength gates pass.
Existing packaged bots, displayed ratings, and production remain unchanged.
