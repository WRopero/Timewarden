"""Neutral sample repositories generated on the fly (no real project names)."""
from pathlib import Path


def w(root: Path, rel: str, text: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def dbt_repo(root: Path) -> Path:
    w(root, "dbt_project.yml", """name: shop
version: '1.0'
profile: shop
model-paths: ["models"]
models:
  shop:
    +materialized: view
    marts:
      +materialized: table
""")
    w(root, "profiles.yml", "shop:\n  outputs:\n    dev:\n      type: snowflake\n      account: acme\n      password: SUPERSECRET123\n      warehouse: wh_x\n      database: shop_db\n      schema: dbt_dev\n    prod:\n      type: snowflake\n      account: acme\n      private_key_path: \"{{ env_var('SF_KEY_PATH') }}\"\n      schema: analytics\n")
    w(root, "models/staging/_sources.yml", """version: 2
sources:
  - name: raw
    schema: raw_data
    tables:
      - name: orders
        description: Raw orders feed
      - name: customers
""")
    w(root, "models/staging/stg_orders.sql", "{{ config(tags=['daily']) }}\nselect * from {{ source('raw', 'orders') }}\n")
    w(root, "models/staging/stg_customers.sql", "select * from {{ source('raw', 'customers') }}\n")
    w(root, "models/staging/_staging.yml", """version: 2
models:
  - name: stg_orders
    description: >
      Orders cleaned
      and typed.
    columns:
      - name: order_id
        tests: [unique, not_null]
      - name: customer_id
        data_tests:
          - relationships:
              to: ref('stg_customers')
              field: customer_id
  - name: stg_customers
    columns:
      - name: customer_id
        tests:
          - unique
""")
    w(root, "models/marts/fct_orders.sql", "{{ config(materialized='incremental', unique_key='order_id') }}\n"
      "select * from {{ ref('stg_orders') }} o join {{ ref('stg_customers') }} c using (customer_id)\n")
    w(root, "models/marts/dim_customers.sql", "select * from {{ ref('stg_customers') }}\n")
    w(root, "models/marts/bad_mart.sql", "select * from {{ source('raw', 'orders') }}\n")
    w(root, "models/marts/dyn.sql", "{% set t = 'x' %}select * from {{ ref(t) }}\n")
    w(root, "models/marts/_marts.yml", """version: 2
models:
  - name: fct_orders
    description: One row per order
exposures:
  - name: revenue_dashboard
    type: dashboard
    depends_on:
      - ref('fct_orders')
      - ref('dim_customers')
""")
    w(root, "models/marts/ghost.sql", "select * from {{ ref('does_not_exist') }}\n")
    w(root, "seeds/country_codes.csv", "code,name\nUS,United States\n")
    return root


def dataform_repo(root: Path) -> Path:
    w(root, "workflow_settings.yaml", "defaultProject: demo-project\ndefaultLocation: US\ndefaultDataset: analytics\n")
    w(root, "definitions/sources/raw_events.sqlx", 'config {\n  type: "declaration",\n  schema: "raw",\n  name: "raw_events"\n}\n')
    w(root, "definitions/staging/stg_events.sqlx", 'config {\n  type: "view",\n  tags: ["hourly"],\n  description: "Clean events"\n}\nselect * from ${ref("raw", "raw_events")}\n')
    w(root, "definitions/marts/daily_events.sqlx", 'config {\n  type: "table",\n  assertions: { nonNull: ["day"] }\n}\nselect day from ${ref("stg_events")}\n')
    w(root, "definitions/marts/rollup.js", 'publish("weekly_rollup").query(ctx => `select * from ${ctx.ref("daily_events")}`)\n')
    return root


def databricks_repo(root: Path) -> Path:
    w(root, "databricks.yml", """bundle:
  name: lakehouse
targets:
  dev:
    mode: development
  prod:
    mode: production
resources:
  pipelines:
    ingest:
      catalog: main
      schema: bronze
      libraries:
        - notebook:
            path: ./pipelines/ingest.py
  jobs:
    nightly:
      schedule:
        quartz_cron_expression: "0 0 2 * * ?"
      tasks:
        - task_key: ingest
          pipeline_task:
            pipeline_id: ${resources.pipelines.ingest.id}
        - task_key: gold
          notebook_task:
            notebook_path: ./jobs/build_gold.sql
""")
    w(root, "pipelines/ingest.py", "import dlt\n\n@dlt.table(name='bronze_events')\ndef bronze_events():\n    return spark.read.table('main.landing.events')\n\n"
      "@dlt.table\ndef silver_events():\n    return dlt.read('bronze_events')\n")
    w(root, "jobs/build_gold.sql", "CREATE OR REPLACE TABLE main.gold.daily_events AS SELECT * FROM main.silver.silver_events\n")
    return root
