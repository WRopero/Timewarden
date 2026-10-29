#### Web application profile
- Before changing the database schema review existing migrations and their production status (deployment ledger); destructive migrations need approval.
- Secrets only via environment variables/secret manager; run the project's tests and linters before calling a task done.
- After deploying and verifying health, record the commit (`memory_deploy.py record`); every security dependency bump cites the CVE in the commit.
