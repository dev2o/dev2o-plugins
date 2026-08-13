#!/usr/bin/env bash

DUMP_DIR="/tmp/cursor-hook-debug"
mkdir -p "$DUMP_DIR" 2>/dev/null || true

fail_open() {
  local reason="$1"
  echo "$(date -u): FAILED (advisor-model-deny) - $reason" >> "$DUMP_DIR/error.log"
  echo '{"permission": "allow"}'
  exit 0
}

INPUT=$(cat 2>/dev/null || echo "")
if [[ -z "$INPUT" ]]; then
  fail_open "Received empty stdin"
fi
echo "$INPUT" > "$DUMP_DIR/latest-advisor-model-deny-payload.json"

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

MODEL=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.model // empty' 2>/dev/null || echo "")
MODEL_LC=$(printf '%s' "$MODEL" | tr '[:upper:]' '[:lower:]')
case "$MODEL_LC" in
  *opus*|*grok*)
    exit 0
    ;;
esac

MSG='ERROR:  You must select a opus high thinking model or grok depending on the project.  see rules below, and then resubmit.

MODEL SELECTION RULES:
When invoking the `advisor` tool, select the `model` parameter from your available model list based on task severity:
- Use High-Thinking Claude-Opus for: Initial architectural plans, complex debugging, recurring errors, or deep refactoring.
- Use High-Thinking Cursor-Grok (or cheaper available model) for: Simple logic checks, fast course corrections, or budget-conscious tasks per user preference.'

if ! OUTPUT_JSON=$(jq -nc --arg m "$MSG" '{permission: "deny", agent_message: $m, user_message: $m}' 2>/dev/null); then
  fail_open "Failed to construct deny JSON payload with jq"
fi
printf '%s\n' "$OUTPUT_JSON"
exit 0
