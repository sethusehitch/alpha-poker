"""Run a reproducible 20-bot capacity smoke test on the local machine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import time
import zipfile

from alpha_poker_api.config import Settings
from alpha_poker_api.db import Database, now_iso
from alpha_poker_api.jobs import archive_run, run_official_league


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hands-per-pairing", type=int, default=20)
    args = parser.parse_args()
    if args.hands_per_pairing < 2 or args.hands_per_pairing % 2:
        raise SystemExit("--hands-per-pairing must be a positive even number")

    with tempfile.TemporaryDirectory(prefix="alpha-poker-load-") as directory:
        root = Path(directory)
        settings = Settings(root, root / "db.sqlite3", root / "uploads", root / "artifacts", seed_demo_data=False)
        settings.ensure_dirs()
        package = root / "bot.zip"
        fixture = Path(__file__).parent / "fixtures" / "caller"
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(fixture / "bot.py", "bot.py")
            archive.write(fixture / "bot.json", "bot.json")
        db = Database(settings.database_path)
        db.initialize(False)
        for index in range(20):
            username = f"user{index:02d}"
            db.execute(
                "INSERT INTO submissions(id,username,bot_name,original_filename,package_path,sha256,status,active,created_at,updated_at) VALUES(?,?,?,?,?,?,'accepted',1,?,?)",
                (f"sub{index}", username, f"Bot{index:02d}", "bot.zip", str(package), "benchmark", now_iso(), now_iso()),
            )
        run_id = "run_load20"
        db.execute(
            "INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,hand_count_per_pairing) VALUES(?,'queued',1,'prototype-0.1','heads-up-v1',?,?,?)",
            (run_id, 424242, now_iso(), args.hands_per_pairing),
        )
        started = time.perf_counter()
        run_official_league(db, run_id, args.hands_per_pairing)
        elapsed = time.perf_counter() - started
        artifact = archive_run(db, run_id, settings.artifact_dir)
        hand_count = 190 * args.hands_per_pairing
        entries = db.all("SELECT bb_per_100,hands FROM leaderboard WHERE run_id=?", (run_id,))
        print(json.dumps({
            "participants": 20,
            "pairings": 190,
            "hands": hand_count,
            "elapsed_seconds": round(elapsed, 3),
            "hands_per_second": round(hand_count / elapsed, 1),
            "database_mb": round(settings.database_path.stat().st_size / 1_048_576, 2),
            "artifact_mb": round(artifact.stat().st_size / 1_048_576, 2),
            "score_sum": round(sum(row["bb_per_100"] for row in entries), 10),
            "hands_per_bot": sorted({row["hands"] for row in entries}),
        }, indent=2))


if __name__ == "__main__":
    main()
