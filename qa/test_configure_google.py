"""Credential installer checks using synthetic credentials only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "ops/configure-google.py"


class ConfigureGoogleTests(unittest.TestCase):
    def test_preserves_settings_and_protects_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            credential = root / "client.json"
            env = root / ".env"
            credential.write_text(json.dumps({"web": {
                "project_id": "alpha-poker-508019",
                "client_id": "synthetic.apps.googleusercontent.com",
                "client_secret": "synthetic-private-value",
                "redirect_uris": ["http://localhost:3001/browser-api/auth/google/callback"],
            }}))
            previous = "INVITE=preserve-me\n# Keep comments\nALPHA_POKER_GOOGLE_CLIENT_ID=old\n"
            env.write_text(previous)
            result = subprocess.run([sys.executable, str(SCRIPT), str(credential),
                                     str(env), "--origin", "http://localhost:3001"],
                                    capture_output=True, text=True, check=True)
            self.assertNotIn("synthetic-private-value", result.stdout + result.stderr)
            self.assertIn("INVITE=preserve-me\n# Keep comments\n", env.read_text())
            self.assertEqual(env.read_text().count("ALPHA_POKER_GOOGLE_CLIENT_ID="), 1)
            backups = list(root.glob(".env.before-google-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), previous)
            for path in (credential, env, backups[0]):
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_wrong_project_leaves_environment_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            credential = root / "client.json"
            env = root / ".env"
            credential.write_text(json.dumps({"web": {"project_id": "wrong"}}))
            env.write_text("INVITE=preserve-me\n")
            result = subprocess.run([sys.executable, str(SCRIPT), str(credential),
                                     str(env), "--origin", "https://alphapoker.io"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(env.read_text(), "INVITE=preserve-me\n")
            self.assertEqual(list(root.glob(".env.before-google-*")), [])


if __name__ == "__main__":
    unittest.main()
