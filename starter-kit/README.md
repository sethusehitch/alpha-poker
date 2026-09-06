# Alpha Poker starter kit

This folder is everything your coding agent needs to build and operate an Alpha Poker bot.
Alpha Poker is a private, play-money heads-up Texas Hold'em bot competition.

Give the ZIP and the prompt from the Alpha Poker website to Claude, ChatGPT,
or Codex. Your coding agent should perform the setup and competition workflow
for you. You do not need to open a terminal or type Alpha Poker commands.

Your agent can also find rivals, send a direct challenge after you approve the
opponent, respond to incoming challenges, wait for results, and bring back a
recap with hand evidence. You choose whom to face and how to change the bot;
the agent handles the CLI and API details.

## Build your bot

1. Change the strategy inside `decide(state)` in `bot.py`.
2. Give your bot a unique name in `bot.json`.
3. Leave the manifest version, language, and entrypoint unchanged.
4. Let your coding agent install the bundled Alpha Poker CLI from the `cli` folder.
5. Give your coding agent your username and invite code when it requests them.
   It will register or log in, validate the bot, train it, and submit it for you.

Only `bot.py` and `bot.json` are uploaded. The CLI packages them for you.
See `WORKFLOWS.md` for the hosted API address and the complete build, train,
submit, status, and log-download workflow your coding agent can perform.

Do not submit from a terminal yourself. Ask your coding agent to validate,
train, upload, and confirm the result. It should explain what it is about to do
and operate the CLI itself.

## Train against the leader

Keep your bot on your computer and play practice hands against a frozen copy of
the current leader. Ask your coding agent to start a training session, inspect
the results, and improve the strategy. It will operate the bundled CLI for you.

Training does not affect the leaderboard. When it finishes, the CLI downloads a
ZIP containing the hand logs into the current directory.

## Challenge a rival

Ask your coding agent to show available rivals or search for a classmate. A
direct challenge always uses the current active bot for each player and plays
200 mirrored heads-up hands after the recipient accepts. It is play-money only,
does not change Elo, and appears in the head-to-head history for those two
players. Your agent can monitor the request, explain whether you won or lost,
download the recap, and help you inspect evidence before you decide what to
change next.

## Bot rules

- Implement one synchronous function: `decide(state: dict) -> dict`.
- Return in less than 250 ms and keep output under 4 KB.
- Use only the Python standard library.
- Do not use the network, subprocesses, secrets, or file writes.
- Read only the information in `state`. Hidden opponent cards are never present.
- If your strategy uses randomness, seed it with `bot_random_seed` so runs can be reproduced.
- Check when possible and fold otherwise if your strategy cannot make a decision.

See `API.md` for the complete state and action contract.
