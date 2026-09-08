import io
import json
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from alpha_poker_api.config import Settings
from alpha_poker_api.main import create_app
from alpha_poker_api import google_login


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(tmp_path, tmp_path / "test.db", tmp_path / "uploads", tmp_path / "artifacts",
        seed_demo_data=False, auth_required=True, invite_code="test-invite",
        operator_usernames=frozenset({"admin"}), google_client_id="test-client",
        google_client_secret="test-secret", google_redirect_uri="http://localhost:3001/browser-api/auth/google/callback")
    monkeypatch.setattr(google_login, "exchange_identity", lambda settings, code, verifier, nonce: code)
    with TestClient(create_app(settings)) as c:
        yield c


def google(client, subject="google-subject", headers=None, link=False):
    start = client.post("/v1/auth/google/start", json={"link": link}, headers=headers or {})
    assert start.status_code == 200
    query = parse_qs(urlparse(start.json()["url"]).query)
    assert query["scope"] == ["openid"]
    assert query["code_challenge_method"] == ["S256"]
    assert "test-secret" not in start.text
    state = start.json()["state"]
    result = client.post("/v1/auth/google/callback", json={"state": state, "code": subject})
    return result, state


def signup(client, subject="google-subject", username="new-player"):
    result, _ = google(client, subject)
    assert result.json()["signup_required"]
    ticket = result.json()["ticket"]
    return client.post("/v1/auth/google/complete", json={"ticket": ticket, "username": username, "invite_code": "test-invite", "preset": "bear"}), ticket


def test_invite_gate_retry_reserved_name_and_signup(client):
    pending, state = google(client)
    ticket = pending.json()["ticket"]
    assert client.post("/v1/auth/google/callback", json={"state": state, "code": "google-subject"}).status_code == 401
    assert client.post("/v1/auth/google/pending", json={"ticket": ticket}).json()["invite_required"]
    payload = {"ticket": ticket, "username": "new-player"}
    assert client.post("/v1/auth/google/complete", json=payload).status_code == 403
    assert client.post("/v1/auth/google/invite", json={"ticket": ticket, "invite_code": "bad"}).status_code == 403
    assert client.post("/v1/auth/google/invite", json={"ticket": ticket, "invite_code": "test-invite"}).status_code == 200
    payload["invite_code"] = "test-invite"
    assert client.post("/v1/auth/google/complete", json={**payload, "username": "admin"}).status_code == 403
    assert client.post("/v1/auth/google/complete", json={**payload, "preset": "custom"}).status_code == 422
    response = client.post("/v1/auth/google/complete", json={**payload, "preset": "bear"})
    assert response.status_code == 201
    token = response.json()["token"]
    me = client.get("/v1/auth/me", headers={"Authorization": "Bearer " + token}).json()
    assert me["username"] == "new-player"
    assert me["avatar"]["id"] == "bear"
    assert client.post("/v1/auth/google/complete", json=payload).status_code == 401
    assert client.post("/v1/auth/login", json={"username": "new-player", "password": "anything-long"}).status_code == 401
    returning, _ = google(client)
    assert returning.json()["username"] == "new-player"
    assert "ticket" not in returning.json()


def test_duplicate_username_keeps_ticket_for_retry(client):
    first, _ = signup(client)
    assert first.status_code == 201
    other, _ = google(client, "other-google")
    payload = {"ticket": other.json()["ticket"], "username": "new-player", "invite_code": "test-invite"}
    assert client.post("/v1/auth/google/complete", json=payload).status_code == 409
    payload["username"] = "another-player"
    assert client.post("/v1/auth/google/complete", json=payload).status_code == 201


def test_expired_missing_tickets_and_disabled_config(client, tmp_path):
    assert client.post("/v1/auth/google/pending", json={"ticket": "x" * 32}).status_code == 401
    assert client.post("/v1/auth/google/start", json={"link": True}).status_code == 401
    settings = Settings(tmp_path, tmp_path / "disabled.db", tmp_path / "u", tmp_path / "a", seed_demo_data=False)
    with TestClient(create_app(settings)) as disabled:
        assert disabled.get("/v1/auth/options").json()["google_enabled"] is False
        assert disabled.post("/v1/auth/google/start", json={}).status_code == 503


def test_linking_preserves_password_account_and_blocks_takeover(client):
    registered = client.post("/v1/auth/register", json={"username": "original", "password": "a-good-password", "invite_code": "test-invite"}).json()
    headers = {"Authorization": "Bearer " + registered["token"]}
    linked, _ = google(client, headers=headers, link=True)
    assert linked.json() == {"linked": True}
    assert client.get("/v1/auth/google/connection", headers=headers).json()["connected"]
    assert client.post("/v1/auth/login", json={"username": "original", "password": "a-good-password"}).status_code == 200
    returning, _ = google(client)
    assert returning.json()["username"] == "original"
    second, _ = signup(client, "second-subject", "second-player")
    second_headers = {"Authorization": "Bearer " + second.json()["token"]}
    conflict, _ = google(client, headers=second_headers, link=True)
    assert conflict.status_code == 409


def test_cli_approval_requires_login_and_is_single_use(client):
    user, _ = signup(client)
    headers = {"Authorization": "Bearer " + user.json()["token"]}
    device = client.post("/v1/auth/browser/start").json()
    assert "device_code" not in device["verification_uri"]
    assert client.post("/v1/auth/browser/poll", json={"device_code": device["device_code"]}).json() == {"pending": True}
    assert client.post("/v1/auth/browser/approve", json={"user_code": device["user_code"]}).status_code == 401
    assert client.post("/v1/auth/browser/approve", json={"user_code": device["user_code"]}, headers=headers).status_code == 200
    assert client.post("/v1/auth/browser/approve", json={"user_code": device["user_code"]}, headers=headers).status_code == 400
    polled = client.post("/v1/auth/browser/poll", json={"device_code": device["device_code"]})
    assert polled.json()["username"] == "new-player"
    assert polled.json()["token"] != user.json()["token"]
    assert client.post("/v1/auth/browser/poll", json={"device_code": device["device_code"]}).status_code == 410
    assert client.post("/v1/auth/browser/poll", json={"device_code": "wrong" * 8}).status_code == 410


@pytest.mark.parametrize("bad_claim", [None, "aud", "iss", "exp", "nonce", "signature"])
def test_real_google_library_validates_signed_tokens(monkeypatch, bad_claim):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from google.auth import crypt, jwt
    from fastapi import HTTPException
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    claims = {"iss": "https://accounts.google.com", "aud": "test-client", "sub": "stable-google-id", "nonce": "test-nonce", "iat": int(time.time()) - 10, "exp": int(time.time()) + 300}
    if bad_claim in {"aud", "iss", "nonce"}:
        claims[bad_claim] = "wrong"
    if bad_claim == "exp":
        claims["exp"] = int(time.time()) - 60
    token = jwt.encode(crypt.RSASigner.from_string(private, key_id="test-key"), claims).decode()
    if bad_claim == "signature":
        parts = token.split(".")
        parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
        token = ".".join(parts)
    monkeypatch.setattr(google_login.urllib.request, "urlopen", lambda *args, **kwargs: io.StringIO(json.dumps({"id_token": token})))
    class CertRequest:
        def __call__(self, *args, **kwargs):
            return SimpleNamespace(status=200, data=json.dumps({"test-key": public}).encode())
    monkeypatch.setattr("google.auth.transport.requests.Request", CertRequest)
    settings = SimpleNamespace(google_client_id="test-client", google_client_secret="secret", google_redirect_uri="http://localhost/callback")
    if bad_claim:
        with pytest.raises(HTTPException) as error:
            google_login.exchange_identity(settings, "code", "verifier", "test-nonce")
        assert error.value.status_code == 401
    else:
        assert google_login.exchange_identity(settings, "code", "verifier", "test-nonce") == "stable-google-id"
