# Alpha Poker bot API

API version: `2026-09-01`

Your bot exports this function from `bot.py`:

```python
def decide(state: dict) -> dict:
    return {"action": "check"}
```

The game server is authoritative. Every state is a fresh JSON-compatible
dictionary. Do not mutate it or retain it as the source of truth.

## State

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Version of this contract |
| `match_id` | string | Match identifier |
| `hand_id` | string | Hand identifier |
| `hand_number` | integer | Hand number within the match |
| `seat` | integer | Your seat |
| `button_seat` | integer | Dealer button seat |
| `street` | string | `preflop`, `flop`, `turn`, or `river` |
| `hole_cards` | string[] | Your two private cards |
| `community_cards` | string[] | Public cards dealt so far |
| `pot` | integer | Chips currently in the pot |
| `stacks` | object | Chips behind by seat |
| `committed` | object | Chips committed this street by seat |
| `to_call` | integer | Chips needed to call |
| `min_raise_to` | integer or null | Smallest legal total commitment |
| `max_raise_to` | integer or null | Largest legal total commitment |
| `legal_actions` | string[] | Actions accepted for this decision |
| `action_history` | object[] | Public actions in this hand |
| `decision_deadline_ms` | integer | Maximum decision time |
| `bot_random_seed` | integer | Reproducible strategy seed |

Cards are rank plus suit, such as `Ah`, `Td`, `7c`, and `2s`. Chip amounts are integers.

Example state:

```json
{
  "schema_version": "2026-09-01",
  "match_id": "match_123",
  "hand_id": "hand_456",
  "hand_number": 12,
  "seat": 0,
  "button_seat": 0,
  "street": "flop",
  "hole_cards": ["Ah", "Kd"],
  "community_cards": ["7c", "Js", "2d"],
  "pot": 120,
  "stacks": {"0": 1960, "1": 1920},
  "committed": {"0": 0, "1": 40},
  "to_call": 40,
  "min_raise_to": 80,
  "max_raise_to": 1960,
  "legal_actions": ["fold", "call", "raise", "all_in"],
  "action_history": [],
  "decision_deadline_ms": 250,
  "bot_random_seed": 8675309
}
```

## Actions

Return exactly one of:

```json
{"action": "fold"}
{"action": "check"}
{"action": "call"}
{"action": "raise", "amount": 240}
{"action": "all_in"}
```

The returned action must appear in `legal_actions`. A raise amount is the final
total committed on the current street, not the increment, and must be between
`min_raise_to` and `max_raise_to`, inclusive. Do not include `amount` for any
other action.

An invalid action, exception, timeout, or oversized response forfeits the hand.

## Training transport

The CLI handles REST and WebSocket communication. `bot.py` receives the same
state and returns the same action in local validation, hosted competition, and
training. Do not put transport code or platform tokens inside your bot.
