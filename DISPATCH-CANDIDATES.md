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

### What Jules doesn't expect 

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

### sc-landscape-lead-intel-system

**Repo:** `sc-landscape-lead-intel-system` (fresh fork, main branch)
**Client:** Bailey Water & Stone — Santa Cruz CA
**Spec:** `context-for-system.md` (full spec + UI flow + scoring engine + architecture)

**Build order (from spec §9):**
1. Scraper — Redfin + Santa Cruz County Assessor → normalized JSON
2. Scoring engine — rules-based Python, testable in isolation
3. SQLite schema — store scored properties
4. Basic web UI — map + pins, read-only
5. Property detail view — tap pin, see score breakdown
6. Manual entry form — inbound calls, no LLM yet
7. LLM parsing layer — bolt on after form works
8. Notifications — alert on new Tier A sales

**Tech stack:** Python + BeautifulSoup → Flask/FastAPI → SQLite → HTML + Tailwind + Google Maps JS
**LLM scope:** Manual entry parsing only (Claude Sonnet via API)
**Hosting:** Pi via Tailscale now, Vercel + Supabase later
**All data sources are free** — no API keys required to start (Google Maps free tier is bonus)

**Good Jules tasks to dispatch from this:**
| Step | Task Brief | Size |
|---|---|---|
| 1 | Build Redfin scraper for Santa Cruz sold listings → JSON | Small |
| 1 | Build County Assessor scraper (or bulk export parser) → JSON | Small |
| 2 | Implement scoring engine with all factors from spec §3 | Small |
| 2 | Write tests for scoring engine (thresholds, edge cases) | Tiny |
| 3 | Design SQLite schema for properties table | Tiny |
| 4 | Flask/FastAPI backend that serves scored properties as JSON | Small |
| 4 | Map view with Google Maps JS + color-coded pins | Medium |
| 5 | Property detail page with score breakdown | Small |
| 6 | Manual lead entry form (no LLM, just form fields + score) | Small |
| 7 | LLM parsing layer for plain English call descriptions | Medium |

**Dependency graph — what can run concurrently:**

The spec defines all data fields upfront, so most steps don't actually
depend on each other — they depend on the spec, which already exists.

```
Wave 0 — no runtime deps, parallelize freely
├── 2a. Scoring engine implementation
├── 2b. Scoring engine tests (thresholds, edge cases, negative scores)
├── 3a. SQLite schema design
└── 1a. Scraper scaffolding (structure + selectors, you verify output)

Wave 1 — needs scoring engine + schema
├── 4a. Flask/FastAPI backend (GET /properties, GET /properties/:id)
├── 4b. Scoring CLI (score a single property from JSON, for testing)
└── 1b. Assessor parser (different source, same output schema)

Wave 2 — needs backend endpoints
├── 5a. Map UI (Google Maps JS + color-coded pins, reads /properties)
├── 6a. Property detail page (score breakdown, reads /properties/:id)
└── 7a. Manual entry form (POST /properties, form fields only)

Wave 3 — needs form
└── 8a. LLM parsing layer (Claude Sonnet → pre-fill form fields)

Wave 4 — needs everything
└── 9a. Notifications (poll DB for new Tier A, alert via ???)
```

**Concrete parallel dispatch combos:**

| Dispatch | Jules/Codex Task A | Jules/Codex Task B | Why They Don't Block |
|---|---|---|---|
| **Now** | Scoring engine + tests (2a+2b) | SQLite schema (3a) | Both read from spec §3. No shared runtime. |
| **Now** | Scoring engine + tests (2a+2b) | Scraper scaffolding (1a) | Scorer is pure logic. Scraper just needs to match the JSON schema. |
| **Wave 1** | Backend API (4a) | Scoring CLI (4b) | API serves the DB. CLI is a standalone test tool. |
| **Wave 2** | Map UI (5a) | Manual entry form (7a) | Both hit same API but different endpoints. |
| **Wave 2** | Property detail (6a) | Manual entry form (7a) | Detail is read-only. Form is write. No collision. |

**What should NOT run in parallel:**
- Scoring engine tests before the scoring engine is implemented -- huh? Against TDD? Or just lazy AI-TDD? 
- LLM parsing before the manual entry form works without it

## Notes

- All repos above have AGENTS.md with relay block + Environment table + Project snapshot.
- All repos above (except one-month-launchpad, gddp-config) have a working setup.sh.
- Relay is live on Render. Free tier = 30s cold start after 15min idle.
- Two-way verified: Jules→relay outbound confirmed. Inbound (you→Jules) needs
  a live Jules session + your `listenj`/`sayj` running simultaneously to confirm.
