"""
Jules Relay — live, low-latency, bidirectional text channel
between an operator (M1) and a running Jules session.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections import deque
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RELAY_TOKEN = os.environ["RELAY_TOKEN"]          # crashes fast if missing
MAX_BUFFER = 500
MAX_TEXT = 4096
KEEPALIVE_INTERVAL = 30                          # seconds between SSE keep-alives
SENTRY_DSN = os.getenv("SENTRY_DSN")

# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------
def _sentry_traces_sample_rate() -> float:
    try:
        return float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    except ValueError:
        return 0.1


def _scrub_sentry_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Remove relay message content and auth-bearing request data before export."""
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("headers", None)
        request.pop("cookies", None)
        request.pop("data", None)
        request.pop("env", None)
        request["query_string"] = "[Filtered]"

    for breadcrumb in event.get("breadcrumbs", {}).get("values", []):
        data = breadcrumb.get("data")
        if isinstance(data, dict):
            for key in ("text", "message", "authorization", "token"):
                if key in data:
                    data[key] = "[Filtered]"

    event.setdefault("tags", {})["service"] = "jules-relay"
    return event


def _init_sentry() -> None:
    if not SENTRY_DSN:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
    except Exception:
        return

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FastApiIntegration()],
        environment=os.getenv("SENTRY_ENVIRONMENT", os.getenv("RENDER_SERVICE_NAME", "production")),
        release=os.getenv("SENTRY_RELEASE"),
        traces_sample_rate=_sentry_traces_sample_rate(),
        send_default_pii=False,
        before_send=_scrub_sentry_event,
    )


_init_sentry()

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
buffer: deque[dict] = deque(maxlen=MAX_BUFFER)
_next_id = 0
_cond = asyncio.Condition()
_subscribers = 0


def _next_id_inc() -> int:
    global _next_id
    _next_id += 1
    return _next_id


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def _check_auth(authorization: str | None = Header(None)) -> None:
    if authorization is None or authorization != f"Bearer {RELAY_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class PostMsg(BaseModel):
    model_config = {"extra": "forbid"}

    from_: str = Field(alias="from")
    kind: str
    text: str

    @field_validator("from_")
    @classmethod
    def _valid_from(cls, v: str) -> str:
        if v not in ("m1", "jules"):
            raise ValueError("must be 'm1' or 'jules'")
        return v

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, v: str) -> str:
        if v not in ("STATE", "ASK", "ACK"):
            raise ValueError("must be 'STATE', 'ASK', or 'ACK'")
        return v

    @field_validator("text")
    @classmethod
    def _valid_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        if len(v) > MAX_TEXT:
            raise ValueError(f"max {MAX_TEXT} chars")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _buffer_after(since: int) -> list[dict]:
    return [m for m in buffer if m["id"] > since]


def _format_event(m: dict) -> str:
    return f"event: msg\ndata: {json.dumps(m)}\n\n"


async def _event_stream(since: int) -> AsyncIterator[str]:
    global _subscribers
    _subscribers += 1
    try:
        cursor = since
        for m in _buffer_after(cursor):
            yield _format_event(m)
            cursor = m["id"]
        while True:
            async with _cond:
                try:
                    await asyncio.wait_for(_cond.wait(), timeout=KEEPALIVE_INTERVAL)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
            for m in _buffer_after(cursor):
                yield _format_event(m)
                cursor = m["id"]
    finally:
        _subscribers -= 1


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="jules-relay")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    return PlainTextResponse(str(exc), status_code=400)


@app.get("/health")
async def health():
    return {"ok": True, "buffer": len(buffer), "subscribers": _subscribers}


if os.getenv("ENABLE_SENTRY_TEST_ENDPOINT") == "1":
    @app.get("/debug/sentry-test", dependencies=[Depends(_check_auth)])
    async def sentry_test():
        raise RuntimeError("jules-relay Sentry smoke test")


@app.post("/msg", dependencies=[Depends(_check_auth)])
async def post_msg(msg: PostMsg):
    entry = {
        "id": _next_id_inc(),
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "from": msg.from_,
        "kind": msg.kind,
        "text": msg.text,
    }
    buffer.append(entry)
    async with _cond:
        _cond.notify_all()
    return {"ok": True, "id": entry["id"]}


@app.get("/events", dependencies=[Depends(_check_auth)])
async def events(since: int = Query(0, ge=0)):
    return StreamingResponse(
        _event_stream(since),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
