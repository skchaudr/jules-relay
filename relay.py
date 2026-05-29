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
from typing import AsyncIterator

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
