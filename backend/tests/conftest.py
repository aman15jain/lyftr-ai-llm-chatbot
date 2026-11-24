"""Test fixtures.

Provider calls are faked at the lowest level (`llm_service.call_model`), but the fake
still runs the *real* `litellm.completion` (with `mock_response`), so LiteLLM's real
cache and response objects are exercised. No real API keys are ever used.
"""
import litellm
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import llm_service


class FakeProvider:
    def __init__(self) -> None:
        self.failing: dict[str, int] = {}  # api_key -> HTTP status to raise
        self.calls: list[str] = []  # api keys that reached the "provider"

    def __call__(self, *, model, messages, api_key, timeout):
        self.calls.append(api_key)
        status = self.failing.get(api_key)
        if status == 429:
            raise litellm.RateLimitError("quota", llm_provider="gemini", model=model)
        if status in (500, 502, 503):
            raise litellm.ServiceUnavailableError("down", llm_provider="gemini", model=model)
        # Real LiteLLM call (so the real cache is used); reply depends on the whole conversation.
        reply = f"answer({len(messages)}):{messages[-1]['content']}"
        return litellm.completion(model=model, messages=messages, api_key=api_key, mock_response=reply)


def make_settings(tmp_path, **overrides) -> Settings:
    values = dict(
        llm_api_keys="fake-key-one,fake-key-two",
        llm_model="gemini/gemini-2.0-flash",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        allowed_origins="http://localhost:3000",
        enable_failure_simulation=True,
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def provider(monkeypatch) -> FakeProvider:
    fake = FakeProvider()
    monkeypatch.setattr(llm_service, "call_model", fake)
    return fake


@pytest.fixture
def client(tmp_path, provider):
    with TestClient(create_app(make_settings(tmp_path))) as c:
        yield c


@pytest.fixture
def client_no_sim(tmp_path, provider):
    with TestClient(create_app(make_settings(tmp_path, enable_failure_simulation=False))) as c:
        yield c


def chat(client, session_id="s1", message="What is the capital of France?", headers=None, **extra):
    return client.post("/chat", json={"session_id": session_id, "message": message, **extra}, headers=headers or {})
