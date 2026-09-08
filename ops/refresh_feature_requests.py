"""Preview by default. Apply reviewed product-request edits after release approval."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def refresh(database, apply=False):
    updates = json.loads(Path(__file__).with_name("feature-request-refresh.json").read_text())
    with sqlite3.connect(f"{Path(database).resolve().as_uri()}?mode=rw", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        changes = []
        for update in updates:
            update.setdefault("hidden", 0)
            row = connection.execute("SELECT * FROM feature_requests WHERE id=?", (update["id"],)).fetchone()
            if row is None:
                raise ValueError(f"Missing reviewed request: {update['id']}")
            if all(row[key] == update[key] for key in ("title", "details", "status", "hidden")):
                continue
            if row["author_username"] != "product-team" or row["title"] != update["previous_title"] or row["status"] != "submitted" or row["hidden"]:
                raise ValueError(f"Request changed since review: {update['id']}. Review before applying.")
            changes.append({"before": dict(row), "after": update})
        if apply and changes:
            # Persist exact original rows for rollback, without touching votes or authors.
            backup = Path(database).with_name("feature-requests-before-refresh-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f") + ".json")
            with backup.open("x") as stream:
                backup.chmod(0o600)
                json.dump(changes, stream, indent=2)
            for change in changes:
                update = change["after"]
                connection.execute("UPDATE feature_requests SET title=?,details=?,status=?,hidden=?,updated_at=? WHERE id=?", (
                    update["title"], update["details"], update["status"], update["hidden"], datetime.now(timezone.utc).isoformat(), update["id"]))
        return [{key: change["after"][key] for key in ("id", "title", "status", "hidden")} for change in changes]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps({"applied": args.apply, "changes": refresh(args.database, args.apply)}, indent=2))
