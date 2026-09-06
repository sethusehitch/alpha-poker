export type DirectRecord = {
  wins: number;
  losses: number;
  draws: number;
  played: number;
};
export type Rival = {
  username: string;
  bot_name: string;
  elo_rating: number;
  rank: number;
  last_activity_at?: string | null;
  direct_record: DirectRecord;
  is_nemesis?: boolean;
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
  hand_count: number;
  seed: number;
  winner_username?: string | null;
  margin_play_chips?: number | null;
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
  rival: Omit<Rival, "direct_record" | "is_nemesis">;
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
  list: (source: "mine" | "leaderboard", q = "") =>
    request<{ items: Rival[]; next_cursor: string | null }>(
      `rivals?source=${source}&q=${encodeURIComponent(q)}`,
    ),
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
  challenges: (status: "incoming" | "running" | "finished") =>
    request<{ items: Challenge[]; next_cursor: string | null }>(
      `challenges?status=${status}`,
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
