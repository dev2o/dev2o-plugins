#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${CURSOR_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
LOG_DIR="$PROJECT_ROOT/.cursor/chat-transcripts"
SCRUB_JQ="$SCRIPT_DIR/scrub.jq"

json_input=$(cat)
conversation_id=$(echo "$json_input" | jq -r '.conversation_id // empty' 2>/dev/null || true)

if [[ -z "$conversation_id" ]]; then
  exit 0
fi

if [[ "$conversation_id" == */* ]] || [[ "$conversation_id" == *..* ]]; then
  exit 0
fi

timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
mkdir -p "$LOG_DIR"
echo "$json_input" | jq -c --arg ts "$timestamp" -f "$SCRUB_JQ" >> "$LOG_DIR/${conversation_id}.jsonl"

exit 0
