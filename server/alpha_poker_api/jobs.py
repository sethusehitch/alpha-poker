from __future__ import annotations

from .db import Database, now_iso
import io
import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
import zipfile
import secrets

from .engine_adapter import load_bot, validate_package
from .ratings import BASE_RATING, ESTABLISHED_K_FACTOR, PROVISIONAL_K_FACTOR, PROVISIONAL_MATCHES, calculate_elo_result


def prune_submission_packages(db: Database) -> list[str]:
    """Remove inactive ZIPs when no league can still be loading them.

    Active bot packages and packages frozen into a live training session are
    retained. Metadata stays in SQLite for auditability.
    """
    if db.one("SELECT 1 FROM runs WHERE status='running' LIMIT 1"):
        return []
    protected = {
        row["leader_submission_id"]
        for row in db.all(
            "SELECT leader_submission_id FROM training_sessions "
            "WHERE status IN ('ready','running') AND expires_at>? "
            "AND leader_submission_id IS NOT NULL",
            (now_iso(),),
        )
    }
    protected.update(
        submission_id
        for row in db.all(
            "SELECT challenger_submission_id,challenged_submission_id FROM rival_challenges "
            "WHERE status IN ('queued','running')"
        )
        for submission_id in (row["challenger_submission_id"], row["challenged_submission_id"])
        if submission_id
    )
    published_leader = db.one(
        "SELECT l.submission_id FROM leaderboard l JOIN runs r ON r.id=l.run_id "
        "WHERE r.status='completed' AND r.official=1 AND l.rank=1 "
        "ORDER BY r.completed_at DESC, r.requested_at DESC LIMIT 1"
    )
    if published_leader and published_leader["submission_id"]:
        protected.add(published_leader["submission_id"])
    removed: list[str] = []
    for row in db.all(
        "SELECT id,package_path FROM submissions "
        "WHERE active=0 AND status IN ('accepted','rejected')"
    ):
        if row["id"] in protected:
            continue
        Path(row["package_path"]).unlink(missing_ok=True)
        removed.append(row["id"])
    return removed


def validate_submission(db: Database, submission_id: str) -> None:
    row = db.one("SELECT * FROM submissions WHERE id=?", (submission_id,))
    if not row:
        return
    db.execute(
        "UPDATE submissions SET status='validating', logs=logs || ?, updated_at=? WHERE id=?",
        ("Validation started.\n", now_iso(), submission_id),
    )
    result = validate_package(__import__("pathlib").Path(row["package_path"]))
    if not result.accepted:
        db.execute(
            "UPDATE submissions SET status='rejected', error=?, logs=logs || ?, updated_at=? WHERE id=?",
            (result.error, result.logs, now_iso(), submission_id),
        )
        prune_submission_packages(db)
        return
    # Activation is atomic: a failed upload never replaces the last good bot.
    with db.connect() as conn:
        conn.execute("UPDATE submissions SET active=0 WHERE username=?", (row["username"],))
        conn.execute(
            "UPDATE submissions SET status='accepted', active=1, error=NULL, logs=logs || ?, updated_at=? WHERE id=?",
            (result.logs + "Submission activated.\n", now_iso(), submission_id),
        )
    prune_submission_packages(db)


def run_official_league(
    db: Database,
    run_id: str,
    hand_count_per_pairing: int | None,
    timeout_seconds: int = 900,
) -> None:
    """Run every active bot through one rated best-of-five series."""
    from alpha_poker import play_tournament_series

    existing = db.one("SELECT status FROM runs WHERE id=?", (run_id,))
    if not existing:
        raise KeyError(run_id)
    if existing["status"] == "completed":
        return
    # A retry after interruption starts the same run from a clean checkpoint.
    # Elo is only published through the completed leaderboard, so partial rows
    # can be removed without changing a player's prior public rating.
    with db.connect() as conn:
        conn.execute("DELETE FROM elo_history WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM tournament_series WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM matchups WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM hands WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM leaderboard WHERE run_id=?", (run_id,))

    # Publish the running state before snapshotting package paths. Submission
    # pruning checks this state, so an upload cannot delete a package between
    # this snapshot and the subprocess launch.
    submissions = db.all("SELECT * FROM submissions WHERE active=1 ORDER BY username")
    total_matchups = len(submissions) * (len(submissions) - 1) // 2
    started_at = now_iso()
    db.execute(
        "UPDATE runs SET status='running',started_at=?,heartbeat_at=?,total_matchups=?,completed_matchups=0 WHERE id=?",
        (started_at, started_at, total_matchups, run_id),
    )
    if len(submissions) < 2:
        db.execute(
            "UPDATE runs SET status='failed', error=?, completed_at=? WHERE id=?",
            ("At least two active bots are required", now_iso(), run_id),
        )
        return
    run = db.one("SELECT * FROM runs WHERE id=?", (run_id,))
    bot_names = {row["username"]: row["bot_name"] for row in submissions}
    submission_ids = {row["username"]: row["id"] for row in submissions}
    ratings: dict[str, int] = {}
    rated_matches: dict[str, int] = {}
    records = {row["username"]: [0, 0, 0] for row in submissions}
    hands_by_player = {row["username"]: 0 for row in submissions}
    for row in submissions:
        previous = db.one(
            "SELECT l.elo_rating FROM leaderboard l "
            "JOIN runs r ON r.id=l.run_id "
            "WHERE l.username=? AND r.status='completed' AND r.official=1 "
            "ORDER BY r.completed_at DESC,r.requested_at DESC LIMIT 1",
            (row["username"],),
        )
        ratings[row["username"]] = int(previous["elo_rating"]) if previous else BASE_RATING
        count = db.one("SELECT COUNT(*) AS count FROM elo_history WHERE username=?", (row["username"],))
        rated_matches[row["username"]] = int(count["count"] if count else 0)
    hand_number = 0
    deadline = monotonic() + timeout_seconds
    try:
        for match_index, (left, right) in enumerate(itertools.combinations(submissions, 2), start=1):
            if monotonic() >= deadline:
                raise TimeoutError(f"League exceeded its {timeout_seconds}-second run deadline")
            db.execute("UPDATE runs SET heartbeat_at=? WHERE id=?", (now_iso(), run_id))
            match_id = f"{run_id}_match_{match_index}"
            bots = (
                load_bot(Path(left["package_path"])),
                load_bot(Path(right["package_path"])),
            )
            try:
                result = play_tournament_series(
                    bots,
                    seed=int(run["seed"]) + match_index * 1_000_000,
                    bot_names=(left["username"], right["username"]), match_id=match_id,
                    timeout_seconds=0.25,
                )
            finally:
                for bot in bots:
                    bot.close()
            score_a = 1.0 if result.winner == 0 else 0.0
            before_a, before_b = ratings[left["username"]], ratings[right["username"]]
            after_a, after_b, ka, kb = calculate_elo_result(
                before_a, before_b, score_a,
                rated_matches_a=rated_matches[left["username"]],
                rated_matches_b=rated_matches[right["username"]],
            )
            ratings[left["username"]], ratings[right["username"]] = after_a, after_b
            rated_matches[left["username"]] += 1
            rated_matches[right["username"]] += 1
            records[left["username"]][0 if score_a == 1.0 else 1] += 1
            records[right["username"]][1 if score_a == 1.0 else 0] += 1
            hands_by_player[left["username"]] += result.hands
            hands_by_player[right["username"]] += result.hands
            hand_rows = []
            for game in result.games:
                for history in game.hand_histories:
                    hand_number += 1
                    winners = history.get("winners", [])
                    winner = left["username"] if winners == [0] else right["username"] if winners == [1] else None
                    hand_id = history.get("hand_id", f"{match_id}_{hand_number}")
                    record = {
                        **history, "id": hand_id, "run_id": run_id,
                        "players": [left["username"], right["username"]], "winner": winner,
                    }
                    hand_rows.append((
                        hand_id, run_id, hand_number, left["username"], right["username"], winner,
                        int(history.get("pot", 0)), json.dumps(record), Database._to_phh(record),
                    ))
            completed_at = now_iso()
            with db.connect() as conn:
                conn.executemany("INSERT INTO hands VALUES(?,?,?,?,?,?,?,?,?)", hand_rows)
                conn.execute(
                    "INSERT INTO matchups VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (match_id, run_id, left["username"], right["username"], result.hands,
                     1.0 if score_a == 1.0 else -1.0, 0.0, 0.0,
                     result.score[0], result.score[1], 0),
                )
                conn.execute(
                    "INSERT INTO tournament_series(matchup_id,run_id,score_a,score_b,result_json) VALUES(?,?,?,?,?)",
                    (match_id, run_id, result.score[0], result.score[1], json.dumps(result.to_dict())),
                )
                for username, submission_id, before, after, score, factor in (
                    (left["username"], left["id"], before_a, after_a, score_a, ka),
                    (right["username"], right["id"], before_b, after_b, 1.0 - score_a, kb),
                ):
                    conn.execute(
                        "INSERT INTO elo_history VALUES(?,?,?,?,?,?,?,?,?)",
                        (run_id, match_id, username, submission_id, before, after, score, factor, completed_at),
                    )
                conn.execute(
                    "UPDATE runs SET completed_matchups=?,heartbeat_at=? WHERE id=?",
                    (match_index, completed_at, run_id),
                )
        scores = sorted(submission_ids, key=lambda username: (-ratings[username], -records[username][0], username))
        for rank, username in enumerate(scores, start=1):
            wins, losses, draws = records[username]
            db.execute(
                "INSERT INTO leaderboard(run_id,rank,username,bot_name,bb_per_100,ci_low,ci_high,hands,submission_id,elo_rating,matchup_wins,matchup_losses,matchup_draws) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, rank, username, bot_names[username], 0.0, 0.0, 0.0, hands_by_player[username],
                 submission_ids[username], ratings[username], wins, losses, draws),
            )
        timestamp = now_iso()
        db.execute("UPDATE runs SET status='completed',heartbeat_at=?,completed_at=? WHERE id=?", (timestamp, timestamp, run_id))
    except Exception as exc:
        db.execute(
            "UPDATE runs SET status='failed', error=?, completed_at=? WHERE id=?",
            (f"{type(exc).__name__}: {exc}", now_iso(), run_id),
        )
        raise


def _challenge_notification_payload(
    challenge: dict,
    recipient: str,
    notification_type: str,
) -> dict:
    opponent = (
        challenge["challenged_username"]
        if recipient == challenge["challenger_username"]
        else challenge["challenger_username"]
    )
    return {
        "challenge_id": challenge["id"],
        "opponent_username": opponent,
        "winner_username": challenge.get("winner_username"),
        "margin_play_chips": challenge.get("margin_play_chips"),
        "series_score": {
            challenge["challenger_username"]: int(challenge.get("series_score_a") or 0),
            challenge["challenged_username"]: int(challenge.get("series_score_b") or 0),
        },
        "status": challenge["status"],
        "notification_type": notification_type,
    }


def _insert_challenge_notification(conn, challenge: dict, username: str, notification_type: str) -> None:
    payload = _challenge_notification_payload(challenge, username, notification_type)
    bot_names = {}
    for role, submission_key in (
        ("challenger", "challenger_submission_id"),
        ("challenged", "challenged_submission_id"),
    ):
        submission = conn.execute(
            "SELECT bot_name FROM submissions WHERE id=?", (challenge.get(submission_key),)
        ).fetchone() if challenge.get(submission_key) else None
        bot_names[role] = submission["bot_name"] if submission else None
    payload["bot_names"] = bot_names
    conn.execute(
        "INSERT OR IGNORE INTO notifications(id,username,type,challenge_id,payload_json,created_at) "
        "VALUES(?,?,?,?,?,?)",
        (
            f"ntf_{challenge['id']}_{username}_{notification_type}",
            username,
            notification_type,
            challenge["id"],
            json.dumps(payload),
            now_iso(),
        ),
    )


def finalize_rival_challenge(db: Database, challenge_id: str) -> bool:
    """Finalize a stored completed rival run after a restart."""
    challenge = db.one("SELECT * FROM rival_challenges WHERE id=?", (challenge_id,))
    if not challenge or not challenge["run_id"]:
        return False
    run = db.one("SELECT status FROM runs WHERE id=?", (challenge["run_id"],))
    matchup = db.one("SELECT * FROM matchups WHERE run_id=?", (challenge["run_id"],))
    series = db.one("SELECT * FROM tournament_series WHERE run_id=?", (challenge["run_id"],))
    if not run or run["status"] != "completed" or not matchup:
        return False
    if series:
        series_result = json.loads(series["result_json"])
        winner = series_result["winner"]
        score_a, score_b = int(series["score_a"]), int(series["score_b"])
        hands = int(matchup["hands"])
    else:
        # Legacy fixed-hand challenges remain recoverable during migration.
        total_a = 0
        for row in db.all("SELECT record_json FROM hands WHERE run_id=?", (challenge["run_id"],)):
            record = json.loads(row["record_json"])
            profits = record.get("bot_profits", [0, 0])
            total_a += int(profits[0])
        winner = (
            challenge["challenger_username"] if total_a > 0
            else challenge["challenged_username"] if total_a < 0
            else None
        )
        score_a = 1 if total_a > 0 else 0
        score_b = 1 if total_a < 0 else 0
        hands = int(matchup["hands"])
    timestamp = now_iso()
    with db.connect() as conn:
        conn.execute(
            "UPDATE rival_challenges SET status='completed',winner_username=?,margin_play_chips=NULL,"
            "series_score_a=?,series_score_b=?,games_completed=?,hands_played=?,current_game=NULL,"
            "completed_at=COALESCE(completed_at,?),updated_at=?,error=NULL WHERE id=?",
            (winner, score_a, score_b, score_a + score_b, hands, timestamp, timestamp, challenge_id),
        )
        completed = dict(conn.execute("SELECT * FROM rival_challenges WHERE id=?", (challenge_id,)).fetchone())
        for username in (completed["challenger_username"], completed["challenged_username"]):
            notification_type = "challenge_won" if winner == username else "challenge_lost"
            if winner is None:
                notification_type = "challenge_drawn"
            _insert_challenge_notification(conn, completed, username, notification_type)
    return True


def recover_rival_challenges(db: Database) -> int:
    """Restore interrupted work without duplicating a completed match."""
    recovered = 0
    for challenge in db.all("SELECT * FROM rival_challenges WHERE status='running'"):
        if finalize_rival_challenge(db, challenge["id"]):
            recovered += 1
            continue
        timestamp = now_iso()
        if challenge["run_id"]:
            db.execute(
                "UPDATE runs SET status='failed',error=COALESCE(error,'Interrupted by API restart'),"
                "completed_at=COALESCE(completed_at,?) WHERE id=? AND status!='completed'",
                (timestamp, challenge["run_id"]),
            )
        db.execute(
            "UPDATE rival_challenges SET status='queued',run_id=NULL,started_at=NULL,updated_at=? WHERE id=?",
            (timestamp, challenge["id"]),
        )
        recovered += 1
    return recovered


def run_rival_challenge(db: Database, challenge_id: str, timeout_seconds: int = 900) -> bool:
    """Atomically claim and execute one unranked best-of-five challenge."""
    from alpha_poker import play_tournament_series

    timestamp = now_iso()
    with db.connect() as conn:
        cursor = conn.execute(
            "UPDATE rival_challenges SET status='running',started_at=COALESCE(started_at,?),updated_at=? "
            "WHERE id=? AND status='queued'",
            (timestamp, timestamp, challenge_id),
        )
        if cursor.rowcount != 1:
            return False
    challenge = db.one("SELECT * FROM rival_challenges WHERE id=?", (challenge_id,))
    run_id = "run_rival_" + secrets.token_hex(8)
    try:
        left = db.one("SELECT * FROM submissions WHERE id=?", (challenge["challenger_submission_id"],))
        right = db.one("SELECT * FROM submissions WHERE id=?", (challenge["challenged_submission_id"],))
        if not left or not right:
            raise RuntimeError("A snapshotted bot package is no longer available")
        if not Path(left["package_path"]).exists() or not Path(right["package_path"]).exists():
            raise RuntimeError("A snapshotted bot package is missing")
        db.execute(
            "INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,started_at,"
            "heartbeat_at,hand_count_per_pairing,total_matchups,completed_matchups) "
            "VALUES(?,'running',0,'prototype-0.2','plhe-tournament-v1',?,?,?,?,?,1,0)",
            (run_id, challenge["seed"], challenge["accepted_at"] or timestamp, timestamp, timestamp, None),
        )
        db.execute(
            "UPDATE rival_challenges SET run_id=?,format='best_of_five_plhe',series_score_a=0,series_score_b=0,"
            "games_completed=0,hands_played=0,current_game=1,updated_at=? WHERE id=?",
            (run_id, now_iso(), challenge_id),
        )
        bots = (load_bot(Path(left["package_path"])), load_bot(Path(right["package_path"])))
        try:
            def game_completed(game, score):
                db.execute(
                    "UPDATE rival_challenges SET series_score_a=?,series_score_b=?,games_completed=?,"
                    "hands_played=hands_played+?,current_game=?,updated_at=? WHERE id=?",
                    (score[0], score[1], game.game_number, game.hands,
                     None if max(score) == 3 else game.game_number + 1, now_iso(), challenge_id),
                )

            result = play_tournament_series(
                bots,
                seed=int(challenge["seed"]),
                bot_names=(challenge["challenger_username"], challenge["challenged_username"]),
                match_id=f"{run_id}_match_1",
                timeout_seconds=0.25,
                on_game_completed=game_completed,
            )
        finally:
            for bot in bots:
                bot.close()
        hand_rows = []
        hand_number = 0
        for game in result.games:
            for history in game.hand_histories:
                hand_number += 1
                winners = history.get("winners", [])
                winner = (
                    challenge["challenger_username"] if winners == [0]
                    else challenge["challenged_username"] if winners == [1]
                    else None
                )
                hand_id = history.get("hand_id", f"{run_id}_match_1_{hand_number}")
                record = {
                    **history, "id": hand_id, "run_id": run_id,
                    "players": [challenge["challenger_username"], challenge["challenged_username"]],
                    "winner": winner,
                }
                hand_rows.append((
                    hand_id, run_id, hand_number,
                    challenge["challenger_username"], challenge["challenged_username"], winner,
                    int(history.get("pot", 0)), json.dumps(record), Database._to_phh(record),
                ))
        completed_at = now_iso()
        winner_username = result.bot_names[result.winner]
        with db.connect() as conn:
            conn.executemany("INSERT INTO hands VALUES(?,?,?,?,?,?,?,?,?)", hand_rows)
            conn.execute(
                "INSERT INTO matchups VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (f"{run_id}_match_1", run_id, challenge["challenger_username"], challenge["challenged_username"],
                 result.hands, 1.0 if result.winner == 0 else -1.0, 0.0, 0.0,
                 result.score[0], result.score[1], 0),
            )
            conn.execute(
                "INSERT INTO tournament_series(matchup_id,run_id,score_a,score_b,result_json) VALUES(?,?,?,?,?)",
                (f"{run_id}_match_1", run_id, result.score[0], result.score[1], json.dumps(result.to_dict())),
            )
            conn.execute(
                "UPDATE runs SET status='completed',heartbeat_at=?,completed_at=?,completed_matchups=1 WHERE id=?",
                (completed_at, completed_at, run_id),
            )
            conn.execute(
                "UPDATE rival_challenges SET status='completed',winner_username=?,margin_play_chips=NULL,"
                "series_score_a=?,series_score_b=?,games_completed=?,hands_played=?,current_game=NULL,"
                "completed_at=?,updated_at=?,error=NULL WHERE id=?",
                (winner_username, result.score[0], result.score[1], len(result.games), result.hands,
                 completed_at, completed_at, challenge_id),
            )
            completed = dict(conn.execute("SELECT * FROM rival_challenges WHERE id=?", (challenge_id,)).fetchone())
            for username in (completed["challenger_username"], completed["challenged_username"]):
                notification_type = "challenge_won" if winner_username == username else "challenge_lost"
                if winner_username is None:
                    notification_type = "challenge_drawn"
                _insert_challenge_notification(conn, completed, username, notification_type)
        return True
    except Exception as exc:
        failed_at = now_iso()
        message = f"{type(exc).__name__}: {exc}"
        with db.connect() as conn:
            conn.execute(
                "UPDATE runs SET status='failed',error=?,completed_at=? WHERE id=?",
                (message, failed_at, run_id),
            )
            conn.execute(
                "UPDATE rival_challenges SET status='failed',error=?,completed_at=?,updated_at=? WHERE id=?",
                (message, failed_at, failed_at, challenge_id),
            )
            failed = conn.execute("SELECT * FROM rival_challenges WHERE id=?", (challenge_id,)).fetchone()
            if failed:
                failed = dict(failed)
                for username in (failed["challenger_username"], failed["challenged_username"]):
                    _insert_challenge_notification(conn, failed, username, "challenge_failed")
        return False


def build_run_artifact(db: Database, run_id: str) -> bytes:
    run = db.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not run:
        raise KeyError(run_id)
    rows = db.all("SELECT * FROM hands WHERE run_id=? ORDER BY hand_number", (run_id,))
    summary = summarize_run(db, run_id, rows)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("result.txt", summary["result_text"] + "\n")
        archive.writestr("summary.json", json.dumps(summary, indent=2) + "\n")
        archive.writestr("hands.jsonl", "".join(row["record_json"] + "\n" for row in rows))
        archive.writestr("hands.phhs", "\n".join(row["phh"] for row in rows))
    return buffer.getvalue()


def summarize_run(db: Database, run_id: str, rows: list[dict] | None = None) -> dict:
    run = db.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if run and not bool(run["official"]):
        challenge = db.one("SELECT * FROM rival_challenges WHERE run_id=?", (run_id,))
        if challenge:
            matchup = db.one("SELECT * FROM matchups WHERE run_id=?", (run_id,))
            series_row = db.one("SELECT * FROM tournament_series WHERE run_id=?", (run_id,))
            submission_names: dict[str, str | None] = {}
            for username, submission_key in (
                (challenge["challenger_username"], "challenger_submission_id"),
                (challenge["challenged_username"], "challenged_submission_id"),
            ):
                submission = db.one(
                    "SELECT bot_name FROM submissions WHERE id=?",
                    (challenge[submission_key],),
                ) if challenge[submission_key] else None
                submission_names[username] = submission["bot_name"] if submission else None
            winner = challenge["winner_username"]
            challenger = challenge["challenger_username"]
            challenged = challenge["challenged_username"]
            series = json.loads(series_row["result_json"]) if series_row else {}
            score = [
                int(series_row["score_a"]) if series_row else int(challenge["series_score_a"] or 0),
                int(series_row["score_b"]) if series_row else int(challenge["series_score_b"] or 0),
            ]
            games = list(series.get("games", []))
            hands = int(matchup["hands"]) if matchup else int(challenge["hands_played"] or 0)
            if winner:
                loser = challenged if winner == challenger else challenger
                winner_score = score[0] if winner == challenger else score[1]
                loser_score = score[1] if winner == challenger else score[0]
                overview = f"{submission_names[winner] or winner} defeated {submission_names[loser] or loser} {winner_score}-{loser_score}."
            else:
                overview = f"{submission_names[challenger] or challenger} and {submission_names[challenged] or challenged} did not finish."
            game_count = len(games) or sum(score)
            all_ins = [sum(int(game.get("all_ins_won", [0, 0])[index]) for game in games) for index in range(2)]
            game_word = "game" if game_count == 1 else "games"
            result_lines = [overview, "", f"{hands:,} hands across {game_count} {game_word}."]
            total_all_ins = sum(all_ins)
            if winner and total_all_ins:
                winner_index = 0 if winner == challenger else 1
                result_lines.append(f"{submission_names[winner] or winner} won {all_ins[winner_index]} of {total_all_ins} all-in pots.")
            result_lines.extend(["", "Highlights are ready. Say \"show me the highlights\" or \"open game 2.\""])
            return {
                "schema_version": "2.0",
                "run_id": run_id,
                "challenge_id": challenge["id"],
                "kind": "direct_rival_challenge",
                "official": False,
                "ranked": False,
                "affects_elo": False,
                "play_money_only": True,
                "overview": overview,
                "result_text": "\n".join(result_lines),
                "outcome": {
                    "winner_username": winner,
                    "is_draw": winner is None,
                    "series_score": {challenger: score[0], challenged: score[1]},
                    "games": game_count,
                    "hands": hands,
                },
                "players": {
                    challenger: {
                        "bot_name": submission_names[challenger],
                        "role": "challenger",
                        "games_won": score[0],
                        "all_in_pots_won": all_ins[0],
                    },
                    challenged: {
                        "bot_name": submission_names[challenged],
                        "role": "challenged",
                        "games_won": score[1],
                        "all_in_pots_won": all_ins[1],
                    },
                },
                "games": games,
                "methodology": {
                    "format": "best-of-five heads-up pot-limit hold'em tournament games",
                    "starting_stack_per_game": 10_000,
                    "win_condition": "first bot to win three games; bankruptcy wins a game",
                    "blinds": "start at 50/100, double every 10 hands, then use current-stack-sized sudden death until one bot is bankrupt",
                    "ranking_effect": "Direct challenges do not change public Elo.",
                },
                "artifacts": ["result.txt", "summary.json", "hands.phhs", "hands.jsonl"],
            }
    rows = rows if rows is not None else db.all(
        "SELECT * FROM hands WHERE run_id=? ORDER BY hand_number", (run_id,)
    )
    standings = db.all("SELECT * FROM leaderboard WHERE run_id=? ORDER BY rank", (run_id,))
    players: dict[str, dict] = {}
    for standing in standings:
        players[standing["username"]] = {
            "bot_name": standing["bot_name"],
            "rank": standing["rank"],
            "elo_rating": standing["elo_rating"],
            "record": {
                "wins": standing["matchup_wins"],
                "losses": standing["matchup_losses"],
                "draws": standing["matchup_draws"],
            },
            "hands": standing["hands"],
            "hands_won": 0,
            "showdown_wins": 0,
            "fold_wins": 0,
            "actions": {"fold": 0, "check": 0, "call": 0, "raise": 0, "all_in": 0},
        }
    for row in rows:
        record = json.loads(row["record_json"])
        winner = record.get("winner")
        result_reason = next(
            (event.get("reason") for event in reversed(record.get("events", [])) if event.get("type") == "result"),
            None,
        )
        if winner in players:
            players[winner]["hands_won"] += 1
            if result_reason == "showdown":
                players[winner]["showdown_wins"] += 1
            elif result_reason == "fold":
                players[winner]["fold_wins"] += 1
        names = record.get("players", [])
        seat_to_bot = record.get("seat_to_bot", [0, 1])
        for event in record.get("events", []):
            action = event.get("action")
            seat = event.get("seat")
            if event.get("type") != "action" or action not in {"fold", "check", "call", "raise", "all_in"}:
                continue
            try:
                username = names[seat_to_bot[int(seat)]]
            except (IndexError, TypeError, ValueError):
                continue
            if username in players:
                players[username]["actions"][action] += 1

    leader = standings[0] if standings else None
    if leader:
        overview = f"{leader['bot_name']} leads at {leader['elo_rating']:,} Elo with {leader['matchup_wins']} wins and {leader['matchup_losses']} losses."
    else:
        overview = "This run has no completed standings."
    result_lines = [overview]
    if standings:
        result_lines.extend(["", "Standings:"])
        result_lines.extend(
            f"{standing['rank']}. {standing['bot_name']} ({standing['username']}): {standing['elo_rating']:,} Elo, {standing['matchup_wins']}-{standing['matchup_losses']}"
            for standing in standings
        )
    return {
        "schema_version": "2.0",
        "run_id": run_id,
        "overview": overview,
        "result_text": "\n".join(result_lines),
        "methodology": {
            "ranking_metric": "elo",
            "starting_rating": BASE_RATING,
            "provisional_k_factor": PROVISIONAL_K_FACTOR,
            "established_k_factor": ESTABLISHED_K_FACTOR,
            "provisional_matches": PROVISIONAL_MATCHES,
            "rating_period": "once per completed best-of-five series",
            "format": "heads-up pot-limit hold'em tournament games",
        },
        "players": players,
        "artifacts": ["result.txt", "summary.json", "hands.phhs", "hands.jsonl"],
    }


def archive_run(db: Database, run_id: str, artifact_dir: Path) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    destination = artifact_dir / f"{run_id}.zip"
    temporary = artifact_dir / f".{run_id}.tmp"
    temporary.write_bytes(build_run_artifact(db, run_id))
    temporary.replace(destination)
    return destination


def archive_and_prune(
    db: Database,
    artifact_dir: Path,
    retained_hand_runs: int,
    retained_artifact_runs: int,
) -> list[str]:
    completed = db.all(
        "SELECT id FROM runs WHERE status='completed' AND official=1 ORDER BY completed_at DESC, requested_at DESC"
    )
    removed: list[str] = []
    for row in completed[retained_hand_runs:]:
        run_id = row["id"]
        if db.one("SELECT 1 FROM hands WHERE run_id=? LIMIT 1", (run_id,)):
            archive_run(db, run_id, artifact_dir)
            db.execute("DELETE FROM hands WHERE run_id=?", (run_id,))
            removed.append(run_id)
    for row in completed[retained_artifact_runs:]:
        (artifact_dir / f"{row['id']}.zip").unlink(missing_ok=True)
    return removed


def cleanup_raw_histories(
    db: Database,
    artifact_dir: Path,
    *,
    now: datetime | None = None,
    dry_run: bool = True,
) -> dict[str, list[str]]:
    """Apply time-based raw-history retention without deleting summaries.

    Every run is archived and checked before its hand rows can be removed.
    Official results keep at least the newest three runs even after 30 days;
    challenge hands keep 90 days. Training scratch data keeps 14 days.
    """
    now = now or datetime.now(UTC)
    cutoffs = {
        "official": (now - timedelta(days=30)).isoformat().replace("+00:00", "Z"),
        "challenge": (now - timedelta(days=90)).isoformat().replace("+00:00", "Z"),
        "training": (now - timedelta(days=14)).isoformat().replace("+00:00", "Z"),
    }
    result: dict[str, list[str]] = {"official_runs": [], "challenge_runs": [], "training_sessions": []}
    newest_official = {
        row["id"] for row in db.all(
            "SELECT id FROM runs WHERE official=1 AND status='completed' "
            "ORDER BY completed_at DESC,requested_at DESC LIMIT 3"
        )
    }
    candidates = db.all(
        "SELECT r.id,r.official,r.completed_at,rc.id AS challenge_id FROM runs r "
        "LEFT JOIN rival_challenges rc ON rc.run_id=r.id "
        "WHERE r.status='completed' AND EXISTS(SELECT 1 FROM hands h WHERE h.run_id=r.id)"
    )
    for row in candidates:
        if row["official"]:
            eligible = row["id"] not in newest_official and str(row["completed_at"] or "") < cutoffs["official"]
            bucket = "official_runs"
        elif row["challenge_id"]:
            eligible = str(row["completed_at"] or "") < cutoffs["challenge"]
            bucket = "challenge_runs"
        else:
            eligible = False
            bucket = "challenge_runs"
        if not eligible:
            continue
        result[bucket].append(row["id"])
        if dry_run:
            continue
        destination = artifact_dir / f"{row['id']}.zip"
        if not destination.exists():
            archive_run(db, row["id"], artifact_dir)
        with zipfile.ZipFile(destination) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"artifact verification failed for {row['id']}")
        db.execute("DELETE FROM hands WHERE run_id=?", (row["id"],))

    sessions = db.all(
        "SELECT id FROM training_sessions WHERE status IN ('completed','expired','failed') AND created_at<?",
        (cutoffs["training"],),
    )
    result["training_sessions"] = [row["id"] for row in sessions]
    if not dry_run:
        for row in sessions:
            with db.connect() as conn:
                conn.execute("DELETE FROM training_actions WHERE session_id=?", (row["id"],))
                conn.execute("DELETE FROM training_events WHERE session_id=?", (row["id"],))
                conn.execute("DELETE FROM training_hands WHERE session_id=?", (row["id"],))
    return result
