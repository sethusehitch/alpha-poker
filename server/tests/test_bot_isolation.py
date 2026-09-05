import io
import json
import time
import zipfile

from alpha_poker_api.engine_adapter import validate_package


def bot_package(tmp_path, source: str):
    path = tmp_path / "bot.zip"
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("bot.py", source)
        archive.writestr(
            "bot.json",
            json.dumps({"api_version": "2026-09-01", "name": "Isolation", "language": "python", "entrypoint": "bot.py:decide"}),
        )
    path.write_bytes(data.getvalue())
    return path


def test_safe_standard_library_import_still_works(tmp_path):
    result = validate_package(
        bot_package(tmp_path, "import random\ndef decide(state):\n    return {'action':'call'}\n")
    )
    assert result.accepted


def test_bot_cannot_read_host_files(tmp_path):
    result = validate_package(
        bot_package(tmp_path, "def decide(state):\n    open('/etc/passwd').read()\n    return {'action':'call'}\n")
    )
    assert not result.accepted
    assert "filesystem access is restricted" in result.error


def test_bot_cannot_open_network_sockets(tmp_path):
    result = validate_package(
        bot_package(tmp_path, "import socket\ndef decide(state):\n    socket.socket()\n    return {'action':'call'}\n")
    )
    assert not result.accepted
    assert "operation blocked" in result.error


def test_bot_cannot_launch_shell_commands(tmp_path):
    result = validate_package(
        bot_package(tmp_path, "import os\ndef decide(state):\n    os.system('true')\n    return {'action':'call'}\n")
    )
    assert not result.accepted
    assert "operation blocked" in result.error


def test_bot_cannot_enumerate_host_directories(tmp_path):
    result = validate_package(
        bot_package(tmp_path, "import os\ndef decide(state):\n    os.listdir('/')\n    return {'action':'call'}\n")
    )
    assert not result.accepted
    assert "operation blocked" in result.error


def test_infinite_decision_is_killed_at_deadline(tmp_path):
    started = time.monotonic()
    result = validate_package(
        bot_package(tmp_path, "def decide(state):\n    while True: pass\n")
    )
    assert not result.accepted
    assert "250 ms" in result.error
    assert time.monotonic() - started < 2


def test_bot_output_is_bounded(tmp_path):
    result = validate_package(
        bot_package(tmp_path, "def decide(state):\n    print('x' * 5000)\n    return {'action':'call'}\n")
    )
    assert not result.accepted
    assert "output exceeded 4 KB" in result.error
