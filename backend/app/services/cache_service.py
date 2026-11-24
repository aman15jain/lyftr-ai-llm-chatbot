"""LiteLLM built-in response caching.

We use litellm.Cache (in-memory). LiteLLM builds the cache key from the model and
the full `messages` list (plus sampling params). The API key and our session id
are NOT part of the key, so identical conversations share a cached answer
across sessions and across keys.
"""
import litellm
from litellm import Cache


def configure_cache() -> None:
    """(Re)create the global LiteLLM cache. Called once at app startup."""
    litellm.cache = Cache(type="local")


def cache_enabled() -> bool:
    return litellm.cache is not None


def was_cache_hit(response: object) -> bool:
    """LiteLLM marks responses served from its cache with hidden param `cache_hit=True`."""
    hidden = getattr(response, "_hidden_params", None) or {}
    return hidden.get("cache_hit") is True
