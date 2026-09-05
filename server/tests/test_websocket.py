def receive_type(ws, wanted):
    while True:
        message = ws.receive_json()
        if message["type"] == wanted:
            return message


def test_training_websocket_action_and_idempotent_retry(client):
    created = client.post("/v1/training/sessions", json={"username": "builder", "hand_limit": 2}).json()
    with client.websocket_connect(created["websocket_url"]) as ws:
        assert ws.receive_json()["type"] == "connection.ready"
        assert ws.receive_json()["type"] == "session.started"
        request = receive_type(ws, "action.requested")
        assert request["payload"]["deadline_ms"] == 250
        assert request["payload"]["state"]["decision_deadline_ms"] == 250
        message = {
            "type": "action.submit", "client_action_id": "action-1", "action": "fold",
            "hand_id": request["payload"]["hand_id"],
            "turn_id": request["payload"]["turn_id"], "turn_token": request["payload"]["turn_token"],
        }
        ws.send_json(message)
        accepted = ws.receive_json()
        assert accepted["type"] == "action.accepted"
        receive_type(ws, "hand.completed")
        receive_type(ws, "action.requested")
        ws.send_json(message)
        assert ws.receive_json() == accepted


def test_training_websocket_rejects_stale_turn(client):
    created = client.post("/v1/training/sessions", json={"username": "builder", "hand_limit": 1}).json()
    with client.websocket_connect(created["websocket_url"]) as ws:
        ws.receive_json(); ws.receive_json(); request = receive_type(ws, "action.requested")
        ws.send_json({
            "type": "action.submit", "client_action_id": "bad-1", "action": "call",
            "hand_id": request["payload"]["hand_id"],
            "turn_id": request["payload"]["turn_id"], "turn_token": "wrong",
        })
        response = ws.receive_json()
        assert response["type"] == "action.rejected"
        assert response["error"]["code"] == "stale_turn"


def test_training_completes_real_hand_and_exports_history(client):
    import io
    import json
    import zipfile

    created = client.post("/v1/training/sessions", json={"username": "builder", "hand_limit": 1}).json()
    with client.websocket_connect(created["websocket_url"]) as ws:
        while True:
            message = ws.receive_json()
            if message["type"] == "action.requested":
                payload = message["payload"]
                action = "check" if "check" in payload["state"]["legal_actions"] else "call"
                ws.send_json({
                    "type": "action.submit", "client_action_id": f"action-{message['seq']}",
                    "action": action, "hand_id": payload["hand_id"], "turn_id": payload["turn_id"],
                    "turn_token": payload["turn_token"],
                })
            if message["type"] == "session.completed":
                break
    artifact = client.get(f"/v1/training/sessions/{created['session_id']}/artifacts")
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        history = json.loads(archive.read("hands.jsonl").splitlines()[0])
        assert history["match_id"] == created["session_id"]
        assert history["currency"] == "play_chips"
        assert isinstance(history["events"], list)
