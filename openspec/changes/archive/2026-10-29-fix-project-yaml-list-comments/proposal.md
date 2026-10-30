## Why

The contract parser in `sync_markdown.py` stripped inline comments from `key: value` lines but not from list items. The shipped template `templates/project.yaml.tmpl` comments its OpenSpec source lines, so every project installed from it ended up with globs such as `openspec/specs/**/*.md          # current OpenSpec specs...` that match nothing: specs and changes were silently never indexed.

## What Changes

- List items in `.agent-memory/project.yaml` have their trailing `# comment` removed before use.
- Tests cover a commented list and the shipped template itself.

## Capabilities

Modified: `openspec-memory`.
