#!/usr/bin/env bash
# Instala (symlink) las skills project-memory-* en .claude/skills/ de un repo y
# las excluye de Git localmente (.git/info/exclude).
set -euo pipefail
REPO="$(cd "${1:?uso: install_skills.sh <repo>}" && pwd)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$REPO/.claude/skills"
for s in "$ROOT"/skills/project-memory-*; do
  n=$(basename "$s"); ln -sfn "$s" "$REPO/.claude/skills/$n"
  grep -qxF ".claude/skills/$n" "$REPO/.git/info/exclude" 2>/dev/null || echo ".claude/skills/$n" >> "$REPO/.git/info/exclude"
  echo "installed: $n"
done
