from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch
from urllib.error import HTTPError

from alpha_poker_cli import main as cli


API = "https://league.test/v1"


class RivalsCliTests(unittest.TestCase):
    def authenticated(self):
        return patch.object(cli, "_identity", return_value=("maya", "session-secret"))

    def test_list_encodes_filters_and_emits_stable_json_object(self):
        response = {"rivals": [{"username": "theo", "bot_name": "Pocket Rocket", "elo": 1589}]}
        output = io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", return_value=response) as request, contextlib.redirect_stdout(output):
            code = cli.main([
                "rivals", "list", "--source", "leaderboard", "--search", "Pocket Rocket",
                "--api-url", API, "--json",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
        self.assertEqual(
            request.call_args,
            call("GET", f"{API}/rivals?source=leaderboard&q=Pocket+Rocket", token="session-secret"),
        )
        self.assertNotIn("session-secret", output.getvalue())

    def test_show_has_short_human_summary(self):
        output = io.StringIO()
        response = {
            "username": "theo", "bot_name": "PocketRocket", "elo_rating": 1589,
            "record": {"wins": 4, "losses": 5}, "is_nemesis": True,
            "current_challenge": {"challenge_id": "ch_pending", "status": "pending"},
        }
        with self.authenticated(), patch.object(cli, "_http_json", return_value=response), contextlib.redirect_stdout(output):
            code = cli.main(["rivals", "show", "theo", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertIn("theo — PocketRocket", output.getvalue())
        self.assertIn("1,589", output.getvalue())
        self.assertIn("4-5", output.getvalue())
        self.assertIn("Nemesis", output.getvalue())
        self.assertIn("Current challenge: pending (ch_pending)", output.getvalue())

    def test_show_agent_format_emits_stable_key_value_facts(self):
        output = io.StringIO()
        response = {
            "rival": {"username": "theo", "bot_name": "PocketRocket", "elo_rating": 1589},
            "direct_record": {"wins": 4, "losses": 5, "draws": 0},
            "is_nemesis": True,
            "current_challenge": {"challenge_id": "ch_pending", "status": "pending"},
        }
        with self.authenticated(), patch.object(cli, "_http_json", return_value=response), contextlib.redirect_stdout(output):
            code = cli.main(["rivals", "show", "theo", "--format", "agent", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertEqual(
            output.getvalue().splitlines(),
            [
                "username=theo", "bot_name=PocketRocket", "elo=1589", "direct_record=4-5",
                "is_nemesis=true", "current_challenge_id=ch_pending", "current_challenge_status=pending",
            ],
        )

    def test_challenge_reviews_fixed_format_and_sends_idempotency_key(self):
        responses = [
            {"username": "theo", "bot_name": "PocketRocket", "your_bot_name": "RiverRat"},
            {"submission": {"bot_name": "RiverRat"}},
            {"id": "ch_123", "status": "pending"},
        ]
        output = io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", side_effect=responses) as request, contextlib.redirect_stdout(output):
            code = cli.main(["rivals", "challenge", "theo", "--yes", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertIn("best-of-five Pot-Limit Hold'em challenge", output.getvalue())
        self.assertIn("Challenge sent: ch_123", output.getvalue())
        mutation = request.call_args_list[2]
        self.assertEqual(mutation.args[:4], ("POST", f"{API}/challenges", {"opponent_username": "theo"}, "session-secret"))
        self.assertRegex(mutation.args[4]["Idempotency-Key"], r"^cli-challenge-")
        self.assertNotIn("session-secret", output.getvalue())

    def test_mutation_without_yes_fails_closed_when_noninteractive(self):
        output, error = io.StringIO(), io.StringIO()
        challenge = {
            "id": "ch_123", "challenger_username": "theo", "challenged_username": "maya",
            "hand_count": 200,
        }
        with self.authenticated(), patch.object(cli, "_http_json", return_value=challenge) as request, patch.object(
            cli.sys.stdin, "isatty", return_value=False
        ), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = cli.main(["rivals", "accept", "ch_123", "--api-url", API])
        self.assertEqual(code, 1)
        self.assertEqual(request.call_count, 1)
        self.assertIn("re-run with --yes", error.getvalue())

    def test_accept_fetches_preview_then_uses_idempotency_key(self):
        challenge = {
            "id": "ch_123", "challenger_username": "theo", "challenged_username": "maya",
            "bot_names": {"challenger": "PocketRocket", "challenged": "RiverRat"}, "hand_count": 200,
        }
        accepted = {**challenge, "status": "queued"}
        output, error = io.StringIO(), io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", side_effect=[challenge, accepted]) as request, contextlib.redirect_stdout(
            output
        ), contextlib.redirect_stderr(error):
            code = cli.main(["rivals", "accept", "ch_123", "--yes", "--api-url", API, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "queued")
        self.assertIn("best-of-five Pot-Limit Hold'em challenge", error.getvalue())
        mutation = request.call_args_list[1]
        self.assertEqual(mutation.args[1], f"{API}/challenges/ch_123/accept")
        self.assertRegex(mutation.args[4]["Idempotency-Key"], r"^cli-accept-")

    def test_status_wait_polls_until_terminal_and_progress_goes_to_stderr(self):
        responses = [
            {"id": "ch_123", "status": "queued"},
            {"id": "ch_123", "status": "running"},
            {
                "id": "ch_123", "status": "completed",
                "challenger_username": "maya", "challenged_username": "theo",
                "winner_username": "maya", "series_score": {"maya": 3, "theo": 1},
            },
        ]
        output, error = io.StringIO(), io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", side_effect=responses) as request, patch.object(
            cli.time, "sleep"
        ), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = cli.main(["rivals", "status", "ch_123", "--wait", "--timeout", "10", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertEqual(request.call_count, 3)
        self.assertIn("queued", error.getvalue())
        self.assertIn("running", error.getvalue())
        self.assertIn("you won", output.getvalue())

    def test_status_wait_json_is_exactly_one_stdout_object(self):
        response = {"id": "ch_123", "status": "completed", "winner_username": "maya"}
        output, error = io.StringIO(), io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", return_value=response), contextlib.redirect_stdout(
            output
        ), contextlib.redirect_stderr(error):
            code = cli.main(["rivals", "status", "ch_123", "--wait", "--json", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(json.loads(output.getvalue()), response)
        self.assertEqual(error.getvalue(), "")

    def test_status_wait_requires_an_id(self):
        error = io.StringIO()
        with self.authenticated(), contextlib.redirect_stderr(error):
            code = cli.main(["rivals", "status", "--wait", "--api-url", API])
        self.assertEqual(code, 1)
        self.assertIn("requires a CHALLENGE_ID", error.getvalue())

    def test_status_wait_timeout_exits_cleanly_and_says_how_to_check_later(self):
        response = {
            "challenge_id": "ch_123", "status": "running", "current_game": 2,
            "series_score": {"maya": 1, "theo": 0}, "hands_played": 73,
            "challenger_username": "maya", "challenged_username": "theo",
        }
        output = io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", return_value=response), patch.object(
            cli.time, "monotonic", side_effect=[0, 2]
        ), contextlib.redirect_stdout(output):
            code = cli.main(["rivals", "status", "ch_123", "--wait", "--timeout", "1", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertIn("Alpha Poker will keep working", output.getvalue())
        self.assertIn("rivals status ch_123 --wait", output.getvalue())

    def test_status_wait_timeout_names_pending_state(self):
        response = {
            "challenge_id": "ch_123", "status": "pending",
            "challenger_username": "maya", "challenged_username": "theo",
        }
        output = io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", return_value=response), patch.object(
            cli.time, "monotonic", side_effect=[0, 2]
        ), contextlib.redirect_stdout(output):
            code = cli.main(["rivals", "status", "ch_123", "--wait", "--timeout", "1", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertIn("Still pending after 1 seconds", output.getvalue())
        self.assertIn("waiting for the other player", output.getvalue())
        self.assertNotIn("Still running", output.getvalue())

    def test_agent_format_emits_compact_stable_facts(self):
        response = {
            "challenge_id": "ch_123", "status": "completed", "format": "best_of_five_plhe",
            "challenger_username": "maya", "challenged_username": "theo",
            "series_score": {"maya": 3, "theo": 1}, "games_completed": 4,
            "hands_played": 214, "winner_username": "maya", "artifacts_url": "/artifacts",
        }
        output = io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", return_value=response), contextlib.redirect_stdout(output):
            code = cli.main(["rivals", "status", "ch_123", "--format", "agent", "--api-url", API])
        self.assertEqual(code, 0)
        assert "status=completed" in output.getvalue()
        assert "score=3-1" in output.getvalue()
        assert "score_order=winner-loser" in output.getvalue()
        assert "viewer_result=win" in output.getvalue()
        assert "hands_played=214" in output.getvalue()

    def test_agent_completed_score_is_winner_first_for_loser(self):
        response = {
            "challenge_id": "ch_123", "status": "completed", "format": "best_of_five_plhe",
            "challenger_username": "maya", "challenged_username": "theo",
            "series_score": {"maya": 3, "theo": 0}, "games_completed": 3,
            "hands_played": 180, "winner_username": "maya",
        }
        output = io.StringIO()
        with patch.object(cli, "_identity", return_value=("theo", "session-secret")), patch.object(
            cli, "_http_json", return_value=response
        ), contextlib.redirect_stdout(output):
            code = cli.main(["rivals", "status", "ch_123", "--format", "agent", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertIn("score=3-0", output.getvalue())
        self.assertIn("score_order=winner-loser", output.getvalue())
        self.assertIn("viewer_result=loss", output.getvalue())

    def test_human_completed_status_uses_winner_and_loser_score_for_recipient(self):
        response = {
            "challenge_id": "ch_123", "status": "completed", "format": "best_of_five_plhe",
            "challenger_username": "maya", "challenged_username": "theo",
            "series_score": {"maya": 3, "theo": 0}, "games_completed": 3,
            "hands_played": 275, "winner_username": "maya",
        }
        output = io.StringIO()
        with patch.object(cli, "_identity", return_value=("theo", "session-secret")), patch.object(
            cli, "_http_json", return_value=response
        ), contextlib.redirect_stdout(output):
            code = cli.main(["rivals", "status", "ch_123", "--format", "human", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertIn("you lost; maya won 3-0", output.getvalue())
        self.assertNotIn("3-3", output.getvalue())

    def test_recap_downloads_artifact_without_printing_token(self):
        response = {
            "challenge_id": "ch_123", "winner_username": "maya", "margin_play_chips": 840,
            "artifacts_url": "/v1/challenges/ch_123/artifacts",
        }
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            output = io.StringIO()
            with self.authenticated(), patch.object(cli, "_http_json", return_value=response), patch.object(
                cli, "_download", side_effect=lambda _url, path, _token: path
            ) as download, contextlib.redirect_stdout(output):
                code = cli.main([
                    "rivals", "recap", "ch_123", "--output", str(destination), "--api-url", API,
                ])
            self.assertEqual(code, 0)
            self.assertEqual(download.call_args.args[0], f"{API}/challenges/ch_123/artifacts")
            self.assertEqual(download.call_args.args[2], "session-secret")
            self.assertNotIn("session-secret", output.getvalue())
            self.assertIn("alpha-poker-rival-ch_123.zip", output.getvalue())

    def test_human_recap_names_viewer_loss_and_winner_first_score(self):
        response = {
            "challenge": {
                "challenge_id": "ch_123", "challenger_username": "maya",
                "challenged_username": "theo", "winner_username": "maya",
                "series_score": {"maya": 3, "theo": 1},
            },
            "summary": {"result_text": "RiverRat defeated PocketRocket 3-1."},
        }
        output = io.StringIO()
        with patch.object(cli, "_identity", return_value=("theo", "session-secret")), patch.object(
            cli, "_http_json", return_value=response
        ), contextlib.redirect_stdout(output):
            code = cli.main(["rivals", "recap", "ch_123", "--format", "human", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertIn("You lost; maya won 3-1.", output.getvalue())

    def test_notifications_list_and_read(self):
        listing = {
            "notifications": [{
                "id": "nt_1", "type": "challenge_won", "message": "You beat Theo by 840 play chips.", "read_at": None,
            }]
        }
        output = io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", return_value=listing) as request, contextlib.redirect_stdout(output):
            code = cli.main(["notifications", "list", "--unread", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertIn("You beat Theo", output.getvalue())
        self.assertEqual(request.call_args.args[1], f"{API}/notifications?unread=true")

        output = io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", return_value={"id": "nt_1", "read_at": "now"}) as request, contextlib.redirect_stdout(output):
            code = cli.main(["notifications", "read", "nt_1", "--api-url", API, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(request.call_args.args[:4], ("POST", f"{API}/notifications/nt_1/read", {}, "session-secret"))
        self.assertEqual(json.loads(output.getvalue())["id"], "nt_1")

    def test_notification_messages_are_derived_from_snapshot_payload(self):
        response = {
            "items": [{
                "notification_id": "nt_2",
                "type": "challenge_lost",
                "payload": {
                    "opponent_username": "theo",
                    "series_score": {"maya": 1, "theo": 3},
                },
                "read_at": None,
            }],
            "unread_count": 1,
        }
        output = io.StringIO()
        with self.authenticated(), patch.object(cli, "_http_json", return_value=response), contextlib.redirect_stdout(output):
            code = cli.main(["notifications", "list", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertIn("theo beat you 3-1", output.getvalue())

    def test_draw_notification_has_plain_language_copy(self):
        response = {
            "items": [{
                "notification_id": "nt_draw",
                "type": "challenge_drawn",
                "payload": {"opponent_username": "maya", "margin_play_chips": 0},
                "read_at": None,
            }],
            "unread_count": 1,
        }
        output = io.StringIO()
        with self.authenticated(), patch.object(
            cli, "_http_json", return_value=response
        ), contextlib.redirect_stdout(output):
            code = cli.main(["notifications", "list", "--api-url", API])
        self.assertEqual(code, 0)
        self.assertIn("challenge with maya ended in a draw", output.getvalue())

    def test_completed_recap_contract_names_download_for_challenge(self):
        response = {
            "challenge": {"challenge_id": "ch_nested", "winner_username": "maya", "margin_play_chips": 42},
            "matchup": {"id": "match_1"},
            "best_hands": [],
            "artifacts_url": "/v1/runs/run_1/artifacts",
        }
        with tempfile.TemporaryDirectory() as directory, patch.object(
            cli, "_download", side_effect=lambda _url, path, _token: path
        ):
            saved = cli._write_recap(response, Path(directory), API, "session-secret")
        self.assertEqual(saved.name, "alpha-poker-rival-ch_nested.zip")

    def test_every_network_rivals_leaf_accepts_json_and_api_url(self):
        parser = cli._parser()
        examples = [
            ["rivals", "list"], ["rivals", "show", "theo"], ["rivals", "history", "theo"],
            ["rivals", "requests"], ["rivals", "challenge", "theo", "--yes"],
            ["rivals", "accept", "ch_1", "--yes"], ["rivals", "decline", "ch_1", "--yes"],
            ["rivals", "cancel", "ch_1", "--yes"], ["rivals", "status", "ch_1"],
            ["rivals", "recap", "ch_1"], ["notifications", "list"], ["notifications", "read", "nt_1"],
        ]
        for command in examples:
            with self.subTest(command=command):
                parsed = parser.parse_args([*command, "--api-url", API, "--json"])
                self.assertEqual(parsed.api_url, API)
                self.assertTrue(parsed.json)

    def test_http_errors_redact_the_session_token(self):
        response_body = io.BytesIO(b'{"detail":"session-secret must never appear"}')
        failure = HTTPError(f"{API}/rivals", 400, "bad request", {}, response_body)
        self.addCleanup(failure.close)
        with patch.object(cli, "urlopen", side_effect=failure):
            with self.assertRaises(cli.CliError) as caught:
                cli._http_json("GET", f"{API}/rivals", token="session-secret")
        self.assertNotIn("session-secret", str(caught.exception))
        self.assertIn("[redacted]", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
