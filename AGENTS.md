# AGENTS.md

## Operator relay

This task may have a live operator on the other end of an HTTPS relay
(this repo: https://github.com/skchaudr/jules-relay).

Env vars (set per-session):
- `RELAY_URL` — base URL of the relay
- `RELAY_TOKEN` — bearer token

On session start, open an SSE subscription:

```bash
curl -N "$RELAY_URL/events" -H "Authorization: Bearer $RELAY_TOKEN" &
```

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

### Message envelope

`POST $RELAY_URL/msg` with `Authorization: Bearer $RELAY_TOKEN`:

```json
{ "from": "jules", "kind": "STATE" | "ASK" | "ACK", "text": "..." }
```

`text` must be ≤ 4096 chars, non-empty.

## Environment

| Var | Purpose | Set by |
|---|---|---|
| `RELAY_URL` | Relay endpoint | Jules session env |
| `RELAY_TOKEN` | Relay auth | Jules session env |

## Project snapshot

- **Language:** Python 3.11+ (FastAPI + uvicorn)
- **Install:** `pip install -r requirements.txt`
- **Test:** `RELAY_TOKEN=test pytest -q test_relay.py`
- **Lint:** none configured
- **Deploy:** Render (free tier) via `render.yaml`
- **Key files:** `relay.py`, `test_relay.py`, `SPEC.md`

---

**This file is the canonical paste-target for any repo Jules operates on.**
Copy this whole block into that repo's `AGENTS.md` (or append it under an
`## Operator relay` heading).
