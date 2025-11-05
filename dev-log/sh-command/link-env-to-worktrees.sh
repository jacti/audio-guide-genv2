#!/usr/bin/env bash
# workflow-* 워크트리에 루트 .env를 심볼릭 링크로 연결한다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_PATH="${SCRIPT_DIR}/.env"

if [[ ! -f "${ENV_PATH}" ]]; then
  echo "❌ .env 파일이 ${ENV_PATH} 위치에 없습니다." >&2
  exit 1
fi

WORKTREE_PATHS=()
while IFS= read -r worktree_path; do
  WORKTREE_PATHS+=("${worktree_path}")
done < <(
  git -C "${SCRIPT_DIR}" worktree list --porcelain |
    awk '/^worktree / { path=$2 } /^$/ { if (path ~ /workflow-/) print path; path="" } END { if (path ~ /workflow-/) print path }'
)

if [[ ${#WORKTREE_PATHS[@]} -eq 0 ]]; then
  echo "⚠️ workflow- 프리픽스를 가진 워크트리를 찾지 못했습니다."
  exit 0
fi

for worktree in "${WORKTREE_PATHS[@]}"; do
  link_path="${worktree}/.env"

  if [[ -L "${link_path}" ]]; then
    current_target="$(readlink "${link_path}")"
    if [[ "${current_target}" == "${ENV_PATH}" ]]; then
      echo "✅ ${worktree}: 이미 올바른 심볼릭 링크가 있습니다."
      continue
    else
      rm "${link_path}"
      ln -s "${ENV_PATH}" "${link_path}"
      echo "♻️ ${worktree}: 기존 심볼릭 링크를 갱신했습니다."
      continue
    fi
  fi

  if [[ -e "${link_path}" ]]; then
    echo "⚠️ ${worktree}: .env 파일이 이미 존재하여 건너뜁니다." >&2
    continue
  fi

  ln -s "${ENV_PATH}" "${link_path}"
  echo "🔗 ${worktree}: 심볼릭 링크를 생성했습니다."
done
