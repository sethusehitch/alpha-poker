import sqlite3

from alpha_poker_api.db import Database


def test_existing_prototype_database_migrates_without_losing_runs(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE runs (
              id TEXT PRIMARY KEY, status TEXT NOT NULL, official INTEGER NOT NULL,
              engine_version TEXT NOT NULL, rules_version TEXT NOT NULL, seed INTEGER NOT NULL,
              requested_at TEXT NOT NULL, completed_at TEXT
            );
            CREATE TABLE leaderboard (
              run_id TEXT NOT NULL, rank INTEGER NOT NULL, username TEXT NOT NULL,
              bot_name TEXT NOT NULL, bb_per_100 REAL NOT NULL, ci_low REAL NOT NULL,
              ci_high REAL NOT NULL, hands INTEGER NOT NULL,
              PRIMARY KEY (run_id, username)
            );
            INSERT INTO runs VALUES ('run_old','completed',1,'old','old',42,'then','then');
            INSERT INTO runs VALUES ('run_interrupted','running',1,'old','old',43,'then',NULL);
            """
        )

    Database(path).initialize(seed=False)

    db = Database(path)
    assert db.one("SELECT id FROM runs WHERE id='run_old'") == {"id": "run_old"}
    interrupted = db.one("SELECT status,error,completed_at FROM runs WHERE id='run_interrupted'")
    assert interrupted["status"] == "failed"
    assert "restarted" in interrupted["error"]
    assert interrupted["completed_at"]
    with db.connect() as conn:
        run_columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
        leaderboard_columns = {row[1] for row in conn.execute("PRAGMA table_info(leaderboard)")}
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"error", "hand_count_per_pairing"} <= run_columns
    assert {
        "submission_id", "elo_rating", "matchup_wins", "matchup_losses", "matchup_draws"
    } <= leaderboard_columns
    assert {"users", "auth_sessions", "league_queue"} <= tables
