from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_poker_api.config import Settings
from alpha_poker_api.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(tmp_path, tmp_path / "db.sqlite3", tmp_path / "uploads", tmp_path / "artifacts", True)
    with TestClient(create_app(settings)) as test_client:
        yield test_client
