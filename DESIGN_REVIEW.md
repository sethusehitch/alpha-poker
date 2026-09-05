# Alpha Poker landing page design review

Prepared by the dedicated Claude design pass.

## Direction

Use a restrained, Notion-like system: white canvas, black system sans-serif typography, thin gray rules, generous whitespace, and one cobalt accent. Do not use cards, chips, felt, casino colors, gradients, or decorative imagery.

Natural page order:

1. Hero
2. Leaderboard
3. Instructions

There is one private league. Do not show room controls or authentication UI. The small `Log in` label may remain as inert preview text.

## Tokens

| Token | Value |
| --- | --- |
| Background | `#ffffff` |
| Primary text | `#111111` |
| Secondary text | `#6b6b6b` |
| Rule | `#e6e6e6` |
| Strong rule | `#d9d9d9` |
| Accent | `#1e4fd8` |
| Accent hover | `#173daa` |
| Winner background | `#eef3fe` |
| Winner border | `#b9ccfa` |
| Code background | `#f7f7f7` |

Use a system font stack. The desktop hero headline is about 56px with 1.08 line height and a slight negative tracking. Mobile uses about 34px. Section headings are 22px. Body and table text are 15px. Labels are 13px. Prompt content uses the system monospace stack.

## Layout

- Keep primary content within a centered 760px column with 24px side padding.
- Use 96px between major sections on desktop and 48px on mobile.
- Center the hero within a slightly narrower column.
- Break the hero headline after `Build a poker bot.` on normal desktop widths.
- Keep both hero buttons 44px tall with a 12px gap.
- Anchor buttons scroll to `#instructions` and `#leaderboard`.

## Leaderboard

- Lead with a pale-blue featured panel for the current leader.
- Use a small cobalt crown, `CURRENT LEADER`, large `RiverRat`, and `Maya • +8.42 bb/100 • 152,000 hands`.
- The regular table begins at rank 2.
- Use real table semantics and tabular numerals.
- Avoid zebra stripes and shadows. A very light hover background is enough.
- On screens below 640px, reflow each table row into a readable stacked row instead of adding horizontal scrolling.
- Keep confidence intervals visible because statistical uncertainty is part of the product.

## Instructions

- Step 1 is `Download the starter kit` and names `alpha-poker-starter.zip` explicitly.
- Step 2 is `Paste this prompt into Claude, ChatGPT, or Codex`.
- Place the prompt in a bordered, light-gray code block with a Copy button.
- After copying, change the label to `Copied` for two seconds and announce the change through an `aria-live` region.
- The download link must target `/alpha-poker-starter.zip`.

## Interaction and accessibility

- Use a visible 2px cobalt `:focus-visible` outline with a 2px offset.
- Keep every action keyboard reachable.
- Use real headings, links, buttons, and table headers.
- Mark the winner panel with `aria-label="Current leader"` and hide the decorative crown from assistive technology.
- Smooth scrolling and subtle transitions are allowed only when reduced motion is not requested.
- Do not make static leaderboard rows focusable.

## Visual QA

- Hero, leaderboard, and instructions appear in that exact order.
- Both hero buttons land on the correct section.
- RiverRat appears only in the featured winner panel, not again in the rank table.
- The mobile table has no horizontal overflow.
- The copy button updates, announces its state, and resets.
- The starter ZIP downloads with the exact filename.
- Focus rings remain visible throughout keyboard navigation.
- No Alpha School copy, casino imagery, gradients, gold, or room UI appears anywhere.
- Reduced-motion mode disables smooth scrolling and transitions.
