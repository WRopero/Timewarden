## Why

The sync labeled every file whose path contains `/specs/` as `openspec-spec` with status `verified`, including the delta specs inside `openspec/changes/**/specs/`. An active, unapproved proposal was therefore retrieved as current verified truth, and archived deltas duplicated the current specs.

## What Changes

- Only `openspec/specs/**` is `openspec-spec` / `verified`. Every file under `openspec/changes/**` (delta specs included) takes its change's label: `openspec-change` / `draft` when active, `openspec-change-archived` / `verified` when archived.
- The registry records `type` and `doc_status`; a document is re-indexed when its label changes even if its content hash does not. Entries indexed before the registry recorded the label are re-checked only for delta specs.

## Capabilities

Modified: `openspec-memory`.
