from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import struct
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
import uuid
import zipfile
import webbrowser

from .runner import LocalBot, RunnerError

API_VERSION = "2026-09-01"
DEFAULT_API_URL = os.environ.get("ALPHA_POKER_API_URL", "http://localhost:8000/v1")
DEFAULT_USERNAME = os.environ.get("ALPHA_POKER_USERNAME", getpass.getuser())
DEFAULT_TOKEN = os.environ.get("ALPHA_POKER_TOKEN")
MAX_PACKAGE_BYTES = 2 * 1024 * 1024
MAX_ACTION_BYTES = 4096
DECISION_LIMIT_SECONDS = 0.250
ALLOWED_ACTIONS = {"fold", "check", "call", "raise", "all_in"}
PACKAGE_FILES = ("bot.py", "bot.json")
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


class CliError(RuntimeError):
    pass


def _prompt_password(prompt: str) -> str:
    try:
        return getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt) as exc:
        raise CliError(
            "secure password input requires an interactive terminal; "
            "re-run this command in a terminal"
        ) from exc


def _prompt_invite_code() -> str:
    try:
        return getpass.getpass("Invite code: ")
    except (EOFError, KeyboardInterrupt) as exc:
        raise CliError(
            "secure invite-code input requires an interactive terminal; "
            "re-run this command in a terminal"
        ) from exc


def _config_path() -> Path:
    override = os.environ.get("ALPHA_POKER_CONFIG")
    if override:
        return Path(override).expanduser()
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return base / "alpha-poker" / "credentials.json"


def _load_credentials() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return {"profiles": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"could not read credentials at {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("profiles"), dict):
        raise CliError(f"credentials at {path} are invalid")
    return value


def _save_credentials(value: dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)
        path.chmod(0o600)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise CliError(f"could not save credentials at {path}: {exc}") from exc


def _profile(api_url: str) -> dict[str, str]:
    value = _load_credentials().get("profiles", {}).get(api_url.rstrip("/"), {})
    return value if isinstance(value, dict) else {}


def _remember_profile(api_url: str, username: str, token: str) -> None:
    value = _load_credentials()
    value["profiles"][api_url.rstrip("/")] = {"username": username, "token": token}
    _save_credentials(value)


def _forget_profile(api_url: str) -> None:
    value = _load_credentials()
    value["profiles"].pop(api_url.rstrip("/"), None)
    _save_credentials(value)


def _identity(api_url: str, username: str | None = None) -> tuple[str, str | None]:
    profile = _profile(api_url)
    return (
        username or os.environ.get("ALPHA_POKER_USERNAME") or profile.get("username") or DEFAULT_USERNAME,
        DEFAULT_TOKEN or profile.get("token"),
    )


def _sample_states() -> list[dict[str, Any]]:
    common = {
        "schema_version": API_VERSION,
        "match_id": "local-validation",
        "hand_id": "sample-hand",
        "hand_number": 1,
        "seat": 0,
        "button_seat": 0,
        "hole_cards": ["Ah", "Kd"],
        "community_cards": [],
        "pot": 3,
        "stacks": {"0": 199, "1": 198},
        "committed": {"0": 1, "1": 2},
        "action_history": [],
        "decision_deadline_ms": 250,
        "bot_random_seed": 8675309,
    }
    return [
        {**common, "street": "preflop", "to_call": 1, "min_raise_to": 4, "max_raise_to": 200, "legal_actions": ["fold", "call", "raise", "all_in"]},
        {**common, "street": "flop", "community_cards": ["7c", "Js", "2d"], "pot": 12, "to_call": 0, "min_raise_to": 2, "max_raise_to": 198, "legal_actions": ["check", "raise", "all_in"]},
        {**common, "street": "turn", "community_cards": ["7c", "Js", "2d", "Tc"], "pot": 36, "to_call": 12, "min_raise_to": 48, "max_raise_to": 186, "legal_actions": ["fold", "call", "raise", "all_in"]},
        {**common, "street": "river", "community_cards": ["7c", "Js", "2d", "Tc", "3h"], "pot": 80, "to_call": 40, "min_raise_to": None, "max_raise_to": None, "legal_actions": ["fold", "call"]},
    ]


def _load_manifest(root: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((root / "bot.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliError("bot.json is missing") from exc
    except json.JSONDecodeError as exc:
        raise CliError(f"bot.json is not valid JSON: {exc}") from exc
    required = {"api_version", "name", "language", "entrypoint"}
    missing = sorted(required - manifest.keys())
    if missing:
        raise CliError(f"bot.json is missing: {', '.join(missing)}")
    if manifest["api_version"] != API_VERSION:
        raise CliError(f"api_version must be {API_VERSION}")
    if manifest["language"] != "python" or manifest["entrypoint"] != "bot.py:decide":
        raise CliError("prototype bots must use python and entrypoint bot.py:decide")
    if not isinstance(manifest["name"], str) or not manifest["name"].strip() or len(manifest["name"]) > 60:
        raise CliError("name must be 1 to 60 characters")
    return manifest


def _check_package(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise CliError(f"bot directory does not exist: {root}")
    for filename in PACKAGE_FILES:
        path = root / filename
        if path.is_symlink():
            raise CliError(f"symlinks are not allowed: {filename}")
        if not path.is_file():
            raise CliError(f"{filename} is missing")
    if (root / "bot.py").stat().st_size + (root / "bot.json").stat().st_size > MAX_PACKAGE_BYTES:
        raise CliError("bot.py and bot.json exceed the 2 MB upload limit")
    return _load_manifest(root)


def _load_bot(root: Path) -> LocalBot:
    try:
        return LocalBot(root)
    except RunnerError as exc:
        raise CliError(str(exc)) from exc


def validate_action(action: Any, state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise CliError("decide(state) must return a dictionary")
    try:
        encoded = json.dumps(action, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise CliError(f"action is not valid JSON: {exc}") from exc
    if len(encoded) > MAX_ACTION_BYTES:
        raise CliError("action exceeds 4 KB")
    name = action.get("action")
    if name not in ALLOWED_ACTIONS:
        raise CliError(f"unknown action: {name!r}")
    if name not in state["legal_actions"]:
        raise CliError(f"action {name!r} is not legal in this state")
    extra = set(action) - ({"action", "amount"} if name == "raise" else {"action"})
    if extra:
        raise CliError(f"unexpected action fields: {', '.join(sorted(extra))}")
    if name == "raise":
        amount = action.get("amount")
        minimum, maximum = state.get("min_raise_to"), state.get("max_raise_to")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise CliError("raise amount must be an integer")
        if minimum is None or maximum is None or not minimum <= amount <= maximum:
            raise CliError(f"raise amount must be between {minimum} and {maximum}")
    elif "amount" in action:
        raise CliError("amount is only valid for raise")
    return action


def validate_bot(root: Path) -> dict[str, Any]:
    manifest = _check_package(root)
    bot = _load_bot(root)
    timings: list[float] = []
    try:
        for state in _sample_states():
            started = time.perf_counter()
            try:
                action = bot.decide(dict(state))
            except RunnerError as exc:
                raise CliError(str(exc)) from exc
            elapsed = time.perf_counter() - started
            timings.append(elapsed)
            validate_action(action, state)
    finally:
        bot.close()
    return {"manifest": manifest, "checks": len(timings), "max_decision_ms": max(timings) * 1000}


def build_submission(root: Path, destination: Path) -> Path:
    _check_package(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for filename in PACKAGE_FILES:
            info = zipfile.ZipInfo(filename, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (root / filename).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    if destination.stat().st_size > MAX_PACKAGE_BYTES:
        destination.unlink()
        raise CliError("submission ZIP exceeds the 2 MB limit")
    return destination


def _http_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode()
    request_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=data, method=method, headers=request_headers)
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        if token:
            detail = detail.replace(token, "[redacted]")
        raise CliError(f"server returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise CliError(f"could not reach Alpha Poker at {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CliError(
            "Alpha Poker did not respond within 30 seconds. Try again; your local bot files are unchanged."
        ) from exc
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise CliError("server returned invalid JSON") from exc


def _authenticated(api_url: str) -> tuple[str, str]:
    username, token = _identity(api_url)
    if not token:
        raise CliError("not logged in; run alpha-poker login USERNAME")
    return username, token


def _query_url(url: str, **parameters: Any) -> str:
    filtered = {key: value for key, value in parameters.items() if value is not None}
    return f"{url}?{urlencode(filtered)}" if filtered else url


def _username_argument(value: str) -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]{2,40}", normalized):
        raise argparse.ArgumentTypeError("username must be 2 to 40 letters, numbers, underscores, or hyphens")
    return normalized


def _resource_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,200}", value):
        raise argparse.ArgumentTypeError("identifier contains unsupported characters")
    return value


def _history_limit(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be an integer") from exc
    if not 1 <= parsed <= 50:
        raise argparse.ArgumentTypeError("limit must be between 1 and 50")
    return parsed


def _json_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {"items": value}


def _print_json(value: Any) -> None:
    print(json.dumps(_json_object(value), sort_keys=True, separators=(",", ":")))


def _items(value: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in keys:
            found = value.get(key)
            if isinstance(found, list):
                return [item for item in found if isinstance(item, dict)]
    return []


def _name(value: dict[str, Any], *keys: str, fallback: str = "unknown") -> str:
    for key in keys:
        found = value.get(key)
        if isinstance(found, str) and found:
            return found
    return fallback


def _challenge_status(value: dict[str, Any]) -> str:
    return _name(value, "status", fallback="unknown")


def _challenge_opponent(value: dict[str, Any], username: str) -> str:
    opponent_username = value.get("opponent_username")
    if isinstance(opponent_username, str) and opponent_username:
        return opponent_username
    direct = value.get("opponent")
    if isinstance(direct, dict):
        return _name(direct, "username", fallback="opponent")
    if isinstance(direct, str):
        return direct
    challenger = _name(value, "challenger_username", "challenger", fallback="")
    challenged = _name(value, "challenged_username", "challenged", fallback="")
    return challenged if challenger.lower() == username.lower() else challenger or challenged or "opponent"


def _confirm(message: str, assume_yes: bool) -> None:
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise CliError("confirmation requires an interactive terminal; review the action and re-run with --yes")
    try:
        answer = input(f"{message} Type yes to continue: ").strip().lower()
    except (EOFError, KeyboardInterrupt) as exc:
        raise CliError("confirmation cancelled") from exc
    if answer != "yes":
        raise CliError("confirmation cancelled")


def _challenge_preview(value: dict[str, Any], username: str, action: str) -> str:
    opponent = _challenge_opponent(value, username)
    bot_names = value.get("bot_names") if isinstance(value.get("bot_names"), dict) else {}
    challenger = _name(value, "challenger_username", fallback="")
    if challenger.lower() == username.lower():
        own_bot, opponent_bot = bot_names.get("challenger"), bot_names.get("challenged")
    else:
        own_bot, opponent_bot = bot_names.get("challenged"), bot_names.get("challenger")
    own_bot = own_bot or value.get("challenger_bot_name") or value.get("your_bot_name") or value.get("caller_bot_name")
    opponent_bot = opponent_bot or value.get("challenged_bot_name") or value.get("opponent_bot_name") or value.get("bot_name")
    bots = f" ({own_bot} vs {opponent_bot})" if own_bot and opponent_bot else ""
    return f"{action} {opponent}{bots} in a best-of-five Pot-Limit Hold'em challenge."


def _format_record(record: Any) -> str:
    if not isinstance(record, dict):
        return "0-0"
    wins = int(record.get("wins", 0))
    losses = int(record.get("losses", 0))
    draws = int(record.get("draws", 0))
    return f"{wins}-{losses}" + (f"-{draws}" if draws else "")


def _write_recap(response: dict[str, Any], output: Path, api_url: str, token: str) -> Path:
    output = output.expanduser().resolve()
    artifact = response.get("artifacts_url") or response.get("artifact_url")
    challenge = response.get("challenge") if isinstance(response.get("challenge"), dict) else response
    challenge_id = challenge.get("challenge_id") or challenge.get("id") or "recap"
    if isinstance(artifact, str):
        if output.exists() and output.is_dir():
            output = output / f"alpha-poker-rival-{challenge_id}.zip"
        elif not output.suffix:
            output.mkdir(parents=True, exist_ok=True)
            output = output / f"alpha-poker-rival-{challenge_id}.zip"
        return _download(urljoin(api_url.rstrip("/") + "/", artifact), output, token)
    if (output.exists() and output.is_dir()) or not output.suffix:
        output.mkdir(parents=True, exist_ok=True)
        output = output / f"alpha-poker-rival-{challenge_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(response, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _multipart_upload(url: str, package: Path, bot_name: str, username: str = "local", token: str | None = None) -> dict[str, Any]:
    boundary = f"alpha-poker-{secrets.token_hex(12)}"
    chunks = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"bot_name\"\r\n\r\n{bot_name}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"username\"\r\n\r\n{username}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"package\"; filename=\"alpha-poker-submission.zip\"\r\nContent-Type: application/zip\r\n\r\n".encode(),
        package.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    headers = {"Accept": "application/json", "Content-Type": f"multipart/form-data; boundary={boundary}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=b"".join(chunks), method="POST", headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            body = response.read()
    except HTTPError as exc:
        raise CliError(f"submission failed with HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc
    except URLError as exc:
        raise CliError(f"could not reach Alpha Poker at {url}: {exc.reason}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise CliError("server returned invalid JSON") from exc


def _wait_for_submission(api_url: str, response: dict[str, Any], token: str | None, timeout_seconds: float = 30) -> dict[str, Any]:
    submission_id = response.get("submission_id")
    if not isinstance(submission_id, str) or response.get("status") not in {"queued", "validating"}:
        return response
    deadline = time.monotonic() + timeout_seconds
    current = response
    while time.monotonic() < deadline:
        current = _http_json("GET", f"{api_url.rstrip('/')}/submissions/{submission_id}", token=token)
        if current.get("status") in {"accepted", "rejected"}:
            return current
        time.sleep(0.25)
    return current


class WebSocket:
    """Small RFC 6455 client for the prototype's text-only socket."""

    def __init__(self, url: str, token: str | None = None, timeout: float = 30):
        parsed = urlparse(url)
        if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
            raise CliError(f"invalid WebSocket URL: {url}")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        raw = socket.create_connection((parsed.hostname, port), timeout=timeout)
        self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname) if parsed.scheme == "wss" else raw
        self.sock.settimeout(timeout)
        self._buffer = bytearray()
        key = base64.b64encode(os.urandom(16)).decode()
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        host = parsed.hostname if port in {80, 443} else f"{parsed.hostname}:{port}"
        headers = [
            f"GET {path} HTTP/1.1", f"Host: {host}", "Upgrade: websocket", "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13",
        ]
        if token:
            headers.append(f"Authorization: Bearer {token}")
        self.sock.sendall(("\r\n".join(headers) + "\r\n\r\n").encode())
        response = self._read_headers()
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if not response.startswith("HTTP/1.1 101") or f"sec-websocket-accept: {accept.lower()}" not in response.lower():
            self.sock.close()
            raise CliError("WebSocket upgrade was rejected")

    def _read_headers(self) -> str:
        data = bytearray()
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > 65536:
                raise CliError("WebSocket response headers are too large")
        headers, _, remaining = data.partition(b"\r\n\r\n")
        self._buffer.extend(remaining)
        return (headers + b"\r\n\r\n").decode("latin1")

    def _recv_exact(self, size: int) -> bytes:
        data = bytearray(self._buffer[:size])
        del self._buffer[:size]
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise CliError("WebSocket connection closed")
            data.extend(chunk)
        return bytes(data)

    def send_json(self, value: dict[str, Any]) -> None:
        payload = json.dumps(value, separators=(",", ":")).encode()
        mask = os.urandom(4)
        length = len(payload)
        header = bytearray([0x81])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.extend([0xFE])
            header.extend(struct.pack("!H", length))
        else:
            header.extend([0xFF])
            header.extend(struct.pack("!Q", length))
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + mask + masked)

    def receive_json(self) -> dict[str, Any]:
        while True:
            first, second = self._recv_exact(2)
            opcode, length = first & 0x0F, second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if second & 0x80 else None
            payload = self._recv_exact(length)
            if mask:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
            if opcode == 0x8:
                raise CliError("WebSocket connection closed")
            if opcode == 0x9:
                self._send_control(0xA, payload)
                continue
            if opcode != 0x1:
                continue
            try:
                value = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise CliError("WebSocket returned invalid JSON") from exc
            if not isinstance(value, dict):
                raise CliError("WebSocket message must be an object")
            return value

    def _send_control(self, opcode: int, payload: bytes) -> None:
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes([0x80 | opcode, 0x80 | len(payload)]) + mask + masked)

    def close(self) -> None:
        try:
            self._send_control(0x8, b"")
        finally:
            self.sock.close()


def _download(url: str, destination: Path, token: str | None = None) -> Path:
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        destination.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(Request(url, headers=headers), timeout=60) as response:
            destination.write_bytes(response.read())
    except (HTTPError, URLError) as exc:
        raise CliError(f"could not download logs: {exc}") from exc
    return destination


def _count_label(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _training_output_path(output: Path | None, session_id: str) -> Path:
    filename = f"alpha-poker-training-{session_id}.zip"
    if output is None:
        return Path.cwd() / filename
    output = output.expanduser()
    if (output.exists() and output.is_dir()) or not output.suffix:
        output.mkdir(parents=True, exist_ok=True)
        return output / filename
    return output


def run_training(root: Path, api_url: str, opponent: str, hands: int, output: Path | None, username: str = "local", auth_token: str | None = None) -> Path:
    _check_package(root)
    session_url = f"{api_url.rstrip('/')}/training/sessions"
    session_payload = {"username": username, "opponent": opponent, "hand_limit": hands, "client_schema_version": API_VERSION}
    session = _http_json("POST", session_url, session_payload, auth_token) if auth_token else _http_json("POST", session_url, session_payload)
    session_id = session.get("session_id")
    websocket_url = session.get("websocket_url")
    if not isinstance(session_id, str) or not isinstance(websocket_url, str):
        raise CliError("training session response is missing session_id or websocket_url")
    bot = _load_bot(root)
    token = session.get("training_token")
    last_seq = 0
    completed: dict[str, Any] | None = None
    try:
        for attempt in range(3):
            ws: WebSocket | None = None
            try:
                connect_url = websocket_url
                if last_seq:
                    parsed = urlparse(websocket_url)
                    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
                    query["after_seq"] = str(last_seq)
                    connect_url = urlunparse(parsed._replace(query=urlencode(query)))
                ws = WebSocket(connect_url, token if isinstance(token, str) else None)
                while True:
                    message = ws.receive_json()
                    seq = message.get("seq")
                    if isinstance(seq, int):
                        last_seq = max(last_seq, seq)
                    message_type = message.get("type")
                    if message_type == "action.requested":
                        payload = message.get("payload", {})
                        state = payload.get("state")
                        if not isinstance(state, dict):
                            raise CliError("action.requested is missing state")
                        started = time.perf_counter()
                        try:
                            proposed = bot.decide(dict(state))
                        except RunnerError as exc:
                            raise CliError(str(exc)) from exc
                        action = validate_action(proposed, state)
                        elapsed = time.perf_counter() - started
                        if elapsed > DECISION_LIMIT_SECONDS:
                            raise CliError(f"decision took {elapsed * 1000:.1f} ms; limit is 250 ms")
                        ws.send_json({
                            "type": "action.submit", "session_id": session_id,
                            "hand_id": payload.get("hand_id"), "turn_id": payload.get("turn_id"),
                            "turn_token": payload.get("turn_token"), "client_action_id": str(uuid.uuid4()),
                            **action,
                        })
                    elif message_type == "action.rejected":
                        raise CliError(f"server rejected action: {message.get('payload', message)}")
                    elif message_type == "error":
                        raise CliError(f"training error: {message.get('payload', message)}")
                    elif message_type == "session.completed":
                        completed = message.get("payload", {})
                        break
                if completed is not None:
                    break
            except (OSError, TimeoutError, CliError) as exc:
                if attempt == 2:
                    if isinstance(exc, CliError):
                        raise
                    raise CliError(
                        "The training connection timed out after three attempts. Try again in a moment; "
                        "your local bot files are unchanged."
                    ) from exc
                time.sleep(0.25 * (attempt + 1))
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except OSError:
                        pass
    finally:
        bot.close()
    destination = _training_output_path(output, session_id)
    artifacts_url = completed.get("artifacts_url") if completed else None
    if not isinstance(artifacts_url, str):
        artifacts_url = f"{api_url.rstrip('/')}/training/sessions/{session_id}/artifacts"
    else:
        artifacts_url = urljoin(api_url.rstrip("/") + "/", artifacts_url)
    return _download(artifacts_url, destination, auth_token) if auth_token else _download(artifacts_url, destination)


def _print_rivals(response: dict[str, Any]) -> None:
    rivals = _items(response, "rivals", "items")
    if not rivals:
        print("No rivals found.")
        return
    for rival in rivals:
        username = _name(rival, "username")
        bot = _name(rival, "bot_name", fallback="no active bot")
        elo = rival.get("elo") if rival.get("elo") is not None else rival.get("elo_rating")
        suffix = f"{int(elo):,} Elo" if isinstance(elo, (int, float)) else "unranked"
        record = rival.get("direct_record") or rival.get("record") or rival.get("head_to_head")
        if isinstance(record, dict):
            suffix += f", {_format_record(record)} direct"
        print(f"{username}: {bot} ({suffix})")


def _print_rivals_agent(response: dict[str, Any]) -> None:
    rivals = _items(response, "rivals", "items")
    print(f"count={len(rivals)}")
    for index, rival in enumerate(rivals, start=1):
        elo = rival.get("elo") if rival.get("elo") is not None else rival.get("elo_rating")
        record = rival.get("direct_record") or rival.get("record") or rival.get("head_to_head")
        fields = {
            "username": _name(rival, "username"),
            "bot_name": _name(rival, "bot_name", fallback=""),
            "elo": int(elo) if isinstance(elo, (int, float)) else "",
            "direct_record": _format_record(record),
            "is_nemesis": str(bool(rival.get("is_nemesis"))).lower(),
        }
        print(f"rival_{index}=" + json.dumps(fields, sort_keys=True, separators=(",", ":")))


def _print_rival_agent(response: dict[str, Any], fallback_username: str) -> None:
    rival = response.get("rival") if isinstance(response.get("rival"), dict) else response
    elo = rival.get("elo") if rival.get("elo") is not None else rival.get("elo_rating")
    record = response.get("direct_record") or rival.get("direct_record") or rival.get("record") or rival.get("head_to_head")
    fields = {
        "username": _name(rival, "username", fallback=fallback_username),
        "bot_name": _name(rival, "bot_name", fallback=""),
        "elo": int(elo) if isinstance(elo, (int, float)) else "",
        "direct_record": _format_record(record),
        "is_nemesis": str(bool(response.get("is_nemesis") or rival.get("is_nemesis"))).lower(),
    }
    current = response.get("current_challenge") if isinstance(response.get("current_challenge"), dict) else {}
    fields.update({
        "current_challenge_id": _name(current, "challenge_id", "id", fallback=""),
        "current_challenge_status": _challenge_status(current) if current else "",
    })
    for key, value in fields.items():
        print(f"{key}={value}")


def _print_challenges(response: dict[str, Any], username: str) -> None:
    challenges = _items(response, "challenges", "items")
    if not challenges and (response.get("id") or response.get("challenge_id")):
        challenges = [response]
    if not challenges:
        print("No matching rival challenges.")
        return
    for challenge in challenges:
        identifier = _name(challenge, "id", "challenge_id")
        opponent = _challenge_opponent(challenge, username)
        status = _challenge_status(challenge)
        bot_names = challenge.get("bot_names") if isinstance(challenge.get("bot_names"), dict) else {}
        challenger = _name(challenge, "challenger_username", fallback="")
        if challenger.lower() == username.lower():
            own_bot, opponent_bot = bot_names.get("challenger"), bot_names.get("challenged")
        else:
            own_bot, opponent_bot = bot_names.get("challenged"), bot_names.get("challenger")
        context = "best of 5 PLHE"
        if own_bot and opponent_bot:
            context = f"{own_bot} vs {opponent_bot}, {context}"
        result = ""
        winner = challenge.get("winner_username") or challenge.get("winner")
        score = challenge.get("series_score")
        if winner:
            if isinstance(score, dict):
                participants = [
                    _name(challenge, "challenger_username", fallback=""),
                    _name(challenge, "challenged_username", fallback=""),
                ]
                loser = next(
                    (participant for participant in participants if participant and participant.lower() != str(winner).lower()),
                    username if username.lower() != str(winner).lower() else opponent,
                )
                winner_score = int(score.get(winner, 0))
                loser_score = int(score.get(loser, 0))
                if username.lower() == str(winner).lower():
                    result = f", you won {winner_score}-{loser_score}"
                else:
                    result = f", you lost; {winner} won {winner_score}-{loser_score}"
            else:
                result = f", winner {winner}"
        elif status == "running":
            result = f", game {challenge.get('current_game') or '?'}"
            if isinstance(score, dict):
                result += f", score {int(score.get(username, 0))}-{int(score.get(opponent, 0))}"
        print(f"{identifier}: {opponent} ({context}) — {status}{result}")


def _output_format(args: argparse.Namespace) -> str:
    return "json" if getattr(args, "json", False) else getattr(args, "output_format", "human")


def _print_challenge_agent(response: dict[str, Any], username: str) -> None:
    challenge = response.get("challenge") if isinstance(response.get("challenge"), dict) else response
    opponent = _challenge_opponent(challenge, username)
    score = challenge.get("series_score") if isinstance(challenge.get("series_score"), dict) else {}
    winner = challenge.get("winner_username") or ""
    if winner:
        participants = [
            _name(challenge, "challenger_username", fallback=""),
            _name(challenge, "challenged_username", fallback=""),
        ]
        loser = next((name for name in participants if name and name != winner), opponent)
        formatted_score = f"{int(score.get(winner, 0))}-{int(score.get(loser, 0))}"
        score_order = "winner-loser"
        viewer_result = "win" if username == winner else "loss"
    else:
        formatted_score = f"{int(score.get(username, 0))}-{int(score.get(opponent, 0))}"
        score_order = "viewer-opponent"
        viewer_result = "pending"
    fields = {
        "challenge_id": _name(challenge, "challenge_id", "id"),
        "status": _challenge_status(challenge),
        "opponent": opponent,
        "format": challenge.get("format") or "best_of_five_plhe",
        "score": formatted_score,
        "score_order": score_order,
        "viewer_result": viewer_result,
        "games_completed": int(challenge.get("games_completed") or 0),
        "hands_played": int(challenge.get("hands_played") or 0),
        "winner": winner,
        "artifacts_url": challenge.get("artifacts_url") or response.get("artifacts_url") or "",
    }
    for key, value in fields.items():
        print(f"{key}={value}")


def _notification_message(item: dict[str, Any]) -> str:
    message = item.get("message")
    if isinstance(message, str) and message:
        return message
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    opponent = _name(payload, "opponent_username", fallback="Your rival")
    series_score = payload.get("series_score") if isinstance(payload.get("series_score"), dict) else {}
    numeric_scores = sorted(
        (int(value) for value in series_score.values() if isinstance(value, (int, float))),
        reverse=True,
    )
    score = f" {numeric_scores[0]}-{numeric_scores[1]}" if len(numeric_scores) >= 2 else ""
    kind = item.get("type")
    if kind == "challenge_received":
        return f"{opponent} challenged you."
    if kind == "challenge_won":
        return f"You beat {opponent}{score}."
    if kind == "challenge_lost":
        return f"{opponent} beat you{score}."
    if kind == "challenge_drawn":
        return f"Your challenge with {opponent} ended in a draw."
    if kind == "challenge_failed":
        return f"Your challenge with {opponent} could not finish. Check the details, then retry."
    return _name(item, "type", fallback="Notification")


def _wait_for_challenge(
    api_url: str,
    challenge_id: str,
    token: str,
    timeout_seconds: float,
    quiet_progress: bool,
) -> dict[str, Any]:
    if not 1 <= timeout_seconds <= 3600:
        raise CliError("--timeout must be between 1 and 3600 seconds")
    terminal = {"completed", "declined", "cancelled", "failed"}
    deadline = time.monotonic() + timeout_seconds
    delay = 0.5
    last_status = ""
    while True:
        response = _http_json("GET", f"{api_url.rstrip('/')}/challenges/{challenge_id}", token=token)
        status = _challenge_status(response)
        if not quiet_progress and status != last_status:
            print(f"Challenge {challenge_id}: {status}", file=sys.stderr)
            last_status = status
        if status in terminal:
            return response
        if time.monotonic() >= deadline:
            return {
                **response,
                "wait_timed_out": True,
                "wait_message": (
                    (
                        f"Still pending after {int(timeout_seconds)} seconds. "
                        "The challenge is waiting for the other player to respond. "
                    )
                    if status == "pending"
                    else f"Still {status} after {int(timeout_seconds)} seconds. Alpha Poker will keep working. "
                )
                + f"Check later with: alpha-poker rivals status {challenge_id} --wait",
            }
        time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
        delay = min(delay * 1.6, 5.0)


def _replay_url(api_url: str, site_url: str | None, path: str) -> str:
    api = urlparse(api_url)
    site = site_url or os.environ.get("ALPHA_POKER_SITE_URL")
    if not site:
        site = "http://localhost:3002" if api.hostname in {"localhost", "127.0.0.1", "::1"} else f"{api.scheme}://{api.netloc}"
    parsed = urlparse(site)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        raise CliError("--site-url must be an HTTP(S) site origin without credentials, path, query, or fragment")
    return site.rstrip("/") + path


def _recap_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--site-url", help="web app origin (or ALPHA_POKER_SITE_URL); local default http://localhost:3002")
    parser.add_argument("--open", action="store_true", help="open the recap in your browser; sign in there separately")
    parser.add_argument("--url", action="store_true", help="print only the replay URL (or include it with --json)")


def _open_recap(url: str) -> None:
    if not webbrowser.open(url):
        raise CliError(f"could not open a browser; open this URL manually: {url}")


def _run_matches(args: argparse.Namespace) -> int:
    _, token = _authenticated(args.api_url)
    api = args.api_url.rstrip("/")
    if args.matches_command == "list":
        path = f"runs/{args.run_id}/matchups" if args.run_id else "matchups"
        response = _http_json("GET", f"{api}/{path}", token=token)
        if args.json:
            _print_json(response)
        else:
            print(f"Run: {response.get('run_id') or 'No completed run'}")
            for match in response.get("matchups", []):
                print(f"{match['matchup_id']}  {match['player_a']} vs {match['player_b']}  {match['hands']} hands")
        return 0
    response = _http_json("GET", f"{api}/runs/{args.run_id}/matchups/{args.matchup_id}/recap", token=token)
    url = _replay_url(args.api_url, args.site_url, f"/recaps/runs/{quote(args.run_id, safe='')}/matches/{quote(args.matchup_id, safe='')}")
    if args.json:
        _print_json({**response, "playback_url": url})
    elif args.url:
        print(url)
    else:
        print(f"{' vs '.join(response.get('players', []))}: {len(response.get('highlights', []))} highlights")
        print(f"View recap: {url}")
    if args.open:
        _open_recap(url)
    return 0


def _run_rivals(args: argparse.Namespace) -> int:
    username, token = _authenticated(args.api_url)
    api = args.api_url.rstrip("/")
    action = args.rivals_command
    output_format = _output_format(args)
    if action == "list":
        response = _http_json("GET", _query_url(f"{api}/rivals", source=args.source, q=args.search), token=token)
        if output_format == "json":
            _print_json(response)
        elif output_format == "agent":
            _print_rivals_agent(response)
        else:
            _print_rivals(response)
        return 0
    if action == "show":
        response = _http_json("GET", f"{api}/rivals/{args.username}", token=token)
        if output_format == "json":
            _print_json(response)
        elif output_format == "agent":
            _print_rival_agent(response, args.username)
        else:
            rival = response.get("rival") if isinstance(response.get("rival"), dict) else response
            elo = rival.get("elo") if rival.get("elo") is not None else rival.get("elo_rating")
            print(f"{_name(rival, 'username', fallback=args.username)} — {_name(rival, 'bot_name', fallback='no active bot')}")
            if isinstance(elo, (int, float)):
                print(f"Elo: {int(elo):,}")
            record = response.get("direct_record") or rival.get("direct_record") or rival.get("record") or rival.get("head_to_head")
            print(f"Direct challenge record: {_format_record(record)}")
            if response.get("is_nemesis") or rival.get("is_nemesis"):
                print("Relationship: Nemesis")
            current = response.get("current_challenge") if isinstance(response.get("current_challenge"), dict) else None
            if current:
                print(
                    f"Current challenge: {_challenge_status(current)} "
                    f"({_name(current, 'challenge_id', 'id')})"
                )
        return 0
    if action == "history":
        response = _http_json(
            "GET", _query_url(f"{api}/rivals/{args.username}/history", limit=args.limit), token=token
        )
        if output_format == "json":
            _print_json(response)
        elif output_format == "agent":
            history = _items(response, "history", "challenges", "items")
            print(f"count={len(history)}")
            for challenge in history:
                _print_challenge_agent(challenge, username)
        else:
            history = _items(response, "history", "challenges", "items")
            _print_challenges({"challenges": history}, username)
        return 0
    if action == "requests":
        response = _http_json("GET", _query_url(f"{api}/challenges", status=args.status), token=token)
        if output_format == "json":
            _print_json(response)
        elif output_format == "agent":
            challenges = _items(response, "challenges", "items")
            print(f"count={len(challenges)}")
            for challenge in challenges:
                _print_challenge_agent(challenge, username)
        else:
            _print_challenges(response, username)
        return 0
    if action == "challenge":
        rival = _http_json("GET", f"{api}/rivals/{args.username}", token=token)
        account = _http_json("GET", f"{api}/account/status", token=token)
        preview = rival.get("rival") if isinstance(rival.get("rival"), dict) else rival
        submission = account.get("submission") if isinstance(account.get("submission"), dict) else {}
        preview = {
            **preview,
            "opponent": args.username,
            "your_bot_name": submission.get("bot_name") or "your active bot",
            "opponent_bot_name": preview.get("bot_name") or "their active bot",
        }
        print(_challenge_preview(preview, username, "Challenge"), file=sys.stderr if output_format == "json" else sys.stdout)
        _confirm("Send this challenge?", args.yes)
        response = _http_json(
            "POST",
            f"{api}/challenges",
            {"opponent_username": args.username},
            token,
            {"Idempotency-Key": f"cli-challenge-{uuid.uuid4()}"},
        )
        if output_format == "json":
            _print_json(response)
        elif output_format == "agent":
            _print_challenge_agent(response, username)
        else:
            print(f"Challenge sent: {_name(response, 'id', 'challenge_id')}")
        return 0
    if action in {"accept", "decline", "cancel"}:
        challenge = _http_json("GET", f"{api}/challenges/{args.challenge_id}", token=token)
        verb = {"accept": "Accept", "decline": "Decline", "cancel": "Cancel"}[action]
        print(_challenge_preview(challenge, username, verb), file=sys.stderr if output_format == "json" else sys.stdout)
        _confirm(f"{verb} this challenge?", args.yes)
        response = _http_json(
            "POST",
            f"{api}/challenges/{args.challenge_id}/{action}",
            {},
            token,
            {"Idempotency-Key": f"cli-{action}-{uuid.uuid4()}"},
        )
        if output_format == "json":
            _print_json(response)
        elif output_format == "agent":
            _print_challenge_agent(response, username)
        else:
            _print_challenges(response, username)
        return 0
    if action == "status":
        if args.wait and not args.challenge_id:
            raise CliError("rivals status --wait requires a CHALLENGE_ID")
        if args.challenge_id:
            response = (
                _wait_for_challenge(api, args.challenge_id, token, args.timeout, output_format != "human")
                if args.wait
                else _http_json("GET", f"{api}/challenges/{args.challenge_id}", token=token)
            )
        else:
            response = _http_json("GET", f"{api}/challenges", token=token)
        if output_format == "json":
            _print_json(response)
        elif output_format == "agent":
            _print_challenge_agent(response, username)
        else:
            _print_challenges(response, username)
            if response.get("wait_timed_out"):
                print(response["wait_message"])
        return 0
    if action == "recap":
        response = _http_json("GET", f"{api}/challenges/{args.challenge_id}/recap", token=token)
        url = _replay_url(api, args.site_url, f"/recaps/challenges/{quote(args.challenge_id, safe='')}")
        saved: Path | None = None
        if args.output:
            saved = _write_recap(response, args.output, api, token)
        if output_format == "json":
            payload = {**response, "playback_url": url, **({"saved_to": str(saved)} if saved else {})}
            _print_json(payload)
        elif args.url:
            print(url)
        elif output_format == "agent":
            _print_challenge_agent(response, username)
            if isinstance(response.get("summary"), dict) and response["summary"].get("result_text"):
                print("result_text=" + json.dumps(response["summary"]["result_text"]))
        else:
            summary = response.get("summary") if isinstance(response.get("summary"), dict) else {}
            challenge = response.get("challenge") if isinstance(response.get("challenge"), dict) else response
            winner = challenge.get("winner_username") or challenge.get("winner")
            score = challenge.get("series_score") if isinstance(challenge.get("series_score"), dict) else {}
            if winner:
                participants = [
                    _name(challenge, "challenger_username", fallback=""),
                    _name(challenge, "challenged_username", fallback=""),
                ]
                loser = next((name for name in participants if name and name != winner), _challenge_opponent(challenge, username))
                winner_score = int(score.get(winner, 0))
                loser_score = int(score.get(loser, 0))
                if username == winner:
                    print(f"You won {winner_score}-{loser_score}.")
                else:
                    print(f"You lost; {winner} won {winner_score}-{loser_score}.")
            if summary.get("result_text"):
                print(summary["result_text"])
            else:
                if not winner:
                    print("The challenge ended in a tie.")
            if saved:
                print(f"Saved recap: {saved}")
            print(f"View recap: {url}")
        if args.open:
            _open_recap(url)
        return 0
    raise CliError(f"unknown rivals command: {action}")


def _run_notifications(args: argparse.Namespace) -> int:
    _, token = _authenticated(args.api_url)
    api = args.api_url.rstrip("/")
    if args.notifications_command == "list":
        response = _http_json(
            "GET", _query_url(f"{api}/notifications", unread="true" if args.unread else None), token=token
        )
        if args.json:
            _print_json(response)
        else:
            notifications = _items(response, "notifications", "items")
            if not notifications:
                print("No notifications.")
            for item in notifications:
                unread = "new" if not item.get("read_at") else "read"
                print(f"{_name(item, 'id', 'notification_id')}: {_notification_message(item)} ({unread})")
        return 0
    response = _http_json("POST", f"{api}/notifications/{args.notification_id}/read", {}, token)
    _print_json(response) if args.json else print(f"Marked notification {args.notification_id} read.")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alpha-poker",
        description="Build, train, compete, and manage Alpha Poker rival challenges",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register", help="create a local Alpha Poker account")
    register.add_argument("username")
    register.add_argument("--api-url", default=DEFAULT_API_URL)
    register.add_argument(
        "--invite-code",
        help="cohort code; omit to enter it securely when the league requires one",
    )
    login = sub.add_parser("login", help="log in and store a revocable local token")
    login.add_argument("username")
    login.add_argument("--api-url", default=DEFAULT_API_URL)
    logout = sub.add_parser("logout", help="revoke the stored session")
    logout.add_argument("--api-url", default=DEFAULT_API_URL)
    whoami = sub.add_parser("whoami", help="show the logged-in account")
    whoami.add_argument("--api-url", default=DEFAULT_API_URL)
    status = sub.add_parser("status", help="show your submission, league, and latest result")
    status.add_argument("--api-url", default=DEFAULT_API_URL)
    logs = sub.add_parser("logs", help="download your validation and latest official hand logs")
    logs.add_argument("--api-url", default=DEFAULT_API_URL)
    logs.add_argument("--output", type=Path, default=Path.cwd(), help="destination directory")
    validate = sub.add_parser("validate", help="validate a local bot")
    validate.add_argument("path", nargs="?", default=".")
    validate.add_argument("--verbose", action="store_true", help="show runner compatibility details")
    submit = sub.add_parser("submit", help="validate, package, and submit a bot")
    submit.add_argument("path", nargs="?", default=".")
    submit.add_argument("--api-url", default=DEFAULT_API_URL)
    submit.add_argument("--username")
    train = sub.add_parser("train", help="play a local bot against the platform leader")
    train.add_argument("path", nargs="?", default=".")
    train.add_argument("--api-url", default=DEFAULT_API_URL)
    train.add_argument("--username")
    train.add_argument("--opponent", default="leader", choices=["leader"])
    train.add_argument("--hands", type=int, default=400, help="number of practice hands (1-400, default: 400)")
    train.add_argument("--output", type=Path, help="destination directory or .zip file")

    rivals = sub.add_parser("rivals", help="find rivals and manage direct challenges")
    rivals_sub = rivals.add_subparsers(dest="rivals_command", required=True)

    rivals_list = rivals_sub.add_parser("list", help="list your rivals or leaderboard participants")
    rivals_list.add_argument("--source", choices=["mine", "leaderboard"], default="mine")
    rivals_list.add_argument("--search")
    rivals_list.add_argument("--api-url", default=DEFAULT_API_URL)
    rivals_list.add_argument("--json", action="store_true")
    rivals_list.add_argument("--format", dest="output_format", choices=["human", "agent", "json"], default="human")
    rivals_show = rivals_sub.add_parser("show", help="show one rival and your direct-challenge record")
    rivals_show.add_argument("username", type=_username_argument)
    rivals_show.add_argument("--api-url", default=DEFAULT_API_URL)
    rivals_show.add_argument("--json", action="store_true")
    rivals_show.add_argument("--format", dest="output_format", choices=["human", "agent", "json"], default="human")
    rivals_history = rivals_sub.add_parser("history", help="show direct challenges against one rival")
    rivals_history.add_argument("username", type=_username_argument)
    rivals_history.add_argument("--limit", type=_history_limit, default=20, metavar="N")
    rivals_history.add_argument("--api-url", default=DEFAULT_API_URL)
    rivals_history.add_argument("--json", action="store_true")
    rivals_history.add_argument("--format", dest="output_format", choices=["human", "agent", "json"], default="human")
    rivals_requests = rivals_sub.add_parser("requests", help="list incoming, running, or finished challenges")
    rivals_requests.add_argument("--status", choices=["incoming", "running", "finished"])
    rivals_requests.add_argument("--api-url", default=DEFAULT_API_URL)
    rivals_requests.add_argument("--json", action="store_true")
    rivals_requests.add_argument("--format", dest="output_format", choices=["human", "agent", "json"], default="human")

    for command, help_text in (
        ("challenge", "send a best-of-five Pot-Limit Hold'em challenge"),
        ("accept", "accept and queue an incoming challenge"),
        ("decline", "decline an incoming challenge"),
        ("cancel", "cancel a challenge you sent"),
    ):
        mutation = rivals_sub.add_parser(command, help=help_text)
        mutation.add_argument(
            "username" if command == "challenge" else "challenge_id",
            type=_username_argument if command == "challenge" else _resource_id,
        )
        mutation.add_argument("--yes", action="store_true", help="confirm after reviewing the action")
        mutation.add_argument("--api-url", default=DEFAULT_API_URL)
        mutation.add_argument("--json", action="store_true")
        mutation.add_argument("--format", dest="output_format", choices=["human", "agent", "json"], default="human")

    rivals_status = rivals_sub.add_parser("status", help="show or wait for rival challenge status")
    rivals_status.add_argument("challenge_id", nargs="?", type=_resource_id)
    rivals_status.add_argument("--wait", action="store_true")
    rivals_status.add_argument("--timeout", type=float, default=300, metavar="SECONDS")
    rivals_status.add_argument("--api-url", default=DEFAULT_API_URL)
    rivals_status.add_argument("--json", action="store_true")
    rivals_status.add_argument("--format", dest="output_format", choices=["human", "agent", "json"], default="human")
    rivals_recap = rivals_sub.add_parser("recap", help="show a completed challenge recap and save evidence")
    rivals_recap.add_argument("challenge_id", type=_resource_id)
    rivals_recap.add_argument("--output", type=Path)
    rivals_recap.add_argument("--api-url", default=DEFAULT_API_URL)
    rivals_recap.add_argument("--json", action="store_true")
    rivals_recap.add_argument("--format", dest="output_format", choices=["human", "agent", "json"], default="human")
    _recap_options(rivals_recap)

    matches = sub.add_parser("matches", help="discover completed round-robin pairings and view their recaps")
    matches_sub = matches.add_subparsers(dest="matches_command", required=True)
    matches_list = matches_sub.add_parser("list", help="list pairings from the latest completed run or a specified run")
    matches_list.add_argument("--run", dest="run_id", type=_resource_id)
    matches_list.add_argument("--api-url", default=DEFAULT_API_URL)
    matches_list.add_argument("--json", action="store_true")
    matches_recap = matches_sub.add_parser("recap", help="view one completed pairing without mixing other hands")
    matches_recap.add_argument("run_id", type=_resource_id)
    matches_recap.add_argument("matchup_id", type=_resource_id)
    matches_recap.add_argument("--api-url", default=DEFAULT_API_URL)
    matches_recap.add_argument("--json", action="store_true")
    _recap_options(matches_recap)

    notifications = sub.add_parser("notifications", help="list and read rival notifications")
    notifications_sub = notifications.add_subparsers(dest="notifications_command", required=True)
    notifications_list = notifications_sub.add_parser("list", help="list recent notifications")
    notifications_list.add_argument("--unread", action="store_true")
    notifications_list.add_argument("--api-url", default=DEFAULT_API_URL)
    notifications_list.add_argument("--json", action="store_true")
    notifications_read = notifications_sub.add_parser("read", help="mark one notification read")
    notifications_read.add_argument("notification_id", type=_resource_id)
    notifications_read.add_argument("--api-url", default=DEFAULT_API_URL)
    notifications_read.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "matches":
            return _run_matches(args)
        if args.command == "rivals":
            return _run_rivals(args)
        if args.command == "notifications":
            return _run_notifications(args)
        if args.command in {"register", "login"}:
            password = _prompt_password("Password: ")
            invite_code = None
            if args.command == "register":
                confirmation = _prompt_password("Confirm password: ")
                if password != confirmation:
                    raise CliError("passwords do not match")
                invite_code = args.invite_code
                if invite_code is None:
                    config = _http_json("GET", f"{args.api_url.rstrip('/')}/config")
                    if config.get("invite_required") is True:
                        invite_code = _prompt_invite_code()
            response = _http_json(
                "POST",
                f"{args.api_url.rstrip('/')}/auth/{args.command}",
                {
                    "username": args.username,
                    "password": password,
                    **({"invite_code": invite_code} if args.command == "register" and invite_code else {}),
                },
            )
            if not isinstance(response.get("token"), str) or not isinstance(response.get("username"), str):
                raise CliError("authentication response is missing a token")
            _remember_profile(args.api_url, response["username"], response["token"])
            print(f"Logged in as {response['username']}")
            return 0
        if args.command == "logout":
            username, token = _identity(args.api_url)
            if token:
                _http_json("POST", f"{args.api_url.rstrip('/')}/auth/logout", token=token)
            _forget_profile(args.api_url)
            print(f"Logged out {username}")
            return 0
        if args.command == "whoami":
            _, token = _identity(args.api_url)
            if not token:
                raise CliError("not logged in; run alpha-poker login USERNAME")
            response = _http_json("GET", f"{args.api_url.rstrip('/')}/auth/me", token=token)
            print(response["username"])
            return 0
        if args.command in {"status", "logs"}:
            _, token = _identity(args.api_url)
            if not token:
                raise CliError("not logged in; run alpha-poker login USERNAME")
            response = _http_json("GET", f"{args.api_url.rstrip('/')}/account/status", token=token)
            submission = response.get("submission")
            league = response.get("league", {})
            queue = league.get("queue", {}) if isinstance(league, dict) else {}
            result = response.get("result")
            if args.command == "status":
                if isinstance(submission, dict):
                    print(f"Bot: {submission.get('bot_name')} ({submission.get('status')})")
                    if submission.get("error"):
                        print(f"Submission error: {submission['error']}")
                else:
                    print("Bot: no submission yet")
                league_message = response.get("participant_message") or queue.get("message", "Status unavailable")
                if queue.get("state") == "waiting_for_players":
                    wait_detail = str(league_message).rstrip(".")
                    print(f"Official league: not started ({wait_detail.lower()}).")
                    if isinstance(result, dict) and isinstance(result.get("elo_rating"), int):
                        print(
                            f"Elo: unchanged at {result['elo_rating']:,} until the next official run completes."
                        )
                    else:
                        print("Elo: not assigned until an official run completes.")
                else:
                    print(f"League: {league_message}")
                current_run = league.get("current_run") if isinstance(league, dict) else None
                progress = current_run.get("progress") if isinstance(current_run, dict) else None
                if queue.get("state") == "running" and isinstance(progress, dict):
                    print(f"Progress: {progress.get('matchups_completed', 0)} of {progress.get('matchups_total', 0)} matchups")
                if isinstance(result, dict):
                    record = result.get("record", {})
                    win_count = int(record.get("wins", 0))
                    loss_count = int(record.get("losses", 0))
                    draw_count = int(record.get("draws", 0))
                    draw_summary = (
                        f", {_count_label(draw_count, 'draw', 'draws')}"
                        if draw_count > 0
                        else ""
                    )
                    print(
                        f"Latest result: rank #{result.get('rank')}, {result.get('elo_rating'):,} Elo, "
                        f"{_count_label(win_count, 'win', 'wins')}, "
                        f"{_count_label(loss_count, 'loss', 'losses')}"
                        f"{draw_summary}"
                    )
                return 0
            destination = args.output.expanduser().resolve()
            destination.mkdir(parents=True, exist_ok=True)
            downloaded: list[Path] = []
            if isinstance(submission, dict) and isinstance(response.get("submission_logs_url"), str):
                url = urljoin(args.api_url.rstrip("/") + "/", response["submission_logs_url"])
                downloaded.append(_download(url, destination / f"{submission['submission_id']}-validation.txt", token))
            if isinstance(result, dict) and isinstance(result.get("artifacts_url"), str):
                url = urljoin(args.api_url.rstrip("/") + "/", result["artifacts_url"])
                downloaded.append(_download(url, destination / f"{result['id']}-official-logs.zip", token))
            if not downloaded:
                raise CliError("no logs are available yet; run alpha-poker status for the current state")
            for path in downloaded:
                print(f"Downloaded: {path}")
            return 0

        root = Path(args.path).expanduser().resolve()
        if args.command == "validate":
            print("Checking your bot...")
            result = validate_bot(root)
            print("✓ Bot check passed")
            print("Ready to train or compete.")
            if args.verbose:
                print(
                    f"Runner policy: local-v1; Python: {sys.version_info.major}.{sys.version_info.minor}; "
                    f"{result['checks']} contract checks; slowest decision: {result['max_decision_ms']:.2f} ms"
                )
                print("The server will repeat these checks after upload.")
        elif args.command == "submit":
            username, token = _identity(args.api_url, args.username)
            result = validate_bot(root)
            package = root / ".alpha-poker-submission.zip"
            try:
                build_submission(root, package)
                response = _multipart_upload(f"{args.api_url.rstrip('/')}/submissions", package, result["manifest"]["name"], username, token)
            finally:
                package.unlink(missing_ok=True)
            response = _wait_for_submission(args.api_url, response, token)
            if response.get("status") == "rejected":
                raise CliError(f"submission rejected: {response.get('error') or 'open the validation log for details'}")
            state = "accepted" if response.get("status") == "accepted" else "submitted"
            print(f"{state.capitalize()} {result['manifest']['name']}: {response.get('submission_id', 'accepted')}")
        elif args.command == "train":
            username, token = _identity(args.api_url, args.username)
            if not 1 <= args.hands <= 400:
                raise CliError("--hands must be between 1 and 400")
            destination = run_training(root, args.api_url, args.opponent, args.hands, args.output, username, token)
            print(f"Training complete. Logs: {destination}")
        return 0
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
