## Decisions

1. **Unattended means no approval gates, not no safety.** All guard rails stay: no `down -v`, no `forget everything`, no secrets printed, ports on 127.0.0.1, live access read-only and metadata-only. Ambiguity that cannot be resolved from evidence (language, project type) still stops the run (exit 3), because guessing there writes wrong rules.
2. **Discovery uses only the user's already-authenticated CLIs** and only fills values that are missing or `TODO`; it never overwrites a value and every call is best-effort (failure is reported in the briefing, never fatal).
3. **Enablement = a successful read-only probe.** A probe is the adapter's cheap signature call; success flips `metadata_sync: true` with a targeted line edit (comments and user edits are preserved); failure is recorded with a 24 h backoff so session start never hammers a broken login.
4. **First indexing in the background and capped.** Documents are queued detached, up to `max_baseline_docs` per run; the remainder continues on later runs. Turn off with `auto_baseline: false`.
5. **Plugin install is default** in `seed.sh project`, because the agent performs it for the user.
