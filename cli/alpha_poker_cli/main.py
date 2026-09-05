from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import struct
import sys
import time
from types import ModuleType
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
import uuid
import zipfile

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


def _config_path() -> Path:
    override = os.environ.get("ALPHA_POKER_CONFIG")
    return Path(override).expanduser() if override else Path.home() / ".config" / "alpha-poker" / "credentials.json"


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


def _load_bot(root: Path) -> tuple[ModuleType, Callable[[dict[str, Any]], dict[str, Any]]]:
    bot_path = root / "bot.py"
    module_name = f"alpha_poker_bot_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, bot_path)
    if spec is None or spec.loader is None:
        raise CliError("could not load bot.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise CliError(f"bot.py failed to import: {type(exc).__name__}: {exc}") from exc
    decide = getattr(module, "decide", None)
    if not callable(decide):
        raise CliError("bot.py must export decide(state)")
    return module, decide


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
    _, decide = _load_bot(root)
    timings: list[float] = []
    for state in _sample_states():
        started = time.perf_counter()
        try:
            action = decide(dict(state))
        except Exception as exc:
            raise CliError(f"decide(state) crashed: {type(exc).__name__}: {exc}") from exc
        elapsed = time.perf_counter() - started
        timings.append(elapsed)
        if elapsed > DECISION_LIMIT_SECONDS:
            raise CliError(f"decision took {elapsed * 1000:.1f} ms; limit is 250 ms")
        validate_action(action, state)
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


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None, token: str | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise CliError(f"server returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise CliError(f"could not reach Alpha Poker at {url}: {exc.reason}") from exc
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise CliError("server returned invalid JSON") from exc


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
    _, decide = _load_bot(root)
    session_url = f"{api_url.rstrip('/')}/training/sessions"
    session_payload = {"username": username, "opponent": opponent, "hand_limit": hands, "client_schema_version": API_VERSION}
    session = _http_json("POST", session_url, session_payload, auth_token) if auth_token else _http_json("POST", session_url, session_payload)
    session_id = session.get("session_id")
    websocket_url = session.get("websocket_url")
    if not isinstance(session_id, str) or not isinstance(websocket_url, str):
        raise CliError("training session response is missing session_id or websocket_url")
    token = session.get("training_token")
    last_seq = 0
    completed: dict[str, Any] | None = None
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
                        proposed = decide(dict(state))
                    except Exception as exc:
                        raise CliError(f"decide(state) crashed: {type(exc).__name__}: {exc}") from exc
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
        except (OSError, TimeoutError, CliError):
            if attempt == 2:
                raise
            time.sleep(0.25 * (attempt + 1))
        finally:
            if ws is not None:
                try:
                    ws.close()
                except OSError:
                    pass
    destination = _training_output_path(output, session_id)
    artifacts_url = completed.get("artifacts_url") if completed else None
    if not isinstance(artifacts_url, str):
        artifacts_url = f"{api_url.rstrip('/')}/training/sessions/{session_id}/artifacts"
    else:
        artifacts_url = urljoin(api_url.rstrip("/") + "/", artifacts_url)
    return _download(artifacts_url, destination, auth_token) if auth_token else _download(artifacts_url, destination)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alpha-poker", description="Build, submit, and train an Alpha Poker bot")
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register", help="create a local Alpha Poker account")
    register.add_argument("username")
    register.add_argument("--api-url", default=DEFAULT_API_URL)
    register.add_argument("--invite-code")
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
    submit = sub.add_parser("submit", help="validate, package, and submit a bot")
    submit.add_argument("path", nargs="?", default=".")
    submit.add_argument("--api-url", default=DEFAULT_API_URL)
    submit.add_argument("--username")
    train = sub.add_parser("train", help="play a local bot against the platform leader")
    train.add_argument("path", nargs="?", default=".")
    train.add_argument("--api-url", default=DEFAULT_API_URL)
    train.add_argument("--username")
    train.add_argument("--opponent", default="leader", choices=["leader"])
    train.add_argument("--hands", type=int, default=5000)
    train.add_argument("--output", type=Path, help="destination directory or .zip file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command in {"register", "login"}:
            password = getpass.getpass("Password: ")
            if args.command == "register":
                confirmation = getpass.getpass("Confirm password: ")
                if password != confirmation:
                    raise CliError("passwords do not match")
            response = _http_json(
                "POST",
                f"{args.api_url.rstrip('/')}/auth/{args.command}",
                {
                    "username": args.username,
                    "password": password,
                    **({"invite_code": args.invite_code} if args.command == "register" and args.invite_code else {}),
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
                print(f"League: {response.get('participant_message') or queue.get('message', 'Status unavailable')}")
                current_run = league.get("current_run") if isinstance(league, dict) else None
                progress = current_run.get("progress") if isinstance(current_run, dict) else None
                if queue.get("state") == "running" and isinstance(progress, dict):
                    print(f"Progress: {progress.get('matchups_completed', 0)} of {progress.get('matchups_total', 0)} matchups")
                if isinstance(result, dict):
                    record = result.get("record", {})
                    win_count = int(record.get("wins", 0))
                    loss_count = int(record.get("losses", 0))
                    print(
                        f"Latest result: rank #{result.get('rank')}, {result.get('elo_rating'):,} Elo, "
                        f"{_count_label(win_count, 'win', 'wins')}, "
                        f"{_count_label(loss_count, 'loss', 'losses')}"
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
            result = validate_bot(root)
            print(f"Valid: {result['manifest']['name']} ({result['checks']} contract checks, max {result['max_decision_ms']:.2f} ms)")
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
            if not 1 <= args.hands <= 10000:
                raise CliError("--hands must be between 1 and 10000")
            destination = run_training(root, args.api_url, args.opponent, args.hands, args.output, username, token)
            print(f"Training complete. Logs: {destination}")
        return 0
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
