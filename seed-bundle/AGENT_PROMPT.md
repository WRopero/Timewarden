# Prompt to paste to an agent

Unzip the kit in any folder (we will call it `<KIT>`: it contains `seed-bundle/SEED.md`). Open Claude Code and paste the block below, changing `<KIT>`, `<repo>` and `<project_id>`:

```text
Install project memory in <repo> with project_id <project_id>.
The installation kit is in <KIT> (the folder that contains seed-bundle/SEED.md). Work from that folder.
Read seed-bundle/SEED.md and follow the phases in order using seed-bundle/seed.sh. Rules:
- Do the whole installation yourself, end to end, with nothing left for me to do by hand: start the containers, install the plugin, set up the project, build the data graph and connection catalog (discover identifiers from my authenticated CLIs and enable read-only live metadata where it works), index, bring up the dashboard and verify. Do not ask for approval at each phase; I authorize all of it by giving you this task. The first indexing spends my Claude subscription tokens: report the cost at the end.
- The only reasons to stop and ask me: the language or the project type is ambiguous (installer exit code 3), or my operating system is not macOS + Docker Desktop.
- If the language (Spanish/English) or the project type (dbt, Dataform, Databricks, Snowflake, BigQuery, web application, etc.) is not obvious, ask me that single question; do not guess. If the installer exits with code 3, that is the question.
- Do not print secrets. No `down -v` and no `forget everything`.
- When finished, give me: what you installed, where, the token cost, how to disconnect it and the results of `seed.sh verify`.
```

Infrastructure only (no project) on a new machine: "Run phases 1 to 3 of SEED.md". For another repository afterwards: repeat from phase 2 with another `project_id`.
