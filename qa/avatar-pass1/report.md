# Independent browser test, pass 1

Tested localhost:3001 in isolated headless Chrome contexts, via rendered UI only. No application source or history read. Desktop 1440x1000, mobile layouts 320x740 and 390x844. These are viewport tests with mouse/keyboard, not physical touch-device tests.

QA users: `avatartest0680502` (custom saved image), `avatarskip0832515` (skipped, default Elephant). Local test accounts only.

| Case | Expected | Actual / result | Evidence |
| --- | --- | --- | --- |
| Initial load | Homepage usable | Initially HTTP 500. Developer fixed during session; reload renders homepage. PASS on retest. | 01-startup-500.png records original failure |
| Signup character step | New account enters picker | Account-created screen shows Elephant selected and four presets. PASS. | 02-signup-character-desktop.png, 13-signup-mobile320.png |
| Preset select/save | Saved Bird appears in account | Selected Bird, saved, returned to instructions; header used /characters/bird.webp. PASS. | UI observation |
| Profile edit and reload | New preset persists | Account > Profile & character > Change character, selected Octopus, saved, reloaded. Header and profile used Octopus. PASS. | 03-invalid-upload.png shows saved Octopus selection |
| Invalid SVG | Useful rejection, saved state retained | “Choose a valid JPG, PNG, or WebP image.” PASS. | 03-invalid-upload.png |
| Oversized valid PNG | Size error | Supplied design bird.png rejected with “Choose an image smaller than 2 MB.” PASS. | UI observation |
| Valid image upload | Crop interface opens | Used browser screenshot of public bird.webp as smaller PNG fixture; crop interface opened. PASS. | 04-crop-desktop.png, upload-bird.png |
| Zoom keyboard | Arrow keys change zoom | Zoom focused, ArrowRight changed 1 to 1.01. PASS. | UI value observation |
| Crop position | Sliders and dragging reframe | Set zoom 2, Horizontal keyboard increment, Vertical 75; drag changed position to 39/67. PASS. | 06-crop-mobile390-positioned.png |
| Cancel crop | Saved image unaffected | Cancel crop returned to picker with Octopus, Cancel returned profile still Octopus. PASS. | UI source observation |
| Crop/save | Preview then save resulting image | Use this crop staged custom preview; Save character committed it. PASS. | 07-crop-staged-mobile390.png, 08-saved-custom-mobile390.png |
| Reload custom | Custom image persists | Same /browser-api/avatars/3277aa86510cc3585c7db18788052773cffbe1c450a7e8bfca99f1b852f75fca after reload. PASS. | 08-saved-custom-mobile390.png |
| Logout/login custom | Account restores custom image | Logged out, logged back in through form; header custom asset matched before reload, then persisted on reload. PASS. | UI source observation |
| Signup skip | Continue with default character | Skip returned to instructions; reload retained Elephant. PASS. | 14-skip-persisted-mobile320.png |
| My Bot discovery without bot | Find profile character edit | Initially absent. Developer added shortcut during test; link now visible and opens /profile. PASS on retest. | 09-mybot-no-bot-mobile390.png, 10-mybot-discovery-fixed.png |
| Preset keyboard/cancel | Space selects, Tab advances, Cancel preserves saved | Space selected Bear (aria-pressed=true), Tab focused Octopus, Cancel kept custom avatar. PASS. | 15-keyboard-preset-focus.png |
| Mobile 320/390 | Usable layout and reachable controls | No horizontal overflow at 320; controls reachable by scrolling. PASS with minor overlay friction below. | 05-crop-mobile320.png, 06/07/08, 13 |
| Leaderboard/Rivals defaults | Existing users have consistent avatar | Seeded leaderboard and Rivals users show Elephant; logged-in header custom image remains visible. PASS for default consistency only. | 11-leaderboard.png, 12-rivals-empty.png |
| Own leaderboard/Rivals participant propagation | Own saved avatar follows bot/player | NOT TESTED. Account has no submitted bot; no UI bot upload route. Header consistency is not proof of participant propagation. | 09/10 My Bot, 11/12 surfaces |

## Final mobile overlay retest

PASS. Retested after developer fix using isolated account `avatarfinal0922453`. Feedback button is hidden during the 320px signup picker, 390px custom crop, and 390px staged selection before Save character. It returns on the saved Profile. Confirmed rendered visibility and visually reviewed final signup, staged selection, and saved Profile screenshots. Original mobile overlap is resolved.

Evidence: 16-final-signup-mobile320.png, 17-final-crop-mobile390.png, 18-final-staged-mobile390.png, 19-final-saved-mobile390.png.

## Original friction, resolved

Low severity: floating feedback bubble overlaps the Octopus label area in the 320px signup screenshot and the upper-right edge of the Save character button at 390px. Main controls remain usable through center clicks, but the overlay competes with selection content and action space. See 13-signup-mobile320.png and 07-crop-staged-mobile390.png.

Crop's “Use this crop” followed by “Save character” worked correctly; it is a two-stage commit and the preview makes this understandable. “Fine-tune position” is collapsed initially, but opens to labeled Horizontal/Vertical keyboard-operable controls.

No app files edited. Evidence screenshots and this report only, plus harmless invalid SVG and public-image PNG test fixtures. No feature requests or production actions performed.
