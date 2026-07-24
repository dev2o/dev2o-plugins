#!/usr/bin/env bash
# We deliberately do NOT use 'set -euo pipefail'. We handle errors explicitly to prevent silent aborts.

DUMP_DIR="/tmp/cursor-hook-debug"
mkdir -p "$DUMP_DIR" 2>/dev/null || true

# 1. Capture raw stdin immediately.
# If reading fails or is empty, dump a timestamped error to /tmp and exit cleanly.
json_input=$(cat 2>/dev/null || echo "")
if [[ -z "$json_input" ]]; then
  echo "$(date -u): FAILED - Received empty stdin" >> "$DUMP_DIR/error.log"
  exit 0
fi

# Always save the latest raw payload so you can inspect exactly what Cursor sent
echo "$json_input" > "$DUMP_DIR/latest-payload.json"

# 2. Explicit Env Var Check - ZERO FALLBACK GUESSING
# If CURSOR_PROJECT_DIR is unset, log exactly why to /tmp and abort. Do not guess paths.
if [[ -z "${CURSOR_PROJECT_DIR:-}" ]]; then
  echo "$(date -u): FAILED - CURSOR_PROJECT_DIR is unset. Payload saved to latest-payload.json" >> "$DUMP_DIR/error.log"
  exit 0
fi

LOG_DIR="$CURSOR_PROJECT_DIR/.cursor/chat-transcripts"
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
  echo "$(date -u): FAILED - Cannot create directory $LOG_DIR. Permission issue?" >> "$DUMP_DIR/error.log"
  exit 0
fi

# 3. Explicit Dependency Check (Log to /tmp instead of black-hole >&2)
if ! command -v jq >/dev/null 2>&1; then
  echo "$(date -u): FAILED - 'jq' is not installed in PATH: $PATH" >> "$DUMP_DIR/error.log"
  exit 0
fi

# 4. Safe ID Extraction without pipefail crashes
conversation_id=$(printf '%s\n' "$json_input" | jq -r '.conversation_id // empty' 2>/dev/null || echo "")
if [[ -z "$conversation_id" ]]; then
  echo "$(date -u): FAILED - Could not extract conversation_id from payload" >> "$DUMP_DIR/error.log"
  exit 0
fi

# Basic path safety without bloated regex
if [[ "$conversation_id" == *".."* ]] || [[ "$conversation_id" == *"/"* ]]; then
  echo "$(date -u): FAILED - Invalid conversation_id format: $conversation_id" >> "$DUMP_DIR/error.log"
  exit 0
fi

LOG_FILE="$LOG_DIR/${conversation_id}.jsonl"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRUB_JQ="$SCRIPT_DIR/scrub.jq"

if [[ ! -f "$SCRUB_JQ" ]]; then
  echo "$(date -u): FAILED - Scrub filter missing at $SCRUB_JQ" >> "$DUMP_DIR/error.log"
  exit 0
fi

# 5. Deduplication Check (No locking, simple inline read)
hook_event=$(printf '%s\n' "$json_input" | jq -r '.hook_event_name // empty' 2>/dev/null || echo "")
if [[ "$hook_event" == "afterAgentThought" && -f "$LOG_FILE" ]]; then
  prev_line=$(tail -n 1 "$LOG_FILE" 2>/dev/null || echo "")
  if [[ -n "$prev_line" ]]; then
    is_dup=$(jq -n -c \
      --argjson prev "$prev_line" \
      --argjson cur "$json_input" \
      '($prev.hook_event_name == "afterAgentThought") and ($prev.text == $cur.text)' 2>/dev/null || echo "false")
    if [[ "$is_dup" == "true" ]]; then
      exit 0
    fi
  fi
fi

# 6. Append to transcript. If it fails, log the failure to /tmp!
timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
if ! printf '%s\n' "$json_input" | jq -c --arg ts "$timestamp" -f "$SCRUB_JQ" >> "$LOG_FILE" 2>/dev/null; then
  echo "$(date -u): FAILED - jq scrub or append failed for $LOG_FILE" >> "$DUMP_DIR/error.log"
fi

exit 0