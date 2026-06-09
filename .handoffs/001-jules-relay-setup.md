Memory saved. Handoff:

---

**jules-relay: state at handoff**

- Relay live at `https://jules-relay.onrender.com`, latest commit `d26015d` on `main`. `/health` working, M1 roundtrip verified earlier.
- Token lives in `~/.zshlocal` (`RELAY_URL` + `RELAY_TOKEN`); `sayj` / `listenj` shell helpers ready.
- Karaoke repo `chore/jules-relay-agents` branch pushed: contains `AGENTS.md` (operator-relay protocol) + `jules-tasks/demo-state-harness.md` (first task brief, demo-state loader with `--confirm-overwrite` flag + relay ACK gate on overwrite).
- jules-relay repo has canonical `AGENTS.md` paste-target.

**What failed:** Take 1 of Jules session was archived — Jules read AGENTS.md, asked for env vars (good — protocol gated), but env on Jules can only be set at **project level pre-VM-spawn**. Mid-session env injection is a no-op. Saved as memory: `project_jules_env_at_project_level.md`.

**Next move:**

1. jules.google.com → project settings → set `RELAY_URL=https://jules-relay.onrender.com` + `RELAY_TOKEN=<from ~/.zshlocal>`.
2. Verify with throwaway session: ask Jules `echo $RELAY_URL`.
3. Run `listenj` in an M1 pane.
4. Dispatch same task text as before, pointing at `jules-tasks/demo-state-harness.md` on `chore/jules-relay-agents`.

**Open question for new session:** does Jules support per-project env, or only per-session? If only per-session, plan B is setting env _at the moment of session create_ via the web UI before pressing dispatch.
