import json
import sqlite3

from tests.conftest import chat, make_settings


# --- health ----------------------------------------------------------------
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "keys_configured": 2, "cache_enabled": True}


def test_only_three_routes_exposed(client):
    for path in ("/docs", "/openapi.json", "/redoc"):
        assert client.get(path).status_code == 404


# --- chat success ----------------------------------------------------------
def test_successful_chat(client):
    r = chat(client)
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "s1"
    assert body["reply"].startswith("answer(")
    m = body["metadata"]
    assert set(m) == {"resolution_source", "model", "latency_ms", "input_tokens",
                      "output_tokens", "key_id", "fallback_attempts"}
    assert m["resolution_source"] == "LIVE_INFERENCE"
    assert m["model"] == "gemini/gemini-2.0-flash"
    assert isinstance(m["latency_ms"], int)
    assert m["input_tokens"] > 0 and m["output_tokens"] > 0
    assert m["key_id"] == "key_1" and m["fallback_attempts"] == 0


def test_api_key_never_in_response(client):
    assert "fake-key" not in chat(client).text


# --- validation ------------------------------------------------------------
def test_missing_session_id(client):
    r = client.post("/chat", json={"message": "hi"})
    assert r.status_code == 422 and "detail" in r.json()


def test_missing_message(client):
    assert client.post("/chat", json={"session_id": "s"}).status_code == 422


def test_empty_and_whitespace_message(client):
    assert chat(client, message="").status_code == 422
    assert chat(client, message="    ").status_code == 422


def test_message_too_long(client):
    assert chat(client, message="a" * 4001).status_code == 422
    assert chat(client, message="a" * 4000).status_code == 200


def test_session_id_length(client):
    assert chat(client, session_id="").status_code == 422
    assert chat(client, session_id="x" * 129).status_code == 422


def test_malformed_json(client):
    r = client.post("/chat", content="{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and "detail" in r.json()


def test_validation_errors_not_stored(client):
    chat(client, session_id="bad", message="")
    assert client.get("/sessions/bad/messages").status_code == 404


# --- history ---------------------------------------------------------------
def test_unknown_session_404(client):
    r = client.get("/sessions/nope/messages")
    assert r.status_code == 404 and r.json() == {"detail": "session not found"}
    # Looking up history must not create the session.
    assert client.get("/sessions/nope/messages").status_code == 404


def test_history_oldest_first_with_metadata(client):
    chat(client, message="first")
    chat(client, message="second")
    r = client.get("/sessions/s1/messages")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[0]["content"] == "first" and msgs[2]["content"] == "second"
    assert "metadata" not in msgs[0]
    meta = msgs[1]["metadata"]
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert meta["input_tokens"] > 0 and meta["output_tokens"] > 0


def test_history_is_sent_to_llm_and_system_prompt_hidden(client, provider, monkeypatch):
    seen = []
    orig = provider.__call__

    def spy(**kw):
        seen.append(kw["messages"])
        return orig(**kw)

    from app.services import llm_service
    monkeypatch.setattr(llm_service, "call_model", spy)
    chat(client, message="one", system_prompt="Be terse.")
    chat(client, message="two")
    assert seen[1] == [
        {"role": "system", "content": "Be terse."},  # session's system prompt is remembered
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "answer(2):one"},
        {"role": "user", "content": "two"},
    ]
    msgs = client.get("/sessions/s1/messages").json()["messages"]
    assert all(m["role"] != "system" for m in msgs) and len(msgs) == 4


def test_sessions_are_separate(client):
    chat(client, session_id="A", message="alpha")
    chat(client, session_id="B", message="beta")
    a = client.get("/sessions/A/messages").json()["messages"]
    b = client.get("/sessions/B/messages").json()["messages"]
    assert [m["content"] for m in a if m["role"] == "user"] == ["alpha"]
    assert [m["content"] for m in b if m["role"] == "user"] == ["beta"]


def test_metadata_stored_in_sqlite_as_json(tmp_path, provider):
    from fastapi.testclient import TestClient
    from app.main import create_app
    s = make_settings(tmp_path)
    with TestClient(create_app(s)) as c:
        chat(c)
    row = sqlite3.connect(tmp_path / "test.db").execute(
        "SELECT role, metadata, created_at FROM messages WHERE role='assistant'").fetchone()
    meta = json.loads(row[1])
    assert meta["resolution_source"] == "LIVE_INFERENCE" and meta["key_id"] == "key_1"
    assert row[2]


def test_history_persists_across_restart(tmp_path, provider):
    from fastapi.testclient import TestClient
    from app.main import create_app
    s = make_settings(tmp_path)
    with TestClient(create_app(s)) as c:
        chat(c, message="remember me")
    with TestClient(create_app(s)) as c2:
        assert len(c2.get("/sessions/s1/messages").json()["messages"]) == 2


# --- error format ----------------------------------------------------------
def test_unknown_route_is_json(client):
    r = client.get("/nothing")
    assert r.status_code == 404 and r.json()["detail"]
