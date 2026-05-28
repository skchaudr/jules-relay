# Jules Relay

A live, low-latency, bidirectional text channel between an operator (M1) and a running Jules session, brokered by a disposable public HTTPS relay on Render.

## Deploy

1. Push this repo to GitHub.
2. In [Render](https://render.com), create a new **Web Service** connected to the repo — or just push and let `render.yaml` do its thing.
3. Render auto-generates a `RELAY_TOKEN` via `generateValue: true`.
4. Copy the **service URL** (e.g. `https://jules-relay-xxxx.onrender.com`) and the **RELAY_TOKEN** from the Render dashboard.

## Use on M1

Add to `~/.zshrc` (or source from a dotfile):

```bash
export RELAY_URL="https://jules-relay-xxxx.onrender.com"
export RELAY_TOKEN="<paste from Render>"

# Send a message (default kind=ASK)
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

# Listen to events (optionally from a cursor)
listenj() {
  curl -N "$RELAY_URL/events?since=${1:-0}" \
    -H "Authorization: Bearer $RELAY_TOKEN"
}
```

Examples:

```bash
sayj "ready to start?"           # sends ASK
sayj STATE "deploying v2 now"    # sends STATE
sayj ACK "looks good, proceed"   # sends ACK
listenj                          # stream from id 0
listenj 42                       # reconnect cursor
```

## Jules-side setup

Set these env vars in the Jules session:

```
RELAY_URL=https://jules-relay-xxxx.onrender.com
RELAY_TOKEN=<same value>
```

Subscribe at session start:

```bash
curl -N "$RELAY_URL/events" -H "Authorization: Bearer $RELAY_TOKEN" &
```

### Rules for Jules

- Post `STATE` before any high-risk or irreversible step.
- If an `ASK` arrives from `m1`, pause that gated decision until an `ACK` arrives.
- If relay is unreachable, proceed per original task brief (except operator-gated steps).
- **Never** put secrets, credentials, private URLs, or tokens in relay messages.

## API

### `POST /msg` *(auth required)*

```json
{ "from": "m1" | "jules", "kind": "STATE" | "ASK" | "ACK", "text": "string" }
```

→ `{ "ok": true, "id": 42 }`

### `GET /events?since=<id>` *(auth required, SSE)*

Replays buffered messages with `id > since`, then streams live events.

### `GET /health` *(no auth)*

→ `{ "ok": true, "buffer": <n>, "subscribers": <n> }`

## Rotate token

1. Go to Render dashboard → jules-relay → Environment.
2. Change `RELAY_TOKEN` to a new value.
3. Manual deploy (or auto-deploy triggers).
4. Update `RELAY_TOKEN` in M1 shell and Jules session.

Old connections get 401 on next request.

## Tear down

Delete the service in Render. Nothing else is affected — no databases, no external accounts, no persistent state.

## Notes

- Free-tier Render services spin down after ~15 min of inactivity. First request after spin-down takes ~30s.
- Buffer is in-memory only (max 500 messages). Restart empties it; `id` resets to 1.
- See `SPEC.md` for the full design document.
