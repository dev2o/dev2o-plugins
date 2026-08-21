#!/usr/bin/env bash

DUMP_DIR="/tmp/cursor-hook-debug"
mkdir -p "$DUMP_DIR" 2>/dev/null || true

# Helper: If anything breaks, log why to /tmp and output default allow so prompt submission NEVER freezes.
fail_open() {
  local reason="$1"
  echo "$(date -u): FAILED (beforeSubmitPrompt) - $reason" >> "$DUMP_DIR/error.log"
  echo '{"continue": true}'
  exit 0
}

# 1. Capture stdin safely and save latest payload for debugging
INPUT=$(cat 2>/dev/null || echo "")
if [[ -z "$INPUT" ]]; then
  fail_open "Received empty stdin"
fi
echo "$INPUT" > "$DUMP_DIR/latest-beforeSubmitPrompt-payload.json"

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

# 4. Safely resolve composer mode without pipefail crashes
COMPOSER_MODE_RAW=$(printf '%s\n' "$INPUT" | jq -r 'if .composer_mode == null then "" else .composer_mode // "" end' 2>/dev/null || echo "")
COMPOSER_MODE="${COMPOSER_MODE_RAW:-agent}"

# Fast exit if not in agent mode
if [[ "$COMPOSER_MODE" != "agent" ]]; then
  echo '{"continue": true}'
  exit 0
fi

# 5. Execute library function with existence guard
if ! command -v orchestrator_context >/dev/null 2>&1; then
  fail_open "Function 'orchestrator_context' not found after sourcing $CONTEXT_LIB"
fi

CONVERSATION_ID=$(printf '%s\n' "$INPUT" | jq -r '.conversation_id // empty' 2>/dev/null || echo "")
PROMPT=$(printf '%s\n' "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || echo "")

# This context tells its reader to delegate work to subagents, so a subagent must
# never receive it. A cloud Task child looks exactly like a main agent here, so
# identity comes from the spawn registry: the prompt the spawn hook recorded on
# the child's first turn, and the conversation id from then on.
if NATIVE_TYPE=$(native_child_type "$INPUT"); then
  log_inject_decision "$CONVERSATION_ID" "skip" "payload names it a child ($NATIVE_TYPE)"
  claim_subagent "$CONVERSATION_ID"
  echo '{"continue": true}'
  exit 0
fi
if is_known_subagent "$CONVERSATION_ID"; then
  log_inject_decision "$CONVERSATION_ID" "skip" "registered child"
  echo '{"continue": true}'
  exit 0
fi
if [[ -n "$PROMPT" ]] && spawn_recorded "$PROMPT"; then
  log_inject_decision "$CONVERSATION_ID" "skip" "prompt matches a recorded spawn"
  claim_subagent "$CONVERSATION_ID"
  echo '{"continue": true}'
  exit 0
fi
log_inject_decision "$CONVERSATION_ID" "inject" "main agent"

CONTEXT=$(orchestrator_context 2>/dev/null || echo "")
if [[ -z "$CONTEXT" ]]; then
  echo '{"continue": true}'
  exit 0
fi

# The plugin's own hooks and a project launcher can both deliver this event, and
# unlike a capture an inject cannot recognize its own duplicate after the fact.
# One claim per prompt, keyed by conversation and generation.
CLAIM_ID=$(printf '%s\n' "$INPUT" | jq -r '[(.conversation_id // empty), (.generation_id // empty)] | join("-")' 2>/dev/null || echo "")
if [[ -n "$CLAIM_ID" && "$CLAIM_ID" != "-" && "$CLAIM_ID" != *".."* && "$CLAIM_ID" != *"/"* ]]; then
  CLAIM_FILE="$DUMP_DIR/injected-$CLAIM_ID"
  if ! (set -o noclobber; : > "$CLAIM_FILE") 2>/dev/null; then
    echo '{"continue": true}'
    exit 0
  fi
fi

# 6. Check character length and construct final JSON payload
MAX_INJECT_CHARS=9000
CONTEXT_LEN=${#CONTEXT}

if (( CONTEXT_LEN > MAX_INJECT_CHARS )); then
  HOOK_MSG="HOOK ISSUE: ALERT USER THAT THE HOOK IS TRYING TO INJECT A MESSAGE ABOVE 9000 CHARS. INJECTION ATTEMPT HAD ${CONTEXT_LEN} CHARS."
  if ! OUTPUT_JSON=$(jq -nc --arg msg "$HOOK_MSG" '{continue: true, additional_context: $msg}' 2>/dev/null); then
    fail_open "Failed to construct size-warning JSON payload with jq"
  fi
else
  if ! OUTPUT_JSON=$(jq -nc --arg ctx "$CONTEXT" '{continue: true, additional_context: $ctx}' 2>/dev/null); then
    fail_open "Failed to construct context JSON payload with jq"
  fi
fi

echo "$OUTPUT_JSON"
exit 0