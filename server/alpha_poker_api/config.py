from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_path: Path
    upload_dir: Path
    artifact_dir: Path
    seed_demo_data: bool = True
    auto_run_on_accept: bool = False
    auto_run_hand_count: int = 200
    auto_run_timeout_seconds: int = 900
    auth_required: bool = False
    retained_hand_runs: int = 3
    retained_artifact_runs: int = 30
    invite_code: str | None = None
    operator_token: str | None = None
    operator_usernames: frozenset[str] = frozenset()
    github_token: str | None = None
    feedback_retention_days: int = 90
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "https://alphapoker.io/browser-api/auth/google/callback"
    public_web_url: str = "https://alphapoker.io"

    def __post_init__(self) -> None:
        if not 2 <= self.auto_run_hand_count <= 100_000 or self.auto_run_hand_count % 2:
            raise ValueError("ALPHA_POKER_AUTO_RUN_HANDS must be an even number from 2 to 100000")
        if not 30 <= self.auto_run_timeout_seconds <= 86_400:
            raise ValueError("ALPHA_POKER_AUTO_RUN_TIMEOUT_SECONDS must be from 30 to 86400")
        if not 1 <= self.retained_hand_runs <= 20:
            raise ValueError("ALPHA_POKER_RETAINED_HAND_RUNS must be from 1 to 20")
        if not self.retained_hand_runs <= self.retained_artifact_runs <= 500:
            raise ValueError("ALPHA_POKER_RETAINED_ARTIFACT_RUNS must be at least the hand-run retention and at most 500")
        if not 1 <= self.feedback_retention_days <= 365:
            raise ValueError("ALPHA_POKER_FEEDBACK_RETENTION_DAYS must be from 1 to 365")

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.environ.get("ALPHA_POKER_DATA_DIR", "./data")).resolve()
        return cls(
            data_dir=data_dir,
            database_path=data_dir / "alpha-poker.sqlite3",
            upload_dir=data_dir / "uploads",
            artifact_dir=data_dir / "artifacts",
            seed_demo_data=os.environ.get("ALPHA_POKER_SEED", "true").lower() == "true",
            auto_run_on_accept=os.environ.get("ALPHA_POKER_AUTO_RUN", "true").lower() == "true",
            auto_run_hand_count=int(os.environ.get("ALPHA_POKER_AUTO_RUN_HANDS", "200")),
            auto_run_timeout_seconds=int(os.environ.get("ALPHA_POKER_AUTO_RUN_TIMEOUT_SECONDS", "900")),
            auth_required=os.environ.get("ALPHA_POKER_AUTH_REQUIRED", "true").lower() == "true",
            retained_hand_runs=int(os.environ.get("ALPHA_POKER_RETAINED_HAND_RUNS", "3")),
            retained_artifact_runs=int(os.environ.get("ALPHA_POKER_RETAINED_ARTIFACT_RUNS", "30")),
            invite_code=os.environ.get("ALPHA_POKER_INVITE_CODE") or None,
            operator_token=os.environ.get("ALPHA_POKER_OPERATOR_TOKEN") or None,
            operator_usernames=frozenset(
                name.strip().lower()
                for name in os.environ.get("ALPHA_POKER_OPERATOR_USERNAMES", "").split(",")
                if name.strip()
            ),
            github_token=os.environ.get("GITHUB_TOKEN") or None,
            feedback_retention_days=int(os.environ.get("ALPHA_POKER_FEEDBACK_RETENTION_DAYS", "90")),
            google_client_id=os.environ.get("ALPHA_POKER_GOOGLE_CLIENT_ID") or None,
            google_client_secret=os.environ.get("ALPHA_POKER_GOOGLE_CLIENT_SECRET") or None,
            google_redirect_uri=os.environ.get("ALPHA_POKER_GOOGLE_REDIRECT_URI", "https://alphapoker.io/browser-api/auth/google/callback"),
            public_web_url=os.environ.get("ALPHA_POKER_PUBLIC_WEB_URL", "https://alphapoker.io").rstrip("/"),
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
