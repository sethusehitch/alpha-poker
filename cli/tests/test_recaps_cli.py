import contextlib
import io
import json
import unittest
from unittest.mock import call, patch

from alpha_poker_cli import main as cli


class RecapsCliTests(unittest.TestCase):
    def run_command(self, args, response):
        output = io.StringIO()
        with patch.object(cli, "_identity", return_value=("alice", "secret-session")), patch.object(cli, "_http_json", return_value=response) as request, patch.object(cli.webbrowser, "open", return_value=True) as browser, contextlib.redirect_stdout(output):
            code = cli.main(args + ["--api-url", "https://api.league.test/v1"])
        return code, output.getvalue(), request.call_args, browser.call_args

    def test_direct_recap_prints_or_opens_same_site_component_without_token(self):
        response = {"challenge": {"winner_username": "alice", "margin_play_chips": 30}}
        code, output, request, browser = self.run_command(["rivals", "recap", "ch_123", "--site-url", "http://localhost:3012", "--url", "--open"], response)
        self.assertEqual(code, 0)
        self.assertEqual(output, "http://localhost:3012/recaps/challenges/ch_123\n")
        self.assertEqual(browser, call(output.strip()))
        self.assertEqual(request, call("GET", "https://api.league.test/v1/challenges/ch_123/recap", token="secret-session"))
        self.assertNotIn("secret-session", output)

    def test_direct_json_includes_url_without_changing_evidence(self):
        code, output, _, browser = self.run_command(["rivals", "recap", "ch_1", "--json", "--site-url", "https://league.test"], {"highlights": [{"hand_id": "h1"}]})
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["playback_url"], "https://league.test/recaps/challenges/ch_1")
        self.assertEqual(json.loads(output)["highlights"], [{"hand_id": "h1"}])
        self.assertIsNone(browser)

    def test_pairing_discovery_and_exact_run_match_route(self):
        response = {"run_id": "run_1", "matchups": [{"matchup_id": "mat_7", "player_a": "alice", "player_b": "bob", "hands": 200}]}
        code, output, request, _ = self.run_command(["matches", "list", "--run", "run_1"], response)
        self.assertEqual(code, 0)
        self.assertIn("mat_7  alice vs bob  200 hands", output)
        self.assertEqual(request.args[1], "https://api.league.test/v1/runs/run_1/matchups")
        code, output, request, _ = self.run_command(["matches", "recap", "run_1", "mat_7", "--url", "--site-url", "https://league.test"], {"players": ["alice", "bob"], "highlights": []})
        self.assertEqual(output, "https://league.test/recaps/runs/run_1/matches/mat_7\n")
        self.assertEqual(request.args[1], "https://api.league.test/v1/runs/run_1/matchups/mat_7/recap")

    def test_invalid_origins_and_browser_failure_are_clear(self):
        for site in ("javascript:alert(1)", "https://user:password@example.com", "https://example.com/?token=secret", "https://example.com/path"):
            with self.assertRaises(cli.CliError):
                cli._replay_url("http://localhost:8000/v1", site, "/recaps/challenges/ch_1")
        with patch.object(cli.webbrowser, "open", return_value=False), self.assertRaisesRegex(cli.CliError, "open this URL manually"):
            cli._open_recap("http://localhost:3002/recaps/challenges/ch_1")

    def test_local_and_environment_origin_defaults(self):
        with patch.dict(cli.os.environ, {}, clear=True):
            self.assertEqual(cli._replay_url("http://localhost:8000/v1", None, "/recaps/challenges/ch_1"), "http://localhost:3002/recaps/challenges/ch_1")
        with patch.dict(cli.os.environ, {"ALPHA_POKER_SITE_URL": "https://league.test"}):
            self.assertEqual(cli._replay_url("https://api.test/v1", None, "/recaps/challenges/ch_1"), "https://league.test/recaps/challenges/ch_1")

    def test_not_ready_does_not_launch_a_browser(self):
        with patch.object(cli, "_identity", return_value=("alice", "secret")), patch.object(cli, "_http_json", side_effect=cli.CliError("Challenge recap is not ready")), patch.object(cli.webbrowser, "open") as browser, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["rivals", "recap", "ch_1", "--open"]), 1)
            browser.assert_not_called()
