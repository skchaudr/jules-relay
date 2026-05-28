# Jules Relay — Implementation Spec

A live, low-latency, bidirectional text channel between an operator (M1) and a running Jules session, brokered by a disposable public HTTPS relay.

Implementation target: **Cline + GLM-5**. Deployment target: **Render** (already integrated with Jules).

---

## 1. Goal

Operator and a Jules sandbox session exchange `STATE / ASK / ACK` messages in real time during a task. Jules can only call outward (Google sandbox = no inbound), so both sides connect *out* to a small public relay. The relay holds an SSE stream open to each subscriber and pushes new messages within ~1s of `POST /msg`.

## 2. Architectural ground truth

1. Jules VM is outbound-HTTPS only. No inbound. No SSH. No listening port.
2. The relay is public HTTPS. Both sides are equal clients of it.
3. Assume the Jules-side bearer token leaks mid-session. Blast radius must stop at the relay.
4. The operator's tailnet, pi-big, GCP, GitHub, and Google account are **off-limits** to Jules. They never appear in env vars, messages, or relay state.

## 3. Wire protocol

Three endpoints. All require `Authorization: Bearer <RELAY_TOKEN>`, including SSE.

### `POST /msg`

Request:
```json
{ "from": "m1" | "jules",
  "kind": "STATE" | "ASK" | "ACK",
  "text": "string" }
```
Server assigns `id` and `ts`. Response:
```json
{ "ok": true, "id": 42 }
```

### `GET /events?since=<id>` (Server-Sent Events)

On connect, the server first replays any buffered messages with `id > since`, then streams new ones live as they arrive. Each event:
```
event: msg
data: {"id": 43, "ts": "...", "from": "...", "kind": "...", "text": "..."}

```
`since` is optional; default `0` (replay full buffer). This is the reconnect cursor.

### `GET /health`
Returns `{ "ok": true, "buffer": <n>, "subscribers": <n> }`. No auth.

## 4. Message envelope (server-assigned fields bold)

| Field | Type | Source | Notes |
|---|---|---|---|
| **`id`** | int | server | monotonic, starts at 1 |
| **`ts`** | string | server | ISO-8601 UTC, e.g. `2026-05-27T19:14:03Z` |
| `from` | enum | client | `"m1"` or `"jules"` only. Reject others with 400. |
| `kind` | enum | client | `"STATE" \| "ASK" \| "ACK"` only. Reject others with 400. |
| `text` | string | client | required, non-empty, ≤ 4096 chars. |

Reject `extra` fields (Pydantic `extra="forbid"`).

## 5. Auth

- Single shared secret: `RELAY_TOKEN` (env var on relay; same value on both clients).
- Send as `Authorization: Bearer <RELAY_TOKEN>` on `/msg` and `/events`.
- Missing/wrong token → 401.
- Token TTL: rotated by operator on a 24h cadence (no server-side expiry needed for MVP).

## 6. Storage

- In-memory `collections.deque(maxlen=N)`, `N=500`.
- No DB. Restart = empty buffer. `id` resets to 1 on restart (documented behavior; `since` clients will simply replay everything).

## 7. Implementation stack

- Python 3.11+
- FastAPI + uvicorn
- `asyncio.Condition` to wake SSE subscribers on new message
- `pydantic` for request validation (`extra="forbid"`)
- Zero other deps

SSE generator pattern:
```python
async def event_stream(since: int):
    # 1. replay buffered messages with id > since
    # 2. then: while True: await cond.wait(); yield new
    while True:
        async with cond:
            await cond.wait()
        for m in drain_new():
            yield f"event: msg\ndata: {json.dumps(m)}\n\n"
```

## 8. File layout

```
jules-relay/
├── relay.py          # the whole service (~80–120 lines)
├── requirements.txt  # fastapi, uvicorn, pydantic
├── render.yaml       # Render service definition
├── README.md         # how to deploy + rotate token
└── SPEC.md           # this file
```

## 9. Render deployment

`render.yaml`:
```yaml
services:
  - type: web
    name: jules-relay
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn relay:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: RELAY_TOKEN
        generateValue: true   # Render generates a strong random token
```

After deploy:
- Copy `RELAY_TOKEN` from Render dashboard.
- Copy the service URL (e.g. `https://jules-relay-xxxx.onrender.com`).

## 10. M1 shell helpers (place in `~/.zshrc` or a sourced file)

```bash
export RELAY_URL="https://jules-relay-xxxx.onrender.com"
export RELAY_TOKEN="..."   # from Render env

# Send (default kind=ASK; override with: sayj STATE "..." or sayj ACK "...")
sayj() {
  local kind="ASK"
  case "$1" in STATE|ASK|ACK) kind="$1"; shift;; esac
  curl -sS "$RELAY_URL/msg" \
    -H "Authorization: Bearer $RELAY_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(jq -nc --arg k "$kind" --arg t "$*" \
          '{from:"m1", kind:$k, text:$t}')"
  echo
}

# Listen — stream events, optionally from a cursor
listenj() {
  curl -N "$RELAY_URL/events?since=${1:-0}" \
    -H "Authorization: Bearer $RELAY_TOKEN"
}
```

Naming: `sayj` not `say` (macOS `say` = TTS).

## 11. Jules-side configuration

In the Jules repo's `AGENTS.md`, append:

```markdown
## Operator relay

This task may have a live operator on the other end of an HTTPS relay.

Env vars (set per-session):
- RELAY_URL — base URL of the relay
- RELAY_TOKEN — bearer token

On session start, open an SSE subscription:

    curl -N "$RELAY_URL/events" -H "Authorization: Bearer $RELAY_TOKEN" &

Behavior rules:
- Post `STATE:` before any high-risk or irreversible step (deploy, migration,
  destructive file ops, network calls with side effects).
- If a message arrives with `from=m1` and `kind=ASK`, **pause the specific
  gated decision it refers to** until an `ACK` arrives from `m1`, or until
  the relay becomes unreachable. Continue everything else.
- If the relay is unreachable (connection refused, 5xx, timeout): proceed
  per the original task brief, EXCEPT for actions explicitly marked
  "operator-gated" in the task.
- NEVER place secrets, credentials, private URLs, tokens, SSH details, or
  sensitive repo contents in relay messages. Coordination text only.
```

## 12. Loss budget (compromise model)

| If leaked | Worst case | Mitigation |
|---|---|---|
| `RELAY_TOKEN` | Attacker can read/inject messages on this relay only | Rotate in Render dashboard; redeploy; old token invalid immediately |
| `RELAY_URL` | Attacker hits authless `/health` | Nothing |
| Message text | Coordination text is read | Hard rule §11: no secrets in messages |
| Whole relay host | Throwaway Render service compromised | Delete the service; redeploy fresh; tailnet, GCP, GitHub, Google account untouched |

## 13. Acceptance tests

Run from the M1 against a deployed relay while a Jules task is in progress.

1. **Round-trip latency.** `listenj &`, then have Jules `curl POST /msg` with a `STATE:`. Event appears on M1 stdout within 1.5s.
2. **Operator → Jules.** `sayj ASK "skip the migration step?"`. Jules's SSE subscriber prints the event within 1.5s and Jules's logic pauses the migration.
3. **ACK unblocks.** `sayj ACK "yes, skip"`. Jules resumes the gated decision and proceeds.
4. **Reconnect with cursor.** Kill `listenj`, send 3 `STATE`s, reconnect with `listenj $LAST_ID`. The 3 missed messages replay, then live stream resumes.
5. **Relay outage.** Stop the Render service. Jules logs the disconnect and continues non-gated work. Operator-gated steps remain paused.
6. **Token rotation.** Change `RELAY_TOKEN` in Render → redeploy. Old `listenj`/`sayj` start returning 401 on next request. Update local env → works again.
7. **Validation.** `POST /msg` with `from=mallory` or `kind=YELL` returns 400 and is not stored.
8. **Auth.** Any request without bearer, or with wrong bearer, returns 401.

## 14. Explicit non-goals

Do not add (now or in v1.1):
- Per-side tokens, JWT, OAuth, mTLS.
- Database persistence, message history beyond the in-memory ring.
- WebSockets, message queues, brokers.
- MCP tool wrappers around the relay.
- Tailscale, VPN, GitHub-issue fallback.
- Reuse of the dormant `agent-bus` code on pi-big.
- Multi-agent fan-out (channel is 1:1 M1 ↔ Jules for v1).

## 15. Definition of done

- `relay.py` deploys cleanly to Render from a fresh checkout.
- All 8 acceptance tests in §13 pass.
- `README.md` documents: deploy, rotate token, tear down.
- Total `relay.py` is < 150 lines.
