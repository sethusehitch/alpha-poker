# Alpha Poker — Community Surfaces Design Spec

Implementation-ready specification for three surfaces:

1. `/feature-requests` — community idea board with voting
2. `/contribute` — open-source contribution page backed by GitHub issues
3. Global feedback widget — floating button available on every page

This document is the single source of truth for these surfaces. Where it conflicts with
`DESIGN_REVIEW.md`, this document wins: `DESIGN_REVIEW.md` describes a superseded leaderboard
(featured bb/100 panel) that no longer ships.

Every value below is a decision, not a suggestion. Implementers should not substitute
alternatives without a new design pass.

---

## 0. Scope, invariants, and hard exclusions

### 0.1 What ships

| Surface | Route | Shipped in MVP |
| --- | --- | --- |
| Feature requests | `/feature-requests` | List, filter tabs, voting, create modal, status chips, operator controls |
| Contribute | `/contribute` | Hero, 4-step guide, good-first-issue rows, "Before you start" rail, closing strip |
| Feedback widget | global (mounted in `app/layout.tsx`) | Closed / open / sending / success / error states |
| Shared header | global | Logo lockup, 3-item nav, account chip, mobile menu |

### 0.2 Invariants (do not change)

- **Leaderboard stays exactly as built.** Podium + `Rank / Bot / Player / Elo / Record` table,
  Elo rating and win–loss record only. No community surface may restyle, re-rank, duplicate, or
  re-skin it.
- **Design system stays as built.** White canvas, Geist Sans / Geist Mono, zinc neutrals, one
  cobalt accent (`blue-600`), thin rules, `rounded-[5px]` buttons, `rounded-[10px]` cards,
  generous whitespace, Notion-like restraint.
- **Header height stays `4.5rem` (72px)** at every breakpoint. The landing hero depends on
  `min-h-[calc(100svh-4.5rem)]` and is covered by `tests/rendered-html.test.mjs`.
- **Account dialog internals are unchanged.** Only its trigger is restyled (§2.4).
- **Logo lockup is unchanged**: `AlphaPokerMark` + "Alpha Poker" wordmark. The approved concepts
  render a wordmark-only header; that is a deliberate rejection — the mark stays.

### 0.3 Hard exclusions — must not appear anywhere in these surfaces

| Excluded | Why |
| --- | --- |
| `bb/100`, win-rate-per-100 figures | Superseded scoring display |
| Confidence intervals / `95% range` | Superseded scoring display |
| `Hands` column or hand counts | Superseded scoring display |
| RiverRat / old leaderboard sample personas as seeded community content | Stale sample data |
| Any Discord link, invite, or "join our server" call to action | Was added accidentally; there is no Discord |
| Comments, comment counts, or reply threads **on feature requests** | Out of MVP scope |
| Casino imagery: felt, chips, dice, suits-as-decoration, gold gradients, neon | Design system rule |
| Character art, mascots, robot illustrations, emoji as UI iconography | Design system rule |
| Scattered decorative glyphs in hero backgrounds (sparkles, hearts, playing cards) | Rejected from approved concept 2; reads as noise and card art reads as casino cliché |

> GitHub issue rows on `/contribute` **do** show a comment count. That is external GitHub
> metadata, not the excluded feature-request comment system.

### 0.4 No seeded content

The feature-request list renders only real API data. No placeholder rows, no demo ideas, no
sample authors ship in the bundle. When the API returns nothing, the empty state (§4.9) renders.
All example rows in this document are wireframe illustration only.

---

## 1. Design tokens

Tokens are named by their Tailwind v4 class, which is the codebase's source of truth. Hex values
are approximate renderings of the oklch palette and are given for design tooling only.

### 1.1 Color

| Role | Token | ≈ Hex | Usage |
| --- | --- | --- | --- |
| Canvas | `white` | `#FFFFFF` | Page background, cards, rows |
| Canvas tint | `zinc-50/60` | `#FAFAFA` @60% | Section bands, row hover |
| Rule | `zinc-200/80` | `#E4E4E7` @80% | Header border, row dividers, card borders |
| Rule strong | `zinc-300` | `#D4D4D8` | Input borders, secondary button borders, dashed connectors |
| Text primary | `zinc-950` | `#09090B` | Headings, row titles, values |
| Text secondary | `zinc-600` | `#52525C` | Body copy, descriptions |
| Text muted | `zinc-500` | `#71717B` | Meta, timestamps, helper text |
| Text faint | `zinc-400` | `#9F9FA9` | Counters, idle vote arrows, closing-strip icon |
| Accent | `blue-600` | `#155DFC` | Primary buttons, FAB, active nav underline, focus ring |
| Accent hover | `blue-700` | `#1447E6` | Primary hover, link text |
| Accent tint | `blue-50` | `#EFF6FF` | Active tab, highlighted row, icon wells, chips |
| Accent tint border | `blue-200` | `#BEDBFF` | Highlighted row border |
| Focus ring | `blue-600` | `#155DFC` | 2px outline, 2px offset (3–4px on large targets) |
| Success | `green-600` / `green-50` | `#00A63E` / `#F0FDF4` | Success toast check, Shipped chip |
| Warning | `amber-700` / `amber-50` | `#A65F00` / `#FFFBEB` | Planned chip |
| Danger | `red-600` / `red-50` / `red-200` | `#E7000B` / `#FEF2F2` / `#FFC9C9` | Error text, error boxes, destructive menu item |
| Violet | `violet-700` / `violet-50` | `#6E11B0` / `#F5F3FF` | `good first issue` GitHub label |

### 1.2 Type scale

Font: `--font-geist-sans` for everything except issue numbers and code, which use
`--font-geist-mono`. Body-level letter-spacing inherits `-0.01em` from `body`.

| Name | Size | Line height | Weight | Tracking | Color |
| --- | --- | --- | --- | --- | --- |
| Page H1 | `clamp(2.5rem, 5vw, 4rem)` (40→64px) | 1.06 | 680 | `-0.045em` | `zinc-950` |
| Page lead | `1.08rem` → `1.25rem` @≥640px | 1.6 | 400 | `-0.018em` | `zinc-600` |
| Eyebrow | `0.6875rem` → `0.75rem` @≥640px | 1 | 700 | `0.25em`, uppercase | `blue-700` |
| Section H2 | `1.375rem` → `1.5rem` @≥640px | 1.25 | 680 | `-0.03em` | `zinc-950` |
| Card H3 | `1rem` | 1.4 | 600 | `-0.02em` | `zinc-950` |
| Row title | `1.0625rem` (17px) | 1.35 | 600 | `-0.02em` | `zinc-950` |
| Body | `0.9375rem` (15px) | 1.6 | 400 | inherit | `zinc-600` |
| Meta | `0.8125rem` (13px) | 1.4 | 400 | inherit | `zinc-500` |
| Nav item | `0.9375rem` (15px) | 1 | 500 | `-0.01em` | `zinc-600` / active `blue-700` |
| Button label | `0.875rem` (14px); hero buttons `1rem` | 1 | 600 | `-0.01em` | — |
| Chip / label | `0.75rem` (12px) | 1 | 600 | `-0.005em` | per status |
| Counter | `0.75rem` (12px) | 1 | 400 | — | `zinc-400` |
| Vote score | `1.0625rem` (17px) | 1 | 600 | `tabular-nums` | `zinc-900` |
| Mono meta | `0.75rem` (12px) | 1 | 500 | — | `zinc-500` |

### 1.3 Spacing scale

4px base. Permitted steps: `4, 6, 8, 10, 12, 16, 20, 24, 32, 40, 48, 56, 64, 80, 96`.

| Gap | Value |
| --- | --- |
| Header height | 72px (`h-[4.5rem]`) |
| Page gutter | 20px `<640px`, 32px `≥640px` |
| Hero top / bottom padding | 56 / 40px mobile · 80 / 48px desktop |
| Hero → toolbar | 32px |
| Toolbar → content grid | 24px |
| Two-column grid gap | 32px |
| Feature-request row gap | 10px |
| Card padding | 16px `<640px`, 20px `≥640px` |
| Between page sections | 48px mobile, 64px desktop |
| Page bottom padding | 96px mobile (clears the FAB), 80px desktop |

### 1.4 Radii

| Element | Radius |
| --- | --- |
| Buttons, tab segments, ghost icon buttons | `5px` |
| Segmented-control container | `7px` |
| Status chips, GitHub labels | `6px` |
| Inputs, textareas, icon wells | `8px` |
| Cards, list rows, popovers, toast | `10px` |
| Large panels (feedback panel, issues card) | `12px` |
| Modal / bottom sheet | `16px` (`rounded-2xl`, matches account dialog) |
| Avatars, FAB, number badges | `9999px` |

### 1.5 Elevation

| Level | Shadow | Used by |
| --- | --- | --- |
| 0 | none | Rows, static cards (borders only) |
| 1 | `0 1px 2px rgba(0,0,0,0.08)` | Primary buttons |
| 2 | `0 8px 24px rgba(9,9,11,0.10)` | Status popover menu |
| 3 | `0 12px 32px rgba(9,9,11,0.12)` | Feedback panel, toast |
| 4 | `0 20px 48px rgba(9,9,11,0.18)` | Modal dialog |
| FAB | `0 6px 20px rgba(21,93,252,0.30)` | Feedback FAB |

### 1.6 Z-index

| Layer | z |
| --- | --- |
| Sticky header | 30 |
| Mobile nav panel | 35 |
| Feedback FAB + panel | 40 |
| Modal overlay + dialog (account, compose) | 50 |
| Toast | 60 |

Rule: while any modal is open, the FAB and feedback panel are unmounted (`hidden`), so nothing
overlaps a dialog. The toast sits above modals so post-submit confirmation is always visible.

### 1.7 Motion

- Only `transition-colors` (150ms) for hover/active color changes — always on.
- Transform/opacity motion (panel rise, toast rise, new-row highlight fade, skeleton pulse, FAB
  icon cross-fade) is wrapped in `motion-safe:` and capped at **200ms**, `ease-out`.
- `prefers-reduced-motion: reduce` → no pulse, no slide, no fade; states swap instantly. The
  new-row highlight still holds for 2s, it just does not fade.

### 1.8 Focus

One rule everywhere:

```
focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600
focus-visible:outline-offset-2
```

Offset exceptions, matching existing code: logo lockup `offset-4`, hero-scale buttons `offset-3`.
Focus is never removed, never replaced by a shadow-only ring, and never suppressed inside modals.

---

## 2. Global chrome

### 2.1 Header layout

Single shared component used by `/`, `/feature-requests`, `/contribute`.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  [mark] Alpha Poker      Leaderboard  Feature requests  Contribute   [ chip ] │ 72px
└──────────────────────────────────────────────────────────────────────────────┘
                                        ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔  ← 2px blue active bar
```

- Outer: `border-b border-zinc-200/80 bg-white`, `relative`.
- Inner: `mx-auto flex h-[4.5rem] max-w-[90rem] items-center justify-between px-5 sm:px-8`
  (unchanged from the live header).
- Nav is **absolutely centered** on `≥1024px`: `absolute left-1/2 -translate-x-1/2 hidden lg:flex`.
  This keeps optical centering regardless of chip width.
- **Sticky behavior:** the header is `sticky top-0 z-30` on `/feature-requests` and `/contribute`
  only. On `/` it stays static. Rationale: the landing page's `100svh` hero and its `scroll-mt-0`
  anchor targets are tuned for a static header; making it sticky would hide section tops behind it.
- New pages using in-page anchors must set `scroll-mt-[5.5rem]` (72px header + 16px).

### 2.2 Nav items

| Label | Href | Active when |
| --- | --- | --- |
| Leaderboard | `/#leaderboard` | pathname is `/` |
| Feature requests | `/feature-requests` | pathname starts with `/feature-requests` |
| Contribute | `/contribute` | pathname starts with `/contribute` |

- Item: `inline-flex h-full items-center px-1 text-[0.9375rem] font-medium tracking-[-0.01em]`.
- Gap between items: **32px**.
- Idle `text-zinc-600` → hover `text-zinc-950` (colors only, no underline on hover).
- Active: `text-blue-700` plus a 2px `bg-blue-600` bar, full item width, positioned
  `absolute bottom-[-1px] inset-x-0` so it covers the header's bottom border.
- Active item carries `aria-current="page"`.
- Logo lockup href changes from `#top` to `/`. `aria-label="Alpha Poker home"` is preserved.
- Nav is a `<nav aria-label="Main">` containing a `<ul>`.

### 2.3 Mobile navigation (`<1024px`)

The centered nav is hidden. A disclosure button sits immediately left of the account chip.

- Toggle: 40×40, `rounded-[5px]`, `text-zinc-700 hover:bg-zinc-100`, 20px icon — three 1.75px
  lines when closed, an X when open. `aria-label="Menu"` / `"Close menu"`, `aria-expanded`,
  `aria-controls="site-nav-panel"`.
- Panel: `absolute inset-x-0 top-full z-35 border-b border-zinc-200 bg-white shadow-[0_8px_24px_rgba(9,9,11,0.10)]`,
  `px-5 py-2`. Not a full-screen overlay; page scroll is **not** locked.
- Each link: 48px tall, `text-[1.0625rem] font-medium`, left-aligned to the page gutter.
- Active link: `text-blue-700 font-semibold`, `bg-blue-50/60`, 2px `blue-600` left border,
  `rounded-[5px]`.
- Behavior: opens with focus on the first link; `Escape` closes and returns focus to the toggle;
  a click or tap outside closes it; a route change closes it. It is a disclosure, not a modal —
  no focus trap.
- `motion-safe`: 150ms fade + 4px rise.

### 2.4 Account chip

Restyle of the existing `AuthButton` trigger only. All dialog behavior, fields, and copy are
unchanged.

| State | Content | Style |
| --- | --- | --- |
| Signed out | 16px person icon + `Log in` | `h-10 gap-2 rounded-[8px] border border-zinc-300 bg-white px-3.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50` |
| Signed in | 16px person icon + username + 14px chevron-down | same, chevron `text-zinc-400` |

- Icon color `text-zinc-500`; icons are 1.5px stroke, `currentColor`, `aria-hidden`.
- Username truncates: `max-w-[9rem] truncate` desktop, `max-w-[6.5rem]` below 640px. Display cap
  16 code points with `…` (mirrors `PLAYER_NAME_DISPLAY_LENGTH` in `Leaderboard.tsx`).
- `aria-haspopup="dialog"`, `aria-expanded={open}`, `data-testid="account-trigger"`.
- Opening the account dialog closes the feedback panel and the mobile nav panel.

> **Implementation note — test update required.** `tests/rendered-html.test.mjs` asserts
> `/<button[^>]*>Log in<\/button>/`, which fails once the trigger contains an `<svg>`. Change that
> assertion to target `data-testid="account-trigger"` and the `Log in` text separately. This is
> the only existing test the chip affects.

---

## 3. Shared components

### 3.1 Buttons

| Variant | Height | Padding | Style |
| --- | --- | --- | --- |
| Primary | 44px (`h-11`); hero 48px (`h-12`) | `px-5` / hero `px-7` | `rounded-[5px] bg-blue-600 text-white font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.08)] hover:bg-blue-700` |
| Secondary | 44px; hero 48px | `px-4` / hero `px-7` | `rounded-[5px] border border-zinc-900 bg-white text-zinc-950 font-semibold hover:bg-zinc-50` |
| Quiet | 44px | `px-4` | `rounded-[5px] border border-zinc-200 bg-white text-zinc-700 font-semibold hover:bg-zinc-50` |
| Ghost icon | 32×32 (36×36 touch) | — | `rounded-[5px] text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900` |
| Text link | — | — | `text-blue-700 font-semibold hover:text-blue-800` |

- Disabled: `disabled:opacity-60 disabled:cursor-not-allowed`, no hover change, `aria-disabled`
  is not used on real `<button disabled>`.
- Busy: label swaps to the progressive form ("Posting…", "Sending…"), `aria-busy="true"`,
  a 14px spinner (`border-2 border-white/40 border-t-white animate-spin motion-reduce:animate-none`)
  sits 8px left of the label.
- Arrow icons reuse the live site's geometry: `strokeWidth 1.75`, round caps, 16px box. Right
  arrow path: `M2.5 8h10m0 0-4-4m4 4-4 4`.

### 3.2 Status chips (feature requests)

Exactly six statuses. Every request always renders exactly one chip — including `Submitted` — so the
right edge of the list is never ragged and the state is never implied by absence.

| Status | Label | Chip style |
| --- | --- | --- |
| `submitted` | Submitted | `bg-zinc-100 text-zinc-700` |
| `under_review` | Under review | `bg-blue-50 text-blue-700` |
| `planned` | Planned | `bg-amber-50 text-amber-700` |
| `in_progress` | In progress | `bg-purple-50 text-purple-700` |
| `shipped` | Shipped | `bg-green-50 text-green-700` |
| `declined` | Declined | `bg-zinc-100 text-zinc-500` |

- Geometry: `h-7 rounded-[6px] px-2.5 text-[0.75rem] font-semibold whitespace-nowrap`.
- No borders, no rings, no dots, no icons. Color + label only.
- Unknown status from the API → render `Submitted`. Never render a raw server string.
- `Declined` mutes the chip only; the row title and description keep normal color and are
  never struck through.

### 3.3 Author avatar

- 20px circle, `rounded-full`, white `0.6875rem` 600-weight initial, centered.
- Initial = first code point of the username, uppercased. If it is not a letter or digit, render
  `?`.
- Background chosen deterministically by `sum(codePoints(username)) % 6` over a fixed palette:
  `#155DFC` (blue-600), `#00A63E` (green-600), `#F54A00` (orange-600), `#9810FA` (purple-600),
  `#D08700` (yellow-600), `#0092B8` (cyan-600). Never derived from server-supplied color values.
- `aria-hidden="true"` — the username text next to it carries the meaning.

### 3.4 Toast

Shared by feature-request post success, feedback success, and operator actions.

- Position: `fixed z-60 bottom-[5.5rem] right-6`; below 640px `left-4 right-4 bottom-[5.25rem]`
  (sits above the FAB in both cases).
- Card: white, `rounded-[10px] border border-zinc-200 shadow-[0_12px_32px_rgba(9,9,11,0.12)]`,
  `h-12 px-4`, `flex items-center gap-3`.
- Leading glyph: 20px filled circle — `green-600` check for success, `red-600` `!` for failure.
- Text: `0.875rem font-medium text-zinc-900`.
- Optional trailing action (used only by operator undo): text link, `0.8125rem font-semibold text-blue-700`.
- `role="status" aria-live="polite"` for success; `role="alert"` for failure.
- Auto-dismiss after **4s** (10s when an action is present). Hover or keyboard focus pauses the
  timer. Click anywhere on the toast dismisses it.
- Only one toast at a time; a new toast replaces the current one.
- `motion-safe`: 150ms fade + 6px rise.

### 3.5 Skeletons

- Blocks: `bg-zinc-100 rounded-[4px] animate-pulse motion-reduce:animate-none`.
- Skeletons mirror the real geometry of the row they replace — same heights, same paddings — so
  nothing shifts when content arrives.
- Container carries `aria-busy="true"` and a visually hidden status line ("Loading ideas…").
- No spinners in list regions. Spinners appear only inside busy buttons.

---

## 4. `/feature-requests`

### 4.1 Page metadata

- `<title>`: `Feature requests — Alpha Poker`
- Description: `Vote on ideas from the Alpha Poker community.`
- No OG image override; the site default applies.

### 4.2 Desktop wireframe (≥1024px)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ [mark] Alpha Poker    Leaderboard  Feature requests  Contribute      [ chip ]   │
└────────────────────────────────────────────────────────────────────────────────┘
                                                                       (sticky)

                       What should we build next?              ← H1, centered
                   Vote on ideas from the Alpha Poker community.   ← lead

┌─────────────────────────────────────────┐            ┌───────────────────────┐
│ [ Top ][ New ][ Planned ]  [Suggest a feature]        │  How ideas work       │
└─────────────────────────────────────────┘            │                       │
  Log in to vote and suggest features.   (signed out)   │  (1) Suggest          │
                                                        │      Share an idea…   │
┌──────┬───────────────────────────────────┬──────────┐ │  ───────────────────  │
│  ▲   │ Watch a hand replay               │ Under    │ │  (2) Community votes  │
│ 812  │ Review any hand from a finished…  │ review   │ │      Upvote the ideas…│
│  ▼   │ ● ada · Sep 2, 2026               │          │ │  ───────────────────  │
└──────┴───────────────────────────────────┴──────────┘ │  (3) We review        │
┌──────┬───────────────────────────────────┬──────────┐ │      We read the top… │
│  ▲   │ Bot vs. bot practice matches      │ Planned  │ │  ───────────────────  │
│ 645  │ Let bots play each other so I can…│          │ │  Have a question?     │
│  ▼   │ ● kai · Aug 28, 2026              │          │ │  Use the feedback     │
└──────┴───────────────────────────────────┴──────────┘ │  button in the corner.│
                     … up to 25 rows …                  └───────────────────────┘
              [        Show more ideas        ]            (sticky, top: 5.5rem)
```

- Content container: `mx-auto w-full max-w-[76rem] px-5 sm:px-8` (1216px).
- Grid at `≥1024px`: `grid grid-cols-[minmax(0,1fr)_20rem] gap-8 items-start`.
  At 1216px this yields a 864px list column and a 320px rail.
- Below 1024px the grid collapses to one column and the rail renders **after** the list
  (`mt-10`), because the list is the point of the page.
- Rail is `lg:sticky lg:top-[5.5rem]`.

### 4.3 Hero

- Padding: `pt-14 pb-10` mobile, `sm:pt-20 sm:pb-12`.
- H1 `What should we build next?` — Page H1 scale, `max-w-[24ch] mx-auto`, centered.
- Lead `Vote on ideas from the Alpha Poker community.` — Page lead scale, `mt-5`, `max-w-xl mx-auto`,
  centered.
- No eyebrow on this page.

### 4.4 Toolbar

Row: `mt-8 flex items-center justify-between gap-4`.

**Filter tabs** — rendered as links, not JS state, so the filter is shareable and back-button
friendly. Wrapped in `<nav aria-label="Filter feature requests">`.

| Tab | Href | Contents | Sort |
| --- | --- | --- | --- |
| Top (default) | `/feature-requests` | all statuses | score desc, then newest |
| New | `?tab=new` | all statuses | newest first |
| Planned | `?tab=planned` | `planned` + `shipped` | `planned` first, then score desc |

- Container: `inline-flex rounded-[7px] border border-zinc-200 bg-white p-0.5`.
- Segment: `h-9 rounded-[5px] px-4 text-sm font-medium`.
- Active: `bg-blue-50 text-blue-700`, `aria-current="page"`.
- Idle: `text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950`.
- An unknown `?tab=` value falls back to Top without an error.

**Suggest a feature** — primary button, right-aligned, 44px.

**Signed-out helper line** — directly under the toolbar, `mt-3 text-[0.8125rem] text-zinc-500`:
`Log in to vote and suggest features.` Rendered only when signed out.

### 4.5 Request row

```
┌────────┬────────────────────────────────────────────────┬──────────────┐
│   ▲    │  Watch a hand replay                           │ Under review │
│  812   │  Review any hand from a finished game, step…   │              │
│   ▼    │  (A) ada  ·  Sep 2, 2026                       │              │
└────────┴────────────────────────────────────────────────┴──────────────┘
  64px    ← flexible, min-w-0 →                             shrink-0
```

- Row: `<li>` inside `<ul role="list" class="space-y-2.5">`; `flex items-stretch rounded-[10px]
  border border-zinc-200 bg-white`, `min-h-[5.5rem]`, `p-0` (children own their padding).
- Hover: `hover:border-zinc-300`. The row itself is **not** a link and **not** focusable — there
  is no detail page in MVP. Only the vote buttons (and operator controls) are interactive.
- **Top-row highlight:** in the **Top** tab only, the first row renders
  `border-blue-200 bg-blue-50/40`. It is purely decorative reinforcement of "highest score, first
  in a score-sorted list" — no label, no badge, no meaning lost for screen readers.
- Vote column: `flex w-16 shrink-0 flex-col items-center justify-center gap-0.5 border-r
  border-zinc-200/80 py-3`. Below 640px: `w-12`, no divider.
- Content column: `min-w-0 flex-1 px-4 py-3.5 sm:px-5 sm:py-4`.
  - Title — Row title scale, `line-clamp-2 break-words`, `title={fullTitle}`.
  - Description — Body scale, `mt-1 line-clamp-2 break-words`, `title={fullDetails}`. Omitted
    entirely when empty (no blank line reserved).
  - Meta — `mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-[0.8125rem] text-zinc-500`:
    avatar, username, a `·` separator (`aria-hidden`), and
    `<time dateTime={iso}>Sep 2, 2026</time>` formatted `Intl.DateTimeFormat("en-US", { month:
    "short", day: "numeric", year: "numeric" })`. Always absolute dates — no "2 days ago".
- Status column: `flex shrink-0 items-center pr-4 sm:pr-5`. Below 640px the chip is not a column;
  it becomes the last item in the wrapping meta row.

### 4.6 Vote control

```
    ▲     36×36 desktop / 40×40 mobile
   812    score, tabular-nums
    ▼
```

- Buttons: `inline-flex h-9 w-9 items-center justify-center rounded-[5px]`
  (`max-sm:h-10 max-sm:w-10`).
- Icons: 16px, `strokeWidth 1.75`, round caps. Up `M8 13.5v-10m0 0 4 4m-4-4-4 4`;
  down `M8 2.5v10m0 0 4-4m-4 4-4-4`.
- Score: Vote score scale, 2px vertical margins. Blue-700 when the viewer has upvoted.

| State | Up arrow | Down arrow |
| --- | --- | --- |
| Idle | `text-zinc-400` | `text-zinc-400` |
| Hover | `text-blue-600 bg-blue-50` | `text-zinc-700 bg-zinc-100` |
| Active (this direction voted) | `text-blue-600 bg-blue-50` | `text-zinc-700 bg-zinc-100` |
| Request in flight | `opacity-60 pointer-events-none` on both | same |

- **Score display:** the exact net value (`up − down`). Zero renders `0`. Negative values render
  with a real minus sign and `text-zinc-500`. The UI never fakes a floor.
- **Toggle semantics:** clicking the currently active direction clears the vote (`value: 0`).
  Clicking the opposite direction switches it (net change of 2).
- **Optimistic update:** score and `my_vote` update immediately; on failure they roll back and an
  error toast appears (`Couldn't save your vote.`).
- **Debounce:** while a vote request for a given request id is in flight, both of that row's
  arrows are inert. Rapid clicks are dropped, not queued.
- **Signed out:** arrows render in idle style and are fully clickable. A click opens the account
  dialog. The vote is **not** replayed after login — the user must click again. This is
  deliberate: no surprise writes on the user's behalf.
- **Accessibility:**
  - `aria-label` — `Upvote: {title}` / `Downvote: {title}` using the untruncated title.
  - `aria-pressed={myVote === "up"}` / `{myVote === "down"}`.
  - After a successful vote, a single polite live region on the page announces
    `{title}, score {n}`. Only the most recent vote is announced.

### 4.7 Create-request modal

Trigger: the **Suggest a feature** button, or the empty-state button.

- Signed out: the trigger opens the account dialog instead. On successful login the compose modal
  opens automatically (the intent was unambiguous). This auto-open applies to this trigger only.

**Geometry**

| Breakpoint | Presentation |
| --- | --- |
| `≥640px` | Centered dialog, `w-full max-w-[32rem]`, `rounded-2xl border border-zinc-200 bg-white p-6 shadow-[0_20px_48px_rgba(9,9,11,0.18)]` |
| `<640px` | Bottom sheet: `fixed inset-x-0 bottom-0`, `rounded-t-2xl`, `max-h-[90svh] overflow-y-auto`, `p-5`, `pb-[max(1.25rem,env(safe-area-inset-bottom))]` |

- Overlay: `fixed inset-0 z-50 bg-black/20 px-5 flex items-center justify-center`
  (`items-end` below 640px) — matches the account dialog's overlay exactly.
- `motion-safe`: overlay 150ms fade; sheet 200ms rise from `translate-y-2`.

**Content**

1. Header row — H `Suggest a feature` (`text-xl font-bold text-zinc-900`), sub
   `Tell us what would make Alpha Poker better.` (`mt-1 text-sm text-zinc-500`), close button
   top-right (ghost icon, 16px X, `aria-label="Close"`).
2. **Title** — required. `<input maxLength={80}>`, `h-11 w-full rounded-lg border border-zinc-300
   px-3 text-[0.9375rem] outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100`
   (identical to the account dialog's inputs). Label `Title`, `text-sm font-medium text-zinc-800`,
   6px above the field. Placeholder: `Watch a hand replay`.
3. **Details** — optional. `<textarea rows={4} maxLength={500}>`, same border/focus treatment,
   `min-h-[6.5rem] py-2.5 leading-6 resize-y`. Label `Details (optional)`. Placeholder:
   `What would it do? Why would it help?`
4. **Counters** — right-aligned below each field, `text-xs text-zinc-400`, format `12/80`. Turn
   `text-zinc-600` at 80% of the cap and `text-red-600` at the cap. Hidden until the field has
   content.
5. **Footer** — `mt-6 flex justify-end gap-3`; `Cancel` (quiet) then `Post idea` (primary).
   Below 640px both are full width, stacked, primary on top.

**Validation and submit**

- `Post idea` is disabled until the trimmed title is ≥ 4 characters.
- On invalid submit attempt: inline error beneath the Title field,
  `mt-1.5 text-[0.8125rem] text-red-600`, `role="alert"`, id referenced by the input's
  `aria-describedby`, and `aria-invalid="true"`:
  `Give your idea a short title (at least 4 characters).`
- Submitting: primary shows spinner + `Posting…`; both fields and `Cancel` are disabled; Escape
  and overlay clicks are ignored.
- Success: modal closes, draft clears, the view switches to the **New** tab with the new request
  prepended, that row scrolls into view (`block: "center"`) and holds a `bg-blue-50/60` highlight
  for 2s (`motion-safe` fades it out), and a toast reads `Idea posted. Thanks!`
- Errors: red box above the footer — `rounded-lg border border-red-200 bg-red-50 px-3 py-2.5
  text-[0.8125rem] text-red-700`, `role="alert"`. Typed content is always preserved.

| Condition | Copy |
| --- | --- |
| `validation_error` / 400 | `That title didn't work. Keep it under 80 characters and try again.` |
| `duplicate_request` / 409 | `Someone already suggested that. Look for it in the list.` |
| `rate_limited` / 429 | `You're posting quickly. Try again in a minute.` |
| `unauthorized` / 401 | Close the modal, open the account dialog, toast: `Log in again to post your idea.` |
| `api_unavailable` / 503 / network | `Couldn't post that. Check your connection and try again.` |
| any other 5xx | `Something went wrong on our side. Try again.` |

Server `error.message` strings are **never** rendered. Only `error.code` is mapped to the copy
above, with the 5xx line as the fallback.

**Modal keyboard behavior**

- Focus moves to the Title input on open.
- Focus is trapped: `Tab` / `Shift+Tab` cycle within the dialog; focus cannot reach the page behind.
- `Escape` closes (unless submitting) and restores focus to the trigger button.
- Overlay `mousedown` closes only when both fields are empty; with content it does nothing, so a
  stray click never destroys a draft.
- `Cmd/Ctrl + Enter` submits from either field.
- `<html>` gets `overflow-hidden` while open; it is removed on close (and on unmount).
- `role="dialog" aria-modal="true" aria-labelledby="suggest-title"`.
- **Draft persistence:** title and details persist in component state for the session until a
  successful post. Reopening restores the draft. Nothing is written to `localStorage`
  (shared-machine safety).

### 4.8 Pagination

- First page: 25 rows.
- `Show more ideas` — quiet button, full width of the list column, `mt-4`, 44px. Visible only when
  the API returns a `next_cursor`.
- While loading: label `Loading…` + spinner, disabled.
- After loading: focus stays on the button; a polite live region announces `25 more ideas loaded.`
  The button disappears when the cursor is exhausted.

### 4.9 States

**Initial load.** Server-render the first page when possible. Client-side fetches (tab change,
retry) show 5 skeleton rows matching §4.5 geometry: 24×12 vote bar, 60%-width 16px title bar,
85%-width 12px description bar, 30%-width 10px meta bar, 84×28 chip block.

**Empty — no requests exist.**

```
┌──────────────────────────────────────────────┐
│                  ( ! )                        │   dashed border-zinc-300
│              No ideas yet.                    │   rounded-[10px], py-14
│  Be the first to suggest what we should       │   text-center
│  build next.                                  │
│          [ Suggest a feature ]                │
└──────────────────────────────────────────────┘
```

- Glyph: 40px `bg-blue-50 rounded-full` well with a 20px `blue-600` lightbulb outline icon.
- H: `No ideas yet.` (`text-lg font-semibold text-zinc-950`, `mt-4`).
- Body: `Be the first to suggest what we should build next.` (`mt-1.5`, Body scale, `max-w-sm mx-auto`).
- Primary button `mt-6`.

**Empty — filtered tab (Planned).** Same shell; glyph is a 20px checklist icon in a `zinc-100`
well; H `Nothing planned yet.`; body `Ideas we decide to build will show up here.`; action is a
text link `See all ideas` → `/feature-requests` (no primary button).

**Error.** `rounded-[10px] border border-red-200 bg-red-50/60 p-6 text-center`, `role="alert"`:
H `Couldn't load ideas.` (`text-base font-semibold text-red-700`), body in `text-red-700/80`, and
a quiet `Try again` button that refetches the current tab.

| Condition | Body copy |
| --- | --- |
| 503 / `api_unavailable` / network | `Ideas are offline right now. Try again in a moment.` |
| any other failure | `Something went wrong on our side.` |

**Refresh policy.** This page does **not** poll. Data refreshes on mount, tab change, load-more,
post success, and explicit retry. Rationale: background polling would make scores jump under the
user's cursor mid-vote. (The leaderboard's 5s poll is unaffected and unchanged.)

### 4.10 "How ideas work" rail

- Card: `rounded-[10px] border border-zinc-200 bg-white p-5`.
- H2 `How ideas work` (Section H2 scale).
- Three steps, separated by `border-t border-zinc-200/70 pt-4 mt-4`:

| # | Title | Body | Icon |
| --- | --- | --- | --- |
| 1 | Suggest | `Share an idea that would make Alpha Poker better.` | pencil |
| 2 | Community votes | `Upvote the ideas you want most. The best ones rise to the top.` | two people |
| 3 | We review | `We read the top ideas and build what helps most.` | clipboard with check |

- Each step: `flex gap-3.5`. Icon well is a 40px `rounded-full bg-blue-50` circle containing a
  20px `blue-600` 1.5px-stroke line icon, `aria-hidden`. Title is Card H3 scale prefixed with
  `1. ` / `2. ` / `3. `; body is Meta scale in `zinc-600`.
- **Footer replaces the concept's Discord link.** After a final divider:
  `Have a question?` (Meta scale, `text-zinc-600`) then a text-link **button**
  `Use the feedback button in the corner` that opens the feedback panel (§6) and moves focus into
  its textarea. No external community links of any kind.

### 4.11 Operator controls

Gated on a boolean `is_operator` from the session endpoint. Non-operators never render these
controls and are never sent operator-only fields.

All operator affordances carry `data-operator="true"` so QA can screenshot them deterministically.

**Status control.** Replaces the static chip with a chip-shaped button: identical chip styling
plus a 12px chevron-down at `pl-1.5`, `hover:brightness-95`,
`aria-haspopup="menu" aria-expanded`.

Popover: `w-[13rem] rounded-[10px] border border-zinc-200 bg-white p-1 shadow-[0_8px_24px_rgba(9,9,11,0.10)]`,
anchored to the chip's right edge, flipping above when it would overflow the viewport.

- Items: `h-8 w-full rounded-[5px] px-2 text-[0.8125rem] text-zinc-700 hover:bg-zinc-50`,
  `role="menuitemradio"`, each with an 8px status dot (chip text color) and a 14px blue check on
  the current status.
- Order: Open · Under review · Planned · Shipped · Not planned.
- Below a `my-1 border-t border-zinc-200` divider: `Hide request` in `text-red-600
  hover:bg-red-50`. First click swaps that item's label to `Confirm hide` (`font-semibold`) for
  4 seconds; a second click within that window performs the action. No second modal.
- Keyboard: `↑ ↓ Home End` move, `Enter/Space` activate, `Escape` closes and returns focus to the
  chip, `Tab` closes.

**Behavior.**

- Status change is optimistic; on failure the chip reverts and a failure toast reads
  `Couldn't update status.`
- Hiding removes the row immediately and shows a 10s toast: `Request hidden.` + `Undo`. Undo
  restores the row in place.
- A `403` on any operator action means the session lost operator rights: remove all operator
  affordances from the page and show `You don't have operator access.`

---

## 5. `/contribute`

### 5.1 Page metadata

- `<title>`: `Contribute — Alpha Poker`
- Description: `Pick an issue, improve the arena, and send a pull request.`

### 5.2 Desktop wireframe (≥1024px)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ [mark] Alpha Poker    Leaderboard  Feature requests  Contribute      [ chip ]   │
└────────────────────────────────────────────────────────────────────────────────┘
                                     </>
                                 OPEN SOURCE
                          Help build Alpha Poker.
                Pick an issue, improve the arena, and send a pull request.
                   [ View open issues → ]  [ View pull requests → ]

┌──────────┐╌╌╌┌──────────┐╌╌╌┌──────────┐╌╌╌┌──────────┐
│ (1)  ⌕   │   │ (2)  ⑂   │   │ (3)  ▸_  │   │ (4)  ⑃   │
│Pick an   │   │Fork and  │   │Run the   │   │Open a    │
│issue     │   │build     │   │tests     │   │pull req. │
│Browse…   │   │Fork the… │   │Run the…  │   │Push your…│
└──────────┘   └──────────┘   └──────────┘   └──────────┘

┌────────────────────────────────────────────────┐  ┌───────────────────────┐
│  Good first issues                             │  │  Before you start     │
│ ─────────────────────────────────────────────  │  │                       │
│ ⊙ Improve lobby empty state UX                 │  │ [▤] Read CONTRIBUTING │
│   #287   [good first issue][frontend]  — · 💬3 │  │     Understand the…   │
│ ─────────────────────────────────────────────  │  │ [◎] Keep changes…     │
│ ⊙ Add docs for running private bots            │  │     Small, targeted…  │
│   #276   [good first issue][docs]      — · 💬2 │  │ [✓] All checks must…  │
│ ─────────────────────────────────────────────  │  │     CI must be green… │
│ View all open issues →                         │  │ Open CONTRIBUTING.md →│
└────────────────────────────────────────────────┘  └───────────────────────┘

──────────────────────────────────────────────────────────────────────────────
   ⌾  You propose. Maintainers review. Nothing merges automatically.
```

Same container and grid as `/feature-requests`: `max-w-[76rem]`, `grid-cols-[minmax(0,1fr)_20rem]
gap-8` at `≥1024px`. The rail moves below the issues card on smaller screens.

### 5.3 Hero

- Padding `pt-14 pb-12`, `sm:pt-20 sm:pb-16`. Centered.
- Glyph: 24px `</>` icon in `blue-600`, centered, `mb-3`, `aria-hidden`.
- Eyebrow `OPEN SOURCE` — Eyebrow scale, `blue-700`.
- H1 `Help build Alpha Poker.` — Page H1 scale, `mt-4`.
- Lead `Pick an issue, improve the arena, and send a pull request.` — Page lead scale, `mt-5`,
  `max-w-2xl mx-auto`.
- Buttons `mt-9`, `flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-3`:
  - Primary `View open issues` + right arrow → `{repo}/issues`
  - Secondary `View pull requests` + right arrow → `{repo}/pulls`
  - Both 48px tall, `target="_blank" rel="noopener noreferrer"`, each with a visually hidden
    `(opens in a new tab)` suffix.
- **No decorative background glyphs.** The approved concept scatters `</>`, sparkle, heart, and a
  playing-card mark; all four are rejected — the card mark reads as casino decoration and the rest
  add noise to a Notion-like page. The single `</>` above the eyebrow is the only ornament.

### 5.4 Four-step guide

- Grid: `mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4`.
- Card: `relative rounded-[10px] border border-zinc-200 bg-white p-5 text-center
  shadow-[0_1px_2px_rgba(0,0,0,0.03)]` (matches the landing page's instruction cards).
- Top row: `flex items-center justify-center gap-2.5` — a 24px `rounded-full bg-blue-50
  text-blue-700 text-xs font-bold` number badge, then a 20px `zinc-700` 1.5px line icon.
- Title: Card H3 scale, `mt-4`. Body: Body scale, `mt-2`, `text-balance`.
- Connector: on `lg` only, cards 1–3 get
  `after:absolute after:right-[-1.15rem] after:top-1/2 after:h-px after:w-[1.2rem]
  after:border-t after:border-dashed after:border-zinc-300`. No end dots. `aria-hidden` by
  construction (pseudo-element).

| # | Icon | Title | Body |
| --- | --- | --- | --- |
| 1 | magnifier | Pick an issue | `Browse open issues and find one labeled "good first issue".` |
| 2 | branch | Fork and build | `Fork the repo, create a branch, and make your change.` |
| 3 | terminal | Run the tests | `Run the test suite locally and make sure every check passes.` |
| 4 | pull request | Open a pull request | `Push your branch and open a pull request with a clear description.` |

Rendered as an `<ol>`; the number badges are real list semantics, not decoration.

### 5.5 Good first issues card

- Card: `rounded-[10px] border border-zinc-200 bg-white overflow-hidden`.
- Header: `p-5 pb-4`, H2 `Good first issues`.
- Rows: `<ul>` with `divide-y divide-zinc-200/80`, `border-t border-zinc-200/80` above the first.
- Maximum **5** rows.

**Row anatomy** — the entire row is a single `<a>`:

```
⊙  Improve lobby empty state UX                [good first issue] [frontend]   No assignee   💬 3
   #287
```

- `<a class="flex items-center gap-3 px-5 py-3.5 min-h-16 hover:bg-zinc-50
  focus-visible:outline focus-visible:-outline-offset-2">`, `target="_blank" rel="noopener noreferrer"`.
- Leading glyph: 16px `green-600` open-issue mark (circle with a centered dot), `shrink-0`,
  `aria-hidden`.
- Middle (`min-w-0 flex-1`): title `text-[0.9375rem] font-medium text-zinc-950 truncate`
  with `title={fullTitle}`; below it `#287` in Mono meta scale.
- Labels: up to **2** chips, `h-6 rounded-[6px] px-2 text-[0.75rem] font-medium`, `shrink-0`,
  hidden below `md`. Colors come from a **fixed local map keyed by label name**, never from
  GitHub's `color` field:

  | Label | Style |
  | --- | --- |
  | `good first issue` | `bg-violet-50 text-violet-700` |
  | `frontend` | `bg-blue-50 text-blue-700` |
  | `docs` | `bg-green-50 text-green-700` |
  | `bug` | `bg-red-50 text-red-700` |
  | anything else | `bg-zinc-100 text-zinc-700` |

  Label text is truncated to 22 code points. Extra labels beyond 2 are dropped silently.
- Assignee: Meta scale, `shrink-0`, hidden below `lg`. `No assignee` when unassigned, otherwise
  `@login` truncated to 14 code points.
- Comments: 14px bubble icon + count, Meta scale, `shrink-0`, hidden below `sm`. `tabular-nums`.
  Counts ≥ 1000 render as `999+`.
- Footer: `border-t border-zinc-200/80 p-5`, text link `View all open issues →` (external, new tab).

### 5.6 "Before you start" rail

- Card: `rounded-[10px] border border-zinc-200 bg-white p-5`, `lg:sticky lg:top-[5.5rem]`.
- H2 `Before you start`.
- Three items, `mt-4 space-y-4`, each `flex gap-3.5`: 36px `rounded-[8px] bg-zinc-50` well with a
  20px `zinc-700` line icon, then Card H3 title + Meta body.

| Icon | Title | Body |
| --- | --- | --- |
| book | Read CONTRIBUTING.md | `Understand the project, setup, and guidelines.` |
| target | Keep changes focused | `Small, targeted changes are easier to review and merge.` |
| check circle | All checks must pass | `CI must be green before your PR can be merged.` |

- Footer: `mt-5 border-t border-zinc-200/70 pt-4`, text link `Open CONTRIBUTING.md →`, external,
  new tab.

### 5.7 Closing strip

- `mt-12 border-t border-zinc-200 py-8`, full container width, `flex items-center justify-center
  gap-3 text-center`.
- 20px `zinc-400` handshake line icon (`aria-hidden`) — monochrome, never an emoji.
- Text: `You propose. Maintainers review. Nothing merges automatically.`
  (`text-[0.9375rem] text-zinc-600`). Wraps to two lines below 480px with the icon above.

### 5.8 Data and states

**Fetching.** GitHub issues are fetched **server-side only** (server component or
`/browser-api/github/issues` route), cached for 10 minutes, filtered to
`label="good first issue"`, `state=open`, `sort=created`, `per_page=5`. No GitHub token ever
reaches the browser. The repository owner/name is a build-time constant; nothing else is
requested.

**URL safety.** Each row's `href` must start with `https://github.com/{owner}/{repo}/issues/` and
end in a numeric id. Any URL failing that check renders as non-interactive text (glyph, title, and
number only, no anchor). Never trust `html_url` verbatim.

**Loading.** 3 skeleton rows matching row geometry: 16px circle, 55%-width 14px title bar,
40px number bar, two 90×24 label blocks. Header, steps, and rail are static and never skeletoned.

**Empty** (query returns zero issues) — inside the card, replacing the rows:
`px-5 py-10 text-center`, 20px `zinc-400` checklist icon, H `No good first issues right now.`
(`text-base font-semibold text-zinc-950`), body `Check the full issue list — there's plenty of
other ways to help.` (Body scale), then the footer link as normal.

**Error / offline** — inside the card, `role="status"`, `px-5 py-10 text-center`:
H `Couldn't load issues from GitHub.`, body `The full list still works.`, a quiet `Try again`
button, and the `View all open issues →` link always remains. The rest of the page — hero, steps,
rail, closing strip — stays fully functional; a GitHub outage never blanks this page.

---

## 6. Global feedback widget

Mounted once in `app/layout.tsx`, after `{children}`. Present on `/`, `/feature-requests`, and
`/contribute`. It never covers the leaderboard's content on any breakpoint (pages add bottom
padding per §1.3).

### 6.1 Closed state — floating action button

```
                                                    ┌────┐
                                                    │ 💬 │  56px, blue-600
                                                    └────┘
```

- `fixed z-40 bottom-5 right-5 sm:bottom-6 sm:right-6`, `h-14 w-14 rounded-full bg-blue-600`,
  white 22px 1.75px-stroke speech-bubble icon, `shadow-[0_6px_20px_rgba(21,93,252,0.30)]`.
- Hover `bg-blue-700` + `motion-safe:-translate-y-px`; active `scale-[0.98]`;
  focus-visible outline 2px `blue-600`, `offset-3`.
- `aria-label="Send feedback"`, `aria-haspopup="dialog"`, `aria-expanded`,
  `aria-controls="feedback-panel"`.
- **When the panel is open the FAB becomes the close control:** icon swaps to a 22px X and the
  label to `Close feedback`. `motion-safe` 150ms cross-fade; no rotation.
- The FAB is hidden (`hidden`, and removed from the tab order) whenever the account dialog or the
  suggest-a-feature modal is open.
- Below 640px the FAB respects `env(safe-area-inset-bottom)`.

### 6.2 Open state — panel

```
┌────────────────────────────────────────┐
│ Send feedback                       ✕  │
│ Help us make Alpha Poker better.       │
│                                        │
│ [  Bug  ] [  Idea  ] [  Other  ]       │  ← Idea selected by default
│ ┌────────────────────────────────────┐ │
│ │ What would make Alpha Poker more   │ │
│ │ fun?                               │ │
│ │                                    │ │
│ └────────────────────────────────────┘ │
│ Sent with your username and this page. │
│ [        Send feedback         ]       │
└────────────────────────────────────────┘
                                   ┌────┐
                                   │ ✕  │
                                   └────┘
```

- Position: `fixed z-40 bottom-[5.5rem] right-6 w-[22rem]` (352px); below 640px
  `left-4 right-4 bottom-[5.25rem] w-auto`.
- Card: `rounded-[12px] border border-zinc-200 bg-white p-5
  shadow-[0_12px_32px_rgba(9,9,11,0.12)]`.
- Header: `Send feedback` (`text-[1.0625rem] font-bold text-zinc-900`) with a 28×28 ghost X at the
  top right (`aria-label="Close"`); sub line `Help us make Alpha Poker better.`
  (`mt-1 text-[0.8125rem] text-zinc-500`).
- **Type selector**: `mt-4 grid grid-cols-3 gap-2`, `role="radiogroup" aria-label="Feedback type"`.
  Each option `h-9 rounded-[5px] border text-[0.8125rem] font-medium`, `role="radio"`,
  `aria-checked`.
  - Unselected: `border-zinc-300 text-zinc-700 hover:bg-zinc-50`
  - Selected: `border-blue-600 bg-blue-600 text-white`
  - Options in order: **Bug**, **Idea**, **Other**. Default: **Idea**.
  - One tab stop for the group; `← → ↑ ↓` move and select; `Home`/`End` jump.
- **Message**: `mt-3`, `<textarea rows={4} maxLength={500}>`, `min-h-[6rem] w-full rounded-lg
  border border-zinc-300 px-3 py-2.5 text-[0.875rem] leading-6 resize-y outline-none
  focus:border-blue-600 focus:ring-2 focus:ring-blue-100`. Placeholder follows the type:

  | Type | Placeholder |
  | --- | --- |
  | Bug | `What went wrong? What were you doing?` |
  | Idea | `What would make Alpha Poker more fun?` |
  | Other | `Tell us anything.` |

  Switching type replaces the placeholder and never clears typed text.
- **Counter**: appears only past 400 characters, right-aligned, `text-xs text-zinc-400`, `red-600`
  at 500.
- **Helper line**: `mt-2 text-[0.75rem] text-zinc-500`.
  - Signed in: `Sent with your username and this page.`
  - Signed out: `Sent anonymously with this page address.`
- **Submit**: `mt-4 w-full` primary, 44px, label `Send feedback`. Disabled until the trimmed
  message has ≥ 3 characters.

### 6.3 Sending state

- Button: spinner + `Sending…`, `disabled`, `aria-busy="true"`.
- Textarea and all three type buttons: `disabled` with `opacity-60`.
- The panel's X is disabled and `Escape` is ignored — a message in flight cannot be lost by a
  stray keystroke.
- No overlay is shown at any point; the page stays interactive behind the panel except for the
  panel's own controls.

### 6.4 Success state

On a `2xx` response:

1. The panel closes immediately and resets — message cleared, type back to **Idea**.
2. A toast (§3.4) appears with a green check and `Thanks — we got it.` for 4 seconds.
3. Focus returns to the FAB.
4. The submitted text is never echoed back into the page.

### 6.5 Error state

Inline in the panel, above the submit button:
`rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-[0.8125rem] text-red-700`,
`role="alert"`. The panel stays open and the typed message is always preserved.

| Condition | Copy |
| --- | --- |
| network / 503 / `api_unavailable` | `Couldn't send that. Check your connection and try again.` |
| 429 / `rate_limited` | `You're sending a lot right now. Try again in a minute.` |
| 401 / `unauthorized` | `Your session expired.` plus an inline `Log in` text-link button that opens the account dialog while keeping the draft |
| 400 / `validation_error` | `That message is too long. Keep it under 500 characters.` |
| any other 5xx | `Something went wrong on our side. Try again.` |

Server `error.message` is never displayed.

### 6.6 Panel behavior

- **Non-modal dialog**: `role="dialog" aria-modal="false" aria-labelledby="feedback-title"`,
  `id="feedback-panel"`.
- Opening moves focus to the textarea. `Escape` closes and returns focus to the FAB.
- A click outside closes the panel **only when the message is empty**; with a draft it stays open.
- Page scroll is not locked; no focus trap (it is non-modal by design, so the page behind stays
  usable).
- Opening the account dialog or the suggest-a-feature modal closes the panel first.
- **Draft persistence**: message text and selected type persist across open/close and full route
  navigation in `sessionStorage` under one Alpha Poker-specific key. It is cleared immediately
  after successful submission and never persists beyond the browser tab's session.
- Route changes may close the panel, but never clear its draft; the `path` recorded at submit time
  is the path at the moment of submission.
- Client guard: a second submit is blocked while one is in flight, and after a success the submit
  button stays disabled for 2s.

### 6.7 Payload

```jsonc
{
  "type": "bug" | "idea" | "other",
  "message": "…",                 // ≤ 500 chars after trim
  "path": "/feature-requests"     // pathname only
}
```

- `path` is `location.pathname` with the query string and hash **stripped**, so tokens or
  identifiers in a URL are never exfiltrated into feedback records.
- The username is attached server-side from the session cookie; the client never sends it.
- No full user-agent string, screen size, referrer, version, or fingerprint is collected. The
  server may retain one coarse category such as `Safari/mobile` for debugging, and automatically
  deletes feedback after the configured retention window (90 days by default).

---

## 7. Cross-cutting rules

### 7.1 Untrusted content

Everything authored outside the codebase is untrusted: feature-request titles and details,
usernames, feedback text (on any future admin view), GitHub issue titles, labels, and logins.

1. **Text only.** Render through React's text children. Never `dangerouslySetInnerHTML`. No
   markdown rendering, no HTML, no auto-linking in MVP — a URL inside a title displays as literal
   text and is not clickable.
2. **Sanitize at the UI boundary**, mirroring `normalizeEntry` in `app/components/Leaderboard.tsx`:
   - Reject the item if the title or username contains C0/C1 controls `/[\x00-\x1f\x7f-]/`.
   - Strip bidi overrides and isolates: `‪-‮`, `⁦-⁩` — prevents right-to-left
     text-direction spoofing of titles and author names.
   - Strip zero-width characters: `​-‍`, `⁠`, `﻿`.
   - Trim, then slice by **code points** (`Array.from(...)`), never by UTF-16 index, so emoji and
     combined characters are not split into mojibake.
3. **Never trust server-supplied styling.** GitHub label colors, status strings, and avatar colors
   are mapped through fixed local tables. An unrecognized value falls back to the neutral entry.
4. **Never trust server-supplied URLs.** Validate against the configured
   `https://github.com/{owner}/{repo}/…` prefix before use as an `href`. Failing that check,
   render text without an anchor.
5. **Never render `error.message` from the API.** Map `error.code` to the copy tables in §4.7,
   §4.9, §5.8, and §6.5.
6. Emoji in user text is allowed and rendered at normal size — this is a kid-friendly product.

### 7.2 Truncation

| Element | Method | Limit | Full text |
| --- | --- | --- | --- |
| Request title | `line-clamp-2 break-words` | 80 code points hard cap (server + client) | `title` attribute |
| Request details | `line-clamp-2 break-words` | 500 stored | `title` attribute |
| Username (row meta) | `truncate` | 20 display code points, `…` | `title` attribute |
| Username (account chip) | `truncate max-w-[9rem]` | 16 display code points | `title` attribute |
| GitHub issue title | `truncate` | 90 display code points | `title` attribute |
| GitHub label | `truncate` | 22 display code points | none |
| Assignee login | `truncate` | 14 display code points | `title` attribute |
| Feedback message | none — not displayed after send | 500 | n/a |

- `break-words` (`overflow-wrap: anywhere`) is mandatory on every user-authored block so a
  300-character unbroken string cannot widen a row or force horizontal scroll.
- Truncation is a display concern only; validation limits are enforced independently on both the
  client and the server.
- `…` is a single ellipsis character, appended by replacing the final visible character (matching
  `displayName()` in `Leaderboard.tsx`).

### 7.3 Responsive matrix

| Width | Header nav | Grid | Row | Feedback panel | Modal |
| --- | --- | --- | --- | --- | --- |
| 360–479 | hamburger | 1 col | vote 48px, no divider, chip inline in meta | `left-4 right-4` | bottom sheet |
| 480–639 | hamburger | 1 col | as above | `left-4 right-4` | bottom sheet |
| 640–767 | hamburger | 1 col | vote 64px + divider, chip column returns | 352px anchored right | centered 512px |
| 768–1023 | hamburger | 1 col, rail below | full row, comment counts visible | 352px | centered |
| 1024–1279 | centered nav | 2 col (`1fr / 320px`) | full row + assignee column | 352px | centered |
| ≥1280 | centered nav | 2 col, container caps at 1216px | full row | 352px | centered |

- No horizontal scrollbar at any width ≥ 320px on any of these surfaces.
- Touch targets: ≥ 40px on touch widths for vote arrows, nav links, chips-as-buttons, and the FAB.
- Sticky rails are disabled below 1024px.

### 7.4 Accessibility

- One `<h1>` per page, matching the visible hero headline.
- Landmarks: `<header>` (with `<nav aria-label="Main">`), `<main>`, and named regions for the list
  (`aria-labelledby` on the list's own heading, visually hidden if needed).
- Lists are real `<ul>`/`<ol>`; steps on `/contribute` are an `<ol>`.
- Every icon-only control has an `aria-label`; every decorative icon has `aria-hidden="true"`.
- One polite live region per page for vote-score, load-more, and copy-style announcements; a
  second `role="alert"` region for errors.
- Color is never the only signal: statuses carry text labels, errors carry text, the top-row
  highlight carries no unique meaning.
- Contrast: all body and meta text meets 4.5:1 on white; chip text meets 4.5:1 on its tint;
  `zinc-400` is used only for non-essential glyphs and counters, never for meaningful text.
- Keyboard: everything reachable in DOM order, nothing reachable behind a modal, no positive
  `tabIndex`, no keyboard traps outside intentional modal focus traps.
- `prefers-reduced-motion` is honored per §1.7.

### 7.5 Client data contracts

All browser calls go through `app/browser-api/*` (session cookie → `Authorization` header) using
the existing `proxyApi` pattern. The browser never talks to the league API or GitHub directly.

| Method | Path | Body / Query | Response |
| --- | --- | --- | --- |
| `GET` | `/browser-api/feature-requests` | `?tab=top\|new\|planned&cursor=` | `{ items: Request[], next_cursor: string \| null }` |
| `POST` | `/browser-api/feature-requests` | `{ title, details }` | `Request` |
| `POST` | `/browser-api/feature-requests/{id}/vote` | `{ value: 1 \| 0 \| -1 }` | `{ score, my_vote }` |
| `PATCH` | `/browser-api/feature-requests/{id}` | `{ status }` — operator | `Request` |
| `POST` | `/browser-api/feature-requests/{id}/hide` | `{ hidden: boolean }` — operator | `204` |
| `POST` | `/browser-api/feedback` | `{ type, message, path }` | `204` |
| `GET` | `/browser-api/github/issues` | — (server-cached 10 min) | `{ items: Issue[] }` |

```ts
type Request = {
  id: string;
  title: string;                   // ≤ 80
  details: string | null;          // ≤ 500
  status: "submitted" | "under_review" | "planned" | "in_progress" | "shipped" | "declined";
  score: number;                   // net, may be negative
  my_vote: "up" | "down" | null;
  author: string;                  // username
  created_at: string;              // ISO-8601
};

type Issue = {
  number: number;
  title: string;
  url: string;                     // validated against the repo prefix before use
  labels: string[];                // names only; colors are local
  assignee: string | null;
  comments: number;
};
```

- Errors use the existing envelope `{ error: { code, message } }`. The client switches on `code`
  and on the HTTP status; `message` is for logs only.
- `is_operator: boolean` is added to the existing session/status response and drives §4.11.
- Missing or malformed fields degrade gracefully: absent `details` hides the description line,
  absent `my_vote` means "no vote", an unknown `status` renders `Open`.

---

## 8. File plan

New files only; nothing existing is restructured.

```
app/
  components/
    SiteHeader.tsx          — logo lockup, nav, mobile disclosure, account chip slot
    FeedbackWidget.tsx      — FAB + panel + all states (mounted in layout.tsx)
    Toast.tsx               — shared toast (§3.4)
    StatusChip.tsx          — §3.2
    FeatureRequestList.tsx  — list, rows, votes, pagination, states
    SuggestFeatureDialog.tsx— compose modal (§4.7)
  feature-requests/page.tsx
  contribute/page.tsx
  browser-api/
    feature-requests/…      — proxy routes
    feedback/route.ts
    github/issues/route.ts
```

Changes to existing files, kept minimal:

- `app/layout.tsx` — mount `<FeedbackWidget />` after `{children}`.
- `app/page.tsx` — swap the inline header for `<SiteHeader />`; hero, leaderboard, and
  instructions sections are untouched.
- `app/components/AuthButton.tsx` — trigger restyled to the chip (§2.4); dialog body unchanged.
- `tests/rendered-html.test.mjs` — relax the `Log in` button assertion (see §2.4 note).

---

## 9. Acceptance checklist

### 9.1 Implementer — structure and behavior

**Global**

- [ ] Header is 72px tall at 360, 768, 1024, and 1440px; the landing hero still fills
      `100svh − 72px`.
- [ ] Nav shows Leaderboard / Feature requests / Contribute, centered at ≥1024px, hamburger below.
- [ ] The correct nav item is active with a 2px blue underline and `aria-current="page"` on each
      of `/`, `/feature-requests`, `/contribute`.
- [ ] Header is sticky on the two community pages and static on `/`.
- [ ] Mobile nav opens, traps nothing, closes on Escape / outside click / route change, and
      returns focus to the toggle.
- [ ] Account chip renders `Log in` signed out and person + username + chevron signed in; the
      account dialog opens with unchanged content.
- [ ] `npm run test` passes after the documented single assertion update; `npm run lint` is clean.

**Feature requests**

- [ ] Tabs are links; `?tab=new` and `?tab=planned` deep-link correctly; an unknown value falls
      back to Top.
- [ ] Vote up/down toggles, is optimistic, rolls back on failure, and blocks concurrent requests
      per row.
- [ ] `aria-pressed` tracks the viewer's vote; score changes are announced politely once.
- [ ] Signed out: arrows and the suggest button open the account dialog; no vote is replayed after
      login; the compose modal auto-opens only after a suggest-triggered login.
- [ ] Compose modal traps focus, opens focus on Title, closes on Escape, ignores backdrop clicks
      while a draft exists, submits on `Cmd/Ctrl+Enter`, and preserves the draft after closing.
- [ ] Post success switches to New, prepends and highlights the row, and shows the toast.
- [ ] Every error path shows mapped copy, never a raw server message.
- [ ] Loading, empty, filtered-empty, and error states all render as specified.
- [ ] Load-more appends 25, announces, and disappears when exhausted.
- [ ] Operator status menu changes status optimistically, hide requires the two-step confirm, and
      undo restores the row; none of it renders for non-operators.
- [ ] No comments, comment counts, or reply UI exist anywhere on the page.

**Contribute**

- [ ] Issues are fetched server-side, cached 10 minutes, and capped at 5 rows.
- [ ] Every issue `href` is validated against the repo prefix; a failing URL renders as text.
- [ ] Label colors come from the local map; GitHub's `color` field is unused.
- [ ] All external links use `target="_blank" rel="noopener noreferrer"` with a hidden
      "opens in a new tab".
- [ ] Loading, empty, and error states render inside the issues card while the rest of the page
      stays usable.

**Feedback widget**

- [ ] The FAB appears on all three pages, hides while any modal is open, and becomes a close
      button when the panel is open.
- [ ] Type radios support arrow keys with a single tab stop; Idea is the default.
- [ ] Submit is disabled under 3 characters; sending disables the form and blocks Escape/close.
- [ ] Success closes the panel, resets it, toasts for 4s, and returns focus to the FAB.
- [ ] Every error keeps the draft; the 401 case offers an inline log-in.
- [ ] The payload contains only `type`, `message`, and a query-stripped `path`.
- [ ] Only the unsent feedback draft is kept in tab-scoped `sessionStorage`; no community data is written to `localStorage`.

**Cross-cutting**

- [ ] No `dangerouslySetInnerHTML` anywhere in the new code.
- [ ] Control characters, bidi overrides, and zero-width characters are stripped from all
      untrusted strings before render.
- [ ] A 300-character unbroken title and a 40-character username produce no horizontal scroll at
      360px.
- [ ] `prefers-reduced-motion` disables pulse, slide, and fade everywhere.
- [ ] No horizontal scrollbar at 320, 360, 390, 768, 1024, 1280, or 1440px.

### 9.2 Screenshot reviewer — visual verification

Capture at **390×844** (mobile) and **1440×900** (desktop) for each item.

**Must be present**

- [ ] `/feature-requests` desktop: centered H1 + lead, tabs left / primary button right, rows with
      a 64px vote rail and a divider, one status chip per row, rail card on the right with three
      numbered steps.
- [ ] `/feature-requests` mobile: hamburger header, full-width 3-up tabs, full-width primary
      button, 48px vote rail, chip inline in the meta line, rail card below the list.
- [ ] Compose modal: centered 512px card on desktop, bottom sheet on mobile, character counters,
      Cancel + Post idea.
- [ ] `/contribute` desktop: `</>` glyph, OPEN SOURCE eyebrow, H1, two hero buttons, four step
      cards in one row joined by dashed connectors, issues card with labels, right rail, closing
      strip.
- [ ] `/contribute` mobile: steps stack 1-up (2-up at 640–1023px), labels/assignee/comments hidden
      per §7.3, rail below the issues card.
- [ ] Feedback FAB bottom-right on every page; open panel with Bug/Idea/Other and Idea selected;
      sending button with spinner; success toast with a green check.
- [ ] Empty, loading, and error states for both pages.
- [ ] Focus rings visible on: nav link, account chip, vote arrow, tab, primary button, FAB, modal
      close, textarea.
- [ ] Landing page unchanged apart from the header nav and account chip.
- [ ] Leaderboard unchanged: podium plus `Rank / Bot / Player / Elo / Record`.

**Must NOT appear**

- [ ] No `bb/100`, `95% range`, confidence interval, or `Hands` column anywhere.
- [ ] No RiverRat-era featured-leader panel or seeded sample requests.
- [ ] No Discord link, icon, or "join our community" invitation.
- [ ] No comment counts, comment icons, or reply threads on feature requests.
- [ ] No casino imagery: felt, chips, dice, decorative suits, gold gradients, neon.
- [ ] No character art, mascots, or emoji used as interface icons.
- [ ] No scattered decorative glyphs behind the `/contribute` hero.
- [ ] No horizontal scrollbar, no clipped text, no overlapping FAB and content at any captured
      width.
- [ ] No raw API error strings, stack traces, or status codes shown to users.
