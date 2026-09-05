from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_sessions (
  token_hash TEXT PRIMARY KEY, username TEXT NOT NULL,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT,
  FOREIGN KEY(username) REFERENCES users(username)
);
CREATE INDEX IF NOT EXISTS auth_sessions_username ON auth_sessions(username, created_at DESC);
CREATE TABLE IF NOT EXISTS submissions (
  id TEXT PRIMARY KEY, username TEXT NOT NULL, bot_name TEXT NOT NULL,
  original_filename TEXT NOT NULL, package_path TEXT NOT NULL, sha256 TEXT NOT NULL,
  status TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 0,
  error TEXT, logs TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS submissions_username ON submissions(username, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_submissions_active_username
ON submissions(active, username) WHERE active=1;
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, status TEXT NOT NULL, official INTEGER NOT NULL,
  engine_version TEXT NOT NULL, rules_version TEXT NOT NULL, seed INTEGER NOT NULL,
  requested_at TEXT NOT NULL, started_at TEXT, heartbeat_at TEXT, completed_at TEXT, error TEXT,
  hand_count_per_pairing INTEGER, total_matchups INTEGER NOT NULL DEFAULT 0,
  completed_matchups INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS leaderboard (
  run_id TEXT NOT NULL, rank INTEGER NOT NULL, username TEXT NOT NULL, bot_name TEXT NOT NULL,
  bb_per_100 REAL NOT NULL, ci_low REAL NOT NULL, ci_high REAL NOT NULL, hands INTEGER NOT NULL,
  submission_id TEXT, elo_rating INTEGER NOT NULL DEFAULT 1200,
  matchup_wins INTEGER NOT NULL DEFAULT 0, matchup_losses INTEGER NOT NULL DEFAULT 0,
  matchup_draws INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (run_id, username), FOREIGN KEY(run_id) REFERENCES runs(id)
);
CREATE INDEX IF NOT EXISTS idx_runs_status_completed
ON runs(status, completed_at DESC);
CREATE TABLE IF NOT EXISTS matchups (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, player_a TEXT NOT NULL, player_b TEXT NOT NULL,
  hands INTEGER NOT NULL, player_a_bb_per_100 REAL NOT NULL, ci_low REAL NOT NULL,
  ci_high REAL NOT NULL, wins_a INTEGER NOT NULL, wins_b INTEGER NOT NULL, ties INTEGER NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);
CREATE TABLE IF NOT EXISTS hands (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, hand_number INTEGER NOT NULL,
  player_a TEXT NOT NULL, player_b TEXT NOT NULL, winner TEXT,
  pot INTEGER NOT NULL, record_json TEXT NOT NULL, phh TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);
CREATE INDEX IF NOT EXISTS idx_hands_run_hand_number
ON hands(run_id, hand_number);
CREATE TABLE IF NOT EXISTS training_sessions (
  id TEXT PRIMARY KEY, username TEXT NOT NULL, opponent TEXT NOT NULL, leader_username TEXT NOT NULL,
  leader_submission_id TEXT,
  hand_limit INTEGER NOT NULL, status TEXT NOT NULL, token TEXT NOT NULL UNIQUE,
  schema_version TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
  hands_played INTEGER NOT NULL DEFAULT 0, seq INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_training_sessions_status_expires
ON training_sessions(status, expires_at);
CREATE TABLE IF NOT EXISTS training_events (
  session_id TEXT NOT NULL, seq INTEGER NOT NULL, payload TEXT NOT NULL,
  PRIMARY KEY(session_id, seq), FOREIGN KEY(session_id) REFERENCES training_sessions(id)
);
CREATE TABLE IF NOT EXISTS training_actions (
  session_id TEXT NOT NULL, client_action_id TEXT NOT NULL, response TEXT NOT NULL,
  PRIMARY KEY(session_id, client_action_id), FOREIGN KEY(session_id) REFERENCES training_sessions(id)
);
CREATE TABLE IF NOT EXISTS training_hands (
  session_id TEXT NOT NULL, hand_number INTEGER NOT NULL, hand_id TEXT NOT NULL,
  client_seat INTEGER NOT NULL, client_profit INTEGER NOT NULL, record_json TEXT NOT NULL,
  PRIMARY KEY(session_id, hand_number), FOREIGN KEY(session_id) REFERENCES training_sessions(id)
);
CREATE TABLE IF NOT EXISTS league_queue (
  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
  requested_generation INTEGER NOT NULL DEFAULT 0,
  completed_generation INTEGER NOT NULL DEFAULT 0,
  running INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self, seed: bool = True) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(training_sessions)")}
            if "leader_submission_id" not in columns:
                conn.execute("ALTER TABLE training_sessions ADD COLUMN leader_submission_id TEXT")
            leaderboard_columns = {row[1] for row in conn.execute("PRAGMA table_info(leaderboard)")}
            elo_columns_added = False
            if "submission_id" not in leaderboard_columns:
                conn.execute("ALTER TABLE leaderboard ADD COLUMN submission_id TEXT")
            for column, definition in (
                ("elo_rating", "INTEGER NOT NULL DEFAULT 1200"),
                ("matchup_wins", "INTEGER NOT NULL DEFAULT 0"),
                ("matchup_losses", "INTEGER NOT NULL DEFAULT 0"),
                ("matchup_draws", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if column not in leaderboard_columns:
                    conn.execute(f"ALTER TABLE leaderboard ADD COLUMN {column} {definition}")
                    elo_columns_added = True
            run_columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
            if "error" not in run_columns:
                conn.execute("ALTER TABLE runs ADD COLUMN error TEXT")
            if "hand_count_per_pairing" not in run_columns:
                conn.execute("ALTER TABLE runs ADD COLUMN hand_count_per_pairing INTEGER")
            for column, definition in (
                ("started_at", "TEXT"),
                ("heartbeat_at", "TEXT"),
                ("total_matchups", "INTEGER NOT NULL DEFAULT 0"),
                ("completed_matchups", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if column not in run_columns:
                    conn.execute(f"ALTER TABLE runs ADD COLUMN {column} {definition}")
            conn.execute(
                "INSERT OR IGNORE INTO league_queue(singleton,requested_generation,completed_generation,running,updated_at) VALUES(1,0,0,0,?)",
                (now_iso(),),
            )
            conn.execute("UPDATE league_queue SET running=0 WHERE singleton=1")
            conn.execute(
                "UPDATE runs SET status='failed',error=COALESCE(error,'API restarted before this run completed'),completed_at=COALESCE(completed_at,?) WHERE status IN ('queued','running')",
                (now_iso(),),
            )
            if seed and not conn.execute("SELECT 1 FROM runs LIMIT 1").fetchone():
                self._seed(conn)
            elif elo_columns_added:
                self._backfill_legacy_elo(conn)
            conn.execute("PRAGMA optimize")

    def one(self, sql: str, values: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(sql, values).fetchone()
            return dict(row) if row else None

    def all(self, sql: str, values: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, values).fetchall()]

    def execute(self, sql: str, values: tuple[Any, ...] = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, values)

    def _seed(self, conn: sqlite3.Connection) -> None:
        timestamp = now_iso()
        run_id = "run_demo"
        conn.execute(
            "INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,completed_at,hand_count_per_pairing) VALUES (?, 'completed', 1, 'prototype-0.1', 'heads-up-v1', 240904, ?, ?, 40000)",
            (run_id, timestamp, timestamp),
        )
        entries = [
            (1, "maya", "RiverRat", 8.42, 4.10, 12.74, 152000, 1264, 4, 0, 0),
            (2, "theo", "PocketRocket", 5.18, 1.04, 9.32, 151500, 1232, 3, 1, 0),
            (3, "jules", "CheckRaise", 1.76, -2.21, 5.73, 150800, 1200, 2, 2, 0),
            (4, "sam", "BlueChip", -3.12, -7.05, 0.81, 150200, 1168, 1, 3, 0),
            (5, "alex", "CallingStation", -7.88, -12.08, -3.68, 149900, 1136, 0, 4, 0),
        ]
        conn.executemany(
            "INSERT INTO leaderboard(run_id,rank,username,bot_name,bb_per_100,ci_low,ci_high,hands,submission_id,elo_rating,matchup_wins,matchup_losses,matchup_draws) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(run_id, *entry[:7], None, *entry[7:]) for entry in entries],
        )
        matchup_rows = [
            ("mat_demo_1", run_id, "maya", "theo", 40000, 3.24, 0.21, 6.27, 19870, 19610, 520),
            ("mat_demo_2", run_id, "maya", "jules", 40000, 7.12, 3.92, 10.32, 20140, 19310, 550),
            ("mat_demo_3", run_id, "theo", "jules", 40000, 2.65, -0.41, 5.71, 19920, 19520, 560),
        ]
        conn.executemany("INSERT INTO matchups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", matchup_rows)
        records = [
            {
                "id": "hand_demo_1", "run_id": run_id, "hand_number": 1,
                "players": ["maya", "theo"], "button": "maya", "board": ["7c", "Js", "2d", "Ah", "9s"],
                "pot": 420, "winner": "maya", "actions": [
                    {"street": "preflop", "player": "maya", "action": "raise", "amount": 60},
                    {"street": "preflop", "player": "theo", "action": "call", "amount": 40},
                    {"street": "flop", "player": "theo", "action": "check"},
                    {"street": "flop", "player": "maya", "action": "bet", "amount": 80},
                    {"street": "flop", "player": "theo", "action": "fold"},
                ], "reproducibility": {"seed": 240904001, "engine_version": "prototype-0.1"},
            },
            {
                "id": "hand_demo_2", "run_id": run_id, "hand_number": 2,
                "players": ["jules", "maya"], "button": "jules", "board": ["Ks", "Qh", "4d"],
                "pot": 180, "winner": "jules", "actions": [],
                "reproducibility": {"seed": 240904002, "engine_version": "prototype-0.1"},
            },
        ]
        for record in records:
            phh = self._to_phh(record)
            conn.execute(
                "INSERT INTO hands VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (record["id"], run_id, record["hand_number"], record["players"][0],
                 record["players"][1], record["winner"], record["pot"], json.dumps(record), phh),
            )

    @staticmethod
    def _backfill_legacy_elo(conn: sqlite3.Connection) -> None:
        """Give pre-Elo completed runs deterministic ratings and records."""
        from .ratings import BASE_RATING, calculate_round_robin_elo

        prior_by_submission: dict[str, int] = {}
        runs = conn.execute(
            "SELECT id FROM runs WHERE status='completed' AND official=1 ORDER BY completed_at,requested_at,id"
        ).fetchall()
        for run in runs:
            run_id = run["id"]
            rows = conn.execute(
                "SELECT username,submission_id,bb_per_100 FROM leaderboard WHERE run_id=?",
                (run_id,),
            ).fetchall()
            if not rows:
                continue
            keys = {
                row["username"]: row["submission_id"] or f"legacy:{row['username']}"
                for row in rows
            }
            starts = {
                username: prior_by_submission.get(key, BASE_RATING)
                for username, key in keys.items()
            }
            results = []
            for matchup in conn.execute(
                "SELECT player_a,player_b,player_a_bb_per_100 FROM matchups WHERE run_id=? ORDER BY player_a,player_b",
                (run_id,),
            ):
                score = 1.0 if matchup["player_a_bb_per_100"] > 0 else 0.0 if matchup["player_a_bb_per_100"] < 0 else 0.5
                results.append((matchup["player_a"], matchup["player_b"], score))
            standings = calculate_round_robin_elo(starts, results)
            ordered = sorted(
                rows,
                key=lambda row: (-standings[row["username"]].rating, -row["bb_per_100"], row["username"]),
            )
            for rank, row in enumerate(ordered, start=1):
                standing = standings[row["username"]]
                conn.execute(
                    "UPDATE leaderboard SET rank=?,elo_rating=?,matchup_wins=?,matchup_losses=?,matchup_draws=? WHERE run_id=? AND username=?",
                    (rank, standing.rating, standing.wins, standing.losses, standing.draws, run_id, row["username"]),
                )
                prior_by_submission[keys[row["username"]]] = standing.rating

    @staticmethod
    def _to_phh(record: dict[str, Any]) -> str:
        blinds = record.get("blinds", {"small": 10, "big": 20})
        starting_stacks = record.get("starting_stacks", [2000, 2000])
        return "\n".join([
            f"# Alpha Poker hand {record['id']}",
            "variant = 'NT'", "antes = [0, 0]",
            f"blinds_or_straddles = [{blinds['small']}, {blinds['big']}]",
            f"min_bet = {blinds['big']}", f"starting_stacks = {json.dumps(starting_stacks)}",
            f"players = {json.dumps(record['players'])}",
            f"board = {json.dumps(record['board'])}", f"pot = {record['pot']}",
            f"winner = {json.dumps(record['winner'])}", "",
        ])
