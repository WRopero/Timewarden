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
