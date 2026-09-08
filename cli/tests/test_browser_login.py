import contextlib
import io
import unittest
from unittest.mock import patch

from alpha_poker_cli.main import _browser_login, main, CliError


class BrowserLoginTests(unittest.TestCase):
    def test_browser_login_polls_and_saves_without_password_or_token_output(self):
        output = io.StringIO()
        responses = [
            {"device_code": "private-device-token", "user_code": "AB12-CD34", "verification_uri": "https://alphapoker.io/authorize-cli"},
            {"pending": True}, {"username": "player", "token": "private-session-token"},
        ]
        with patch("alpha_poker_cli.main._http_json", side_effect=responses), patch("alpha_poker_cli.main._remember_profile") as save, patch("alpha_poker_cli.main.time.sleep"), patch("alpha_poker_cli.main._prompt_password") as password, contextlib.redirect_stdout(output):
            assert main(["login", "--browser", "--no-open", "--api-url", "https://alphapoker.io/v1"]) == 0
            password.assert_not_called()
            save.assert_called_once_with("https://alphapoker.io/v1", "player", "private-session-token")
        assert "AB12-CD34" in output.getvalue()
        assert "private-" not in output.getvalue()

    def test_unsafe_remote_http_is_rejected(self):
        with self.assertRaises(CliError):
            _browser_login("http://example.org/v1")

    def test_timeout_does_not_save_credentials(self):
        flow = {"device_code": "private-device-token", "user_code": "AB12-CD34", "verification_uri": "https://alphapoker.io/authorize-cli"}
        with patch("alpha_poker_cli.main._http_json", return_value=flow), patch("alpha_poker_cli.main.time.monotonic", side_effect=[0, 601]), patch("alpha_poker_cli.main._remember_profile") as save, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(CliError, "timed out"):
                _browser_login("https://alphapoker.io/v1", True)
            save.assert_not_called()
