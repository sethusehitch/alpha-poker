"""Isolated JSON-lines runner for one uploaded bot.

This process is intentionally dependency-free and launched with Python's
isolated mode. It is a defense-in-depth boundary for a small trusted cohort,
not a replacement for a hardened container sandbox against hostile code.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import resource
import sys
import zipfile


MAX_ACTION_BYTES = 4096
MAX_CAPTURE_BYTES = 4096


class LimitedText(io.TextIOBase):
    def __init__(self) -> None:
        self.size = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8", errors="replace")
        self.size += len(encoded)
        if self.size > MAX_CAPTURE_BYTES:
            raise RuntimeError("bot output exceeded 4 KB")
        return len(value)


def apply_limits() -> None:
    limits = (
        ("RLIMIT_CORE", 0),
        ("RLIMIT_FSIZE", 1 * 1024 * 1024),
        ("RLIMIT_NOFILE", 32),
        # Per-decision wall deadlines are the primary CPU control. This outer
        # emergency ceiling is high enough not to distort a valid long match.
        ("RLIMIT_CPU", 24 * 60 * 60),
        ("RLIMIT_AS", 256 * 1024 * 1024),
        ("RLIMIT_STACK", 8 * 1024 * 1024),
    )
    if sys.platform.startswith("linux"):
        limits += (("RLIMIT_NPROC", 0),)
    for name, value in limits:
        kind = getattr(resource, name, None)
        if kind is None:
            continue
        try:
            resource.setrlimit(kind, (value, value))
        except (OSError, ValueError):
            pass


def install_audit_boundary() -> None:
    allowed_root = Path(sys.base_prefix).resolve()

    def audit(event: str, args: tuple[object, ...]) -> None:
        blocked = (
            "socket.", "subprocess.", "os.system", "os.exec", "os.spawn",
            "os.fork", "os.kill", "os.listdir", "os.scandir", "os.chdir",
            "os.remove", "os.rename", "os.replace", "os.rmdir", "os.mkdir",
            "os.chmod", "os.chown", "os.link", "os.symlink", "os.truncate",
            "os.utime", "pty.", "ctypes.dlopen",
        )
        if event.startswith(blocked):
            raise PermissionError(f"operation blocked by Alpha Poker: {event}")
        if event == "open" and args:
            target = args[0]
            mode = args[1] if len(args) > 1 else "r"
            flags = args[2] if len(args) > 2 else 0
            if isinstance(target, int):
                return
            try:
                resolved = Path(os.fspath(target)).resolve()
                resolved.relative_to(allowed_root)
            except (TypeError, ValueError, OSError):
                raise PermissionError("bot filesystem access is restricted")
            if isinstance(mode, str) and any(flag in mode for flag in "wax+"):
                raise PermissionError("bot filesystem writes are disabled")
            if isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                raise PermissionError("bot filesystem writes are disabled")

    sys.addaudithook(audit)


def send(protocol: io.TextIOBase, value: dict[str, object]) -> None:
    encoded = json.dumps(value, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_ACTION_BYTES + 1024:
        encoded = json.dumps({"ok": False, "error": "runner response exceeded limit"})
    protocol.write(encoded + "\n")
    protocol.flush()


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    package_path = Path(sys.argv[1])
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
        send(protocol, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1
    send(protocol, {"ok": True, "ready": True})

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
            send(protocol, {"ok": True, "action": action})
        except BaseException as exc:
            send(protocol, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
