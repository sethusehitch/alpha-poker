import io
import json
import logging
import zipfile

from fastapi.testclient import TestClient

from alpha_poker_api.auth import hash_password, verify_password
from alpha_poker_api.config import Settings
from alpha_poker_api.main import RedactCapabilityTokens, create_app


def package() -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("bot.py", "def decide(state):\n    return {'action': 'call'}\n")
        archive.writestr(
            "bot.json",
            json.dumps(
                {
                    "api_version": "2026-09-01",
                    "name": "Auth Bot",
                    "language": "python",
                    "entrypoint": "bot.py:decide",
                }
            ),
        )
    return data.getvalue()


def auth_client(tmp_path, invite_code=None, operator_token=None):
    settings = Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=False,
        auth_required=True,
        invite_code=invite_code,
        operator_token=operator_token,
    )
    return TestClient(create_app(settings))


def test_scrypt_password_hash_is_salted_and_verifiable():
    first = hash_password("correct horse")
    second = hash_password("correct horse")
    assert first != second
    assert verify_password("correct horse", first)
    assert not verify_password("wrong password", first)


def test_websocket_capability_tokens_are_redacted_from_logs():
    record = logging.LogRecord(
        "uvicorn.error",
        logging.INFO,
        __file__,
        1,
        '%s - "WebSocket %s" [accepted]',
        (("127.0.0.1", 1), "/v1/training/ws?session_id=one&token=super-secret"),
        None,
    )
    assert RedactCapabilityTokens().filter(record)
    rendered = record.getMessage()
    assert "super-secret" not in rendered
    assert "token=[redacted]" in rendered


def test_register_login_me_and_revoke(tmp_path):
    with auth_client(tmp_path) as client:
        registered = client.post(
            "/v1/auth/register", json={"username": "Maya_1", "password": "correct horse"}
        )
        assert registered.status_code == 201
        assert registered.json()["username"] == "maya_1"
        token = registered.json()["token"]
        user_row = client.app.state.db.one(
            "SELECT password_hash FROM users WHERE username=?", ("maya_1",)
        )
        session_row = client.app.state.db.one(
            "SELECT token_hash FROM auth_sessions WHERE username=?", ("maya_1",)
        )
        assert user_row["password_hash"] != "correct horse"
        assert token not in user_row["password_hash"]
        assert session_row["token_hash"] != token

        assert client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json() == {
            "username": "maya_1", "is_operator": False
        }
        assert client.post(
            "/v1/auth/login", json={"username": "maya_1", "password": "wrong password"}
        ).status_code == 401
        logged_in = client.post(
            "/v1/auth/login", json={"username": "maya_1", "password": "correct horse"}
        )
        assert logged_in.status_code == 200
        second_token = logged_in.json()["token"]

        assert client.post(
            "/v1/auth/logout", headers={"Authorization": f"Bearer {second_token}"}
        ).status_code == 204
        assert client.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {second_token}"}
        ).status_code == 401
        assert client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_protected_mutations_use_authenticated_username(tmp_path):
    with auth_client(tmp_path) as client:
        assert client.post(
            "/v1/submissions",
            data={"username": "maya", "bot_name": "Nope"},
            files={"package": ("bot.zip", package(), "application/zip")},
        ).status_code == 401
        registered = client.post(
            "/v1/auth/register", json={"username": "maya", "password": "correct horse"}
        ).json()
        headers = {"Authorization": f"Bearer {registered['token']}"}
        mismatch = client.post(
            "/v1/submissions",
            headers=headers,
            data={"username": "someone_else", "bot_name": "Nope"},
            files={"package": ("bot.zip", package(), "application/zip")},
        )
        assert mismatch.status_code == 403
        submitted = client.post(
            "/v1/submissions",
            headers=headers,
            data={"username": "maya", "bot_name": "Mine"},
            files={"package": ("bot.zip", package(), "application/zip")},
        )
        assert submitted.status_code == 202
        assert client.get("/v1/submissions/current", headers=headers).json()["username"] == "maya"


def test_account_status_exposes_submission_and_waiting_state(tmp_path):
    settings = Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=False,
        auto_run_on_accept=True,
        auto_run_hand_count=2,
        auth_required=True,
    )
    with TestClient(create_app(settings)) as client:
        registered = client.post(
            "/v1/auth/register", json={"username": "maya", "password": "correct horse"}
        ).json()
        headers = {"Authorization": f"Bearer {registered['token']}"}
        submitted = client.post(
            "/v1/submissions",
            headers=headers,
            data={"username": "maya", "bot_name": "Mine"},
            files={"package": ("bot.zip", package(), "application/zip")},
        ).json()
        status = client.get("/v1/account/status", headers=headers)
        assert status.status_code == 200
        body = status.json()
        assert body["submission"]["submission_id"] == submitted["submission_id"]
        assert body["submission"]["status"] == "accepted"
        assert body["league"]["queue"]["state"] == "waiting_for_players"
        assert body["participant_state"] == "waiting_for_players"
        assert "1 more active bot" in body["participant_message"]
        assert body["result"] is None
        assert body["submission_logs_url"].endswith("/logs")
        assert client.get("/v1/account/status").status_code == 401


def test_registration_conflict_does_not_reveal_password_state(tmp_path):
    with auth_client(tmp_path) as client:
        body = {"username": "maya", "password": "correct horse"}
        assert client.post("/v1/auth/register", json=body).status_code == 201
        conflict = client.post("/v1/auth/register", json=body)
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "username_taken"


def test_optional_invite_code_gates_registration(tmp_path):
    with auth_client(tmp_path, invite_code="cohort-only") as client:
        body = {"username": "maya", "password": "correct horse"}
        rejected = client.post("/v1/auth/register", json=body)
        assert rejected.status_code == 403
        assert rejected.json()["error"]["code"] == "invite_invalid"
        body["invite_code"] = "cohort-only"
        assert client.post("/v1/auth/register", json=body).status_code == 201


def test_allowlisted_operator_name_requires_server_operator_token(tmp_path):
    settings = Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=False,
        auth_required=True,
        operator_token="operator-secret",
        operator_usernames=frozenset({"captain"}),
    )
    with TestClient(create_app(settings)) as client:
        body = {"username": "captain", "password": "correct horse"}
        blocked = client.post("/v1/auth/register", json=body)
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "operator_required"
        created = client.post(
            "/v1/auth/register",
            headers={"X-Alpha-Operator": "operator-secret"},
            json=body,
        )
        assert created.status_code == 201
        token = created.json()["token"]
        assert client.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        ).json()["is_operator"] is True


def test_registration_and_login_are_rate_limited_by_client_ip(tmp_path):
    with auth_client(tmp_path) as client:
        register_body = {"username": "same_name", "password": "correct horse"}
        for attempt in range(8):
            response = client.post(
                "/v1/auth/register",
                headers={"X-Forwarded-For": "203.0.113.10"},
                json={**register_body, "username": f"student_{attempt}"},
            )
            assert response.status_code == 201
        limited = client.post(
            "/v1/auth/register",
            headers={"X-Forwarded-For": "203.0.113.10"},
            json={**register_body, "username": "student_9"},
        )
        assert limited.status_code == 429

        for attempt in range(20):
            response = client.post(
                "/v1/auth/login",
                headers={"X-Forwarded-For": "203.0.113.11"},
                json={"username": f"nobody_{attempt}", "password": "wrong password"},
            )
            assert response.status_code == 401
        limited = client.post(
            "/v1/auth/login",
            headers={"X-Forwarded-For": "203.0.113.11"},
            json={"username": "another_nobody", "password": "wrong password"},
        )
        assert limited.status_code == 429


def test_failed_login_is_rate_limited_per_account_across_client_ips(tmp_path):
    with auth_client(tmp_path) as client:
        for attempt in range(10):
            response = client.post(
                "/v1/auth/login",
                headers={"X-Forwarded-For": f"198.51.100.{attempt + 1}"},
                json={"username": "known_student", "password": "wrong password"},
            )
            assert response.status_code == 401
        limited = client.post(
            "/v1/auth/login",
            headers={"X-Forwarded-For": "198.51.100.250"},
            json={"username": "known_student", "password": "wrong password"},
        )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "rate_limited"


def test_training_resources_and_manual_runs_enforce_authentication(tmp_path):
    with auth_client(tmp_path) as client:
        tokens = {}
        for username in ("maya", "leo"):
            tokens[username] = client.post(
                "/v1/auth/register",
                json={"username": username, "password": "correct horse"},
            ).json()["token"]
        maya_headers = {"Authorization": f"Bearer {tokens['maya']}"}
        leo_headers = {"Authorization": f"Bearer {tokens['leo']}"}
        created = client.post(
            "/v1/training/sessions",
            headers=maya_headers,
            json={"username": "maya", "hand_limit": 2},
        )
        assert created.status_code == 201
        session_id = created.json()["session_id"]
        assert client.get(f"/v1/training/sessions/{session_id}", headers=maya_headers).status_code == 200
        assert client.get(f"/v1/training/sessions/{session_id}", headers=leo_headers).status_code == 403
        assert client.get(f"/v1/training/sessions/{session_id}/artifacts", headers=leo_headers).status_code == 403
        assert client.delete(f"/v1/training/sessions/{session_id}", headers=leo_headers).status_code == 403
        assert client.post("/v1/admin/runs", json={"hand_count_per_pairing": 2}).status_code == 401
        assert client.post(
            "/v1/admin/runs",
            headers=maya_headers,
            json={"hand_count_per_pairing": 2},
        ).status_code == 403


def test_manual_run_requires_operator_token_when_auth_is_enabled(tmp_path):
    with auth_client(tmp_path, operator_token="local-operator-secret") as client:
        account = client.post(
            "/v1/auth/register",
            json={"username": "maya", "password": "correct horse"},
        ).json()
        headers = {
            "Authorization": f"Bearer {account['token']}",
            "X-Alpha-Operator": "local-operator-secret",
        }
        response = client.post(
            "/v1/admin/runs",
            headers=headers,
            json={"hand_count_per_pairing": 2},
        )
        assert response.status_code == 202
