from test_rivals_api import auth_client, participant, wait_for_challenge


def test_notification_fanout_unread_and_authorization(tmp_path):
    with auth_client(tmp_path) as client:
        alice = participant(client, "alice", "call")
        bob = participant(client, "bob", "fold")
        created = client.post("/v1/challenges", headers=alice, json={"opponent_username": "bob"}).json()

        incoming = client.get("/v1/notifications?unread=true", headers=bob).json()
        assert incoming["unread_count"] == 1
        assert incoming["items"][0]["type"] == "challenge_received"
        notification_id = incoming["items"][0]["notification_id"]
        assert client.post(f"/v1/notifications/{notification_id}/read", headers=alice).status_code == 403
        read = client.post(f"/v1/notifications/{notification_id}/read", headers=bob).json()
        assert read["read_at"]

        client.post(f"/v1/challenges/{created['challenge_id']}/accept", headers=bob)
        completed = wait_for_challenge(client, created["challenge_id"], alice)
        assert completed["status"] == "completed"
        assert completed["winner_username"] in {"alice", "bob", None}
        assert max(completed["series_score"].values()) == 3
        alice_types = {row["type"] for row in client.get("/v1/notifications", headers=alice).json()["items"]}
        bob_types = {row["type"] for row in client.get("/v1/notifications", headers=bob).json()["items"]}
        assert alice_types & {"challenge_won", "challenge_lost", "challenge_drawn"}
        assert bob_types & {"challenge_won", "challenge_lost", "challenge_drawn"}
        result_notification = next(
            row for row in client.get("/v1/notifications", headers=alice).json()["items"]
            if row["type"] != "challenge_received"
        )
        assert result_notification["payload"]["bot_names"] == {
            "challenger": "alice-bot", "challenged": "bob-bot"
        }
        assert result_notification["payload"]["series_score"] == completed["series_score"]
        assert client.post("/v1/notifications/read-all", headers=alice).json()["read_count"] >= 1
