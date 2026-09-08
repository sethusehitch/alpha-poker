import contextlib
import io
import json
import socket
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
import zipfile

from alpha_poker_cli import local_recap as local
from alpha_poker_cli import main as cli


def record(number=1, names=None, match="m1"):
    return {"hand_id": f"{match}-{number}", "hand_number": number, "match_id": match,
            "players": names or ["alice", "bob"], "starting_stacks": [100, 100], "final_stacks": [110, 90],
            "profits": [10, -10], "pot": 20, "hole_cards": [["As", "Kd"], ["2c", "3d"]],
            "events": [{"type": "result", "reason": "fold", "winners": [0]}]}


class LocalRecapTests(unittest.TestCase):
    def test_idle_browser_connection_does_not_block_requests(self):
        server, url = local.make_server(local.Evidence(self.archive()))
        accepted = threading.Event()
        original = server.get_request
        def get_request():
            connection = original()
            accepted.set()
            return connection
        server.get_request = get_request
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        idle = socket.create_connection(server.server_address)
        try:
            self.assertTrue(accepted.wait(2))
            with urlopen(url + "manifest.json", timeout=2) as response:
                self.assertEqual(response.status, 200)
        finally:
            idle.close()
            server.shutdown()
            server.server_close()
            worker.join(3)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, records=None, summary=None):
        path = self.root / "training.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("hands.jsonl", "\n".join(json.dumps(r) for r in (records if records is not None else [record()])))
            archive.writestr("summary.json", json.dumps(summary or {"username": "alice", "hands_played": 1}))
        return path

    def test_training_evidence_and_shared_viewer_payload(self):
        evidence = local.Evidence(self.archive())
        value = evidence.recap("0")
        self.assertEqual(value["schema_version"], "recap-v1")
        hand = value["highlights"][0]
        self.assertTrue(hand["players"][0]["is_viewer"])
        self.assertEqual(hand["steps"][0]["hole_cards"], [["As", "Kd"], ["2c", "3d"]])
        self.assertEqual(evidence.recap("0", "0")["highlights"][0]["label"], "Selected hand")

    def test_matches_and_games_do_not_mix(self):
        records = [record(1), record(2), record(1, ["alice", "carol"], "m2")]
        records[0]["game_number"] = 2
        records[1]["game_number"] = 1
        evidence = local.Evidence(self.archive(records, {"hands_played": 3}))
        self.assertEqual(len(evidence.groups), 2)
        self.assertEqual([h["game"] for h in evidence.groups[0]["hands"]], [1, 2])
        self.assertEqual(len(evidence.recap("0")["highlights"]), 2)
        self.assertEqual(evidence.recap("1")["players"], ["alice", "carol"])
        with self.assertRaises(local.RecapError):
            evidence.recap("0", "2")

    def test_partial_and_incomplete_evidence_is_explicit(self):
        incomplete = record(2)
        incomplete["events"] = []
        evidence = local.Evidence(self.archive([record(), incomplete], {"hands_played": 2}))
        self.assertFalse(evidence.complete)
        self.assertTrue(any("Skipped 1" in w for w in evidence.warnings))
        self.assertNotIn("Opening momentum", [h["label"] for h in evidence.recap("0")["highlights"]])

    def test_rejects_empty_duplicate_and_unsupported(self):
        for records in ([], [record(), record()], [{"unexpected": True}]):
            with self.assertRaises(local.RecapError):
                local.Evidence(self.archive(records))
        with self.assertRaises(local.RecapError):
            local.Evidence(self.root / "missing.zip")
        bad = self.root / "bot.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr("bot.py", "raise RuntimeError('must not execute')")
        with self.assertRaisesRegex(local.RecapError, "not replay logs"):
            local.Evidence(bad)

    def test_archive_limit_and_no_path_extraction(self):
        path = self.archive()
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("../escape.txt", "ignored")
        local.Evidence(path)
        self.assertFalse((self.root.parent / "escape.txt").exists())
        with patch.object(local, "MAX_BYTES", 10), self.assertRaises(local.RecapError):
            local.Evidence(path)

    def test_saved_recap_json(self):
        value = local.Evidence(self.archive()).recap("0")
        path = self.root / "recap.json"
        path.write_text(json.dumps(value))
        evidence = local.Evidence(path)
        self.assertEqual(len(evidence.recap("0", "0")["highlights"]), 1)
        self.assertIn("selected highlights only", evidence.warnings[0])

    def test_latest_is_explicit_and_private(self):
        with patch.dict(local.os.environ, {"ALPHA_POKER_RECAP_STATE": str(self.root / "state.json")}):
            with self.assertRaises(local.RecapError):
                local.latest()
            path = self.archive()
            local.remember(path)
            self.assertEqual(local.latest(), path.resolve())
            self.assertEqual(local.state_path().stat().st_mode & 0o777, 0o600)
            path.unlink()
            with self.assertRaises(local.RecapError):
                local.latest()

    def test_loopback_server_only_exposes_allowed_evidence_and_assets(self):
        server, url = local.make_server(local.Evidence(self.archive()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.assertEqual(server.server_address[0], "127.0.0.1")
        for suffix in ("", "manifest.json", "recap/0", "recap/0/0"):
            with urlopen(url + suffix) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertIn("connect-src 'self'", response.headers["Content-Security-Policy"])
        for request in (url + "../../pyproject.toml", url + "recap/2", url.split(urlsplit_path(url))[0] + "/manifest.json",
                        Request(url + "manifest.json", headers={"Origin": "https://evil.test"}),
                        Request(url + "manifest.json", headers={"Host": "evil.test"})):
            with self.assertRaises(HTTPError) as caught:
                urlopen(request)
            caught.exception.close()

    def test_cli_recap_needs_no_identity_or_network(self):
        with patch.object(local, "launch") as launch, patch.object(cli, "_identity", side_effect=AssertionError("no login")):
            self.assertEqual(cli.main(["recap", "run.zip", "--open"]), 0)
            launch.assert_called_once_with(Path("run.zip"), True)
        for args in (["recap"], ["recap", "a.zip", "--latest"]):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(args), 1)

    def test_train_recap_opens_saved_output_and_tracks_latest(self):
        path = self.archive()
        with patch.object(cli, "_identity", return_value=("alice", None)), patch.object(cli, "run_training", return_value=path), patch.object(local, "remember") as remember, patch.object(local, "launch") as launch, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["train", str(self.root), "--recap"]), 0)
            remember.assert_called_once_with(path)
            launch.assert_called_once_with(path, True)

    def test_malformed_saved_json_fails_before_browser(self):
        path = self.root / "bad.json"
        path.write_text(json.dumps({"schema_version": "recap-v1", "highlights": [{"players": [{}, {}], "steps": [{}]}]}))
        with self.assertRaises(local.RecapError):
            local.Evidence(path)


def urlsplit_path(url):
    from urllib.parse import urlsplit
    return urlsplit(url).path
