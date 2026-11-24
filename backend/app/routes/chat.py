"""The three application endpoints."""
import json
import logging
import time

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from ..schemas import ChatMetadata, ChatRequest, ChatResponse
from ..services import cache_service
from ..services.failover_service import (
    AllProvidersUnavailable,
    UpstreamRejected,
    parse_simulation,
    run_with_failover,
)

logger = logging.getLogger("app.chat")
router = APIRouter()


@router.get("/health")
def health(request: Request):
    settings, db = request.app.state.settings, request.app.state.db
    try:
        db.ping()
        keys = len(settings.api_keys)
        cache_on = cache_service.cache_enabled()
        if keys < 1 or not cache_on:
            raise RuntimeError("no API keys configured or cache disabled")
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "unhealthy", "detail": "service not ready"})
    return {"status": "ok", "keys_configured": keys, "cache_enabled": cache_on}


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    request: Request,
    x_simulate_failure: str | None = Header(default=None),
):
    started = time.perf_counter()
    settings, db = request.app.state.settings, request.app.state.db

    # Failure simulation only works when explicitly enabled; otherwise the header is ignored.
    simulation = parse_simulation(x_simulate_failure) if settings.enable_failure_simulation else {}

    # Full message list: system prompt + stored history + new user message.
    rows = db.get_messages(body.session_id)
    stored_system = next((r.content for r in reversed(rows) if r.role == "system"), None)
    system_prompt = body.system_prompt or stored_system or settings.default_system_prompt
    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": r.role, "content": r.content} for r in rows if r.role in ("user", "assistant")]
    messages.append({"role": "user", "content": body.message})

    try:
        result = run_with_failover(
            model=settings.llm_model,
            messages=messages,
            api_keys=settings.api_keys,
            timeout=settings.llm_timeout_seconds,
            simulation=simulation,
        )
    except AllProvidersUnavailable:
        raise HTTPException(status_code=503, detail="all providers unavailable")
    except UpstreamRejected:
        raise HTTPException(status_code=502, detail="provider rejected the request (check LLM_MODEL)")

    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    metadata = ChatMetadata(
        resolution_source="LLM_CACHE" if result.cache_hit else "LIVE_INFERENCE",
        model=settings.llm_model,
        latency_ms=latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        key_id=result.key_id,
        fallback_attempts=result.fallback_attempts,
    )
    # Only reached on success: user + assistant rows are saved in one transaction.
    new_system = body.system_prompt if body.system_prompt and body.system_prompt != stored_system else None
    db.save_exchange(body.session_id, body.message, result.reply, metadata.model_dump(), system_prompt=new_system)
    return ChatResponse(session_id=body.session_id, reply=result.reply, metadata=metadata)


@router.get("/sessions/{session_id}/messages")
def session_messages(session_id: str, request: Request):
    rows = request.app.state.db.get_messages(session_id)
    if not rows:
        raise HTTPException(status_code=404, detail="session not found")
    out = []
    for r in rows:
        if r.role == "system":
            continue  # never expose the system prompt
        item: dict = {"role": r.role, "content": r.content}
        if r.role == "assistant" and r.metadata_json:
            m = json.loads(r.metadata_json)
            item["metadata"] = {
                "resolution_source": m["resolution_source"],
                "input_tokens": m["input_tokens"],
                "output_tokens": m["output_tokens"],
            }
        out.append(item)
    return {"session_id": session_id, "messages": out}
