# Dispatch Candidates

Repos with relay-enabled AGENTS.md + setup.sh, ready for Jules/Codex tasks.
Last updated: 2026-05-29.

## How the relay works during a task (concrete walkthrough)

The relay is a **finish line + escalation channel**, not a progress feed.

### Before the task starts

You set `RELAY_URL` and `RELAY_TOKEN` in the Jules session env vars.
You open `listenj` in your terminal.

Jules reads AGENTS.md, sees the relay block, opens an SSE subscription
(`curl -N "$RELAY_URL/events" -H "Authorization: Bearer $RELAY_TOKEN" &`).

### During the task — what Jules sends

**Three messages only:**

```
STATE "starting: implement check_performance() in vault-doctor"    ← task start
STATE "done: check_performance() added, 27 tests pass, on main"     ← task finish
ASK   "deploy to prod or stay on branch?"                           ← blocked, needs you
```

That's it. No checkpoints, no "about to run tests", no "deps verified".
You fire off the task, go do other things, and see `done` when it's finished.

### What Jules does NOT do

- It does NOT stream every file edit or every thought.
- It does NOT post at regular intervals.
- It does NOT expect you to respond to STATE messages.
- It does NOT pause on STATE — only on ASK from you.

### The three message types and when they're used

| Kind | Who sends it | When | Does the other side pause? |
|---|---|---|---|
| `STATE` | Jules | Task start and task finish only | No |
| `STATE` | You | Mid-course correction (optional, rare) | No |
| `ASK` | You | "Stop, do Y instead" or "don't deploy yet" | **Yes** — Jules pauses that step |
| `ACK` | You | "Proceed with what you asked about" | Unpauses the gated step |
| `ASK` | Jules | Genuinely blocked, needs human input | Waits for your ACK or ASK back |

### The actual value

The relay is useful in very few scenarios — and that's the point:

1. **Async finish notification.** You dispatch a task, close the tab, come back
   when you see `done` in your terminal. No polling the web UI.

2. **Mid-course redirect.** You realize the brief was wrong. Send one ASK,
   Jules pivots. Without the relay, you'd have to open the web UI and hope
   it hasn't already passed that point.

3. **Deploy block.** Jules hits a deploy step and posts ASK. You ACK when
   you're ready. Without the relay, it just deploys.

Everything else is noise. If the relay adds friction, don't use it for that task.

---

## Dispatch Candidates

| Repo | Branch | Possible Task | Scope | Why It's Good |
|---|---|---|---|---|
| vault-doctor | main | Implement `check_performance()` + `generate_dashboard()` | Small — both marked "ready" in AGENTS.md | Bounded, tests exist as scaffolding, pure Python |
| dev-journal | feat/note-command | Add `dj search <query>` command (grep journal entries) | Small — single new CLI subcommand | Tests pass cleanly, editable install |
| offline-interactive-pages | main | Create a new interactive page from a template | Small — no build step | Setup instant, clear structure |
| MyAPI | feat/corpus-v1-normalization | Add a new triage pass to `context_refinery/` | Medium | Core repo, setup verified, tests available |
| transcript-triage | feat/reel-capture | Add `--dry-run` mode (validate URLs without downloading) | Small — Bash flag + validation | System tools verified, clear boundary |
| socialxp | docs/avatar-reflection-spec | Implement first handoff task from `docs/superpowers/plans/` | Medium — spec-driven | Has spec + plan + handoff template ready |
| gddp-runtime | docs/share-pdf | Add error handling + retry to `intake_server.py` | Small — robustness pass | dry_run.py verifies pipeline end-to-end |
| aqua-stone-studio | feat/premium-media-library | Add testimonials carousel or new page section | Medium | Build verified, shadcn/ui components available |
| saboorkc.dev | main | Add new content piece or update portfolio layout | Small–Medium | Next.js build verified |
| karoake-players-intro | chore/jules-relay-agents | Add tests for Flask app endpoints | Small — no tests exist yet | Flask app import verified |
| gddp-config | feat/openclaw-nodes | Add a new rule/schema YAML and validate it | Small — declarative | YAML validation in setup.sh |
| jules-relay | main | Add `/stats` endpoint (message counts by kind/from) | Tiny | Relay already live, tests need running server |

## Beiley Tasks (pending)

<!-- Add new tasks here as they come up -->

## Notes

- All repos above have AGENTS.md with relay block + Environment table + Project snapshot.
- All repos above (except one-month-launchpad, gddp-config) have a working setup.sh.
- Relay is live on Render. Free tier = 30s cold start after 15min idle.
- Two-way verified: Jules→relay outbound confirmed. Inbound (you→Jules) needs
  a live Jules session + your `listenj`/`sayj` running simultaneously to confirm.
