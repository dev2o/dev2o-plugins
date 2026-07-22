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
LOG_FILE="$LOG_DIR/${conversation_id}.jsonl"

# Cursor fires afterAgentThought twice per thought: once with the parent
# generation_id and once with a per-block suffixed id (…-0-abcd), with
# identical text. Skip the event if the previous line already captured the
# same thought.
hook_event=$(echo "$json_input" | jq -r '.hook_event_name // empty' 2>/dev/null || true)
if [[ "$hook_event" == "afterAgentThought" && -f "$LOG_FILE" ]]; then
  prev_line=$(tail -n 1 "$LOG_FILE" 2>/dev/null || true)
  if [[ -n "$prev_line" ]]; then
    is_dup=$(jq -n -c \
      --argjson prev "$prev_line" \
      --argjson cur "$json_input" \
      '($prev.hook_event_name == "afterAgentThought")
       and ($prev.text == $cur.text)
       and ($prev.duration_ms == $cur.duration_ms)' 2>/dev/null || echo false)
    if [[ "$is_dup" == "true" ]]; then
      exit 0
    fi
  fi
fi

echo "$json_input" | jq -c --arg ts "$timestamp" -f "$SCRUB_JQ" >> "$LOG_FILE"

exit 0
