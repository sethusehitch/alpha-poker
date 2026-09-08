"""Local dojo matches and explicitly self-reported account progress."""
import hashlib
import fcntl
import json
import os
from pathlib import Path
import secrets
import tempfile
import zipfile

from .dojo_engine.dojo import VERSION, IDS, PackagedBot, catalog
from .dojo_engine.engine import play_hand, shuffled_deal


def state_path():
    return Path(os.environ.get("ALPHA_POKER_DOJO_STATE", Path.home() / ".config/alpha-poker/dojo.json"))


def read_state():
    try:
        data = json.loads(state_path().read_text())
        return data if isinstance(data, dict) and isinstance(data.get("runs", {}), dict) else {}
    except (OSError, ValueError):
        return {}


def save_result(result):
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = read_state()
        data.setdefault("runs", {})[result["run_id"]] = result
        # Bound local metadata. Evidence ZIPs remain independent.
        data["runs"] = dict(list(data["runs"].items())[-1000:])
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".dojo-")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(data, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)


def run(root, opponent, hands, output, username="local"):
    from .main import _check_package, _load_bot, _training_output_path, CliError
    if opponent not in IDS or not 2 <= hands <= 400 or hands % 2:
        raise CliError("Dojo training requires a known opponent and an even hand count from 2 to 400.")
    _check_package(root)
    if username in IDS:
        username = "local-student"
    fingerprint = hashlib.sha256((root / "bot.py").read_bytes() + b"\0" + (root / "bot.json").read_bytes()).hexdigest()
    run_id, seed = "dojo_" + secrets.token_hex(12), secrets.randbelow(2**31)
    destination = _training_output_path(output, run_id)
    if destination.exists():
        raise CliError(f"Output already exists: {destination}. Choose a new ZIP name or directory.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    student = _load_bot(root)
    bot = PackagedBot(opponent)
    rows, net, errors = [], 0, 0
    try:
        for index in range(hands):
            # A pair reuses the same physical seats/cards, swapping the bots.
            seat = index % 2
            bots = (student, bot) if seat == 0 else (bot, student)
            deal = shuffled_deal(seed + index // 2)
            result = play_hand(bots, seed=seed + index // 2, deal=deal, dealer=0,
                hand_id=f"{run_id}_{index+1}", match_id=run_id, hand_number=index+1,
                starting_stack=2000, small_blind=10, big_blind=20, timeout_seconds=.25,
                bot_random_seeds=(seed + index * 2, seed + index * 2 + 1))
            row = result.to_dict()
            row["players"] = [username, opponent] if seat == 0 else [opponent, username]
            rows.append(row)
            net += result.profits[seat]
            errors += sum(e.get("type") == "bot_error" for e in row["events"])
            if (index + 1) % 20 == 0 or index + 1 == hands:
                print(f"Dojo: {index+1}/{hands} hands • net {net:+} play chips", flush=True)
    finally:
        student.close()
    summary = {"source": "local_dojo", "verification": "self_reported", "run_id": run_id,
        "username": username, "opponent": opponent, "opponent_version": VERSION, "bot_sha256": fingerprint,
        "hands_played": hands, "net_chips": net, "bot_errors": errors,
        "qualified": hands >= 200 and net > 0 and errors == 0, "seed": seed}
    with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("summary.json", json.dumps(summary))
        archive.writestr("hands.jsonl", "\n".join(json.dumps(row) for row in rows))
    summary["evidence_path"] = str(destination.resolve())
    try:
        save_result(summary)
    except OSError as exc:
        raise CliError(f"Evidence is safe at {destination}, but local progress could not be saved: {exc}") from exc
    print("Beaten locally!" if summary["qualified"] else "Practice saved. A checkmark needs at least 200 hands, a positive net result, and no bot errors.")
    print("Local practice only. Public Elo unchanged.")
    print(f"Sync to your signed-in account if you want: alpha-poker dojo sync {run_id}")
    saved = read_state().get("runs", {}).values()
    beaten = {r.get("opponent") for r in saved if r.get("qualified") and r.get("opponent_version") == VERSION}
    next_bot = next((item for item in catalog()["bots"] if item["id"] not in beaten), None)
    if next_bot:
        print(f"Suggested next: {next_bot['name']} ({next_bot['rating']} Dojo Elo). Ask the student before another run.")
        print(f"View opponent: https://alphapoker.io/training?opponent={next_bot['id']}")
    return destination


def command(args):
    from .main import _http_json, _identity, CliError
    if args.dojo_command == "list":
        data = {**catalog(), "leader": None, "leader_status": "Not fetched (offline)."}
        if not args.offline:
            try:
                remote = _http_json("GET", f"{args.api_url.rstrip('/')}/dojo/opponents")
                data["leader"] = remote.get("leader")
                data["leader_status"] = "Available over WebSocket only." if data["leader"] else "No published leader available."
            except CliError:
                data["leader_status"] = "Could not fetch current leader. Local opponents remain available."
        if args.json:
            print(json.dumps(data))
        else:
            print("Opponent      Name       Difficulty  Dojo Elo   Runs")
            for bot in data["bots"]:
                print(f"{bot['id']:<13} {bot['name']:<10} {bot['difficulty']:<11} {str(bot['rating'] or 'Calibrating'):<10} Locally packaged")
            print(data["rating_note"])
            if data["leader"]:
                leader = data["leader"]
                print(f"leader        {leader['bot_name']} ({leader['username']}) | {leader['elo_rating']} public Elo | WebSocket only")
            else:
                print("leader        " + data["leader_status"])
            print("Run: alpha-poker train . --opponent pebble --hands 200")
        return 0
    runs = read_state().get("runs", {})
    if args.dojo_command == "status":
        progress = {bot: any(r.get("opponent") == bot and r.get("opponent_version") == VERSION and r.get("qualified") for r in runs.values()) for bot in IDS}
        data = {"verification": "self_reported", "version": VERSION, "progress": progress, "runs": list(runs.values())}
        if args.json:
            print(json.dumps(data))
        else:
            print("Local practice on this computer (not verified wins):")
            for bot, beaten in progress.items():
                print(f"{bot}: {'Beaten locally' if beaten else 'Not beaten yet'}")
            for run in list(runs.values())[-5:]:
                print(f"{run['run_id']} | {run['opponent']} | {run['net_chips']:+} play chips")
        return 0
    result = runs.get(args.run_id)
    if not result:
        raise CliError("Local run not found. Use alpha-poker dojo status to list saved runs.")
    username, token = _identity(args.api_url)
    if not token:
        raise CliError("Log in before syncing. Your local evidence is already saved.")
    payload = {key: result[key] for key in ("run_id", "opponent", "opponent_version", "bot_sha256", "hands_played", "net_chips", "bot_errors", "seed")}
    response = _http_json("POST", f"{args.api_url.rstrip('/')}/dojo/results", payload, token=token)
    print(json.dumps(response) if args.json else f"Synced local practice to {username}. Self-reported, not a verified win; public Elo unchanged.")
    return 0
