## Why

`sync_markdown.py --apply` submitted every pending document and then ran a single synchronous `cognify` with a 600 s HTTP timeout. With about 40 documents the client timed out while Cognee kept working; an immediate retry then hung on `DELETE`, and a first install with many OpenSpec files hit this.

## What Changes

- Pending documents are indexed in small batches (`--batch-size`, default 8), several batches at once (`--parallel`, default 2). Each batch adds its documents, starts `cognify` in the background (no HTTP wait), polls Cognee's processing status for its own items, and verifies by search.
- A failed or timed-out batch is recorded and does not stop the others; its documents are retried on the next run.
- Before deleting and re-adding a `submitted`/`unverified`/`error` document, the sync searches for it and, if it is retrievable, marks it `indexed` without spending more tokens.

## Capabilities

New: `batched-indexing`.
