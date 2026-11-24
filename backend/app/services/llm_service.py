"""Thin wrapper around litellm.completion (the single place that talks to the provider)."""
from typing import Any

import litellm


def call_model(*, model: str, messages: list[dict], api_key: str, timeout: float) -> Any:
    """One real LiteLLM call using one specific API key.

    num_retries=0: retrying is handled by *our* key failover, not by LiteLLM
    hammering the same exhausted key.
    """
    return litellm.completion(
        model=model,
        messages=messages,
        api_key=api_key,
        timeout=timeout,
        num_retries=0,
    )
