import pytest

from tests.conftest import chat

ALL_DOWN = {"detail": "all providers unavailable"}


# --- real failover (provider errors) ---------------------------------------
@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_first_key_fails_second_succeeds(client, provider, status):
    provider.failing["fake-key-one"] = status
    r = chat(client)
    assert r.status_code == 200
    m = r.json()["metadata"]
    assert m["key_id"] == "key_2" and m["fallback_attempts"] == 1
    assert provider.calls == ["fake-key-one", "fake-key-two"]


def test_all_keys_fail_503_and_nothing_saved(client, provider):
    provider.failing = {"fake-key-one": 429, "fake-key-two": 500}
    r = chat(client)
    assert r.status_code == 503 and r.json() == ALL_DOWN
    assert client.get("/sessions/s1/messages").status_code == 404


def test_no_permanent_key_disabling(client, provider):
    provider.failing["fake-key-one"] = 429
    chat(client, message="a")
    provider.failing.clear()
    assert chat(client, message="b").json()["metadata"]["key_id"] == "key_1"


# --- X-Simulate-Failure ----------------------------------------------------
def test_simulate_key1_429_real_call_on_key2(client, provider):
    r = chat(client, headers={"X-Simulate-Failure": "key_1=429"})
    assert r.status_code == 200
    m = r.json()["metadata"]
    assert m["key_id"] == "key_2" and m["fallback_attempts"] == 1
    assert provider.calls == ["fake-key-two"]  # key_1 never called; key_2 really called
    # one-request-only: next request uses key_1 again
    assert chat(client, message="other").json()["metadata"]["key_id"] == "key_1"


def test_simulate_both_keys_503(client, provider):
    r = chat(client, headers={"X-Simulate-Failure": "key_1=429,key_2=500"})
    assert r.status_code == 503 and r.json() == ALL_DOWN
    assert provider.calls == []
    assert client.get("/sessions/s1/messages").status_code == 404


def test_simulate_wildcard(client):
    r = chat(client, headers={"X-Simulate-Failure": "*=429"})
    assert r.status_code == 503 and r.json() == ALL_DOWN
    assert client.get("/sessions/s1/messages").status_code == 404


def test_simulation_disabled_ignores_header(client_no_sim, provider):
    r = chat(client_no_sim, headers={"X-Simulate-Failure": "*=429"})
    assert r.status_code == 200
    assert r.json()["metadata"]["key_id"] == "key_1"


def test_simulation_ignores_unsupported_status(client):
    r = chat(client, headers={"X-Simulate-Failure": "key_1=418,garbage"})
    assert r.json()["metadata"]["fallback_attempts"] == 0


# --- LiteLLM cache ---------------------------------------------------------
def test_cache_hit_same_session_and_across_sessions(client, provider):
    first = chat(client, session_id="A").json()
    assert first["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    second = chat(client, session_id="B").json()  # same first message, different session
    m = second["metadata"]
    assert m["resolution_source"] == "LLM_CACHE"
    assert second["reply"] == first["reply"]
    assert m["key_id"] is None and m["fallback_attempts"] == 0
    assert m["input_tokens"] == first["metadata"]["input_tokens"]
    assert m["output_tokens"] == first["metadata"]["output_tokens"]


def test_cache_hit_is_saved_in_history_with_source(client):
    chat(client, session_id="A")
    chat(client, session_id="B")
    msgs = client.get("/sessions/B/messages").json()["messages"]
    assert msgs[1]["metadata"]["resolution_source"] == "LLM_CACHE"


def test_cache_key_includes_full_history(client, provider):
    # Same final message, but different earlier history -> must NOT hit the cache.
    chat(client, session_id="A", message="my name is Ann")
    chat(client, session_id="B", message="my name is Bob")
    a = chat(client, session_id="A", message="what is my name?").json()
    b = chat(client, session_id="B", message="what is my name?").json()
    assert a["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert b["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    # Identical history + identical message DOES hit.
    chat(client, session_id="C", message="my name is Ann")
    c = chat(client, session_id="C", message="what is my name?").json()
    assert c["metadata"]["resolution_source"] == "LLM_CACHE"
    assert c["reply"] == a["reply"]


def test_different_message_is_not_cached(client):
    chat(client, message="one")
    assert chat(client, session_id="x", message="two").json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"


def test_cache_hit_when_key1_is_down_for_real(client, provider):
    chat(client)  # populate cache via key_1
    provider.failing["fake-key-one"] = 429
    r = chat(client, session_id="other").json()
    assert r["metadata"]["resolution_source"] == "LLM_CACHE"  # cache is key-independent
