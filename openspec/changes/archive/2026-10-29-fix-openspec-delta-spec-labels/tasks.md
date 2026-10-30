## 1. Fix
- [x] 1.1 Classify by change, not by the `/specs/` substring (`openspec_label`)
- [x] 1.2 Record `type`/`doc_status` in the registry and relabel on mismatch (`label_changed`)
## 2. Verify
- [x] 2.1 `tests/test_sync_markdown.py` (classification and relabel plan)
- [x] 2.2 Re-sync affected projects with `memctl.sh sync <repo> --apply`
