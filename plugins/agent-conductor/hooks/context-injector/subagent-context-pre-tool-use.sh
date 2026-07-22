#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/context.sh"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
if [[ "$TOOL_NAME" != "Task" ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty')
CONVERSATION_ID=$(echo "$INPUT" | jq -r '.conversation_id // empty')
PARENT_CONVERSATION_ID=$(echo "$INPUT" | jq -r '.parent_conversation_id // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
ORIG_PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // empty')

CONTEXT=$(build_subagent_context "$SUBAGENT_TYPE" "$CONVERSATION_ID" "$PARENT_CONVERSATION_ID" "$SESSION_ID")
if [[ -z "$CONTEXT" ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

NEW_PROMPT="${CONTEXT}

---

${ORIG_PROMPT}"

CONTEXT_LEN=$(printf '%s' "$CONTEXT" | wc -c | tr -d ' ')
HAS_UNAVAILABLE=$(grep -qF '(conversation id unavailable)' <<< "$CONTEXT" && echo true || echo false)
debug_log "subagent-context-pre-tool-use.sh:exit" "preToolUse prompt injection" "$(jq -nc \
  --arg t "$SUBAGENT_TYPE" \
  --arg cid "$CONVERSATION_ID" \
  --arg pcid "$PARENT_CONVERSATION_ID" \
  --arg sid "$SESSION_ID" \
  --argjson context_len "$CONTEXT_LEN" \
  --argjson has_unavailable "$HAS_UNAVAILABLE" \
  '{subagent_type:$t, conversation_id:$cid, parent_conversation_id:$pcid, session_id:$sid, context_len:$context_len, conversation_id_unavailable:$has_unavailable}')"

jq -nc \
  --arg prompt "$NEW_PROMPT" \
  --argjson tool_input "$(echo "$INPUT" | jq -c '.tool_input')" \
  '{permission: "allow", updated_input: ($tool_input + {prompt: $prompt})}'
