## 1. Detection and profiles
- [x] 1.1 `scripts/detect_project_type.py` with evidence, confidence, and exit code 3 if ambiguous
- [x] 1.2 `profiles/` with `dbt-snowflake`, `dataform-bigquery`, `bigquery-sql`, `webapp`, `generic` (es/en)
- [x] 1.3 Integrate `--profile` into `install_project.py` and `seed.sh project`; record `profile:` and `memory_system:` in the contract
- [x] 1.4 Extend `memory_deps.py` to `packages.yml`/`dbt_project.yml`/`@dataform/core`

## 2. Security, deployment, and OpenSpec memory
- [x] 2.1 Review `memory_deps.py`, `memory_audit.py`, `memory_deploy.py` and their integration into the briefing
- [x] 2.2 Ambiguity and OpenSpec rule in the `CLAUDE.md` templates and in the recall skill
- [x] 2.3 Skill/paths without absolute locations (use `memory_system:` from the contract)

## 3. Portability and packaging
- [x] 3.1 Remove project and account names from the bundle, the spec, and the texts
- [x] 3.2 Relocatable root and panel included in the package
- [x] 3.3 `scripts/package_bundle.sh` with an allowlist and neutrality/secrets scanning
- [x] 3.4 `LEEME` and guide for data projects (BigQuery/Dataform, Snowflake/dbt)

## 4. Verification
- [x] 4.1 Unzip into a temporary directory and run `doctor`
- [x] 4.2 Install the contract in sample dbt and Dataform repos and verify detection and rules
- [x] 4.3 `openspec validate portable-bundle-v2` and archive the change
