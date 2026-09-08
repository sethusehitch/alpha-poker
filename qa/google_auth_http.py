"""Isolated HTTP integration of built web routes with a fake Google exchange.

Builds an isolated localhost web bundle. No production accounts or credentials are used.
Only the Google provider exchange is stubbed; cookies/API/database are real.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import requests
import uvicorn

from alpha_poker_api.config import Settings
from alpha_poker_api.main import create_app


def main():
    root = Path(__file__).resolve().parents[1]
    origin = "http://localhost:3026"
    env = {**os.environ, "ALPHA_POKER_API_URL": "http://127.0.0.1:8026/v1"}
    subprocess.run(["npm", "run", "build"], cwd=root, env=env, check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory(prefix="alpha-google-http-") as directory:
        data = Path(directory)
        settings = Settings(data, data / "db.sqlite", data / "uploads", data / "artifacts", seed_demo_data=False,
            auth_required=True, invite_code="fixture-invite", google_client_id="fixture-client", google_client_secret="fixture-secret",
            google_redirect_uri=origin + "/browser-api/auth/google/callback", public_web_url=origin)
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=8026, log_level="error", access_log=False))
        with patch("alpha_poker_api.google_login.exchange_identity", return_value="fixture-subject"):
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            with tempfile.TemporaryFile() as log:
                web = subprocess.Popen([str(root / "node_modules/.bin/vinext"), "start", "--port", "3026"], cwd=root,
                    env=env, stdout=log, stderr=log)
                try:
                    for _ in range(100):
                        try:
                            readiness = requests.get(origin + "/browser-api/auth/options", timeout=1)
                            if readiness.json().get("google_enabled"):
                                break
                        except (requests.RequestException, ValueError):
                            pass
                        time.sleep(.1)
                    else:
                        log.seek(0)
                        print(log.read().decode()[-2000:])
                        print("Readiness:", readiness.status_code, readiness.text[:300])
                        raise AssertionError("test web/API did not become ready")
                    browser = requests.Session()
                    headers = {"Origin": origin}
                    start_url = origin + "/browser-api/auth/google/start"
                    # Model Caddy's TLS termination: HTTP to Vinext, public Host,
                    # but the browser's Origin is HTTPS. No user session here.
                    public_headers = {"Host": "alphapoker.io", "Origin": "https://alphapoker.io"}
                    assert requests.post(start_url, json={"link": True}, headers=public_headers).status_code == 401
                    assert requests.post(start_url, json={"link": True}, headers={**public_headers, "Origin": "http://alphapoker.io"}).status_code == 403
                    public_failure = requests.get(origin + "/browser-api/auth/google/callback", headers={"Host": "alphapoker.io"}, allow_redirects=False)
                    assert public_failure.headers["Location"].startswith("https://alphapoker.io/")
                    assert "Secure" in public_failure.headers["Set-Cookie"]
                    assert browser.post(start_url, json={}, headers={"Origin": "https://evil.invalid"}).status_code == 403
                    start = browser.post(start_url, json={"next": "cli"}, headers=headers)
                    assert start.status_code == 200
                    assert "state" not in start.json()
                    assert "HttpOnly" in start.headers["Set-Cookie"]
                    state = parse_qs(urlparse(start.json()["url"]).query)["state"][0]
                    callback = origin + "/browser-api/auth/google/callback"
                    assert requests.get(callback, params={"state": state, "code": "fixture"}, allow_redirects=False).headers["Location"].endswith("login_error=google")
                    response = browser.get(callback, params={"state": state, "code": "fixture"}, allow_redirects=False)
                    assert response.status_code == 303
                    assert response.headers["Location"].endswith("/join?next=cli")
                    assert browser.get(origin + "/browser-api/auth/google/pending").json()["pending"]
                    assert browser.post(origin + "/browser-api/auth/google/invite", headers=headers, json={"invite_code": "wrong"}).status_code == 403
                    assert browser.post(origin + "/browser-api/auth/google/invite", headers=headers, json={"invite_code": "fixture-invite"}).status_code == 200
                    result = browser.post(origin + "/browser-api/auth/google/complete", headers=headers, json={"username": "fixture-player", "invite_code": "fixture-invite", "preset": "bird"})
                    assert result.status_code == 201, result.status_code
                    assert "token" not in result.json()
                    assert "HttpOnly" in result.headers["Set-Cookie"]
                    assert browser.get(origin + "/browser-api/auth/me").json()["username"] == "fixture-player"
                    assert browser.get(origin + "/browser-api/auth/google/pending").status_code in {401, 422}
                    flow = requests.post("http://127.0.0.1:8026/v1/auth/browser/start").json()
                    assert browser.post(origin + "/browser-api/auth/browser/approve", headers=headers, json={"user_code": flow["user_code"]}).status_code == 200
                    poll = requests.post("http://127.0.0.1:8026/v1/auth/browser/poll", json={"device_code": flow["device_code"]})
                    assert poll.json()["username"] == "fixture-player"
                    assert requests.post("http://127.0.0.1:8026/v1/auth/browser/poll", json={"device_code": flow["device_code"]}).status_code == 410
                    browser.post(origin + "/browser-api/auth/logout")
                    start = browser.post(start_url, headers=headers, json={"returnTo": "/#leaderboard"})
                    state = parse_qs(urlparse(start.json()["url"]).query)["state"][0]
                    returning = browser.get(callback, params={"state": state, "code": "fixture"}, allow_redirects=False)
                    assert returning.headers["Location"].endswith("/#leaderboard")
                    assert browser.get(origin + "/browser-api/auth/me").json()["username"] == "fixture-player"
                    print("PASS: real web/API cookies, CSRF rejection, invite signup, returning login, CLI approval; Google provider exchange mocked.")
                finally:
                    web.terminate()
                    try:
                        web.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        web.kill()
                        web.wait()
                    server.should_exit = True
                    thread.join(timeout=10)


if __name__ == "__main__":
    main()
