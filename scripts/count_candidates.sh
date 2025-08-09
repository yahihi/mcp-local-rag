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

# Helpers to read JSON keys from a given config file
read_config_file_key() {
  local file="$1"; shift
  local key="$1"; shift
  if [ -f "$file" ]; then
    python3 - "$file" "$key" <<'PY' || true
import json,sys
path=sys.argv[1]
key=sys.argv[2]
cfg=json.load(open(path))
for v in cfg.get(key, []):
    print(v)
PY
  fi
}

# Defaults when no config provided
DEFAULT_EXT=(.py .md .json .yaml .yml .toml)
DEFAULT_EXC=(.git venv .venv env site-packages site_packages __pycache__ node_modules .pytest_cache .mypy_cache .ruff_cache dist build .next target logs log output outputs artifacts checkpoints data datasets)

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
  # Load base repo config
  mapfile -t EXCLUDES < <(read_config_file_key "$REPO_ROOT/config.json" exclude_dirs)
  mapfile -t EXTENSIONS < <(read_config_file_key "$REPO_ROOT/config.json" file_extensions)
  # Per-project override if present
  PROJECT_CFG="$ROOT/.mcp-local-rag.json"
  if [ -f "$PROJECT_CFG" ]; then
    # Override arrays if keys present
    mapfile -t EXC2 < <(read_config_file_key "$PROJECT_CFG" exclude_dirs)
    mapfile -t EXT2 < <(read_config_file_key "$PROJECT_CFG" file_extensions)
    if [ ${#EXC2[@]} -gt 0 ]; then EXCLUDES=("${EXC2[@]}"); fi
    if [ ${#EXT2[@]} -gt 0 ]; then EXTENSIONS=("${EXT2[@]}"); fi
  fi
  # Apply defaults if still empty
  if [ ${#EXTENSIONS[@]} -eq 0 ]; then EXTENSIONS=("${DEFAULT_EXT[@]}"); fi
  if [ ${#EXCLUDES[@]} -eq 0 ]; then EXCLUDES=("${DEFAULT_EXC[@]}"); fi

  if have_fd; then
    CNT=$(count_with_fd "$ROOT")
    TOOL=fd
  else
    CNT=$(count_with_find "$ROOT")
    TOOL=find
  fi
  echo "${ROOT}: ${CNT} files (via ${TOOL})"

  # If only one root provided, show top-level breakdown
  if [ "$#" -eq 1 ]; then
    echo "Top-level breakdown (non-zero):"
    # Count files directly under root
    if [ "$TOOL" = "fd" ]; then
      ROOT_FILES=$(fd -t f -d 1 $(printf ' -E %q' "${EXCLUDES[@]}") \
        $(printf ' -e %q' "${EXTENSIONS[@]/#/}") . "$ROOT" 2>/dev/null | wc -l | tr -d ' ')
    else
      # find variant: maxdepth 1 and names
      name=( )
      for ext in "${EXTENSIONS[@]}"; do
        [[ "$ext" == .* ]] && name+=( -name "*${ext}" -o )
      done
      [ ${#name[@]} -gt 0 ] && unset 'name[${#name[@]}-1]'
      ROOT_FILES=$(find "$ROOT" -maxdepth 1 -type f \( "${name[@]}" \) -print | wc -l | tr -d ' ')
    fi
    [ "${ROOT_FILES}" != "0" ] && echo "  (root files): ${ROOT_FILES}"

    # List immediate subdirectories and count per directory
    while IFS= read -r child; do
      base=$(basename "$child")
      # Skip excluded directory names
      skip=false
      for pat in "${EXCLUDES[@]}"; do
        if [[ "$base" == $pat ]]; then skip=true; break; fi
      done
      $skip && continue
      if [ "$TOOL" = "fd" ]; then
        subcnt=$(count_with_fd "$child")
      else
        subcnt=$(count_with_find "$child")
      fi
      [ "${subcnt}" != "0" ] && echo "  ${base}: ${subcnt}"
    done < <(find "$ROOT" -mindepth 1 -maxdepth 1 -type d -print)
  fi
done
