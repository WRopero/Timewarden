## 1. Implement
- [x] 1.1 Batches with background cognify and per-item status wait (`wait_processed`)
- [x] 1.2 Parallel batches, failure isolation
- [x] 1.3 Reconcile interrupted entries by search before re-indexing
- [x] 1.4 `--batch-size` and `--parallel` flags
## 2. Verify
- [x] 2.1 Tests with an in-memory Cognee (batching, failure isolation, reconcile)
- [x] 2.2 Real run: 10 documents, batch 3, parallel 2, all indexed in 64 s
