#!/usr/bin/env bash
# UNUSED: not registered in hooks.json. Disabled so the gatekeeper
# can decide whether a first-turn advisor call is premature. Re-register if that approach fails.

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
  exit 0
fi

SUBAGENT_TYPE=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null || echo "")
if [[ "$SUBAGENT_TYPE" != "advisor" ]]; then
  exit 0
fi

if [[ -z "${CURSOR_PROJECT_DIR:-}" ]]; then
  fail_open "CURSOR_PROJECT_DIR is unset"
fi

CONVERSATION_ID=$(printf '%s\n' "$INPUT" | jq -r '.conversation_id // empty' 2>/dev/null || echo "")
if [[ -z "$CONVERSATION_ID" || "$CONVERSATION_ID" == *".."* || "$CONVERSATION_ID" == *"/"* ]]; then
  fail_open "Invalid or missing conversation_id"
fi

GEN_ID=$(printf '%s\n' "$INPUT" | jq -r '.generation_id // empty' 2>/dev/null || echo "")
if [[ -z "$GEN_ID" ]]; then
  fail_open "Missing generation_id"
fi

LOG_FILE="$CURSOR_PROJECT_DIR/.cursor/chat-transcripts/${CONVERSATION_ID}.jsonl"
if [[ -f "$LOG_FILE" ]]; then
  if grep -E "\"generation_id\":[[:space:]]*\"${GEN_ID}\"" "$LOG_FILE" 2>/dev/null \
    | grep -qE '"hook_event_name":[[:space:]]*"beforeReadFile"|"tool_name":[[:space:]]*"Grep"'; then
    exit 0
  fi
fi

MSG='SYSTEM BLOCK: The Advisor cannot be called on Turn 1. RULE: You must first gather context (read files, check environment, establish baseline) before requesting strategic guidance. NEXT STEP: Proceed with information gathering. CRITICAL: This tool is fully functional. Do NOT avoid using the Advisor later. You are expected to call it once you have initial findings, per the advisor_protocol.'
if ! OUTPUT_JSON=$(jq -nc --arg m "$MSG" '{permission: "deny", agent_message: $m, user_message: $m}' 2>/dev/null); then
  fail_open "Failed to construct deny JSON payload with jq"
fi
printf '%s\n' "$OUTPUT_JSON"
exit 0
