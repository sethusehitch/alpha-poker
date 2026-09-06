# Agent-led rookie tutorial

## Product decision

Alpha Poker onboarding stays in the student's coding-agent conversation. The
website continues to offer the starter kit and one shared copy button. There is
no website wizard, duplicate checklist, or separate onboarding state machine.

## First response

After locating and reading the newest starter kit, the agent must:

1. Welcome the student and say it will handle the technical setup.
2. Show Build, Train, Compete, Challenge someone, Review hands, and Check
   progress in a compact table, including whether each changes Elo.
3. Fetch and show up to three real leaders with Elo and record.
4. Invite the student to chase the podium in a playful, encouraging tone.
5. Offer the six actions, recommend **Build my first bot** to a beginner, and
   wait for a choice before acting.

## Rookie path

The beginner path has four conversational milestones:

- **Create:** choose a bot name and Bold, Patient, Tricky, or Surprise me.
- **Build:** create and validate the bot while explaining its strategy simply.
- **Practice:** train against the leader, review hands, explain one strength and
  one improvement, make a useful change, and validate again.
- **Compete:** explain replacement behavior, request approval, submit, and
  report the real league status.

Rivals, detailed logs, and advanced commands remain available when requested,
but they are introduced to beginners after the first bot is competing.

## Safety and trust

- The agent operates the CLI and does not make the student copy commands.
- Public standings are fetched live and never fabricated.
- Passwords and required invite codes remain inside the CLI's secure prompts.
- Invite codes and session tokens never enter bot files, logs, summaries, or
  source control.
- Submission, replacement, and rival-challenge actions require explicit human
  approval.
- An accepted bot waiting for more players is active but unranked; onboarding
  must say that its Elo has not changed yet.

## Acceptance criteria

- The landing page and signed-in My Bot page copy the same prompt.
- The prompt stops after presenting the opening menu and waits for a choice.
- A new student can complete Create, Build, Practice, and Compete without
  operating a terminal or understanding the API.
- A returning student can choose a specific workflow without repeating rookie
  onboarding.
- Empty or unavailable standings do not block the menu.
- Independent clean-slate agents can finish the flow using only the website,
  copied prompt, starter kit, and required human inputs.
