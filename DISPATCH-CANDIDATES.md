# Dispatch Candidates

Repos with relay-enabled AGENTS.md + setup.sh, ready for Jules/Codex tasks.
Last updated: 2026-05-29.

## How the relay works during a task (concrete walkthrough)

The relay is **not** a live progress stream. It's a gated checkpoint channel.
Here is exactly what happens:

### Before the task starts

You set `RELAY_URL` and `RELAY_TOKEN` in the Jules session env vars.
You open `listenj` in your terminal.

Jules reads AGENTS.md, sees the relay block, opens an SSE subscription
(`curl -N "$RELAY_URL/events" -H "Authorization: Bearer $RELAY_TOKEN" &`).

### During the task — what Jules actually sends

Jules posts STATE messages **only at checkpoints**, not continuously.
Think of it as guard rails, not a log feed:

```
STATE "starting task: implement check_performance() in vault-doctor"
STATE "ran bash setup.sh — all deps verified, 23 tests pass"
STATE "check_performance() implemented, 4 tests added"
ASK   "about to modify cli.py to wire in the new method — proceed?"   ← gated
```

You see these in your `listenj` terminal. Most you ignore.
The ASK ones are the ones that matter — Jules **pauses** at that point
and waits for your ACK before continuing:

```
ACK   "yes, proceed"        ← you send this via sayj
```

Then Jules continues:

```
STATE "cli.py updated, running full test suite"
STATE "all 27 tests pass. task complete. PR-ready on main."
```

### What Jules does NOT do

- It does NOT stream every file edit, every line of code, or every thought.
- It does NOT post on a timer or at regular intervals.
- It does NOT expect you to respond to every STATE.
- It does NOT halt on STATE messages — only on ASK messages from you,
  or when it hits something it classified as operator-gated (deploy,
  migration, destructive ops, network calls with side effects).

### The three message types and when they're used

| Kind | Who sends it | What it means | Does the other side pause? |
|---|---|---|---|
| `STATE` | Jules | "Here's where I am." Checkpoint only. | No — you can ignore it. |
| `STATE` | You | "Here's where you are / here's context." | No — Jules logs it, keeps going. |
| `ASK` | You | "Don't do X, do Y instead" or "pause and confirm" | **Yes** — Jules pauses that specific step. |
| `ACK` | You | "Yes, proceed with what you asked about" | Unpauses the gated step. |
| `ASK` | Jules | Rare — Jules asking you a question | You respond with ACK or a new ASK. |

### The actual value

The relay is useful in three real scenarios:

1. **Deploy gates.** Jules is about to push to main or deploy. It posts STATE,
   you see it, you can ACK or redirect. Without the relay, Jules just does it
   or you have to watch the web UI.

2. **Direction changes mid-task.** You realize the task brief was wrong.
   You send `ASK "stop working on X, switch to Y"`. Jules receives it via SSE
   and pivots. Without the relay, you'd have to open the web UI and type into
   the chat, which may already be past that point.

3. **Multi-agent coordination.** Codex and Jules are both working.
   They can see each other's STATE messages on the same relay and avoid
   stepping on each other's files.

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
