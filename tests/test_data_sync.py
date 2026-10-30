import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(Path(__file__).parent))
import data_connect as dc  # noqa: E402
import data_graph as dg  # noqa: E402
import data_sources as ds  # noqa: E402
import data_sync  # noqa: E402
import fixtures as fx  # noqa: E402


def git_repo(maker) -> Path:
    d = Path(tempfile.mkdtemp())
    maker(d)
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    return d


class Connect(unittest.TestCase):
    def test_catalog_has_no_secrets_and_recipes_render(self):
        repo = fx.dbt_repo(Path(tempfile.mkdtemp()))
        (repo / ".agent-memory").mkdir()
        (repo / ".agent-memory/project.yaml").write_text("project_id: demo\nprofile: dbt,snowflake\n")
        subprocess.run([sys.executable, "-I", str(ROOT / "scripts/data_connect.py"), "--repo", str(repo), "init"], check=True, capture_output=True)
        cat = (repo / dc.CATALOG).read_text()
        self.assertNotIn("SUPERSECRET123", cat)
        self.assertIn("auth_secret_settings_present: [password]", cat)
        self.assertIn("warehouse: snowflake", cat)
        doc = (repo / dc.DOC).read_text()
        self.assertIn("dbt debug --target dev", doc)
        self.assertIn("snow connection test", doc)
        self.assertNotIn("SUPERSECRET123", doc)
        before = (repo / dc.CATALOG).read_text()
        subprocess.run([sys.executable, "-I", str(ROOT / "scripts/data_connect.py"), "--repo", str(repo), "init"], check=True, capture_output=True)
        self.assertEqual(before, (repo / dc.CATALOG).read_text())      # never overwritten
        out = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/data_connect.py"), "--repo", str(repo), "check"], capture_output=True, text=True).stdout
        self.assertIn("host:", out); self.assertNotIn("SUPERSECRET123", out)


class LiveAdapters(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def fake(cmd, timeout=120):
            self.calls.append(cmd)
            sql = cmd[-1]
            if "__TABLES__" in sql and "COUNT" in sql:
                return json.dumps([{"c": "2", "m": "1700"}])
            if "__TABLES__" in sql:
                return json.dumps([{"table_id": "fct_orders", "type": "1", "row_count": "9"}, {"table_id": "stray", "type": "1", "row_count": "1"}])
            if "INFORMATION_SCHEMA.COLUMNS" in sql:
                return json.dumps([{"table_name": "fct_orders", "column_name": "order_id", "data_type": "INT64", "is_partitioning_column": "YES", "clustering_ordinal_position": None}])
            return "[]"
        self.old, ds.RUN = ds.RUN, fake

    def tearDown(self):
        ds.RUN = self.old

    def env(self):
        return {"warehouse": "bigquery", "identifiers": {"project": "demo", "datasets": ["analytics"], "location": "US"}, "metadata_sync": True}

    def test_bigquery_fetch_shape(self):
        d = ds.bigquery_fetch(self.env())
        t = {x["name"]: x for x in d["tables"]}
        self.assertEqual(t["fct_orders"]["rows"], 9)
        self.assertTrue(t["fct_orders"]["columns"][0]["partition"])
        self.assertEqual(d["scanned"], ["demo.analytics"])
        self.assertTrue(all(c[-1].lstrip().lower().startswith("select") for c in self.calls))

    def test_refuses_writes(self):
        for bad in ("DROP TABLE x", "select 1; drop table x", "DELETE FROM x", "CREATE TABLE x AS select 1"):
            with self.assertRaises(ds.LiveError):
                ds._sql_guard(bad)

    def test_sync_only_when_changed(self):
        repo = fx.dbt_repo(Path(tempfile.mkdtemp()))
        (repo / ".agent-memory").mkdir()
        (repo / ".agent-memory/project.yaml").write_text("project_id: demo\nprofile: dbt,bigquery\ndata_graph:\n  auto_sync: true\n  live_ttl_hours: 0\n")
        (repo / ".agent-memory/connections.yaml").write_text(
            "schema_version: 1\nlayers: [dbt, bigquery]\nenvironments:\n  dev:\n    role: development\n    system: dbt\n    warehouse: bigquery\n"
            "    identifiers:\n      project: demo\n      datasets: [analytics]\n      location: US\n    metadata_sync: true\n")
        r1 = data_sync.run(repo, index="off")
        self.assertTrue(r1["changed"]); self.assertEqual(r1["live"], {"dev": "fetched 2 tables"})
        gj = repo / dg.OUT_REL / "graph.json"
        m1 = {p.name: p.stat().st_mtime_ns for p in (repo / dg.OUT_REL).glob("*")}
        time.sleep(0.05)
        r2 = data_sync.run(repo, index="off")
        self.assertFalse(r2["changed"]); self.assertEqual(r2["live"], {"dev": "unchanged"})
        self.assertEqual(m1, {p.name: p.stat().st_mtime_ns for p in (repo / dg.OUT_REL).glob("*")})   # nothing rewritten
        # a model changes -> rebuild; only the cards that mention it change
        before = {p.name: p.read_text() for p in (repo / dg.OUT_REL).glob("*.md")}
        (repo / "models/marts/dim_customers.sql").write_text("select 1 as customer_id from {{ ref('stg_orders') }}\n")
        r3 = data_sync.run(repo, index="off")
        self.assertTrue(r3["changed"])
        after = {p.name: p.read_text() for p in (repo / dg.OUT_REL).glob("*.md")}
        changed = {k for k in after if before.get(k) != after[k]}
        self.assertTrue(changed and changed < set(after), changed)          # some, not all
        self.assertIn("cards-marts.md", changed)
        d = json.loads(gj.read_text())
        n = {x["name"]: x for x in d["nodes"]}
        self.assertTrue(n["fct_orders"]["live"]); self.assertEqual(n["stray"]["kind"], "live_table")

    def test_not_opted_in_means_no_live_calls(self):
        repo = fx.dbt_repo(Path(tempfile.mkdtemp()))
        (repo / ".agent-memory").mkdir()
        (repo / ".agent-memory/project.yaml").write_text("project_id: demo\nprofile: dbt,bigquery\n")
        (repo / ".agent-memory/connections.yaml").write_text(
            "schema_version: 1\nlayers: [dbt]\nenvironments:\n  prod:\n    role: production\n    system: dbt\n    warehouse: bigquery\n    identifiers: {}\n    metadata_sync: false\n")
        data_sync.run(repo, index="off")
        self.assertEqual(self.calls, [])

    def test_live_error_never_breaks_the_sync(self):
        def boom(cmd, timeout=120):
            raise ds.LiveError("bq failed: not authenticated")
        ds.RUN = boom
        repo = fx.dbt_repo(Path(tempfile.mkdtemp()))
        (repo / ".agent-memory").mkdir()
        (repo / ".agent-memory/project.yaml").write_text("project_id: demo\nprofile: dbt,bigquery\n")
        (repo / ".agent-memory/connections.yaml").write_text(
            "schema_version: 1\nlayers: [dbt]\nenvironments:\n  dev:\n    role: development\n    system: dbt\n    warehouse: bigquery\n    identifiers:\n      project: p\n      datasets: [a]\n    metadata_sync: true\n")
        r = data_sync.run(repo, index="off")
        self.assertTrue(r["changed"]); self.assertTrue(any("not authenticated" in e for e in r["errors"]))

    def test_hook_line(self):
        repo = fx.dbt_repo(Path(tempfile.mkdtemp()))
        (repo / ".agent-memory").mkdir()
        (repo / ".agent-memory/project.yaml").write_text("project_id: demo\nprofile: dbt,snowflake\n")
        text, need = data_sync.line(repo)
        self.assertTrue(need and "not built yet" in text)
        data_sync.run(repo, index="off")
        text, need = data_sync.line(repo)
        self.assertFalse(need); self.assertIn("current", text); self.assertIn("impact|upstream", text)


class Install(unittest.TestCase):
    def test_install_builds_graph_and_catalog(self):
        repo = git_repo(fx.dbt_repo)
        r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/install_project.py"), str(repo), "--project-id", "demo", "--lang", "en",
                            "--profile", "dbt,snowflake", "--openspec", "no"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("data_graph:", (repo / ".agent-memory/project.yaml").read_text())
        self.assertTrue((repo / dg.OUT_REL / "graph.json").exists())
        self.assertTrue((repo / dc.CATALOG).exists())
        self.assertIn("Data graph and connections", (repo / "CLAUDE.md").read_text())
        self.assertIn(".agent-memory/data-sync-state/", (repo / ".git/info/exclude").read_text())
        self.assertNotIn("SUPERSECRET123", (repo / "CLAUDE.md").read_text())
        brief = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/memory_brief.py"), str(repo)], capture_output=True, text=True).stdout
        self.assertIn("Data graph:", brief); self.assertIn("Connections:", brief)



class IndexPolicy(unittest.TestCase):
    def _repo(self):
        repo = fx.dbt_repo(Path(tempfile.mkdtemp()))
        (repo / ".agent-memory").mkdir()
        (repo / ".agent-memory/project.yaml").write_text("project_id: demo\nprofile: dbt,snowflake\nmemory_dataset: demo-knowledge\n")
        return repo

    def test_first_index_is_never_automatic(self):
        repo = self._repo()
        launched = []
        old_plan, old_up, old_popen = data_sync.index_plan, data_sync.stack_up, data_sync.subprocess.Popen
        data_sync.index_plan = lambda r: {"new": 7, "changed": 0, "unchanged": 0, "retry": 0, "deleted": 0}
        data_sync.stack_up = lambda: True
        data_sync.subprocess.Popen = lambda *a, **k: launched.append(a)
        try:
            r = data_sync.run(repo)
        finally:
            data_sync.index_plan, data_sync.stack_up, data_sync.subprocess.Popen = old_plan, old_up, old_popen
        self.assertEqual(launched, []); self.assertIn("baseline pending", r["indexed"])

    def test_incremental_changes_are_indexed_in_background_with_cap(self):
        repo = self._repo()
        launched = []
        old_plan, old_up, old_popen = data_sync.index_plan, data_sync.stack_up, data_sync.subprocess.Popen
        data_sync.index_plan = lambda r: {"new": 0, "changed": 2, "unchanged": 30, "retry": 0, "deleted": 0}
        data_sync.stack_up = lambda: True
        data_sync.subprocess.Popen = lambda cmd, **k: launched.append(cmd)
        try:
            r = data_sync.run(repo)
        finally:
            data_sync.index_plan, data_sync.stack_up, data_sync.subprocess.Popen = old_plan, old_up, old_popen
        self.assertEqual(len(launched), 1)
        self.assertIn("--only", launched[0]); self.assertIn("--max-docs", launched[0]); self.assertEqual(r["indexed"], "2 of 2 queued")

    def test_stack_down_defers(self):
        repo = self._repo()
        old_plan, old_up = data_sync.index_plan, data_sync.stack_up
        data_sync.index_plan = lambda r: {"new": 0, "changed": 1, "unchanged": 30, "retry": 0, "deleted": 0}
        data_sync.stack_up = lambda: False
        try:
            r = data_sync.run(repo)
        finally:
            data_sync.index_plan, data_sync.stack_up = old_plan, old_up
        self.assertIn("stack is down", r["indexed"])


if __name__ == "__main__":
    unittest.main()
