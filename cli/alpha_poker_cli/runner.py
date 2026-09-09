"""Dependency-free local bot subprocess using the hosted runner policy."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import resource
import selectors
import subprocess
import sys
import tempfile
import zipfile


MAX_ACTION_BYTES = 4_096
MAX_CAPTURE_BYTES = 4_096
DECISION_TIMEOUT_SECONDS = 0.250
BLOCKED_AUDIT_PREFIXES = (
    "socket.", "subprocess.", "os.system", "os.exec", "os.spawn",
    "os.fork", "os.kill", "os.listdir", "os.scandir", "os.chdir",
    "os.remove", "os.rename", "os.replace", "os.rmdir", "os.mkdir",
    "os.chmod", "os.chown", "os.link", "os.symlink", "os.truncate",
    "os.utime", "pty.", "ctypes.dlopen",
)


class RunnerError(RuntimeError):
    pass


class LimitedText(io.TextIOBase):
    def __init__(self) -> None:
        self.size = 0

    def write(self, value: str) -> int:
        self.size += len(value.encode("utf-8", errors="replace"))
        if self.size > MAX_CAPTURE_BYTES:
            raise RuntimeError("bot output exceeded 4 KB")
        return len(value)


def apply_limits() -> None:
    limits = (
        ("RLIMIT_CORE", 0),
        ("RLIMIT_FSIZE", 1 * 1024 * 1024),
        ("RLIMIT_NOFILE", 32),
        ("RLIMIT_CPU", 24 * 60 * 60),
        ("RLIMIT_AS", 256 * 1024 * 1024),
        ("RLIMIT_STACK", 8 * 1024 * 1024),
    )
    if sys.platform.startswith("linux"):
        limits += (("RLIMIT_NPROC", 0),)
    for name, value in limits:
        kind = getattr(resource, name, None)
        if kind is not None:
            try:
                resource.setrlimit(kind, (value, value))
            except (OSError, ValueError):
                pass


def install_audit_boundary() -> None:
    allowed_root = Path(sys.base_prefix).resolve()

    def audit(event: str, args: tuple[object, ...]) -> None:
        if event.startswith(BLOCKED_AUDIT_PREFIXES):
            raise PermissionError(f"operation blocked by Alpha Poker: {event}")
        if event == "open" and args:
            target = args[0]
            mode = args[1] if len(args) > 1 else "r"
            flags = args[2] if len(args) > 2 else 0
            if isinstance(target, int):
                return
            try:
                Path(os.fspath(target)).resolve().relative_to(allowed_root)
            except (TypeError, ValueError, OSError):
                raise PermissionError("bot filesystem access is restricted")
            if isinstance(mode, str) and any(flag in mode for flag in "wax+"):
                raise PermissionError("bot filesystem writes are disabled")
            if isinstance(flags, int) and flags & (
                os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
            ):
                raise PermissionError("bot filesystem writes are disabled")

    sys.addaudithook(audit)


def _send(protocol: io.TextIOBase, value: dict[str, object]) -> None:
    encoded = json.dumps(value, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_ACTION_BYTES + 1_024:
        encoded = json.dumps({"ok": False, "error": "runner response exceeded limit"})
    protocol.write(encoded + "\n")
    protocol.flush()


def child_main(package_path: Path) -> int:
    protocol = sys.stdout
    sys.stdout = LimitedText()
    sys.stderr = LimitedText()
    try:
        with zipfile.ZipFile(package_path) as archive:
            source = archive.read("bot.py").decode("utf-8")
        apply_limits()
        install_audit_boundary()
        namespace: dict[str, object] = {"__name__": "alpha_poker_bot", "__file__": "bot.py"}
        exec(compile(source, f"{package_path}!/bot.py", "exec"), namespace)
        decide = namespace.get("decide")
        if not callable(decide):
            raise ValueError("bot.py must define decide(state)")
    except BaseException as exc:
        _send(protocol, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1
    _send(protocol, {"ok": True, "ready": True})
    for line in sys.stdin:
        try:
            state = json.loads(line)
            capture = LimitedText()
            sys.stdout = capture
            sys.stderr = capture
            action = decide(state)
            encoded = json.dumps(action, separators=(",", ":"), allow_nan=False).encode("utf-8")
            if len(encoded) > MAX_ACTION_BYTES:
                raise ValueError("action exceeds 4 KB")
            _send(protocol, {"ok": True, "action": action})
        except BaseException as exc:
            _send(protocol, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return 0


class LocalBot:
    """A killable bot process reused for every local decision."""

    _alpha_poker_enforces_timeout = True

    def __init__(self, root: Path, timeout_seconds: float = DECISION_TIMEOUT_SECONDS):
        self.timeout_seconds = timeout_seconds
        self._temporary = tempfile.TemporaryDirectory(prefix="alpha-poker-local-bot-")
        package = Path(self._temporary.name) / "bot.zip"
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(root / "bot.py", "bot.py")
            archive.write(root / "bot.json", "bot.json")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0", "LANG": "C.UTF-8"}
        self._process = subprocess.Popen(
            [sys.executable, "-I", "-S", "-u", str(Path(__file__).resolve()), str(package)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, cwd=self._temporary.name,
            env=env, start_new_session=True,
        )
        ready = self._read(1.0)
        if not ready.get("ok") or not ready.get("ready"):
            self.close()
            raise RunnerError(str(ready.get("error", "bot runner failed to start")))

    def _read(self, timeout_seconds: float) -> dict[str, object]:
        if not self._process.stdout:
            raise RunnerError("bot runner has no output pipe")
        selector = selectors.DefaultSelector()
        try:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout_seconds):
                self.close()
                raise RunnerError("decision exceeded 250 ms")
            line = self._process.stdout.readline(8_193)
        finally:
            selector.close()
        if not line:
            raise RunnerError("bot runner exited unexpectedly")
        if len(line.encode("utf-8")) > 8_192:
            self.close()
            raise RunnerError("bot response exceeded 8 KB")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RunnerError("bot runner returned invalid JSON") from exc
        if not isinstance(response, dict):
            raise RunnerError("bot runner returned an invalid response")
        return response

    def decide(self, state: dict[str, object]) -> object:
        if self._process.poll() is not None or not self._process.stdin:
            raise RunnerError("bot runner is not available")
        try:
            self._process.stdin.write(json.dumps(state, separators=(",", ":"), allow_nan=False) + "\n")
            self._process.stdin.flush()
        except BrokenPipeError as exc:
            raise RunnerError("bot runner exited unexpectedly") from exc
        response = self._read(self.timeout_seconds)
        if not response.get("ok"):
            raise RunnerError(str(response.get("error", "bot decision failed")))
        return response.get("action")

    def close(self) -> None:
        process = getattr(self, "_process", None)
        if process is not None and process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        temporary = getattr(self, "_temporary", None)
        if temporary is not None:
            temporary.cleanup()

    def __enter__(self) -> "LocalBot":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)
    raise SystemExit(child_main(Path(sys.argv[1])))
