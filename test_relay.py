"""Self-contained acceptance tests for relay.py."""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

PORT = 19876
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "test-token"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

passed = 0
failed = 0


def req(method, path, data=None, headers=None):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    hdrs = dict(headers if headers is not None else (HEADERS if path != "/health" else {}))
    r = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(r)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body.decode()}


def test(name, func):
    global passed, failed
    try:
        func()
        print(f"  ✅ {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        failed += 1



# --- Launch server ---
print("Starting relay server...")
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "relay:app", "--host", "127.0.0.1", "--port", str(PORT)],
    env={**os.environ, "RELAY_TOKEN": TOKEN},
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
time.sleep(2)

if proc.poll() is not None:
    print("Server failed to start!")
    print(proc.stderr.read().decode())
    sys.exit(1)

print(f"Server running (PID {proc.pid})\n")

try:
    # === Auth ===
    print("=== Auth ===")

    def test_no_token_401():
        code, _ = req("POST", "/msg", {"from": "m1", "kind": "STATE", "text": "hi"}, headers={})
        assert code == 401, f"expected 401 got {code}"

    def test_wrong_token_401():
        code, _ = req("POST", "/msg", {"from": "m1", "kind": "STATE", "text": "hi"},
                      headers={**HEADERS, "Authorization": "Bearer wrong"})
        assert code == 401, f"expected 401 got {code}"

    def test_sse_no_token_401():
        code, _ = req("GET", "/events", headers={})
        assert code == 401, f"expected 401 got {code}"

    test("No token → 401", test_no_token_401)
    test("Wrong token → 401", test_wrong_token_401)
    test("SSE no token → 401", test_sse_no_token_401)

    # === Validation ===
    print("\n=== Validation ===")

    def test_bad_from():
        code, _ = req("POST", "/msg", {"from": "mallory", "kind": "STATE", "text": "hi"})
        assert code == 400, f"expected 400 got {code}"

    def test_bad_kind():
        code, _ = req("POST", "/msg", {"from": "m1", "kind": "YELL", "text": "hi"})
        assert code == 400, f"expected 400 got {code}"

    def test_empty_text():
        code, _ = req("POST", "/msg", {"from": "m1", "kind": "STATE", "text": "  "})
        assert code == 400, f"expected 400 got {code}"

    def test_extra_fields():
        code, _ = req("POST", "/msg", {"from": "m1", "kind": "STATE", "text": "hi", "evil": True})
        assert code == 400, f"expected 400 got {code}"

    def test_too_long():
        code, _ = req("POST", "/msg", {"from": "m1", "kind": "STATE", "text": "x" * 4097})
        assert code == 400, f"expected 400 got {code}"

    test("Bad 'from' → 400", test_bad_from)
    test("Bad 'kind' → 400", test_bad_kind)
    test("Empty text → 400", test_empty_text)
    test("Extra fields → 400", test_extra_fields)
    test("Text > 4096 → 400", test_too_long)

    # === Message flow ===
    print("\n=== Message flow ===")

    def test_post_msg():
        code, body = req("POST", "/msg", {"from": "m1", "kind": "STATE", "text": "hello"})
        assert code == 200, f"got {code}"
        assert body["ok"] is True
        assert body["id"] == 1

    def test_second_msg():
        code, body = req("POST", "/msg", {"from": "jules", "kind": "ACK", "text": "got it"})
        assert code == 200
        assert body["id"] == 2

    def test_health():
        code, body = req("GET", "/health")
        assert code == 200
        assert body["ok"] is True
        assert body["buffer"] == 2, f"expected buffer=2 got {body['buffer']}"

    def test_all_kinds():
        for kind in ("STATE", "ASK", "ACK"):
            code, _ = req("POST", "/msg", {"from": "jules", "kind": kind, "text": f"test {kind}"})
            assert code == 200, f"{kind} rejected: {code}"

    test("POST /msg → id=1", test_post_msg)
    test("POST /msg → id=2", test_second_msg)
    test("Health shows buffer=2", test_health)
    test("All kind values accepted", test_all_kinds)


    # === SSE replay + live ===
    print("\n=== SSE ===")

    def test_sse_replay_and_live():
        results = []

        async def sse_client():
            r = urllib.request.Request(
                f"{BASE}/events?since=0",
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
            resp = urllib.request.urlopen(r)
            start = time.time()
            while len(results) < 6 and (time.time() - start) < 5:
                line = resp.readline().decode().strip()
                if line.startswith("data: "):
                    msg = json.loads(line[6:])
                    results.append(msg)
                    if len(results) == 5:
                        req("POST", "/msg", {"from": "m1", "kind": "ASK", "text": "live msg"})
            resp.close()

        asyncio.run(asyncio.wait_for(sse_client(), timeout=10))
        assert len(results) == 6, f"expected 6 got {len(results)}"
        assert results[0]["id"] == 1
        assert results[4]["id"] == 5
        assert results[5]["id"] == 6
        assert results[5]["text"] == "live msg"

    def test_sse_since_cursor():
        results = []

        async def sse_client():
            r = urllib.request.Request(
                f"{BASE}/events?since=3",
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
            resp = urllib.request.urlopen(r)
            start = time.time()
            while len(results) < 3 and (time.time() - start) < 5:
                line = resp.readline().decode().strip()
                if line.startswith("data: "):
                    results.append(json.loads(line[6:]))
            resp.close()

        asyncio.run(asyncio.wait_for(sse_client(), timeout=10))
        assert len(results) == 3, f"expected 3 got {len(results)}"
        assert results[0]["id"] == 4
        assert results[2]["id"] == 6

    test("SSE replay + live delivery", test_sse_replay_and_live)
    test("SSE since cursor works", test_sse_since_cursor)

    # === Envelope ===
    print("\n=== Envelope ===")

    def test_envelope_fields():
        req("POST", "/msg", {"from": "m1", "kind": "STATE", "text": "check fields"})
        results = []

        async def sse_client():
            r = urllib.request.Request(
                f"{BASE}/events?since=6",
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
            resp = urllib.request.urlopen(r)
            start = time.time()
            while len(results) < 1 and (time.time() - start) < 5:
                line = resp.readline().decode().strip()
                if line.startswith("data: "):
                    results.append(json.loads(line[6:]))
            resp.close()

        asyncio.run(asyncio.wait_for(sse_client(), timeout=10))
        msg = results[0]
        assert "id" in msg
        assert "ts" in msg
        assert msg["ts"].endswith("Z"), f"ts not UTC: {msg['ts']}"
        assert "T" in msg["ts"]
        assert msg["from"] == "m1"
        assert msg["kind"] == "STATE"
        assert msg["text"] == "check fields"

    test("Envelope has all required fields", test_envelope_fields)

finally:
    proc.terminate()
    proc.wait(timeout=5)

print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
if failed:
    sys.exit(1)
