export type DirectRecord = {
  wins: number;
  losses: number;
  draws: number;
  played: number;
};
export type Rival = {
  username: string;
  // A player advertised only by the leaderboard has no uploaded package, so the
  // API answers with a null bot name and rank while the profile stays viewable.
  bot_name: string | null;
  elo_rating: number;
  rank: number | null;
  // Availability is derived from the active bot, not from live presence.
  has_active_bot?: boolean;
  last_activity_at?: string | null;
  direct_record: DirectRecord;
  is_nemesis?: boolean;
};
export type RivalsList = {
  items: Rival[];
  next_cursor: string | null;
  viewer?: { has_active_bot: boolean };
  // Returned only when "mine" is empty and unfiltered, so the page is never bare.
  suggested_items?: Rival[];
  suggested_for_elo?: number;
};
export type Challenge = {
  challenge_id: string;
  challenger_username: string;
  challenged_username: string;
  opponent_username: string | null;
  status:
    | "pending"
    | "queued"
    | "running"
    | "completed"
    | "declined"
    | "cancelled"
    | "failed";
  format: "best_of_five_plhe";
  best_of: 5;
  series_score: Record<string, number>;
  games_completed: number;
  hands_played: number;
  current_game?: number | null;
  seed: number;
  winner_username?: string | null;
  viewer_result?: "win" | "loss" | "draw" | null;
  winner_first_score?: [number, number] | null;
  run_id?: string | null;
  created_at: string;
  accepted_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at: string;
  error?: string | null;
  bot_names: { challenger: string | null; challenged: string | null };
  recap_url?: string | null;
  artifacts_url?: string | null;
};
export type RivalDetail = {
  // A rival advertised only by the seeded leaderboard has no uploaded package,
  // so bot_name and rank come back null while the profile is still viewable.
  rival: Omit<Rival, "direct_record" | "is_nemesis" | "bot_name" | "rank"> & {
    bot_name: string | null;
    rank: number | null;
    has_active_bot: boolean;
  };
  viewer: { has_active_bot: boolean };
  direct_record: DirectRecord;
  is_nemesis: boolean;
  nemesis_explanation?: string | null;
  current_challenge?: Challenge | null;
  history: { items: Challenge[]; next_cursor: string | null };
};
export type Compare = {
  player_a: string;
  player_b: string;
  direct_record: {
    player_a_wins: number;
    player_b_wins: number;
    draws: number;
    played: number;
  };
  items: Challenge[];
  next_cursor: string | null;
};
export type LeaderboardStanding = {
  rank: number;
  username: string;
  bot_name: string;
  elo_rating?: number;
  matchup_wins?: number;
  matchup_losses?: number;
  matchup_draws?: number;
};
export type LeaderboardStandings = {
  run_id: string | null;
  updated_at: string | null;
  entries: LeaderboardStanding[];
  // The API answers with the first five ranks, plus the caller's own row only
  // when their rank falls outside that window.
  top_entries?: LeaderboardStanding[];
  viewer_entry?: LeaderboardStanding | null;
};
export type Notification = {
  notification_id: string;
  type:
    | "challenge_received"
    | "challenge_won"
    | "challenge_lost"
    | "challenge_drawn"
    | "challenge_failed";
  challenge_id: string;
  payload?: Record<string, unknown>;
  created_at: string;
  read_at?: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/browser-api/${path}`, {
    cache: "no-store",
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      body?.error?.message ?? "Could not reach Rivals right now.",
    );
  return body as T;
}

export const rivalsApi = {
  list: (source: "mine" | "leaderboard" | "suggested", q = "") =>
    request<RivalsList>(`rivals?source=${source}&q=${encodeURIComponent(q)}`),
  // Proxied so the signed-in cookie reaches the API and `viewer_entry` comes
  // back for players ranked outside the top five.
  leaderboard: () => request<LeaderboardStandings>("leaderboard"),
  detail: (username: string) =>
    request<RivalDetail>(`rivals/${encodeURIComponent(username)}`),
  history: (username: string, cursor?: string | null) =>
    request<{ items: Challenge[]; next_cursor: string | null }>(
      `rivals/${encodeURIComponent(username)}/history?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    ),
  compare: (a: string, b: string) =>
    request<Compare>(
      `rivalries/compare?player_a=${encodeURIComponent(a)}&player_b=${encodeURIComponent(b)}&limit=20`,
    ),
  challenges: (status?: "incoming" | "running" | "finished") =>
    request<{ items: Challenge[]; next_cursor: string | null }>(
      `challenges${status ? `?status=${status}` : ""}`,
    ),
  challenge: (id: string) =>
    request<Challenge>(`challenges/${encodeURIComponent(id)}`),
  create: (username: string) =>
    request<Challenge>("challenges", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ opponent_username: username }),
    }),
  transition: (id: string, action: "accept" | "decline" | "cancel") =>
    request<Challenge>(`challenges/${encodeURIComponent(id)}/${action}`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
    }),
  recap: (id: string) =>
    request<{
      challenge: Challenge;
      matchup: unknown;
      summary: { result_text: string; overview: string };
      best_hands: {
        hand_id: string;
        hand_number: number;
        winner?: string | null;
        pot: number;
      }[];
      artifacts_url?: string | null;
    }>(`challenges/${encodeURIComponent(id)}/recap`),
  notifications: () =>
    request<{
      items: Notification[];
      unread_count: number;
      next_cursor: string | null;
    }>("notifications?limit=20"),
  readNotification: (id: string) =>
    request<Notification>(`notifications/${encodeURIComponent(id)}/read`, {
      method: "POST",
    }),
};
