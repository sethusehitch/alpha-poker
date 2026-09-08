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

## Rival challenge API

The coding agent should use the bundled `alpha-poker` CLI instead of writing
transport code. This section documents the platform surface so an agent can
understand responses and diagnose a problem. All endpoints below use the
hosted `/v1` base URL and require the stored login session.

### Discover rivals

```text
GET /rivals?source=mine|leaderboard&q=SEARCH
GET /rivals/{username}
GET /rivals/{username}/history?limit=20&cursor=CURSOR
GET /rivalries/compare?player_a=maya&player_b=theo&limit=20
```

Rival summaries contain the player's username, active bot, public Elo, direct
challenge record against the caller, current shared challenge when one is
open, and whether that opponent is the caller's Nemesis. History and Nemesis
are computed from direct challenges only. Official round-robin meetings are
never included.

### Create and manage a challenge

```text
POST /challenges
GET  /challenges?status=incoming|running|finished
GET  /challenges/{challenge_id}
POST /challenges/{challenge_id}/accept
POST /challenges/{challenge_id}/decline
POST /challenges/{challenge_id}/cancel
GET  /challenges/{challenge_id}/recap
```

Creation body:

```json
{"opponent_username":"maya"}
```

Creation and state-changing requests include an `Idempotency-Key` header.
Every challenge is a best-of-five, play-money Pot-Limit Hold'em series. Each game starts 10,000 to 10,000, carries stacks between hands, and doubles blinds every 10 hands until a current-stack-sized sudden-death level. Bankruptcy ends a game; the first bot to win three games wins the series. A pending request has not started. Acceptance snapshots both current active bots and moves the challenge into the server queue.

Challenge states are:

```text
pending -> queued -> running -> completed
pending -> declined
pending -> cancelled
queued or running -> failed
```

A completed challenge reports `winner_username`, `series_score`, `games_completed`, and `hands_played`. A direct challenge never changes either player's Elo.

The server rejects self-challenges, participants without an active bot,
duplicate open challenges between the same pair, and transitions attempted by
the wrong user. Treat those errors as explanations for the participant, not as
a reason to expose tokens or retry indefinitely.

### Notifications

```text
GET  /notifications?unread=true&limit=20&cursor=CURSOR
POST /notifications/{notification_id}/read
POST /notifications/read-all
```

Notification types are `challenge_received`, `challenge_won`,
`challenge_lost`, and `challenge_failed`. Display facts are snapshotted so an
old message does not change after someone uploads a new bot. Read a
notification only after its target challenge or recap opens successfully.

### CLI result behavior

Rivals result commands accept `--format human|agent|json`; `--json` remains an alias. JSON mode emits exactly one object on stdout, agent mode emits stable `key=value` facts, and human mode uses concise prose. No password, bearer token, invite code, or training capability is included in output or artifacts.
