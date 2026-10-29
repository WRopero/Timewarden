# Prompt to paste to an agent

Unzip the kit in any folder (we will call it `<KIT>`: it contains `seed-bundle/SEED.md`). Open Claude Code and paste the block below, changing `<KIT>`, `<repo>` and `<project_id>`:

```text
Install project memory in <repo> with project_id <project_id>.
The installation kit is in <KIT> (the folder that contains seed-bundle/SEED.md). Work from that folder.
Read seed-bundle/SEED.md and follow the phases in order using seed-bundle/seed.sh. Rules:
- Ask me before starting containers, installing the plugin, bringing up the dashboard or indexing (indexing spends tokens).
- If the language (Spanish/English) or the project type (dbt, Dataform, Snowflake, BigQuery, web application, etc.) is not obvious, ask me; do not guess. If the installer exits with code 3, that is a question for me.
- Do not print secrets. No `down -v` and no `forget everything`.
- Only macOS + Docker Desktop is validated: if I am on another system, tell me before continuing.
- When finished, give me: what you installed, where, the token cost, how to disconnect it and the results of `seed.sh verify`.
```

Infrastructure only (no project) on a new machine: "Run phases 1 to 3 of SEED.md". For another repository afterwards: repeat from phase 2 with another `project_id`.
