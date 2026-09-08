#!/usr/bin/env python3
"""Install a downloaded Google web client into a protected environment file.

Never prints credentials. Backups and output are mode 0600. Existing invite,
operator and unrelated settings are preserved. Run locally or on the server.
"""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import UTC, datetime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("credential_file", type=Path)
    parser.add_argument("environment_file", type=Path)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    allowed = {"https://alphapoker.io", "http://localhost:3001"}
    if args.origin not in allowed:
        raise SystemExit("Unexpected site origin")
    args.credential_file.chmod(0o600)
    client = json.loads(args.credential_file.read_text())["web"]
    callback = args.origin + "/browser-api/auth/google/callback"
    if client.get("project_id") != "alpha-poker-508019" or callback not in client.get("redirect_uris", []):
        raise SystemExit("Wrong Google project or missing authorized callback")
    values = {"ALPHA_POKER_GOOGLE_CLIENT_ID": client["client_id"],
              "ALPHA_POKER_GOOGLE_CLIENT_SECRET": client["client_secret"],
              "ALPHA_POKER_GOOGLE_REDIRECT_URI": callback,
              "ALPHA_POKER_PUBLIC_WEB_URL": args.origin}
    if not all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_./:\-]+", v) for v in values.values()):
        raise SystemExit("Unexpected credential format")
    path = args.environment_file
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text() if path.exists() else ""
    if previous:
        backup = path.with_name(path.name + ".before-google-" + datetime.now(UTC).strftime("%Y%m%d%H%M%S"))
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(previous)
    retained = [line for line in previous.splitlines() if line.split("=", 1)[0] not in values]
    contents = "\n".join(retained + [f"{key}={value}" for key, value in values.items()]) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".google-env-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(contents)
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("Google configuration installed; credentials suppressed; unrelated settings preserved.")


if __name__ == "__main__":
    main()
