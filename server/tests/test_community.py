from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from alpha_poker_api.config import Settings
from alpha_poker_api.main import create_app


def auth_client(tmp_path: Path, **overrides):
    settings = Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=False,
        auth_required=True,
        **overrides,
    )
    return TestClient(create_app(settings))


def register(client, username, password="correct horse", operator_token=None):
    headers = {"X-Alpha-Operator": operator_token} if operator_token else None
    response = client.post(
        "/v1/auth/register", headers=headers, json={"username": username, "password": password}
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['token']}"}


# --- Auth boundaries -------------------------------------------------------


def test_reading_feature_requests_is_public(client):
    response = client.get("/v1/feature-requests")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


def test_creating_and_voting_require_authentication_when_auth_is_required(tmp_path):
    with auth_client(tmp_path) as client:
        created = client.post("/v1/feature-requests", json={"title": "Watch a hand replay"})
        assert created.status_code == 401
        assert created.json()["error"]["code"] == "authentication_required"

        headers = register(client, "maya")
        posted = client.post("/v1/feature-requests", json={"title": "Watch a hand replay"}, headers=headers)
        assert posted.status_code == 201
        request_id = posted.json()["id"]

        unauth_vote = client.post(f"/v1/feature-requests/{request_id}/vote", json={"value": 1})
        assert unauth_vote.status_code == 401


def test_feature_request_create_defaults_to_local_user_without_auth(client):
    posted = client.post("/v1/feature-requests", json={"title": "Add a dark mode toggle"})
    assert posted.status_code == 201
    assert posted.json()["author"] == "local"


# --- Validation --------------------------------------------------------


def test_title_validation_rejects_short_and_long_titles(client):
    too_short = client.post("/v1/feature-requests", json={"title": "hi"})
    assert too_short.status_code == 400
    assert too_short.json()["error"]["code"] == "validation_error"

    too_long = client.post("/v1/feature-requests", json={"title": "x" * 81})
    assert too_long.status_code == 400


def test_details_validation_rejects_overlong_details(client):
    response = client.post(
        "/v1/feature-requests", json={"title": "A perfectly good title", "details": "x" * 501}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_duplicate_titles_are_rejected(client):
    client.post("/v1/feature-requests", json={"title": "Add replay support"})
    duplicate = client.post("/v1/feature-requests", json={"title": "add replay support"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_request"


def test_untrusted_title_text_is_sanitized(client):
    # Explicit \uXXXX escapes, never literal characters, so this test file
    # itself never contains invisible/formatting code points.
    zero_width_space = "​"
    rtl_override = "‮"
    dirty_title = f"Bad{zero_width_space}idea{rtl_override}title"
    response = client.post("/v1/feature-requests", json={"title": dirty_title})
    assert response.status_code == 201
    cleaned = response.json()["title"]
    assert zero_width_space not in cleaned
    assert rtl_override not in cleaned
    assert cleaned == "Badideatitle"


def test_control_characters_are_rejected_outright(client):
    response = client.post("/v1/feature-requests", json={"title": "Bad\x00title"})
    assert response.status_code == 400


# --- Voting invariants -------------------------------------------------


def test_vote_toggle_switch_and_clear(client):
    created = client.post("/v1/feature-requests", json={"title": "Bot vs bot practice"}).json()
    request_id = created["id"]

    upvoted = client.post(f"/v1/feature-requests/{request_id}/vote", json={"value": 1})
    assert upvoted.json() == {"score": 1, "my_vote": "up"}

    switched = client.post(f"/v1/feature-requests/{request_id}/vote", json={"value": -1})
    assert switched.json() == {"score": -1, "my_vote": "down"}

    cleared = client.post(f"/v1/feature-requests/{request_id}/vote", json={"value": 0})
    assert cleared.json() == {"score": 0, "my_vote": None}


def test_vote_score_reflects_multiple_voters(tmp_path):
    with auth_client(tmp_path) as client:
        maya = register(client, "maya")
        leo = register(client, "leo")
        request_id = client.post(
            "/v1/feature-requests", json={"title": "Watch a hand replay"}, headers=maya
        ).json()["id"]
        client.post(f"/v1/feature-requests/{request_id}/vote", json={"value": 1}, headers=maya)
        client.post(f"/v1/feature-requests/{request_id}/vote", json={"value": 1}, headers=leo)
        listed = client.get("/v1/feature-requests", headers=maya).json()["items"][0]
        assert listed["score"] == 2
        assert listed["my_vote"] == "up"
        listed_anonymous = client.get("/v1/feature-requests").json()["items"][0]
        assert listed_anonymous["my_vote"] is None


def test_voting_on_hidden_or_missing_request_returns_404(client):
    response = client.post("/v1/feature-requests/feat_missing/vote", json={"value": 1})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "request_not_found"


# --- Sorting -------------------------------------------------------------


def test_top_tab_sorts_by_score_then_recency(client):
    first = client.post("/v1/feature-requests", json={"title": "First idea here"}).json()
    second = client.post("/v1/feature-requests", json={"title": "Second idea here"}).json()
    client.post(f"/v1/feature-requests/{second['id']}/vote", json={"value": 1})

    top = client.get("/v1/feature-requests?tab=top").json()["items"]
    assert [item["id"] for item in top] == [second["id"], first["id"]]


def test_new_tab_sorts_by_recency_regardless_of_score(client):
    first = client.post("/v1/feature-requests", json={"title": "First idea here"}).json()
    second = client.post("/v1/feature-requests", json={"title": "Second idea here"}).json()
    client.post(f"/v1/feature-requests/{first['id']}/vote", json={"value": 1})

    new = client.get("/v1/feature-requests?tab=new").json()["items"]
    assert [item["id"] for item in new] == [second["id"], first["id"]]


def test_completed_tab_separates_finished_requests_and_supports_old_links(client):
    submitted_request = client.post("/v1/feature-requests", json={"title": "Stays submitted forever"}).json()
    planned_request = client.post("/v1/feature-requests", json={"title": "Gets planned soon"}).json()
    in_progress_request = client.post("/v1/feature-requests", json={"title": "Being built right now"}).json()
    shipped_request = client.post("/v1/feature-requests", json={"title": "Already shipped it"}).json()
    declined_request = client.post("/v1/feature-requests", json={"title": "Was declined outright"}).json()
    client.patch(f"/v1/feature-requests/{planned_request['id']}", json={"status": "planned"})
    client.patch(f"/v1/feature-requests/{in_progress_request['id']}", json={"status": "in_progress"})
    client.patch(f"/v1/feature-requests/{shipped_request['id']}", json={"status": "shipped"})
    client.patch(f"/v1/feature-requests/{declined_request['id']}", json={"status": "declined"})

    planned = client.get("/v1/feature-requests?tab=planned").json()["items"]
    planned_ids = [item["id"] for item in planned]
    assert planned_ids == [shipped_request["id"]]
    assert client.get("/v1/feature-requests?tab=completed").json()["items"] == planned
    for tab in ("top", "new"):
        active_ids = [item["id"] for item in client.get(f"/v1/feature-requests?tab={tab}").json()["items"]]
        assert shipped_request["id"] not in active_ids
        assert planned_request["id"] in active_ids
        assert in_progress_request["id"] in active_ids
    assert submitted_request["id"] not in planned_ids
    assert declined_request["id"] not in planned_ids


def test_unknown_tab_falls_back_to_top(client):
    created = client.post("/v1/feature-requests", json={"title": "Some idea worth trying"}).json()
    fallback = client.get("/v1/feature-requests?tab=bogus").json()["items"]
    assert [item["id"] for item in fallback] == [created["id"]]


def test_pagination_returns_next_cursor_when_more_rows_exist(client):
    from alpha_poker_api.db import now_iso

    db = client.app.state.db
    timestamp = now_iso()
    for index in range(26):
        db.execute(
            "INSERT INTO feature_requests(id,title,details,status,author_username,hidden,created_at,updated_at) "
            "VALUES(?,?,NULL,'submitted','local',0,?,?)",
            (f"feat_seed_{index:02d}", f"Idea number {index:02d}", timestamp, timestamp),
        )
    first_page = client.get("/v1/feature-requests").json()
    assert len(first_page["items"]) == 25
    assert first_page["next_cursor"] == "25"
    second_page = client.get(f"/v1/feature-requests?cursor={first_page['next_cursor']}").json()
    assert len(second_page["items"]) == 1
    assert second_page["next_cursor"] is None


# --- Lifecycle statuses ----------------------------------------------------


def test_new_feature_request_defaults_to_submitted_status(client):
    created = client.post("/v1/feature-requests", json={"title": "A brand new idea"}).json()
    assert created["status"] == "submitted"


def test_status_update_accepts_every_lifecycle_status(tmp_path):
    with auth_client(tmp_path, operator_usernames=frozenset({"opperson"}), operator_token="op-secret") as client:
        operator = register(client, "opperson", operator_token="op-secret")
        request_id = client.post(
            "/v1/feature-requests", json={"title": "Cycle through every status"}, headers=operator
        ).json()["id"]
        for status in ("under_review", "planned", "in_progress", "shipped", "declined", "submitted"):
            response = client.patch(
                f"/v1/feature-requests/{request_id}", json={"status": status}, headers=operator
            )
            assert response.status_code == 200
            assert response.json()["status"] == status


# --- Unknown/unrecognized status handling --------------------------------


def test_unknown_status_from_storage_renders_as_submitted(client):
    created = client.post("/v1/feature-requests", json={"title": "Mystery status idea"}).json()
    client.app.state.db.execute(
        "UPDATE feature_requests SET status='some_future_status' WHERE id=?", (created["id"],)
    )
    listed = client.get("/v1/feature-requests").json()["items"][0]
    assert listed["status"] == "submitted"


# --- Public config -----------------------------------------------------------


def test_public_config_exposes_auth_required_without_authentication(client):
    response = client.get("/v1/config")
    assert response.status_code == 200
    assert response.json() == {"auth_required": False, "invite_required": False}


def test_public_config_reflects_hosted_auth_required(tmp_path):
    with auth_client(tmp_path) as client:
        assert client.get("/v1/config").json() == {
            "auth_required": True,
            "invite_required": False,
        }


def test_public_config_reports_invite_requirement_without_exposing_code(tmp_path):
    with auth_client(tmp_path, invite_code="cohort-secret") as client:
        assert client.get("/v1/config").json() == {
            "auth_required": True,
            "invite_required": True,
        }


# --- Moderation ------------------------------------------------------------


def test_status_change_requires_operator(tmp_path):
    with auth_client(tmp_path, operator_usernames=frozenset({"opperson"}), operator_token="op-secret") as client:
        operator = register(client, "opperson", operator_token="op-secret")
        regular = register(client, "regular")
        request_id = client.post(
            "/v1/feature-requests", json={"title": "Needs a status change"}, headers=operator
        ).json()["id"]

        forbidden = client.patch(
            f"/v1/feature-requests/{request_id}", json={"status": "planned"}, headers=regular
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "operator_required"

        allowed = client.patch(
            f"/v1/feature-requests/{request_id}", json={"status": "planned"}, headers=operator
        )
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "planned"


def test_hide_requires_operator_and_removes_from_public_list(tmp_path):
    with auth_client(tmp_path, operator_usernames=frozenset({"opperson"}), operator_token="op-secret") as client:
        operator = register(client, "opperson", operator_token="op-secret")
        request_id = client.post(
            "/v1/feature-requests", json={"title": "Should be hidden"}, headers=operator
        ).json()["id"]

        hidden = client.post(
            f"/v1/feature-requests/{request_id}/hide", json={"hidden": True}, headers=operator
        )
        assert hidden.status_code == 204
        assert client.get("/v1/feature-requests").json()["items"] == []

        restored = client.post(
            f"/v1/feature-requests/{request_id}/hide", json={"hidden": False}, headers=operator
        )
        assert restored.status_code == 204
        assert len(client.get("/v1/feature-requests").json()["items"]) == 1


# --- Promotion idempotency --------------------------------------------------


def test_promote_requires_operator_token_when_auth_required(tmp_path):
    with auth_client(
        tmp_path,
        operator_token="secret-op-token",
        operator_usernames=frozenset({"maya"}),
    ) as client:
        headers = register(client, "maya", operator_token="secret-op-token")
        request_id = client.post(
            "/v1/feature-requests", json={"title": "Promote this idea please"}, headers=headers
        ).json()["id"]

        missing_token = client.post(f"/v1/feature-requests/{request_id}/promote", headers=headers)
        assert missing_token.status_code == 403

        with patch(
            "alpha_poker_api.community.create_github_issue",
            return_value={"number": 42, "url": "https://github.com/sethusehitch/alpha-poker/issues/42"},
        ):
            promoted = client.post(
                f"/v1/feature-requests/{request_id}/promote",
                headers={**headers, "X-Alpha-Operator": "secret-op-token"},
            )
        assert promoted.status_code == 200
        body = promoted.json()
        assert body == {
            "issue_number": 42,
            "issue_url": "https://github.com/sethusehitch/alpha-poker/issues/42",
            "already_promoted": False,
        }


def test_promote_requires_allowlisted_operator_even_with_shared_token(tmp_path):
    with auth_client(
        tmp_path,
        operator_token="secret-op-token",
        operator_usernames=frozenset({"operator"}),
    ) as client:
        headers = register(client, "maya")
        request_id = client.post(
            "/v1/feature-requests", json={"title": "Only operators promote"}, headers=headers
        ).json()["id"]
        response = client.post(
            f"/v1/feature-requests/{request_id}/promote",
            headers={**headers, "X-Alpha-Operator": "secret-op-token"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "operator_required"


def test_promotion_is_idempotent(client):
    request_id = client.post(
        "/v1/feature-requests", json={"title": "Promote this idea twice"}
    ).json()["id"]

    with patch(
        "alpha_poker_api.community.create_github_issue",
        return_value={"number": 7, "url": "https://github.com/sethusehitch/alpha-poker/issues/7"},
    ) as mocked:
        first = client.post(f"/v1/feature-requests/{request_id}/promote")
        second = client.post(f"/v1/feature-requests/{request_id}/promote")

    assert first.json()["already_promoted"] is False
    assert second.json()["already_promoted"] is True
    assert second.json()["issue_number"] == 7
    mocked.assert_called_once()


def test_concurrent_promotion_creates_exactly_one_github_issue(client):
    request_id = client.post(
        "/v1/feature-requests", json={"title": "Promote this concurrently"}
    ).json()["id"]

    def create_once(*_args, **_kwargs):
        time.sleep(0.05)
        return {"number": 9, "url": "https://github.com/sethusehitch/alpha-poker/issues/9"}

    with patch("alpha_poker_api.community.create_github_issue", side_effect=create_once) as mocked:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: client.post(f"/v1/feature-requests/{request_id}/promote"), range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(response.json()["already_promoted"] for response in responses) == [False, True]
    mocked.assert_called_once()


def test_promote_without_github_token_configured_returns_503(client):
    request_id = client.post(
        "/v1/feature-requests", json={"title": "No token configured for this"}
    ).json()["id"]
    response = client.post(f"/v1/feature-requests/{request_id}/promote")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "github_not_configured"


# --- GitHub cache behavior ---------------------------------------------------


def test_github_issues_are_cached_and_served_from_cache(client):
    from alpha_poker_api.db import now_iso

    summary = {
        "good_first_issues": [],
        "open_issue_count": 3,
        "open_pr_count": 1,
        "fetched_at": now_iso(),
    }
    with patch("alpha_poker_api.github.fetch_github_summary", return_value=summary) as mocked:
        first = client.get("/v1/github/issues")
        second = client.get("/v1/github/issues")
    assert first.status_code == 200
    assert first.json()["open_issue_count"] == 3
    assert first.json()["stale"] is False
    assert second.json()["stale"] is False
    mocked.assert_called_once()


def test_concurrent_github_cache_miss_is_single_flight(client):
    from alpha_poker_api.db import now_iso

    summary = {
        "good_first_issues": [],
        "open_issue_count": 3,
        "open_pr_count": 1,
        "fetched_at": now_iso(),
    }

    def fetch_once(_settings):
        time.sleep(0.05)
        return summary

    with patch("alpha_poker_api.github.fetch_github_summary", side_effect=fetch_once) as mocked:
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda _: client.get("/v1/github/issues"), range(8)))

    assert all(response.status_code == 200 for response in responses)
    mocked.assert_called_once()


def test_github_outage_serves_stale_cache_when_available(client):
    from alpha_poker_api.db import now_iso

    summary = {
        "good_first_issues": [],
        "open_issue_count": 5,
        "open_pr_count": 2,
        "fetched_at": now_iso(),
    }
    with patch("alpha_poker_api.github.fetch_github_summary", return_value=summary):
        client.get("/v1/github/issues")
    with patch("alpha_poker_api.github.fetch_github_summary", side_effect=RuntimeError("boom")):
        client.app.state.db.execute(
            "UPDATE github_cache SET fetched_at='2000-01-01T00:00:00Z' WHERE cache_key='contribute_summary'"
        )
        stale = client.get("/v1/github/issues")
    assert stale.status_code == 200
    assert stale.json()["stale"] is True
    assert stale.json()["open_issue_count"] == 5


def test_github_outage_without_cache_returns_503(client):
    with patch("alpha_poker_api.github.fetch_github_summary", side_effect=RuntimeError("boom")):
        response = client.get("/v1/github/issues")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "api_unavailable"


def test_github_issue_urls_are_built_from_configured_repo_not_the_api_response():
    from alpha_poker_api.github import _public_issue

    issue = _public_issue({
        "number": 12,
        "title": "Improve lobby empty state",
        "labels": [{"name": "good first issue"}, {"name": "frontend"}],
        "assignee": {"login": "octocat"},
        "comments": 3,
        "html_url": "https://evil.example.com/not-the-repo",
    })
    assert issue["url"] == "https://github.com/sethusehitch/alpha-poker/issues/12"
    assert issue["labels"] == ["good first issue", "frontend"]
    assert issue["assignee"] == "octocat"


# --- Rate limits -------------------------------------------------------------


def test_feature_creation_is_rate_limited_per_account(client):
    for index in range(5):
        response = client.post("/v1/feature-requests", json={"title": f"Rate limited idea {index}"})
        assert response.status_code == 201
    limited = client.post("/v1/feature-requests", json={"title": "One too many ideas here"})
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"


def test_feedback_is_rate_limited_per_account(client):
    for index in range(5):
        response = client.post(
            "/v1/feedback", json={"type": "idea", "message": f"idea {index}", "path": "/feature-requests"}
        )
        assert response.status_code == 204
    limited = client.post(
        "/v1/feedback", json={"type": "idea", "message": "one too many", "path": "/feature-requests"}
    )
    assert limited.status_code == 429


# --- Feedback ----------------------------------------------------------------


def test_feedback_submission_persists_coarse_context_and_strips_query_and_hash(client):
    response = client.post(
        "/v1/feedback",
        headers={"User-Agent": "AlphaPoker-Test/1.0"},
        json={"type": "bug", "message": "Something broke", "path": "/feature-requests?tab=new#top"},
    )
    assert response.status_code == 204
    row = client.app.state.db.one("SELECT username, path, type, message, client_context FROM feedback")
    assert row["username"] is None
    assert row["path"] == "/feature-requests"
    assert row["type"] == "bug"
    assert row["message"] == "Something broke"
    assert row["client_context"] == "Other/desktop"


def test_feedback_message_length_is_validated(client):
    too_short = client.post(
        "/v1/feedback", json={"type": "idea", "message": "hi", "path": "/"}
    )
    assert too_short.status_code == 400
    too_long = client.post(
        "/v1/feedback", json={"type": "idea", "message": "x" * 501, "path": "/"}
    )
    assert too_long.status_code == 400


def test_feedback_allows_anonymous_submission_when_auth_is_required(tmp_path):
    with auth_client(tmp_path) as client:
        response = client.post(
            "/v1/feedback", json={"type": "idea", "message": "A good idea", "path": "/"}
        )
        assert response.status_code == 204
        assert client.app.state.db.one("SELECT username FROM feedback")["username"] is None


def test_feedback_older_than_retention_window_is_deleted_on_startup(tmp_path):
    settings = Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=False,
        feedback_retention_days=30,
    )
    with TestClient(create_app(settings)) as client:
        client.app.state.db.execute(
            "INSERT INTO feedback(id,username,type,message,path,client_context,created_at) VALUES(?,?,?,?,?,?,?)",
            ("fb_old", None, "idea", "Old feedback", "/", "Other/desktop", "2000-01-01T00:00:00Z"),
        )
    with TestClient(create_app(settings)) as restarted:
        assert restarted.app.state.db.one("SELECT id FROM feedback WHERE id='fb_old'") is None
