# Feature request refresh (awaiting user review)

No production rows have been changed. Preview data is isolated locally.

The UI replaces Planned with Completed. Top and New exclude shipped requests;
Completed shows shipped requests, newest update first. Existing planned links
resolve to Completed. Planned remains an available operator status.

The reviewed JSON updates three exact product-team records. The rookie tutorial
is completed; My Bot next actions and recap strategy questions remain in progress.
All other requests remain unchanged. IDs, authors, creation dates, votes, and
GitHub associations are preserved. No completed subfeature is duplicated as a
new request.

After user approval and normal release validation, run the refresh script on
the verified target database without --apply first. Review the three changes.
Then run with --apply. It is idempotent, checks identities/titles/statuses before
writing, applies all changes in one transaction, and saves original rows next
to the database for recovery. Keep the normal pre-release SQLite backup too.
Do not run this as an automatic startup migration.

Verify production Completed contains the tutorial, Top/New exclude it, and the
two narrowed in-progress requests retain their original IDs and votes.
