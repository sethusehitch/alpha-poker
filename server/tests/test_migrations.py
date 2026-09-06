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
    assert {"feature_requests", "feature_votes", "feedback", "github_cache"} <= tables


def test_community_tables_are_created_idempotently_without_losing_data(tmp_path):
    path = tmp_path / "community.sqlite3"
    db = Database(path)
    db.initialize(seed=False)
    db.execute(
        "INSERT INTO feature_requests(id,title,details,status,author_username,hidden,created_at,updated_at) "
        "VALUES('feat_1','Keep this idea',NULL,'submitted','maya',0,'then','then')"
    )
    db.execute(
        "INSERT INTO feature_votes(request_id,username,value,created_at,updated_at) "
        "VALUES('feat_1','maya',1,'then','then')"
    )

    # Re-running initialize (e.g. on process restart) must not drop existing rows.
    db.initialize(seed=False)

    assert db.one("SELECT title FROM feature_requests WHERE id='feat_1'")["title"] == "Keep this idea"
    assert db.one("SELECT value FROM feature_votes WHERE request_id='feat_1'")["value"] == 1
    with db.connect() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"feature_requests", "feature_votes", "feedback", "github_cache"} <= tables


def test_early_community_schema_migrates_statuses_and_feedback_context(tmp_path):
    path = tmp_path / "early-community.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE feature_requests (
              id TEXT PRIMARY KEY, title TEXT NOT NULL, details TEXT,
              status TEXT NOT NULL, author_username TEXT NOT NULL,
              hidden INTEGER NOT NULL DEFAULT 0, github_issue_number INTEGER,
              github_issue_url TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE feedback (
              id TEXT PRIMARY KEY, username TEXT, type TEXT NOT NULL,
              message TEXT NOT NULL, path TEXT, created_at TEXT NOT NULL
            );
            INSERT INTO feature_requests VALUES
              ('old-open','Open idea',NULL,'open','maya',0,NULL,NULL,'then','then'),
              ('old-no','No idea',NULL,'not_planned','maya',0,NULL,NULL,'then','then');
            INSERT INTO feedback VALUES ('fb-old','maya','idea','Keep me','/','then');
            """
        )

    db = Database(path)
    db.initialize(seed=False)

    assert db.one("SELECT status FROM feature_requests WHERE id='old-open'")["status"] == "submitted"
    assert db.one("SELECT status FROM feature_requests WHERE id='old-no'")["status"] == "declined"
    with db.connect() as conn:
        feedback_columns = {row[1] for row in conn.execute("PRAGMA table_info(feedback)")}
    assert "client_context" in feedback_columns
    assert db.one("SELECT message FROM feedback WHERE id='fb-old'")["message"] == "Keep me"
