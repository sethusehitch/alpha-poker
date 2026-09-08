"""Read-only, loopback-only replay of saved evidence. No API credentials needed."""
from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

MAX_BYTES = 64 * 1024 * 1024
MAX_HANDS = 10000
PACKAGE = Path(__file__).resolve().parent


class RecapError(ValueError):
    pass


def state_path():
    return Path(os.environ.get("ALPHA_POKER_RECAP_STATE", str(Path.home() / ".config/alpha-poker/latest-recap.json"))).expanduser()


def remember(path: Path):
    target = state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"path": str(path.resolve())}, stream)
        os.replace(temp, target)
    finally:
        Path(temp).unlink(missing_ok=True)


def latest():
    try:
        path = Path(json.loads(state_path().read_text())["path"])
        if path.is_file():
            return path
    except (OSError, ValueError, KeyError, TypeError):
        pass
    raise RecapError("No saved run found. Train a bot or run: alpha-poker recap <training.zip>")


def _json(raw):
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RecapError("Invalid JSON in saved evidence.") from exc


class Evidence:
    def __init__(self, path):
        from ._recap.recaps import normalize_hand, select_highlights
        self.normalize, self.select = normalize_hand, select_highlights
        path = Path(path).expanduser().resolve()
        self.name, self.warnings, self.groups = path.name, [], []
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise RecapError("Choose an existing training ZIP, hands.jsonl, or recap JSON smaller than 64 MB.")
        summary = {}
        if path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(path) as archive:
                    # Never extract files or execute saved bot code. Only these members are read.
                    names = archive.namelist()
                    if names.count("hands.jsonl") != 1:
                        raise RecapError("This ZIP must contain exactly one hands.jsonl. Bot submission ZIPs are not replay logs.")
                    if sum(i.file_size for i in archive.infolist()) > MAX_BYTES:
                        raise RecapError("Uncompressed archive exceeds the 64 MB replay limit.")
                    raw = archive.read("hands.jsonl")
                    if names.count("summary.json") == 1:
                        summary = _json(archive.read("summary.json"))
            except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
                raise RecapError("Cannot read this training/match ZIP.") from exc
        elif path.suffix.lower() == ".jsonl":
            raw = path.read_bytes()
        elif path.suffix.lower() == ".json":
            data = _json(path.read_bytes())
            if not isinstance(data, dict) or data.get("schema_version") != "recap-v1" or not data.get("highlights"):
                raise RecapError("Expected a saved recap-v1 JSON. For full runs use the ZIP or hands.jsonl.")
            if not isinstance(data["highlights"], list) or len(data["highlights"]) > MAX_HANDS or not isinstance(data.get("players"), list) or len(data["players"]) != 2 or not all(isinstance(n, str) for n in data["players"]):
                raise RecapError("Invalid recap JSON player/highlight list.")
            for h in data["highlights"]:
                if not isinstance(h, dict) or not isinstance(h.get("players"), list) or len(h["players"]) != 2 or not isinstance(h.get("steps"), list) or not h["steps"]:
                    raise RecapError("Incomplete recap JSON: players or replay steps are missing.")
                if not isinstance(h.get("label"), str) or type(h.get("hand_number")) is not int or not isinstance(h.get("winners"), list):
                    raise RecapError("Incomplete recap JSON hand metadata.")
                for p in h["players"]:
                    if not isinstance(p, dict) or not isinstance(p.get("username"), str) or p.get("seat") not in (0, 1) or not isinstance(p.get("hole_cards"), list):
                        raise RecapError("Invalid recap JSON player.")
                for step in h["steps"]:
                    if not isinstance(step, dict) or not isinstance(step.get("street"), str) or not isinstance(step.get("board"), list) or not isinstance(step.get("stacks"), list) or len(step["stacks"]) != 2 or not isinstance(step.get("hole_cards"), list) or len(step["hole_cards"]) != 2:
                        raise RecapError("Incomplete recap JSON replay step.")
            self.saved = data
            self.groups = [{"id": "0", "name": " vs ".join(data.get("players", [])), "hands": [
                {"id": str(i), "number": h.get("hand_number", i+1), "game": h.get("game_number")} for i,h in enumerate(data["highlights"])]}]
            self.warnings = ["This saved recap contains selected highlights only. Use the full match ZIP to view every hand."]
            return
        else:
            raise RecapError("Unsupported format. Use a training/match ZIP, hands.jsonl, or saved recap JSON.")
        if not isinstance(summary, dict):
            raise RecapError("Invalid summary.json: expected an object.")
        lines = [line for line in raw.splitlines() if line.strip()]
        if not lines or len(lines) > MAX_HANDS:
            raise RecapError("Saved run must contain 1–10,000 hands.")
        self.records, self.stats, self.labels = {}, {}, {}
        groups = {}
        skipped = 0
        seen = set()
        for i, line in enumerate(lines):
            record = _json(line)
            if not isinstance(record, dict):
                raise RecapError(f"Hand record {i+1} must be an object.")
            events = record.get("events")
            if not isinstance(events, list) or not any(isinstance(e, dict) and e.get("type") == "result" for e in events):
                skipped += 1
                continue
            names = record.get("players")
            if not isinstance(names, list) or len(names) != 2 or any(not isinstance(n, str) or not n or len(n)>160 for n in names) or names[0] == names[1]:
                raise RecapError(f"Hand record {i+1} needs two distinct player names.")
            group_key = (str(record.get("match_id", "")), tuple(sorted(names)))
            if group_key not in groups:
                groups[group_key] = str(len(groups))
                self.groups.append({"id": groups[group_key], "name": " vs ".join(names), "hands": [], "players": names})
            gid = groups[group_key]
            identity = (gid, str(record.get("id", record.get("hand_id", i))))
            if identity in seen:
                raise RecapError("Duplicate hand IDs in saved evidence; refusing to double-count results.")
            seen.add(identity)
            hid = str(i)
            number = record.get("hand_number")
            if type(number) is not int or number < 1:
                number = len(self.groups[int(gid)]["hands"]) + 1
            row = {"id": hid, "hand_number": number}
            players = self.groups[int(gid)]["players"]
            matchup = {"player_a": players[0], "player_b": players[1]}
            viewer = summary.get("username")
            try:
                stat = self.normalize(record, row, matchup, viewer, include_steps=False)
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                raise RecapError(f"Invalid hand record {i+1}.") from exc
            self.records[hid] = (record, row, matchup, viewer)
            self.stats[hid] = stat
            self.groups[int(gid)]["hands"].append({"id": hid, "number": stat["hand_number"], "game": stat["game_number"]})
        if not self.groups:
            raise RecapError("No completed hands with replay events were saved. Finish a training hand first.")
        expected = summary.get("hands_played")
        if expected is None and isinstance(summary.get("challenge"), dict):
            expected = summary["challenge"].get("hands")
        self.complete = type(expected) is int and expected == len(self.records) and not skipped
        if not self.complete:
            self.warnings.append("Partial or unverified history: only retained completed hands are shown; match-wide momentum is not inferred.")
        if skipped:
            self.warnings.append(f"Skipped {skipped} incomplete hands without a result event.")
        for group in self.groups:
            group["hands"].sort(key=lambda h: (h["game"] or 0, h["number"], int(h["id"])))
            stats = [self.stats[h["id"]] for h in group["hands"]]
            self.labels[group["id"]] = self.select(stats, complete=self.complete and not any(h.get("game_number") for h in stats))

    def manifest(self):
        return {"name": self.name, "groups": self.groups, "warnings": self.warnings}

    def recap(self, gid, hid=None):
        group = next((g for g in self.groups if g["id"] == gid), None)
        if group is None or (hid is not None and hid not in [h["id"] for h in group["hands"]]):
            raise RecapError("Hand or match not found.")
        if hasattr(self, "saved"):
            return {**self.saved, "highlights": [self.saved["highlights"][int(hid)]] if hid is not None else self.saved["highlights"]}
        selected = [{**self.stats[hid], "label": "Selected hand", "labels": ["Selected hand"]}] if hid is not None else self.labels[gid]
        hands = []
        for stat in selected:
            record, row, matchup, viewer = self.records[stat["hand_id"]]
            hands.append({**self.normalize(record, row, matchup, viewer), "label": stat["label"], "labels": stat["labels"]})
        return {"schema_version": "recap-v1", "source": "local", "players": group["players"], "total_hands": len(group["hands"]),
                "retained_hands": len(group["hands"]), "complete_history": True, "highlights": hands}


def make_server(evidence):
    prefix = "/" + secrets.token_urlsafe(24) + "/"
    assets = {"/" + p.relative_to(PACKAGE / "viewer").as_posix(): p for p in (PACKAGE / "viewer").rglob("*") if p.is_file()}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != host or self.headers.get("Origin", f"http://{host}") != f"http://{host}":
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if path == "/robot-avatars.png":
                relative = path
            elif path.startswith(prefix):
                relative = "/" + path[len(prefix):]
            else:
                self.send_error(404)
                return
            try:
                if relative == "/manifest.json":
                    body, kind = json.dumps(evidence.manifest()).encode(), "application/json"
                elif relative.startswith("/recap/"):
                    parts = relative.split("/")[2:]
                    if len(parts) not in (1, 2):
                        raise RecapError("Invalid recap path")
                    body, kind = json.dumps(evidence.recap(*parts)).encode(), "application/json"
                else:
                    asset = assets.get("/index.html" if relative == "/" else relative)
                    if asset is None:
                        raise RecapError("Not found")
                    body = asset.read_bytes()
                    kind = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'")
                self.end_headers()
                self.wfile.write(body)
                self.server.last_access = time.monotonic()
            except (RecapError, ValueError, TypeError, KeyError, IndexError):
                self.send_error(422, "Invalid or unavailable hand evidence")
    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout, server.last_access = 1, time.monotonic()
    return server, f"http://127.0.0.1:{server.server_port}{prefix}"


def launch(path, open_browser=False):
    path = Path(path).expanduser().resolve()
    if not (PACKAGE / "viewer/index.html").is_file():
        raise RecapError("Viewer assets missing. Install the current starter kit (developers: npm run build:local-recap).")
    Evidence(path)  # Fail clearly in the foreground, before spawning anything.
    with tempfile.TemporaryDirectory(prefix="alpha-poker-recap-") as temp:
        ready = Path(temp) / "ready.json"
        child_env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL") if key in os.environ}
        child_env["PYTHONPATH"] = str(PACKAGE.parent)
        process = subprocess.Popen([sys.executable, "-m", "alpha_poker_cli.local_recap", str(path), str(ready)], env=child_env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + 30
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        if not ready.exists():
            process.terminate()
            raise RecapError("Local viewer could not start. Reinstall the starter kit and retry.")
        url = json.loads(ready.read_text())["url"]
    remember(path)
    print(f"Local recap: {url}", flush=True)
    print("Private to this computer. Viewer stops after 30 minutes without requests.", flush=True)
    if open_browser and not webbrowser.open(url):
        print("Browser could not open automatically. Open the URL above.")
    return url


if __name__ == "__main__":
    server, url = make_server(Evidence(sys.argv[1]))
    ready = Path(sys.argv[2])
    temp = ready.with_suffix(".tmp")
    temp.write_text(json.dumps({"url": url}))
    temp.replace(ready)
    started = time.monotonic()
    try:
        while time.monotonic() - server.last_access < 1800 and time.monotonic() - started < 8 * 3600:
            server.handle_request()
    finally:
        server.server_close()
