"""Real isolated WebSocket training -> saved ZIP -> standalone CLI viewer.

PYTHONPATH=server:cli server/.venv/bin/python qa/local_recap_smoke.py
Leaves only its printed temporary evidence directory for browser verification.
Never uses production credentials, databases, or ports.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen
import zipfile

root = Path(__file__).resolve().parents[1]
work = Path(tempfile.mkdtemp(prefix="alpha-local-recap-qa-"))
os.environ["ALPHA_POKER_DATA_DIR"] = str(work / "db")
os.environ["ALPHA_POKER_AUTO_RUN"] = "false"
os.environ["ALPHA_POKER_AUTH_REQUIRED"] = "false"
os.environ["ALPHA_POKER_RECAP_STATE"] = str(work / "latest.json")
os.environ["ALPHA_POKER_CONFIG"] = str(work / "credentials.json")
from alpha_poker_api.main import app
from alpha_poker.engine import play_hand
from alpha_poker_cli.local_recap import Evidence
import uvicorn

sock = socket.socket()
sock.bind(("127.0.0.1", 0))
port = sock.getsockname()[1]
server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
thread.start()
while not server.started:
    if not thread.is_alive():
        raise RuntimeError("Isolated API did not start")
    time.sleep(.05)
try:
    training = subprocess.run([sys.executable, "-m", "alpha_poker_cli", "train", str(root / "starter-kit"), "--hands", "12", "--username", "local-recap-qa",
                               "--api-url", f"http://127.0.0.1:{port}/v1", "--output", str(work / "training.zip")], capture_output=True, text=True, check=True)
    assert "Training complete" in training.stdout
finally:
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()
evidence = Evidence(work / "training.zip")
assert len(evidence.groups) == 1 and len(evidence.groups[0]["hands"]) == 12
assert evidence.complete
for hand in evidence.recap("0")["highlights"]:
    assert len(hand["steps"]) > 1
    assert all(len(cards) == 2 for cards in hand["steps"][0]["hole_cards"])

def passive(state):
    return {"action": "check" if "check" in state["legal_actions"] else "call"}
records = []
for match, names in (("m1", ["alice", "bob"]), ("m2", ["alice", "carol"])):
    for number in range(1, 4):
        r = play_hand([passive, passive], seed=number, hand_id=f"{match}-{number}", hand_number=number, match_id=match).to_dict()
        r["players"] = names
        records.append(r)
with zipfile.ZipFile(work / "matches.zip", "w") as archive:
    archive.writestr("hands.jsonl", "\n".join(json.dumps(r) for r in records))
assert len(Evidence(work / "matches.zip").groups) == 2

# Run entirely from the release ZIP, with no server or repository packages.
kit = work / "kit"
with zipfile.ZipFile(root / "public/alpha-poker-starter.zip") as archive:
    archive.extractall(kit)  # Our own reproducible build, never input evidence.
env = {**os.environ, "PYTHONPATH": str(kit / "cli")}
result = subprocess.run([sys.executable, "-m", "alpha_poker_cli", "recap", "--latest"], env=env, cwd=kit, capture_output=True, text=True, check=True)
url = next(line.split("Local recap: ", 1)[1] for line in result.stdout.splitlines() if line.startswith("Local recap: "))
with urlopen(url + "manifest.json") as response:
    assert len(json.load(response)["groups"][0]["hands"]) == 12
with urlopen(url + "recap/0/8") as response:
    assert json.load(response)["highlights"][0]["hand_number"] == 9
print(json.dumps({"evidence": str(work), "viewer": url, "training_hands": 12, "match_groups": 2, "standalone_kit": "passed"}))
