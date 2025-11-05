#!/usr/bin/env bash
set -euo pipefail

main_branch="${1:-main}"
workflow_prefix="${2:-workflow-}"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if ! git show-ref --verify --quiet "refs/heads/$main_branch"; then
  echo "error: main branch '$main_branch' not found" >&2
  exit 1
fi

workflow_branches=$(git for-each-ref --format='%(refname:short)' refs/heads \
  | grep -E "(^|/)${workflow_prefix//\//\\/}.*" || true)

if [[ -z "$workflow_branches" ]]; then
  echo "no workflow branches matching prefix '$workflow_prefix'" >&2
  exit 0
fi

main_ref="$(git rev-parse "$main_branch")"

while IFS= read -r branch; do
  [[ -z "$branch" ]] && continue
  if [[ "$branch" == "$main_branch" ]]; then
    continue
  fi
  echo "resetting branch '$branch' to '$main_branch'"
  git branch -f "$branch" "$main_ref"
done <<< "$workflow_branches"

