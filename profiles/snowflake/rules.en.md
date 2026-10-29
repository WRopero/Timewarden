#### Snowflake layer
- **Cost = warehouse credits.** Pick size per workload (XS by default) with a short `AUTO_SUSPEND`; never leave warehouses running or resize them without approval. Tag queries with `QUERY_TAG` (in dbt: `query_tag` on the target or `+query_tag`).
- **Security:** key-pair or OAuth auth for service accounts (no passwords); least-privilege roles (one for dbt/ETL, one read-only); masking policies and `ROW ACCESS POLICY` for personal data. `.p8/.pem` keys and `connections.toml` **never** go to the repo or to memory.
- **Safe development:** clone production with `CREATE ... CLONE` (zero-copy) instead of pointing `dev` at `prod`; use `TRANSIENT` for intermediates (less *Fail-safe*) and set `DATA_RETENTION_TIME_IN_DAYS` deliberately.
- **Performance:** `cluster_by` only on large tables with selective filters; read the *query profile* (spilling, *partitions scanned*) before scaling the warehouse; avoid `SELECT *` on wide tables.
- **Operations:** `COPY CURRENT GRANTS` / `copy_grants` when recreating objects; production DDL only through the pipeline. Record accounts/environments by logical name in memory (never credentials).
