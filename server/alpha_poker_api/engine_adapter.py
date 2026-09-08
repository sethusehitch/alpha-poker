from __future__ import annotations

import json
import os
import selectors
import subprocess
import sys
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


MAX_EXPANDED_BYTES = 10 * 1024 * 1024


@dataclass
class ValidationResult:
    accepted: bool
    logs: str
    error: str | None = None


def validate_package(package_path: Path) -> ValidationResult:
    """Validate the portable package contract without executing untrusted code.

    If the engine package later exposes ``alpha_poker.validation.validate_package``,
    its validator is called after these archive safety and manifest checks.
    """
    try:
        with zipfile.ZipFile(package_path) as archive:
            infos = archive.infolist()
            names = {info.filename for info in infos if not info.is_dir()}
            for info in infos:
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts:
                    return ValidationResult(False, "Archive rejected.\n", "Unsafe archive path")
                if info.file_size > MAX_EXPANDED_BYTES:
                    return ValidationResult(False, "Archive rejected.\n", "File exceeds expanded size limit")
            if sum(info.file_size for info in infos) > MAX_EXPANDED_BYTES:
                return ValidationResult(False, "Archive rejected.\n", "Expanded package exceeds 10 MB")
            missing = {"bot.py", "bot.json"} - names
            if missing:
                return ValidationResult(False, "Package structure invalid.\n", f"Missing {', '.join(sorted(missing))}")
            manifest = json.loads(archive.read("bot.json"))
            version = manifest.get("api_version")
            if version != "2026-09-01":
                return ValidationResult(False, "Manifest parsed.\n", "Unsupported api_version")
            if not manifest.get("name"):
                return ValidationResult(False, "Manifest parsed.\n", "bot.json must include name")
            if manifest.get("language") != "python":
                return ValidationResult(False, "Manifest parsed.\n", "language must be python")
            if manifest.get("entrypoint") != "bot.py:decide":
                return ValidationResult(False, "Manifest parsed.\n", "entrypoint must be bot.py:decide")
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return ValidationResult(False, "Could not parse package.\n", str(exc))

    logs = "Archive safety checks passed.\nManifest parsed.\nbot.py found.\n"
    sample = {
        "schema_version": "2026-09-01", "match_id": "validation", "hand_id": "smoke",
        "hand_number": 1, "seat": 0, "button_seat": 0, "street": "preflop",
        "hole_cards": ["Ah", "Kd"], "community_cards": [], "pot": 30,
        "stacks": {"0": 1990, "1": 1980}, "committed": {"0": 10, "1": 20},
        "to_call": 10, "min_raise_to": 40, "max_raise_to": 2000,
        "legal_actions": ["fold", "call", "raise", "all_in"], "action_history": [],
        "decision_deadline_ms": 250, "bot_random_seed": 1,
    }
    bot = None
    try:
        bot = load_bot(package_path)
        decision = bot.decide(sample)
        if not isinstance(decision, dict) or decision.get("action") not in sample["legal_actions"]:
            return ValidationResult(False, logs + "Smoke test returned an invalid action.\n", "decide(state) returned an invalid action")
        if decision.get("action") == "raise" and not sample["min_raise_to"] <= decision.get("amount", -1) <= sample["max_raise_to"]:
            return ValidationResult(False, logs + "Smoke test returned an invalid raise.\n", "Raise amount is outside the legal range")
        logs += "Smoke decision passed.\n"
    except TimeoutError:
        return ValidationResult(False, logs + "Smoke decision timed out.\n", "Decision exceeded 250 ms")
    except Exception as exc:
        return ValidationResult(False, logs + "Smoke test failed.\n", f"{type(exc).__name__}: {exc}")
    finally:
        if bot is not None:
            bot.close()
    logs += "Isolated smoke validation complete. Package accepted.\n"
    return ValidationResult(True, logs)


class PortableBot:
    """Adapt a module-level public ``decide`` function to the engine Bot shape."""

    _alpha_poker_enforces_timeout = True

    def __init__(self, package_path: Path, timeout_seconds: float = 0.22):
        self.package_path = package_path
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._working_dir = tempfile.TemporaryDirectory(prefix="alpha-poker-bot-")
        runner = Path(__file__).with_name("bot_runner.py")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0", "LANG": "C.UTF-8"}
        self._process = subprocess.Popen(
            [sys.executable, "-I", "-S", "-u", str(runner), str(package_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=self._working_dir.name,
            env=env,
            start_new_session=True,
        )
        ready = self._read_response(timeout_seconds=1.0)
        if not ready.get("ok") or not ready.get("ready"):
            self.close()
            raise ValueError(str(ready.get("error", "bot runner failed to start")))

    def _read_response(self, timeout_seconds: float) -> dict:
        if not self._process.stdout:
            raise RuntimeError("bot runner has no output pipe")
        selector = selectors.DefaultSelector()
        try:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout_seconds):
                self.close()
                raise TimeoutError("bot decision timed out")
            line = self._process.stdout.readline(8193)
        finally:
            selector.close()
        if not line:
            raise RuntimeError("bot runner exited unexpectedly")
        if len(line.encode("utf-8")) > 8192:
            self.close()
            raise ValueError("bot response exceeded 8 KB")
        response = json.loads(line)
        if not isinstance(response, dict):
            raise ValueError("bot runner returned an invalid response")
        return response

    def decide(self, engine_state):
        with self._lock:
            if self._process.poll() is not None or not self._process.stdin:
                raise RuntimeError("bot runner is not available")
            payload = json.dumps(dict(engine_state), separators=(",", ":"), allow_nan=False)
            try:
                self._process.stdin.write(payload + "\n")
                self._process.stdin.flush()
            except BrokenPipeError as exc:
                raise RuntimeError("bot runner exited unexpectedly") from exc
            response = self._read_response(self.timeout_seconds)
            if not response.get("ok"):
                raise RuntimeError(str(response.get("error", "bot decision failed")))
            return response.get("action")

    def close(self) -> None:
        process = getattr(self, "_process", None)
        if process is not None and process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        working_dir = getattr(self, "_working_dir", None)
        if working_dir is not None:
            working_dir.cleanup()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def load_bot(package_path: Path) -> PortableBot:
    """Launch a bot in a constrained isolated Python subprocess."""
    return PortableBot(package_path)
