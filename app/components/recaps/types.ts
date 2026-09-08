export type ReplayStep = {
  street: string;
  summary: string;
  board: string[];
  pot: number | null;
  stacks: (number | null)[];
  hole_cards: string[][];
};
export type ReplayPlayer = {
  username: string;
  seat: number;
  is_viewer: boolean;
  starting_stack: number | null;
  final_stack: number | null;
  profit: number | null;
  hole_cards: string[];
  cards_revealed: boolean;
  category: string | null;
};
export type Highlight = {
  hand_id: string;
  hand_number: number;
  label: string;
  labels: string[];
  players: ReplayPlayer[];
  dealer: number | null;
  board: string[];
  pot: number | null;
  winners: string[];
  outcome: string;
  steps: ReplayStep[];
};
export type MatchRecap = {
  schema_version: "recap-v1";
  source: "direct_challenge" | "round_robin";
  viewer_username: string | null;
  run_id: string;
  matchup_id: string;
  players: string[];
  total_hands: number;
  retained_hands: number;
  complete_history: boolean;
  playback_url: string;
  highlights: Highlight[];
  challenge?: { challenge_id: string; opponent_username: string | null };
};
