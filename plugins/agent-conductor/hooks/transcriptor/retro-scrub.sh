#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${CURSOR_PROJECT_DIR:-$(pwd)}"
LOG_DIR="$PROJECT_ROOT/.cursor/chat-transcripts"
SCRUB_JQ="$SCRIPT_DIR/scrub.jq"

if [[ ! -d "$LOG_DIR" ]]; then
  echo "No transcript directory: $LOG_DIR" >&2
  exit 0
fi

shopt -s nullglob
files=("$LOG_DIR"/*.jsonl)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "No transcript files in $LOG_DIR" >&2
  exit 0
fi

for file in "${files[@]}"; do
  tmp=$(mktemp)
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    ts=$(echo "$line" | jq -r '.ts // empty' 2>/dev/null || true)
    if [[ -z "$ts" ]]; then
      ts=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    fi
    echo "$line" | jq -c --arg ts "$ts" -f "$SCRUB_JQ" >> "$tmp"
  done < "$file"
  mv "$tmp" "$file"
  echo "Re-scrubbed $(basename "$file")"
done
