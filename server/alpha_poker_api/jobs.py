from __future__ import annotations

from .db import Database, now_iso
import csv
import io
import itertools
import json
from pathlib import Path
from time import monotonic
import zipfile
import secrets

from .engine_adapter import load_bot, validate_package
from .ratings import BASE_RATING, calculate_round_robin_elo


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
    hand_count_per_pairing: int,
    timeout_seconds: int = 900,
) -> None:
    """Run every active bot head-to-head using the deterministic engine."""
    from alpha_poker import play_match

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
    aggregate: dict[str, list[int]] = {row["username"]: [] for row in submissions}
    bot_names = {row["username"]: row["bot_name"] for row in submissions}
    submission_ids = {row["username"]: row["id"] for row in submissions}
    starting_ratings: dict[str, int] = {}
    for row in submissions:
        previous = db.one(
            "SELECT l.elo_rating FROM leaderboard l "
            "JOIN runs r ON r.id=l.run_id "
            "WHERE l.submission_id=? AND r.status='completed' AND r.official=1 "
            "ORDER BY r.completed_at DESC,r.requested_at DESC LIMIT 1",
            (row["id"],),
        )
        starting_ratings[row["username"]] = previous["elo_rating"] if previous else BASE_RATING
    elo_results: list[tuple[str, str, float]] = []
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
                result = play_match(
                    bots,
                    pairs=max(1, hand_count_per_pairing // 2), seed=int(run["seed"]) + match_index * 100000,
                    bot_names=(left["username"], right["username"]), match_id=match_id,
                    timeout_seconds=0.25,
                )
            finally:
                for bot in bots:
                    bot.close()
            wins_a = wins_b = ties = 0
            for history in result.hand_histories:
                hand_number += 1
                profits = history["bot_profits"]
                aggregate[left["username"]].append(int(profits[0]))
                aggregate[right["username"]].append(int(profits[1]))
                if profits[0] > 0: wins_a += 1
                elif profits[1] > 0: wins_b += 1
                else: ties += 1
                winner = left["username"] if profits[0] > 0 else right["username"] if profits[1] > 0 else None
                hand_id = history.get("hand_id", f"{match_id}_{hand_number}")
                record = {**history, "id": hand_id, "run_id": run_id, "players": [left["username"], right["username"]], "winner": winner}
                db.execute(
                    "INSERT INTO hands VALUES(?,?,?,?,?,?,?,?,?)",
                    (hand_id, run_id, hand_number, left["username"], right["username"], winner,
                     int(history.get("pot", 0)), json.dumps(record), Database._to_phh({
                         "id": hand_id, "players": [left["username"], right["username"]],
                         "board": history.get("board", []), "pot": history.get("pot", 0), "winner": winner,
                         "blinds": history.get("blinds", {"small": 50, "big": 100}),
                         "starting_stacks": history.get("starting_stacks", [10000, 10000]),
                     })),
                )
            db.execute(
                "INSERT INTO matchups VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (match_id, run_id, left["username"], right["username"], result.hands,
                 result.bb_per_100[0], result.confidence_95[0][0], result.confidence_95[0][1], wins_a, wins_b, ties),
            )
            match_score = 1.0 if result.bb_per_100[0] > 0 else 0.0 if result.bb_per_100[0] < 0 else 0.5
            elo_results.append((left["username"], right["username"], match_score))
            db.execute(
                "UPDATE runs SET completed_matchups=?,heartbeat_at=? WHERE id=?",
                (match_index, now_iso(), run_id),
            )
        scores = []
        from alpha_poker.match import summarize_profits
        elo_standings = calculate_round_robin_elo(starting_ratings, elo_results)
        for username, profits in aggregate.items():
            summary = summarize_profits(profits, big_blind=100, cluster_size=2)
            scores.append((
                username,
                elo_standings[username],
                summary["bb_per_100"],
                summary["confidence_95"][0],
                summary["confidence_95"][1],
                summary["hands"],
            ))
        scores.sort(key=lambda item: (-item[1].rating, -item[2], item[0]))
        for rank, (username, elo, score, low, high, hands) in enumerate(scores, start=1):
            db.execute(
                "INSERT INTO leaderboard(run_id,rank,username,bot_name,bb_per_100,ci_low,ci_high,hands,submission_id,elo_rating,matchup_wins,matchup_losses,matchup_draws) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, rank, username, bot_names[username], score, low, high, hands,
                 submission_ids[username], elo.rating, elo.wins, elo.losses, elo.draws),
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
    if not run or run["status"] != "completed" or not matchup:
        return False
    # The stored per-hand profit is authoritative and avoids reconstructing a
    # chip margin from a rounded bb/100 value.
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
    timestamp = now_iso()
    with db.connect() as conn:
        conn.execute(
            "UPDATE rival_challenges SET status='completed',winner_username=?,margin_play_chips=?,"
            "completed_at=COALESCE(completed_at,?),updated_at=?,error=NULL WHERE id=?",
            (winner, abs(total_a), timestamp, timestamp, challenge_id),
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
    """Atomically claim and execute one 200-hand, unranked direct challenge."""
    from alpha_poker import play_match

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
            "VALUES(?,'running',0,'prototype-0.1','heads-up-v1',?,?,?,?,?,1,0)",
            (run_id, challenge["seed"], challenge["accepted_at"] or timestamp, timestamp, timestamp, challenge["hand_count"]),
        )
        db.execute("UPDATE rival_challenges SET run_id=?,updated_at=? WHERE id=?", (run_id, now_iso(), challenge_id))
        bots = (load_bot(Path(left["package_path"])), load_bot(Path(right["package_path"])))
        try:
            result = play_match(
                bots,
                pairs=max(1, int(challenge["hand_count"]) // 2),
                seed=int(challenge["seed"]),
                bot_names=(challenge["challenger_username"], challenge["challenged_username"]),
                match_id=f"{run_id}_match_1",
                timeout_seconds=0.25,
            )
        finally:
            for bot in bots:
                bot.close()
        total_a = wins_a = wins_b = ties = 0
        hand_rows = []
        for hand_number, history in enumerate(result.hand_histories, start=1):
            profits = history["bot_profits"]
            total_a += int(profits[0])
            if profits[0] > 0:
                wins_a += 1
            elif profits[1] > 0:
                wins_b += 1
            else:
                ties += 1
            winner = (
                challenge["challenger_username"] if profits[0] > 0
                else challenge["challenged_username"] if profits[1] > 0
                else None
            )
            hand_id = history.get("hand_id", f"{run_id}_match_1_{hand_number}")
            record = {
                **history,
                "id": hand_id,
                "run_id": run_id,
                "players": [challenge["challenger_username"], challenge["challenged_username"]],
                "winner": winner,
            }
            hand_rows.append((
                hand_id, run_id, hand_number,
                challenge["challenger_username"], challenge["challenged_username"], winner,
                int(history.get("pot", 0)), json.dumps(record), Database._to_phh({
                    "id": hand_id,
                    "players": record["players"],
                    "board": history.get("board", []),
                    "pot": history.get("pot", 0),
                    "winner": winner,
                    "blinds": history.get("blinds", {"small": 50, "big": 100}),
                    "starting_stacks": history.get("starting_stacks", [10000, 10000]),
                }),
            ))
        completed_at = now_iso()
        winner_username = (
            challenge["challenger_username"] if total_a > 0
            else challenge["challenged_username"] if total_a < 0
            else None
        )
        with db.connect() as conn:
            conn.executemany("INSERT INTO hands VALUES(?,?,?,?,?,?,?,?,?)", hand_rows)
            conn.execute(
                "INSERT INTO matchups VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (f"{run_id}_match_1", run_id, challenge["challenger_username"], challenge["challenged_username"],
                 result.hands, result.bb_per_100[0], result.confidence_95[0][0], result.confidence_95[0][1],
                 wins_a, wins_b, ties),
            )
            conn.execute(
                "UPDATE runs SET status='completed',heartbeat_at=?,completed_at=?,completed_matchups=1 WHERE id=?",
                (completed_at, completed_at, run_id),
            )
            conn.execute(
                "UPDATE rival_challenges SET status='completed',winner_username=?,margin_play_chips=?,"
                "completed_at=?,updated_at=?,error=NULL WHERE id=?",
                (winner_username, abs(total_a), completed_at, completed_at, challenge_id),
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
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("hands.jsonl", "".join(row["record_json"] + "\n" for row in rows))
        archive.writestr("hands.phh", "\n".join(row["phh"] for row in rows))
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["hand_id", "hand_number", "player_a", "player_b", "winner", "pot"])
        writer.writerows(
            [[row["id"], row["hand_number"], row["player_a"], row["player_b"], row["winner"], row["pot"]] for row in rows]
        )
        archive.writestr("hands.csv", csv_buffer.getvalue())
        archive.writestr("manifest.json", json.dumps(run, indent=2))
        archive.writestr("summary.json", json.dumps(summarize_run(db, run_id, rows), indent=2))
    return buffer.getvalue()


def summarize_run(db: Database, run_id: str, rows: list[dict] | None = None) -> dict:
    run = db.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if run and not bool(run["official"]):
        challenge = db.one("SELECT * FROM rival_challenges WHERE run_id=?", (run_id,))
        if challenge:
            matchup = db.one("SELECT * FROM matchups WHERE run_id=?", (run_id,))
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
            margin = int(challenge["margin_play_chips"] or 0)
            challenger = challenge["challenger_username"]
            challenged = challenge["challenged_username"]
            hands = int(matchup["hands"]) if matchup else int(challenge["hand_count"])
            if winner:
                loser = challenged if winner == challenger else challenger
                overview = (
                    f"{submission_names[winner] or winner} ({winner}) beat "
                    f"{submission_names[loser] or loser} ({loser}) by {margin:,} play chips "
                    f"across {hands} mirrored hands."
                )
            else:
                overview = (
                    f"{submission_names[challenger] or challenger} ({challenger}) and "
                    f"{submission_names[challenged] or challenged} ({challenged}) drew "
                    f"after {hands} mirrored hands."
                )
            return {
                "run_id": run_id,
                "challenge_id": challenge["id"],
                "kind": "direct_rival_challenge",
                "official": False,
                "ranked": False,
                "affects_elo": False,
                "play_money_only": True,
                "overview": overview,
                "outcome": {
                    "winner_username": winner,
                    "is_draw": winner is None,
                    "margin_play_chips": margin,
                    "hands": hands,
                },
                "players": {
                    challenger: {
                        "bot_name": submission_names[challenger],
                        "role": "challenger",
                        "hands_won": int(matchup["wins_a"]) if matchup else None,
                    },
                    challenged: {
                        "bot_name": submission_names[challenged],
                        "role": "challenged",
                        "hands_won": int(matchup["wins_b"]) if matchup else None,
                    },
                },
                "methodology": {
                    "format": "heads-up no-limit hold'em",
                    "seat_mirroring": True,
                    "duplicate_deal_pairs": hands // 2,
                    "winner_metric": "aggregate_play_chip_profit",
                    "ranking_effect": "Direct challenges do not change public Elo.",
                },
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
            "bb_per_100": standing["bb_per_100"],
            "confidence_95": [standing["ci_low"], standing["ci_high"]],
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
    runner_up = standings[1] if len(standings) > 1 else None
    intervals_overlap = True
    if leader and runner_up:
        intervals_overlap = not (leader["ci_low"] > runner_up["ci_high"])
    if leader:
        overview = (
            f"{leader['bot_name']} ({leader['username']}) finished first with "
            f"{leader['elo_rating']:,} Elo and a "
            f"{leader['matchup_wins']}-{leader['matchup_losses']} round-robin record. "
            "Match results use mirrored seats and identical duplicate deals."
        )
        confidence_note = (
            "The first- and second-place 95% intervals overlap, so more hands are needed before treating the ordering as conclusive."
            if runner_up and intervals_overlap
            else "The first-place 95% interval is separated from second place in this run."
        )
    else:
        overview = "This run has no completed standings."
        confidence_note = "No statistical comparison is available."
    return {
        "run_id": run_id,
        "overview": overview,
        "confidence_note": confidence_note,
        "methodology": {
            "ranking_metric": "elo",
            "starting_rating": BASE_RATING,
            "k_factor": 32,
            "rating_period": "one complete round robin",
            "seat_mirroring": True,
            "confidence_level": 0.95,
            "confidence_clusters": "duplicate deal pairs",
        },
        "players": players,
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
