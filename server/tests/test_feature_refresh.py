import importlib.util
import json
from pathlib import Path

import pytest
from alpha_poker_api.db import Database

spec = importlib.util.spec_from_file_location("feature_refresh", Path(__file__).resolve().parents[2] / "ops/refresh_feature_requests.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def seed(tmp_path):
    path = tmp_path / "requests.sqlite3"
    db = Database(path)
    db.initialize(seed=False)
    updates = json.loads(Path(module.__file__).with_name("feature-request-refresh.json").read_text())
    for row in updates:
        db.execute("INSERT INTO feature_requests(id,title,details,status,author_username,created_at,updated_at) VALUES(?,?,?,'submitted','product-team','original','original')", (row["id"], row["previous_title"], "Original request"))
    return path, db, updates


def test_refresh_is_dry_run_by_default_and_idempotent(tmp_path):
    path, db, updates = seed(tmp_path)
    assert len(module.refresh(path)) == 3
    assert all(row["status"] == "submitted" for row in db.all("SELECT status FROM feature_requests"))
    assert len(module.refresh(path, apply=True)) == 3
    assert module.refresh(path, apply=True) == []
    assert db.one("SELECT COUNT(*) AS n FROM feature_requests")["n"] == 3
    assert db.one("SELECT status FROM feature_requests WHERE id=?", (updates[0]["id"],))["status"] == "shipped"
    assert len(list(tmp_path.glob("feature-requests-before-refresh-*.json"))) == 1


def test_refresh_fails_closed_if_request_changed(tmp_path):
    path, db, updates = seed(tmp_path)
    db.execute("UPDATE feature_requests SET title='Someone edited this' WHERE id=?", (updates[1]["id"],))
    with pytest.raises(ValueError, match="changed since review"):
        module.refresh(path, apply=True)
    assert all(row["status"] == "submitted" for row in db.all("SELECT status FROM feature_requests"))
    assert not list(tmp_path.glob("feature-requests-before-refresh-*.json"))
