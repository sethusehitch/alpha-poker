# Alpha Poker participant instructions

Alpha Poker is one private, play-money competition for autonomous poker bots. You build one bot, validate it locally, upload it for official competition, and use the same bot against the current leader through the training socket.

## Step 1: Download the starter kit

Click **Download starter kit** on the website. The downloaded file is named:

```text
alpha-poker-starter.zip
```

Leave it in your Downloads folder. You do not need to open or reorganize it first.

## Step 2: Paste this prompt into Claude, ChatGPT, or Codex

Copy the entire prompt below into your coding agent:

```text
The file I downloaded is named alpha-poker-starter.zip and should be in my Downloads folder. Find it and extract it into a new folder named alpha-poker-bot.

Build me a poker bot for Alpha Poker using that starter kit. Read the included README.md and API.md before changing any code. Implement my complete strategy in bot.py through the decide(state) function. Do not modify the supplied competition or WebSocket adapters.

Requirements:
- Return only legal fold, check, call, raise, or all_in actions.
- For a raise, amount means the final total committed on the current street, not the increment.
- Respect legal_actions, min_raise_to, max_raise_to, and decision_deadline_ms.
- Never assume that an opponent's hidden cards are available.
- Use no network requests, subprocesses, secrets, external services, or file writes.
- Use only the Python standard library.
- Keep normal decisions comfortably below the 250 ms limit.
- Use bot_random_seed if the strategy needs reproducible randomness.
- Fail safely by checking when legal, otherwise folding.

After implementing the strategy:
1. Run alpha-poker validate .
2. Run local reference matches and fix every invalid action, timeout, and crash.
3. Summarize the strategy, likely weaknesses, and validation result.
4. Leave the extracted alpha-poker-bot folder ready for me to submit.

The identical bot.py must work in hosted competition and through the local training WebSocket adapter. Never put an Alpha Poker token or password in bot.py.
```

## Submit and train

When your coding agent finishes, open a terminal in the extracted `alpha-poker-bot` folder:

```bash
alpha-poker login
alpha-poker submit .
alpha-poker train --opponent leader --hands 5000
```

The CLI creates the submission ZIP for you. You do not need to package it manually. There is one league, so there is no room to select or join.

## Package format

The starter kit has this structure:

```text
alpha-poker-bot/
  bot.py
  bot.json
  README.md
  API.md
  alpha_poker_runner.py
  alpha_poker_cli.py
```

Only `bot.py` and `bot.json` become part of the submitted ZIP. The CLI rejects symlinks, executables, nested archives, files outside the package root, and packages over 2 MB.

Example `bot.json`:

```json
{
  "api_version": "2026-09-01",
  "name": "RiverRat",
  "language": "python",
  "entrypoint": "bot.py:decide"
}
```

## Bot function

Your bot exports one function:

```python
def decide(state: dict) -> dict:
    if "check" in state["legal_actions"]:
        return {"action": "check"}
    return {"action": "fold"}
```

The function receives a read-only game-state dictionary and returns one action dictionary.

### State fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Version of this state contract |
| `match_id` | string | Current match identifier |
| `hand_id` | string | Current hand identifier |
| `hand_number` | integer | Hand number within the match |
| `seat` | integer | Your seat |
| `button_seat` | integer | Dealer button seat |
| `street` | string | `preflop`, `flop`, `turn`, or `river` |
| `hole_cards` | string[] | Your two private cards |
| `community_cards` | string[] | Public board cards currently dealt |
| `pot` | integer | Current pot in integer chips |
| `stacks` | object | Chips behind for each seat |
| `committed` | object | Chips committed on the current street |
| `to_call` | integer | Chips required to call |
| `min_raise_to` | integer or null | Minimum legal raise-to amount |
| `max_raise_to` | integer or null | Maximum legal raise-to amount |
| `legal_actions` | string[] | Actions currently accepted |
| `action_history` | object[] | Public actions in this hand |
| `decision_deadline_ms` | integer | Time budget for this decision |
| `bot_random_seed` | integer | Reproducible randomness seed unrelated to the deck seed |

Cards use rank followed by suit, such as `Ah`, `Td`, `7c`, or `2s`.

### Action format

```json
{"action": "fold"}
```

```json
{"action": "check"}
```

```json
{"action": "call"}
```

```json
{"action": "raise", "amount": 240}
```

```json
{"action": "all_in"}
```

For `raise`, `amount` is the total amount committed on the current street after the raise.

## Validation

`alpha-poker validate .` performs:

- ZIP safety and manifest checks
- Import test in a clean Python environment
- State and response schema tests
- Legal-action property tests
- 100 smoke-test hands against reference bots
- Determinism check using repeated decision seeds
- CPU, memory, output-size, and timeout checks

A failed submission never replaces the user's active bot.

## Training

Training connects your local bot to a frozen snapshot of the current leader:

```bash
alpha-poker train --opponent leader --hands 5000
```

The CLI:

1. Imports your local `bot.py`.
2. Creates a short-lived training session.
3. Opens the authenticated Alpha Poker WebSocket.
4. Converts `action.requested` messages into calls to `decide(state)`.
5. Sends your action back with the current hand, turn, and idempotency identifiers.
6. Reconnects and resynchronizes automatically when needed.
7. Downloads the training hand history when the session completes.

Training does not affect the leaderboard. Opponent cards remain hidden unless they are shown down. Training tokens expire after one hour and are never passed into `bot.py`.

## Competition and scoring

Official evaluation uses heads-up no-limit Texas Hold'em with play money, fixed 100 big-blind stacks, no rake, and stacks reset each hand.

Every deal is played twice with seats reversed. Rankings use average `bb/100` against the current room field. The leaderboard also reports a 95% confidence interval and hand count.

Uploads validate immediately. The official league uses one nightly snapshot containing every member's latest accepted bot. This prevents early and late uploaders from being evaluated against different fields.

## Full protocol

See [API.md](./API.md) for the REST endpoints, WebSocket message catalog, authentication rules, errors, limits, and reconnection behavior.
