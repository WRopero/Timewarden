#### BigQuery layer
- **Cost = bytes processed (on-demand) or slots (reservations).** Before running a new or heavy query do a *dry run* (`bq query --dry_run` or API `dryRun`) and report the estimated bytes; do not run if above the agreed budget without approval. No `SELECT *` (BigQuery bills columns read) and no `LIMIT` as a cost control.
- **Table design:** partition by date/ingestion (`PARTITION BY`) and require the filter (`require_partition_filter = TRUE`) on large tables; `CLUSTER BY` on frequent filter/join columns; set expiration on staging datasets; use native types (`DATE`, `NUMERIC`) and explicit schemas.
- **Location:** datasets and queries must share a *location*; do not mix regions (fails or doubles cost).
- **Security and IAM:** minimal roles (`bigquery.jobUser` to run, `dataViewer`/`dataEditor` per dataset, not project-wide); service accounts via Workload Identity/ADC, **no JSON keys in the repo**; authorized views or column-level security for personal data.
- **Infrastructure as code:** if Terraform is present, `terraform plan` before every `apply`; **`apply`/`destroy` only with approval**; remote state, never `*.tfstate` or `*.tfvars` in the repo.
- **Memory:** record per table: grain, partitioning/clustering, owner, SLA and typical cost per run; per environment: project, *location* and datasets (logical names, no credentials).
