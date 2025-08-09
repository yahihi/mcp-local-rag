#!/usr/bin/env bash
set -euo pipefail

# Count index candidate files respecting config.json excludes and extensions.
# Usage: bash scripts/count_candidates.sh /path/to/project [more/paths...]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [ "$#" -lt 1 ]; then
  echo "Usage: bash scripts/count_candidates.sh <dir> [dir2 ...]" >&2
  exit 1
fi

# Read config.json (no jq dependency; use Python if available)
read_config() {
  python3 - "$1" <<'PY' || true
import json,sys
cfg=json.load(open('config.json'))
key=sys.argv[1]
for v in cfg.get(key, []):
    print(v)
PY
}

mapfile -t EXCLUDES < <(read_config exclude_dirs)
mapfile -t EXTENSIONS < <(read_config file_extensions)

# Fallback defaults if config keys missing
if [ ${#EXTENSIONS[@]} -eq 0 ]; then
  EXTENSIONS=(.py .md .json .yaml .yml .toml)
fi
if [ ${#EXCLUDES[@]} -eq 0 ]; then
  EXCLUDES=(.git venv .venv env site-packages site_packages __pycache__ node_modules .pytest_cache .mypy_cache .ruff_cache dist build .next target logs log output outputs artifacts checkpoints data datasets)
fi

have_fd() { command -v fd >/dev/null 2>&1; }

count_with_fd() {
  local root="$1"
  local args=(-t f)
  # Excludes
  for e in "${EXCLUDES[@]}"; do
    args+=( -E "$e" )
  done
  # Extensions (only ".ext" forms are supported here)
  for ext in "${EXTENSIONS[@]}"; do
    if [[ "$ext" == .* ]]; then
      args+=( -e "${ext#.}" )
    fi
  done
  fd "${args[@]}" . "$root" | wc -l | tr -d ' '
}

count_with_find() {
  local root="$1"
  local prune=( )
  for e in "${EXCLUDES[@]}"; do
    prune+=( -path "*/$e/*" -o -name "$e" )
  done
  local name=( )
  for ext in "${EXTENSIONS[@]}"; do
    if [[ "$ext" == .* ]]; then
      name+=( -name "*${ext}" -o )
    fi
  done
  # Drop trailing -o
  if [ ${#name[@]} -gt 0 ]; then unset 'name[${#name[@]}-1]'; fi
  if [ ${#prune[@]} -gt 0 ]; then
    find "$root" \( "${prune[@]}" \) -prune -o -type f \( "${name[@]}" \) -print | wc -l | tr -d ' '
  else
    find "$root" -type f \( "${name[@]}" \) -print | wc -l | tr -d ' '
  fi
}

for ROOT in "$@"; do
  if [ ! -d "$ROOT" ]; then
    echo "[skip] $ROOT (not a directory)" >&2
    continue
  fi
  if have_fd; then
    CNT=$(count_with_fd "$ROOT")
    TOOL=fd
  else
    CNT=$(count_with_find "$ROOT")
    TOOL=find
  fi
  echo "${ROOT}: ${CNT} files (via ${TOOL})"
done

