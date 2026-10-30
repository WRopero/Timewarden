#### Databricks layer
- **Names are three-part** (`catalog.schema.table`, Unity Catalog). Never hard-code workspace URLs, tokens or cluster IDs in code; take them from bundle variables or the user's CLI profile.
- **Targets decide the environment.** Work with `databricks bundle validate|summary -t dev`; `bundle deploy -t prod` and running production jobs/pipelines need explicit approval. Prefer `mode: development` targets for experiments.
- **Cost = compute.** Use serverless SQL warehouses or job clusters sized for the workload with auto-termination; never leave all-purpose clusters running; prefer jobs over interactive clusters.
- **Delta tables:** state partitioning/clustering (liquid clustering) deliberately, `OPTIMIZE`/`VACUUM` only via the pipeline, and check `DESCRIBE HISTORY` before destructive changes. Use DLT expectations for data quality.
- **Security:** OAuth (U2M/M2M) over personal access tokens; secrets in secret scopes, never in notebooks; least-privilege grants on catalogs/schemas. `.databrickscfg` and tokens **never** go to the repo or to memory.
- **Lineage and connection:** query the project graph before asking how objects relate and read the connection catalog before asking how to connect.
