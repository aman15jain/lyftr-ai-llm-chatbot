"""Ordered API-key failover plus the X-Simulate-Failure test hook."""
import logging
from dataclasses import dataclass

import litellm

from . import cache_service, llm_service

logger = logging.getLogger("app.failover")

SIMULATABLE_STATUSES = {429, 500, 502, 503}
# 401/403 mean *this key* is bad/revoked, so trying the next key is sensible.
FAILOVER_STATUSES = {401, 403, 408, 429}


class AllProvidersUnavailable(Exception):
    pass


class UpstreamRejected(Exception):
    """Provider rejected the request itself (e.g. bad model name); other keys won't help."""


@dataclass
class LLMResult:
    reply: str
    input_tokens: int
    output_tokens: int
    key_id: str | None
    fallback_attempts: int
    cache_hit: bool


def parse_simulation(header: str | None) -> dict[str, int]:
    """'key_1=429,key_2=500' or '*=429' -> {'key_1': 429, ...}. Invalid parts are ignored."""
    result: dict[str, int] = {}
    if not header:
        return result
    for part in header.split(","):
        name, sep, status = part.strip().partition("=")
        name, status = name.strip(), status.strip()
        if sep and name and status.isdigit() and int(status) in SIMULATABLE_STATUSES:
            result[name] = int(status)
    return result


def _is_failover_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and (status in FAILOVER_STATUSES or status >= 500):
        return True
    return isinstance(
        exc,
        (
            litellm.RateLimitError,
            litellm.ServiceUnavailableError,
            litellm.InternalServerError,
            litellm.APIConnectionError,
            litellm.Timeout,
            litellm.AuthenticationError,
        ),
    )


def run_with_failover(
    *,
    model: str,
    messages: list[dict],
    api_keys: list[str],
    timeout: float,
    simulation: dict[str, int],
) -> LLMResult:
    """Try key_1, key_2, ... in order; return the first success."""
    failures = 0
    for index, api_key in enumerate(api_keys, start=1):
        key_id = f"key_{index}"
        simulated = simulation.get(key_id, simulation.get("*"))
        if simulated is not None:
            # Pretend this key failed for THIS request only. No state is kept.
            logger.warning("%s: simulated failure %s", key_id, simulated)
            failures += 1
            continue
        try:
            response = llm_service.call_model(
                model=model, messages=messages, api_key=api_key, timeout=timeout
            )
        except Exception as exc:  # noqa: BLE001 - classified below; message never logged (may hold key)
            status = getattr(exc, "status_code", None)
            if _is_failover_error(exc):
                logger.warning("%s failed (%s, status=%s); trying next key", key_id, type(exc).__name__, status)
                failures += 1
                continue
            logger.error("%s: non-failover provider error %s (status=%s)", key_id, type(exc).__name__, status)
            raise UpstreamRejected(type(exc).__name__) from None

        hit = cache_service.was_cache_hit(response)
        usage = response.usage
        return LLMResult(
            reply=response.choices[0].message.content or "",
            input_tokens=int(usage.prompt_tokens or 0),
            output_tokens=int(usage.completion_tokens or 0),
            key_id=None if hit else key_id,
            fallback_attempts=0 if hit else failures,
            cache_hit=hit,
        )
    raise AllProvidersUnavailable()
