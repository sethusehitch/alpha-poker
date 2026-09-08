# Local recap design

The CLI serves immutable saved evidence through a read-only Python HTTP server
bound to 127.0.0.1 on an OS-selected port. The detached process owns no browser
credentials, opens no external connection, and exits after 30 minutes idle or
eight hours. Requests require the exact Host, same-origin Origin when present,
and an unguessable per-session path. Only explicitly mapped assets/JSON routes
are exposed; no directory listing, file upload, or arbitrary filesystem endpoint.
Responses disable caching, set nosniff/no-referrer, and restrict scripts and
connections to the same origin. Local users with the URL can view the log.

Evidence ZIP members are read, never extracted or executed. Only hands.jsonl
and summary.json are consumed. Input is bounded to 64 MB and 10,000 records.
Completed result events are required; invalid inputs fail clearly. Grouping uses
match ID plus the participant pair, then game/hand chronology. Unknown total
history suppresses cumulative momentum claims. Saved recap JSON is explicitly
highlight-only. Missing cards remain unavailable instead of fabricated.

`local-viewer/main.tsx` imports the actual site's `RecapView`; it is not a visual
copy. It adds only a local file label and match/hand selector. `backHref=null`
suppresses site navigation, while web usage keeps its default navigation.
The frontend is compiled using existing Vite/React dependencies and bundled
with avatars/licenses in the Python package. `local-viewer/package.mjs` packages
the exact shared Python normalizer, highlight selector, chip ledger, evaluator,
and equity code with only the engine import made package-relative. Generated
files are ignored, rebuilt by QA, and included in the reproducible starter ZIP.
Users need Python 3.11+ only. Future changes to shared rendering/normalization
must rebuild the local bundle before releasing the starter kit.

Validation: `npm run qa`; `PYTHONPATH=server:cli server/.venv/bin/python
qa/local_recap_smoke.py` performs real isolated WebSocket training, shuts down
the API, and opens the saved ZIP from the extracted starter kit with no server
package on PYTHONPATH. It also validates a multi-match engine artifact and a
specific non-highlight hand. Browser QA covers hand selection, playback, cards,
and desktop/mobile layout. Test artifact locations and local URLs are printed.

Existing deployments stay on the established AWS release workflow. This local
viewer does not add a hosted service or change the retained Sites configuration.
