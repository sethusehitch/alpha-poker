# Standalone recap integration test

PASS. Isolated headless Chrome, 1440x1000 viewport, rendered UI only; no source inspection. Tested local viewer at `http://127.0.0.1:63108/H9OeF2i0ElmHwf42GTKYFMVHz3aOc5OS/`.

- All four avatar images loaded successfully from relative `characters/elephant.webp` (natural width 768px). Visual inspection confirms Elephant in both sidebar player summaries and both table seats, as expected without character metadata.
- Replay reset Hand 1 from result step17/17 to step1/17. Pause worked. Selected Hand2, Play advanced through steps3 and5 of21, and Pause stopped it. Hand cards, stacks, and action text rendered correctly.
- Network capture began before navigation. Seven requests total, all GETs under the same local viewer path: document, bundled JS, bundled CSS, manifest.json, recap/0, characters/elephant.webp, and recap/0/1. Zero `/browser-api` requests and zero external-origin requests.
- Zero browser page errors observed.

Screenshot: [20-offline-recap.png](20-offline-recap.png), showing Hand2 paused at step5/21 with all four bundled Elephant avatars visible.
