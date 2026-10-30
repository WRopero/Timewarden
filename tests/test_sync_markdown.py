import sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import sync_markdown as sm  # noqa: E402

FILES = [
    "openspec/specs/cap/spec.md",
    "openspec/changes/active-one/proposal.md",
    "openspec/changes/active-one/specs/cap/spec.md",
    "openspec/changes/archive/2026-01-01-old/proposal.md",
    "openspec/changes/archive/2026-01-01-old/specs/cap/spec.md",
]


def repo_with_openspec() -> Path:
    d = Path(tempfile.mkdtemp())
    for rel in FILES:
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text("# " + rel + "\n\n### Requirement: x\nThe system SHALL x.\n")
    return d


class OpenSpecClassification(unittest.TestCase):
    def setUp(self):
        repo = repo_with_openspec()
        cfg = {"sources": ["openspec/specs/**/*.md", "openspec/changes/**/*.md"], "exclude": []}
        self.docs = sm.enumerate_docs(repo, cfg)

    def kind(self, rel):
        return self.docs[rel]["type"], self.docs[rel]["status"]

    def test_current_spec_is_verified_spec(self):
        self.assertEqual(self.kind("openspec/specs/cap/spec.md"), ("openspec-spec", "verified"))

    def test_active_change_files_are_draft_even_its_delta_specs(self):
        self.assertEqual(self.kind("openspec/changes/active-one/proposal.md"), ("openspec-change", "draft"))
        self.assertEqual(self.kind("openspec/changes/active-one/specs/cap/spec.md"), ("openspec-change", "draft"))

    def test_archived_change_files_are_archived_type_even_its_delta_specs(self):
        self.assertEqual(self.kind("openspec/changes/archive/2026-01-01-old/proposal.md"), ("openspec-change-archived", "verified"))
        self.assertEqual(self.kind("openspec/changes/archive/2026-01-01-old/specs/cap/spec.md"), ("openspec-change-archived", "verified"))

    def test_plan_relabels_entries_indexed_with_old_classification(self):
        rel = "openspec/changes/active-one/specs/cap/spec.md"
        d = self.docs[rel]
        stale = {rel: {"hash": d["hash"], "status": "indexed", "data_id": "x", "type": "openspec-spec", "doc_status": "verified"}}
        self.assertEqual(sm.plan({rel: d}, stale)["changed"], [rel])
        legacy = {rel: {"hash": d["hash"], "status": "indexed", "data_id": "x"}}   # indexed before the registry recorded the label
        self.assertEqual(sm.plan({rel: d}, legacy)["changed"], [rel])
        fresh = {rel: {"hash": d["hash"], "status": "indexed", "data_id": "x", "type": d["type"], "doc_status": d["status"]}}
        self.assertEqual(sm.plan({rel: d}, fresh)["unchanged"], [rel])


if __name__ == "__main__":
    unittest.main()


class ProjectYaml(unittest.TestCase):
    def test_list_items_with_inline_comments_keep_their_glob(self):
        repo = Path(tempfile.mkdtemp())
        (repo / ".agent-memory").mkdir()
        (repo / ".agent-memory/project.yaml").write_text(
            "project_id: demo\nsources:\n  - docs/agent-memory/**/*.md\n"
            "  - openspec/specs/**/*.md          # current OpenSpec specs\n"
            "  - openspec/changes/**/*.md        # active and archived proposals\n"
            "exclude:\n  - '**/.env*'   # secrets\n")
        cfg = sm.load_project(repo)
        self.assertEqual(cfg["sources"], ["docs/agent-memory/**/*.md", "openspec/specs/**/*.md", "openspec/changes/**/*.md"])
        self.assertEqual(cfg["exclude"], ["**/.env*"])

    def test_shipped_template_sources_match_openspec_files(self):
        repo = repo_with_openspec()
        (repo / ".agent-memory").mkdir()
        tmpl = (ROOT / "templates/project.yaml.tmpl").read_text().replace("__PROJECT_ID__", "demo").replace("__LANG__", "en")
        (repo / ".agent-memory/project.yaml").write_text(tmpl)
        docs = sm.enumerate_docs(repo, sm.load_project(repo))
        self.assertEqual(sorted(p for p in docs if p.startswith("openspec/")), sorted(FILES))


class FakeCognee:
    """In-memory stand-in: add -> data_id, background cognify marks everything pending as searchable."""
    calls: dict = {}
    fail_cognify_on: set = set()

    def __init__(self):
        import threading
        self.lock = threading.Lock()
        s = FakeCognee
        s.calls = {"add": [], "delete": [], "cognify": [], "search": 0}
        self.added, self.processed, self.failed, self.n = {}, set(), set(), 0

    def ensure_dataset(self, name): return {}
    def datasets(self): return [{"name": "d", "id": "ds1"}]

    def add_text(self, dataset, text):
        with self.lock:
            self.n += 1
            did = f"data-{self.n}"
            self.added[did] = text
            FakeCognee.calls["add"].append(did)
        return {"data_ingestion_info": [{"data_id": did}]}

    def cognify(self, dataset, background=False):
        with self.lock:
            FakeCognee.calls["cognify"].append(background)
            batch = [i for i in self.added if i not in self.processed and i not in self.failed]
            if any(any(t in self.added[i] for t in FakeCognee.fail_cognify_on) for i in batch):
                self.failed.update(batch)      # a failing run consumes its pending items once
                raise sm.CogneeError("boom")
            self.processed.update(batch)
        return {"ds1": {"status": "PipelineRunStarted"}}

    def processing_status(self, dataset_id):
        return {"total": len(self.added), "completed": len(self.processed), "pending": len(self.added) - len(self.processed) - len(self.failed)}

    def search(self, dataset, query, search_type="CHUNKS", top_k=5):
        FakeCognee.calls["search"] += 1
        return [{"search_result": [{"document_id": i} for i in self.processed]}]

    def _request(self, method, path, **kw):
        FakeCognee.calls["delete"].append(path)


class BatchedApply(unittest.TestCase):
    def setUp(self):
        self.real = sm.Cognee
        sm.Cognee = FakeCognee
        FakeCognee.fail_cognify_on = set()
        sm.save_registry = lambda reg: None      # never touch the real registry
        sm.POLL_SECONDS = 0
        self.cfg = {"project_id": "p", "memory_dataset": "d"}

    def tearDown(self):
        sm.Cognee = self.real

    def docs(self, n):
        return {f"docs/agent-memory/d{i}.md": {"path": f"docs/agent-memory/d{i}.md", "hash": f"h{i}", "doc_id": f"d{i}", "status": "draft",
                "type": "doc", "commit": "", "updated_at": "", "text": f"# Doc {i}\nbody {i}"} for i in range(n)}

    def test_runs_in_small_batches_with_background_cognify(self):
        reg = {}
        sm.apply(Path("."), self.cfg, self.docs(25), reg, True, batch_size=10, parallel=2)
        self.assertEqual(len(FakeCognee.calls["cognify"]), 3)
        self.assertTrue(all(FakeCognee.calls["cognify"]))                      # background=True: no 600 s HTTP wait
        self.assertEqual({e["status"] for e in reg["p"].values()}, {"indexed"})
        self.assertEqual(len(reg["p"]), 25)

    def test_failed_batch_does_not_stop_the_others(self):
        FakeCognee.fail_cognify_on = {"body 3"}
        reg = {}
        sm.apply(Path("."), self.cfg, self.docs(12), reg, True, batch_size=4, parallel=1)
        states = [e["status"] for e in reg["p"].values()]
        self.assertGreater(states.count("indexed"), 0)
        self.assertGreater(states.count("error"), 0)
        self.assertEqual(len(states), 12)

    def test_submitted_entries_are_reconciled_by_search_instead_of_reindexed(self):
        docs = self.docs(2)
        reg = {"p": {k: {"doc_id": d["doc_id"], "hash": d["hash"], "status": "submitted", "data_id": f"old-{i}"} for i, (k, d) in enumerate(docs.items())}}
        orig = FakeCognee.__init__
        def seeded(self_):
            orig(self_); self_.processed.update({"old-0", "old-1"})
        FakeCognee.__init__ = seeded
        try:
            sm.apply(Path("."), self.cfg, docs, reg, True, batch_size=5, parallel=2)
        finally:
            FakeCognee.__init__ = orig
        self.assertEqual({e["status"] for e in reg["p"].values()}, {"indexed"})
        self.assertEqual(FakeCognee.calls["add"], [])
        self.assertEqual(FakeCognee.calls["delete"], [])
