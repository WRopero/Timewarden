import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(Path(__file__).parent))
import data_graph as dg  # noqa: E402
import fixtures as fx  # noqa: E402
import miniyaml  # noqa: E402


def edges(d):
    nm = {n["id"]: n["name"] for n in d["nodes"]}
    return {(nm[a], nm[b], t) for a, b, t in d["edges"]}


class MiniYaml(unittest.TestCase):
    def test_subset_matches_pyyaml_on_dbt_style_file(self):
        text = (Path(tempfile.mkdtemp()) / "x")
        fx.dbt_repo(text)
        src = (text / "models/staging/_staging.yml").read_text()
        os.environ["TIMEWARDEN_NO_PYYAML"] = "1"
        try:
            a = miniyaml.load(src)
        finally:
            del os.environ["TIMEWARDEN_NO_PYYAML"]
        b = miniyaml.load(src)
        self.assertEqual(a["models"][0]["name"], b["models"][0]["name"])
        self.assertEqual(a["models"][0]["columns"][0]["tests"], ["unique", "not_null"])
        self.assertIn("Orders cleaned", a["models"][0]["description"])


class Dbt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = fx.dbt_repo(Path(tempfile.mkdtemp()))
        cls.d = dg.build(cls.repo, tools="off")

    def test_edges_and_kinds(self):
        e = edges(self.d)
        self.assertIn(("fct_orders", "stg_orders", "depends_on"), e)
        self.assertIn(("stg_orders", "raw.orders", "depends_on"), e)
        self.assertIn(("revenue_dashboard", "fct_orders", "depends_on"), e)
        self.assertIn(("stg_orders", "stg_customers", "relates"), e)
        kinds = {n["name"]: n["kind"] for n in self.d["nodes"]}
        self.assertEqual(kinds["country_codes"], "seed")
        self.assertEqual(kinds["raw.customers"], "source")

    def test_config_and_properties(self):
        n = {x["name"]: x for x in self.d["nodes"]}
        self.assertEqual(n["fct_orders"]["materialization"], "incremental")
        self.assertEqual(n["dim_customers"]["materialization"], "table")      # folder default
        self.assertEqual(n["stg_orders"]["materialization"], "view")
        self.assertIn("daily", n["stg_orders"]["tags"])
        self.assertEqual(n["stg_orders"]["description"], "Orders cleaned and typed.")
        self.assertIn("unique", n["stg_orders"]["tests"])

    def test_dynamic_and_unresolved(self):
        r = dg.check(self.d)
        types = {(i["type"], i.get("node")) for i in r["issues"]}
        self.assertIn(("dynamic_ref", "dyn"), types)
        self.assertIn(("unresolved_ref", "ghost"), types)
        self.assertIn(("layer_skip", "bad_mart"), types)

    def test_no_secrets_anywhere(self):
        blob = "".join(p.read_text() for p in (self.repo / dg.OUT_REL).glob("*") if p.is_file())
        self.assertNotIn("SUPERSECRET123", blob)
        self.assertNotIn("acme", blob)

    def test_deterministic_and_rules_preserved(self):
        out = self.repo / dg.OUT_REL
        before = {p.name: p.read_text() for p in out.glob("*.md")}
        (out / "rules.md").write_text("mine")
        dg.build(self.repo, tools="off")
        self.assertEqual((out / "rules.md").read_text(), "mine")
        after = {p.name: p.read_text() for p in out.glob("*.md") if p.name != "rules.md"}
        self.assertEqual({k: v for k, v in before.items() if k != "rules.md"}, after)

    def test_card_split_and_relation_sentences(self):
        txt = (self.repo / dg.OUT_REL / "cards-marts.md").read_text()
        self.assertIn("fct_orders depends on: stg_customers, stg_orders.", txt)
        self.assertIn("stg_orders is used by:", (self.repo / dg.OUT_REL / "cards-staging.md").read_text())

    def test_queries(self):
        run = lambda *a: subprocess.run([sys.executable, "-I", str(ROOT / "scripts/data_graph.py"), "--repo", str(self.repo), *a], capture_output=True, text=True)
        r = run("impact", "stg_customers")
        self.assertIn("fct_orders", r.stdout); self.assertIn("revenue_dashboard", r.stdout)
        self.assertIn("exposures affected", r.stdout)
        self.assertIn("stg_orders", run("upstream", "fct_orders", "--depth", "1").stdout)
        self.assertIn("->", run("path", "revenue_dashboard", "raw.orders").stdout)


class Manifest(unittest.TestCase):
    def test_manifest_preferred_when_fresh(self):
        repo = fx.dbt_repo(Path(tempfile.mkdtemp()))
        (repo / "target").mkdir()
        (repo / "target/manifest.json").write_text(json.dumps({
            "nodes": {"model.shop.a": {"resource_type": "model", "name": "a", "original_file_path": "models/a.sql", "schema": "s", "database": "d",
                                       "config": {"materialized": "table"}, "package_name": "shop", "depends_on": {"nodes": ["source.shop.raw.orders"]}},
                      "model.shop.b": {"resource_type": "model", "name": "b", "original_file_path": "models/b.sql", "package_name": "shop",
                                       "depends_on": {"nodes": ["model.shop.a"]}}},
            "sources": {"source.shop.raw.orders": {"source_name": "raw", "name": "orders", "original_file_path": "models/s.yml"}}, "exposures": {}}))
        future = __import__("time").time() + 100
        os.utime(repo / "target/manifest.json", (future, future))
        d = dg.build(repo, tools="auto")
        self.assertEqual(d["sources"]["dbt"]["tier"], "manifest")
        self.assertIn(("b", "a", "depends_on"), edges(d))


class Dataform(unittest.TestCase):
    def test_static(self):
        repo = fx.dataform_repo(Path(tempfile.mkdtemp()))
        d = dg.build(repo, tools="off")
        e = edges(d)
        self.assertIn(("stg_events", "raw_events", "depends_on"), e)
        self.assertIn(("daily_events", "stg_events", "depends_on"), e)
        self.assertIn(("weekly_rollup", "daily_events", "depends_on"), e)
        kinds = {n["name"]: n["kind"] for n in d["nodes"]}
        self.assertEqual(kinds["raw_events"], "declaration")
        self.assertEqual(kinds["stg_events"], "view")
        self.assertEqual(d["sources"]["dataform"]["default_dataset"], "analytics")


class Databricks(unittest.TestCase):
    def test_bundle_and_lineage(self):
        repo = fx.databricks_repo(Path(tempfile.mkdtemp()))
        d = dg.build(repo, tools="off")
        e = edges(d)
        self.assertIn(("nightly", "ingest", "runs"), e)
        self.assertIn(("main.gold.daily_events", "main.silver.silver_events", "derived"), e)
        self.assertIn(("silver_events", "bronze_events", "derived"), e)
        self.assertIn("databricks", d["systems"])


class Live(unittest.TestCase):
    def test_merge_and_drift(self):
        repo = fx.dbt_repo(Path(tempfile.mkdtemp()))
        st = repo / ".agent-memory/data-sync-state"; st.mkdir(parents=True)
        (st / "live.json").write_text(json.dumps({"scanned": ["db.analytics"], "tables": [
            {"db": "db", "schema": "analytics", "name": "fct_orders", "type": "table", "rows": 5,
             "columns": [{"name": "order_id", "type": "INT", "partition": True}, {"name": "x", "type": "INT", "cluster": 1}]},
            {"db": "db", "schema": "analytics", "name": "stray", "type": "table"}]}))
        d = dg.build(repo, tools="off")
        n = {x["name"]: x for x in d["nodes"]}
        self.assertTrue(n["fct_orders"]["live"]); self.assertEqual(n["fct_orders"]["partitioned_by"], ["order_id"])
        self.assertEqual(n["stray"]["kind"], "live_table")
        self.assertTrue(any(i["type"] == "drift_live_only" for i in dg.check(d)["issues"]))


if __name__ == "__main__":
    unittest.main()
