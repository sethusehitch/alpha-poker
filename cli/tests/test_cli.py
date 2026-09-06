from __future__ import annotations

import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from alpha_poker_cli import main as cli
import build_starter_kit


VALID_BOT = '''def decide(state):
    if "check" in state["legal_actions"]:
        return {"action": "check"}
    if "call" in state["legal_actions"]:
        return {"action": "call"}
    return {"action": "fold"}
'''


def make_bot(root: Path, source: str = VALID_BOT) -> None:
    (root / "bot.py").write_text(source, encoding="utf-8")
    (root / "bot.json").write_text(json.dumps({
        "api_version": cli.API_VERSION,
        "name": "Test Bot",
        "language": "python",
        "entrypoint": "bot.py:decide",
    }), encoding="utf-8")


class CliTests(unittest.TestCase):
    def test_credentials_honor_xdg_config_home_for_isolated_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                "os.environ",
                {"XDG_CONFIG_HOME": directory},
                clear=False,
            ), patch.object(cli, "DEFAULT_TOKEN", None):
                expected = Path(directory) / "alpha-poker" / "credentials.json"
                self.assertEqual(cli._config_path(), expected)
                cli._remember_profile("https://league.test/v1", "maya", "session-token")
                self.assertEqual(cli._identity("https://league.test/v1"), ("maya", "session-token"))
                self.assertEqual(expected.stat().st_mode & 0o777, 0o600)

    def test_starter_kit_bundles_cli_and_agent_workflow(self):
        destination = build_starter_kit.build()
        with zipfile.ZipFile(destination) as archive:
            names = archive.namelist()
            self.assertIn("WORKFLOWS.md", names)
            self.assertIn("cli/pyproject.toml", names)
            self.assertIn("cli/alpha_poker_cli/main.py", names)
            workflow = archive.read("WORKFLOWS.md").decode("utf-8")
            readme = archive.read("README.md").decode("utf-8")
            self.assertIn("Hosted API:", workflow)
            self.assertIn("perform it for them", workflow)
            self.assertIn("Agent-operated rival flow", workflow)
            self.assertIn("rivals challenge maya --yes --json", workflow)
            self.assertIn("Rival challenge API", archive.read("API.md").decode("utf-8"))
            self.assertIn("do not need to open a terminal", readme)
            self.assertIn("Challenge a rival", readme)
            self.assertNotIn("alpha-poker submit .", readme)

    def test_credentials_are_scoped_by_api_and_written_private(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "credentials.json"
            with patch.dict("os.environ", {"ALPHA_POKER_CONFIG": str(config)}):
                cli._remember_profile("http://one.test/v1", "maya", "secret-one")
                cli._remember_profile("http://two.test/v1", "leo", "secret-two")
                self.assertEqual(cli._identity("http://one.test/v1"), ("maya", "secret-one"))
                self.assertEqual(cli._identity("http://two.test/v1"), ("leo", "secret-two"))
                self.assertEqual(config.stat().st_mode & 0o777, 0o600)
                cli._forget_profile("http://one.test/v1")
                self.assertIsNone(cli._profile("http://one.test/v1").get("token"))

    def test_register_prompts_for_password_and_secure_invite_then_stores_session(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "credentials.json"
            response = {"username": "maya", "token": "session-token", "expires_at": "later"}
            output = io.StringIO()
            with patch.dict("os.environ", {"ALPHA_POKER_CONFIG": str(config)}), patch.object(
                cli.getpass, "getpass", side_effect=["correct horse", "correct horse", "cohort-secret"]
            ), patch.object(
                cli,
                "_http_json",
                side_effect=[{"auth_required": True, "invite_required": True}, response],
            ) as request, contextlib.redirect_stdout(output):
                code = cli.main(["register", "Maya", "--api-url", "http://league.test/v1"])
            self.assertEqual(code, 0)
            self.assertIn("Logged in as maya", output.getvalue())
            saved = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(saved["profiles"]["http://league.test/v1"]["token"], "session-token")
            self.assertEqual(request.call_args_list[0].args[:2], ("GET", "http://league.test/v1/config"))
            payload = request.call_args_list[1].args[2]
            self.assertEqual(payload["password"], "correct horse")
            self.assertEqual(payload["invite_code"], "cohort-secret")

    def test_register_flag_avoids_invite_prompt_for_automation(self):
        response = {"username": "maya", "token": "session-token", "expires_at": "later"}
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {"ALPHA_POKER_CONFIG": str(Path(directory) / "credentials.json")}
        ), patch.object(
            cli.getpass, "getpass", side_effect=["correct horse", "correct horse"]
        ) as prompt, patch.object(cli, "_http_json", return_value=response) as request:
            code = cli.main([
                "register", "maya", "--invite-code", "automation-code", "--api-url", "http://league.test/v1"
            ])
        self.assertEqual(code, 0)
        self.assertEqual(prompt.call_count, 2)
        self.assertEqual(request.call_args.args[2]["invite_code"], "automation-code")

    def test_login_without_an_interactive_terminal_has_a_clear_error(self):
        error = io.StringIO()
        with patch.object(cli.getpass, "getpass", side_effect=EOFError), contextlib.redirect_stderr(error):
            code = cli.main(["login", "maya", "--api-url", "https://league.test/v1"])
        self.assertEqual(code, 1)
        self.assertIn("Error: secure password input requires an interactive terminal", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())

    def test_validate_accepts_contract_compliant_bot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bot(root)
            result = cli.validate_bot(root)
            self.assertEqual(result["manifest"]["name"], "Test Bot")
            self.assertEqual(result["checks"], 3)

    def test_validate_rejects_illegal_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bot(root, 'def decide(state): return {"action": "dance"}\n')
            with self.assertRaisesRegex(cli.CliError, "unknown action"):
                cli.validate_bot(root)

    def test_submission_zip_is_deterministic_and_minimal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bot(root)
            first, second = root / "one.zip", root / "two.zip"
            cli.build_submission(root, first)
            cli.build_submission(root, second)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), ["bot.py", "bot.json"])
                self.assertTrue(all(item.date_time == cli.FIXED_ZIP_TIME for item in archive.infolist()))

    def test_submit_posts_multipart_package(self):
        captured = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured["path"] = self.path
                captured["content_type"] = self.headers["Content-Type"]
                captured["authorization"] = self.headers.get("Authorization")
                captured["body"] = self.rfile.read(int(self.headers["Content-Length"]))
                response = json.dumps({"submission_id": "sub_test"}).encode()
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                make_bot(root)
                out, err = io.StringIO(), io.StringIO()
                with patch.object(cli, "DEFAULT_TOKEN", "secret-token"), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = cli.main(["submit", str(root), "--username", "maya", "--api-url", f"http://127.0.0.1:{server.server_port}/v1"])
                self.assertEqual(code, 0, err.getvalue())
                self.assertIn("Submitted Test Bot: sub_test", out.getvalue())
                self.assertEqual(captured["path"], "/v1/submissions")
                self.assertIn("multipart/form-data", captured["content_type"])
                self.assertIn(b'filename="alpha-poker-submission.zip"', captured["body"])
                self.assertIn(b'name="username"\r\n\r\nmaya', captured["body"])
                self.assertEqual(captured["authorization"], "Bearer secret-token")
                self.assertNotIn(b"secret-token", captured["body"])
        finally:
            server.shutdown()
            server.server_close()

    def test_submission_waits_for_validation_to_finish(self):
        responses = [
            {"submission_id": "sub_test", "status": "validating"},
            {"submission_id": "sub_test", "status": "accepted", "active": True},
        ]
        with patch.object(cli, "_http_json", side_effect=responses[1:]) as request, patch.object(cli.time, "sleep"):
            result = cli._wait_for_submission("https://league.test/v1", responses[0], "secret", timeout_seconds=1)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(request.call_args.args[:2], ("GET", "https://league.test/v1/submissions/sub_test"))

    def test_train_handles_action_and_downloads_logs(self):
        messages = [
            {"type": "connection.ready", "seq": 1},
            {"type": "action.requested", "seq": 2, "payload": {
                "hand_id": "hand_1", "turn_id": "turn_1", "turn_token": "token_1",
                "state": cli._sample_states()[1],
            }},
            {"type": "session.completed", "seq": 3, "payload": {"artifacts_url": "/v1/training/sessions/trn_test/artifacts"}},
        ]

        class FakeWebSocket:
            instance = None

            def __init__(self, url, token=None):
                self.url, self.token, self.sent = url, token, []
                FakeWebSocket.instance = self

            def receive_json(self):
                return messages.pop(0)

            def send_json(self, message):
                self.sent.append(message)

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bot(root)
            output = root / "logs.zip"
            session = {"session_id": "trn_test", "websocket_url": "ws://localhost/socket", "training_token": "secret"}
            with patch.object(cli, "_http_json", return_value=session) as request, patch.object(cli, "WebSocket", FakeWebSocket), patch.object(cli, "_download", side_effect=lambda _url, path: path) as download:
                result = cli.run_training(root, "http://localhost:8000/v1", "leader", 10, output, "maya")
            self.assertEqual(result, output)
            submitted = FakeWebSocket.instance.sent[0]
            self.assertEqual(submitted["type"], "action.submit")
            self.assertEqual(submitted["action"], "check")
            self.assertEqual(submitted["turn_token"], "token_1")
            download.assert_called_once_with("http://localhost:8000/v1/training/sessions/trn_test/artifacts", output)
            self.assertEqual(request.call_args.args[2]["username"], "maya")

    def test_train_accepts_an_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = cli._training_output_path(Path(directory), "trn_test")
            self.assertEqual(destination, Path(directory) / "alpha-poker-training-trn_test.zip")

            nested = Path(directory) / "new-training-logs"
            destination = cli._training_output_path(nested, "trn_next")
            self.assertEqual(destination, nested / "alpha-poker-training-trn_next.zip")
            self.assertTrue(nested.is_dir())

    def test_train_reconnects_from_the_last_received_sequence(self):
        connections = []

        class FakeWebSocket:
            def __init__(self, url, token=None):
                self.url, self.token = url, token
                self.number = len(connections)
                self.reads = 0
                connections.append(self)

            def receive_json(self):
                self.reads += 1
                if self.number == 0 and self.reads == 1:
                    return {"type": "connection.ready", "seq": 7}
                if self.number == 0:
                    raise OSError("connection dropped")
                return {
                    "type": "session.completed", "seq": 8,
                    "payload": {"artifacts_url": "/v1/training/sessions/trn_test/artifacts"},
                }

            def send_json(self, _message):
                pass

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bot(root)
            output = root / "logs.zip"
            session = {
                "session_id": "trn_test",
                "websocket_url": "ws://localhost/socket?session_id=trn_test&token=secret",
                "training_token": "secret",
            }
            with patch.object(cli, "_http_json", return_value=session), patch.object(cli, "WebSocket", FakeWebSocket), patch.object(cli, "_download", side_effect=lambda _url, path: path):
                result = cli.run_training(root, "http://localhost:8000/v1", "leader", 10, output)

            self.assertEqual(result, output)
            self.assertEqual(len(connections), 2)
            self.assertIn("after_seq=7", connections[1].url)

    def test_http_timeout_becomes_a_clear_cli_error(self):
        with patch.object(cli, "urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaisesRegex(cli.CliError, "did not respond within 30 seconds"):
                cli._http_json("POST", "https://league.test/v1/training/sessions", {})

    def test_training_connection_timeout_is_wrapped_after_retries(self):
        class TimedOutWebSocket:
            def __init__(self, *_args, **_kwargs):
                pass

            def receive_json(self):
                raise TimeoutError("timed out")

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bot(root)
            session = {
                "session_id": "trn_test",
                "websocket_url": "wss://league.test/socket",
                "training_token": "secret",
            }
            with patch.object(cli, "_http_json", return_value=session), patch.object(
                cli, "WebSocket", TimedOutWebSocket
            ), patch.object(cli.time, "sleep"):
                with self.assertRaisesRegex(cli.CliError, "timed out after three attempts"):
                    cli.run_training(root, "https://league.test/v1", "leader", 10, None)

    def test_status_prints_waiting_state_and_latest_result(self):
        payload = {
            "submission": {"submission_id": "sub_one", "bot_name": "Test Bot", "status": "accepted", "error": None},
            "league": {"queue": {"state": "waiting_for_players", "message": "Waiting for 1 more active bot."}, "current_run": None},
            "result": {"id": "run_one", "rank": 1, "elo_rating": 1264, "record": {"wins": 2, "losses": 0, "draws": 0}},
        }
        output = io.StringIO()
        with patch.object(cli, "_identity", return_value=("maya", "secret")), patch.object(
            cli, "_http_json", return_value=payload
        ), contextlib.redirect_stdout(output):
            code = cli.main(["status", "--api-url", "https://league.test/v1"])
        self.assertEqual(code, 0)
        self.assertIn("Bot: Test Bot (accepted)", output.getvalue())
        self.assertIn("Official league: not started (waiting for 1 more active bot)", output.getvalue())
        self.assertIn("Elo: unchanged at 1,264 until the next official run completes", output.getvalue())
        self.assertIn("1,264 Elo", output.getvalue())
        self.assertIn("2 wins, 0 losses", output.getvalue())

        payload["result"] = None
        output = io.StringIO()
        with patch.object(cli, "_identity", return_value=("maya", "secret")), patch.object(
            cli, "_http_json", return_value=payload
        ), contextlib.redirect_stdout(output):
            code = cli.main(["status", "--api-url", "https://league.test/v1"])
        self.assertEqual(code, 0)
        self.assertIn("Elo: not assigned until an official run completes", output.getvalue())

        payload["result"] = {"id": "run_one", "rank": 1, "elo_rating": 1264, "record": {"wins": 2, "losses": 0, "draws": 0}}

        payload["result"]["record"] = {"wins": 1, "losses": 1, "draws": 0}
        output = io.StringIO()
        with patch.object(cli, "_identity", return_value=("maya", "secret")), patch.object(
            cli, "_http_json", return_value=payload
        ), contextlib.redirect_stdout(output):
            code = cli.main(["status", "--api-url", "https://league.test/v1"])
        self.assertEqual(code, 0)
        self.assertIn("1 win, 1 loss", output.getvalue())

        payload["result"]["record"] = {"wins": 1, "losses": 1, "draws": 2}
        output = io.StringIO()
        with patch.object(cli, "_identity", return_value=("maya", "secret")), patch.object(
            cli, "_http_json", return_value=payload
        ), contextlib.redirect_stdout(output):
            code = cli.main(["status", "--api-url", "https://league.test/v1"])
        self.assertEqual(code, 0)
        self.assertIn("1 win, 1 loss, 2 draws", output.getvalue())

    def test_logs_downloads_validation_and_official_artifacts(self):
        payload = {
            "submission": {"submission_id": "sub_one", "bot_name": "Test Bot", "status": "accepted"},
            "league": {"queue": {"state": "completed", "message": "Complete"}},
            "result": {"id": "run_one", "artifacts_url": "/v1/runs/run_one/artifacts"},
            "submission_logs_url": "/v1/submissions/sub_one/logs",
        }
        with tempfile.TemporaryDirectory() as directory, patch.object(
            cli, "_identity", return_value=("maya", "secret")
        ), patch.object(cli, "_http_json", return_value=payload), patch.object(
            cli, "_download", side_effect=lambda _url, path, _token: path
        ) as download:
            code = cli.main(["logs", "--api-url", "https://league.test/v1", "--output", directory])
        self.assertEqual(code, 0)
        self.assertEqual(download.call_count, 2)


if __name__ == "__main__":
    unittest.main()
