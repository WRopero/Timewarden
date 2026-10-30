# batched-indexing Specification

## Purpose
Index large sets of documents reliably without long synchronous requests, and recover from interrupted runs without paying twice.

## Requirements

### Requirement: Indexing in small parallel batches
The sync SHALL index pending documents in batches of a configurable small size, processing several batches at once, and SHALL NOT depend on a single long synchronous request to Cognee.

#### Scenario: Many pending documents
- **WHEN** more documents are pending than the batch size
- **THEN** they are indexed in several batches, each started with a background `cognify` and awaited through Cognee's processing status

#### Scenario: A batch fails
- **WHEN** one batch fails or times out
- **THEN** its documents are recorded as `error` and the remaining batches continue; the next run retries only those

### Requirement: Interrupted documents are reconciled before re-indexing
The sync SHALL search for documents left `submitted`, `unverified` or `error` by an earlier run and mark them `indexed` when they are retrievable, instead of deleting and re-adding them.

#### Scenario: Run cut short while Cognee kept working
- **WHEN** a previous run ended before verification and Cognee finished the documents afterwards
- **THEN** the next run marks them `indexed` without adding them again or spending tokens
