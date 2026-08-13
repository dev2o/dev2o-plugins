#!/usr/bin/env bash

DUMP_DIR="/tmp/cursor-hook-debug"
mkdir -p "$DUMP_DIR" 2>/dev/null || true

fail_open() {
  local reason="$1"
  echo "$(date -u): FAILED (advisor-first-turn-deny) - $reason" >> "$DUMP_DIR/error.log"
  echo '{"permission": "allow"}'
  exit 0
}

INPUT=$(cat 2>/dev/null || echo "")
if [[ -z "$INPUT" ]]; then
  fail_open "Received empty stdin"
fi
echo "$INPUT" > "$DUMP_DIR/latest-advisor-first-turn-deny-payload.json"

if ! command -v jq >/dev/null 2>&1; then
  fail_open "'jq' is not installed in PATH: $PATH"
fi

TOOL_NAME=$(printf '%s\n' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null || echo "")
if [[ "$TOOL_NAME" != "Task" ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

SUBAGENT_TYPE=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null || echo "")
if [[ "$SUBAGENT_TYPE" != "advisor" ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

if [[ -z "${CURSOR_PROJECT_DIR:-}" ]]; then
  fail_open "CURSOR_PROJECT_DIR is unset"
fi

CONVERSATION_ID=$(printf '%s\n' "$INPUT" | jq -r '.conversation_id // empty' 2>/dev/null || echo "")
if [[ -z "$CONVERSATION_ID" || "$CONVERSATION_ID" == *".."* || "$CONVERSATION_ID" == *"/"* ]]; then
  fail_open "Invalid or missing conversation_id"
fi

LOG_FILE="$CURSOR_PROJECT_DIR/.cursor/chat-transcripts/${CONVERSATION_ID}.jsonl"
COUNT=0
if [[ -f "$LOG_FILE" ]]; then
  COUNT=$(grep -cE '"hook_event_name":[[:space:]]*"beforeSubmitPrompt"' "$LOG_FILE" 2>/dev/null || true)
fi
COUNT=${COUNT:-0}

if [[ "$COUNT" -ge 2 ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

MSG='ensure your usage of the advisor follows the advisor_protocol, then reuse when ready'
if ! OUTPUT_JSON=$(jq -nc --arg m "$MSG" '{permission: "deny", agent_message: $m}' 2>/dev/null); then
  fail_open "Failed to construct deny JSON payload with jq"
fi
printf '%s\n' "$OUTPUT_JSON"
exit 0
