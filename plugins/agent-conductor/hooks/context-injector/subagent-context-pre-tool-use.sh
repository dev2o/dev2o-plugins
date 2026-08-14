#!/usr/bin/env bash

DUMP_DIR="/tmp/cursor-hook-debug"
mkdir -p "$DUMP_DIR" 2>/dev/null || true

fail_open() {
  local reason="$1"
  echo "$(date -u): FAILED (preToolUse) - $reason" >> "$DUMP_DIR/error.log"
  echo '{"permission": "allow"}'
  exit 0
}

# 1. Capture stdin safely and save latest payload
INPUT=$(cat 2>/dev/null || echo "")
if [[ -z "$INPUT" ]]; then
  fail_open "Received empty stdin"
fi
echo "$INPUT" > "$DUMP_DIR/latest-preToolUse-payload.json"

# 2. Check essential dependencies
if ! command -v jq >/dev/null 2>&1; then
  fail_open "'jq' is not installed in PATH: $PATH"
fi

# 3. Safely locate and source the context library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT_LIB="$SCRIPT_DIR/lib/context.sh"

if [[ ! -f "$CONTEXT_LIB" ]]; then
  fail_open "Context library missing at $CONTEXT_LIB"
fi

source "$CONTEXT_LIB" 2>/dev/null || fail_open "Failed to source $CONTEXT_LIB"

# 4. Check if tool is "Task" (fast exit without logging if not a subagent task)
TOOL_NAME=$(printf '%s\n' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null || echo "")
if [[ "$TOOL_NAME" != "Task" ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

# 5. Safely extract variables without pipefail crashes
SUBAGENT_TYPE=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null || echo "")
CONVERSATION_ID=$(printf '%s\n' "$INPUT" | jq -r '.conversation_id // empty' 2>/dev/null || echo "")
PARENT_CONVERSATION_ID=$(printf '%s\n' "$INPUT" | jq -r '.parent_conversation_id // empty' 2>/dev/null || echo "")
SESSION_ID=$(printf '%s\n' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || echo "")
ORIG_PROMPT=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.prompt // empty' 2>/dev/null || echo "")

if [[ "$SUBAGENT_TYPE" == "advisor" ]]; then
  if ! command -v advisor_gatekeeper_prompt >/dev/null 2>&1; then
    fail_open "Function 'advisor_gatekeeper_prompt' not found after sourcing $CONTEXT_LIB"
  fi
  NEW_PROMPT=$(advisor_gatekeeper_prompt "$CONVERSATION_ID" "$PARENT_CONVERSATION_ID" "$SESSION_ID" 2>/dev/null || echo "")
  if [[ -z "$NEW_PROMPT" ]]; then
    echo "$(date -u): FAILED (preToolUse) - advisor_gatekeeper_prompt returned empty" >> "$DUMP_DIR/error.log"
    NEW_PROMPT=$(advisor_gatekeeper_prompt "" "" "" 2>/dev/null || echo "")
  fi
elif [[ "$SUBAGENT_TYPE" == "exe-advisor" ]]; then
  if ! command -v advisor_injection_prompt >/dev/null 2>&1; then
    fail_open "Function 'advisor_injection_prompt' not found after sourcing $CONTEXT_LIB"
  fi
  EXECUTOR_CID=""
  if command -v parse_exe_advisor_cid >/dev/null 2>&1; then
    EXECUTOR_CID=$(parse_exe_advisor_cid "$ORIG_PROMPT" 2>/dev/null || echo "")
  fi
  NEW_PROMPT=$(advisor_injection_prompt "$EXECUTOR_CID" "" "" 2>/dev/null || echo "")
  if [[ -z "$NEW_PROMPT" ]]; then
    echo "$(date -u): FAILED (preToolUse) - advisor_injection_prompt returned empty" >> "$DUMP_DIR/error.log"
    NEW_PROMPT=$(advisor_wrap_transcript "$ID_UNAVAILABLE")
  fi
else
  if ! command -v build_subagent_context >/dev/null 2>&1; then
    fail_open "Function 'build_subagent_context' not found after sourcing $CONTEXT_LIB"
  fi
  CONTEXT=$(build_subagent_context "$SUBAGENT_TYPE" "$CONVERSATION_ID" "$PARENT_CONVERSATION_ID" "$SESSION_ID" 2>/dev/null || echo "")
  if [[ -z "$CONTEXT" ]]; then
    echo '{"permission": "allow"}'
    exit 0
  fi
  NEW_PROMPT="${CONTEXT}

---

${ORIG_PROMPT}"
fi

if ! OUTPUT_JSON=$(jq -nc \
  --arg prompt "$NEW_PROMPT" \
  --argjson tool_input "$(printf '%s\n' "$INPUT" | jq -c '.tool_input' 2>/dev/null || echo "{}")" \
  '{permission: "allow", updated_input: ($tool_input + {prompt: $prompt})}' 2>/dev/null); then
  fail_open "Failed to construct final JSON payload with jq"
fi

echo "$OUTPUT_JSON"
exit 0