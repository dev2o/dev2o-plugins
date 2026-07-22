#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/context.sh"

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.subagent_type // empty')
TRANSCRIPT_LOOKUP_ID=$(echo "$INPUT" | jq -r '.parent_conversation_id // .session_id // empty')
CONVERSATION_ID=$(echo "$INPUT" | jq -r '.conversation_id // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
TASK_LEN=$(echo "$INPUT" | jq -r '(.task // "") | length')

CONTEXT_RAW=$(subagent_context "$SUBAGENT_TYPE")
TOKENS_USED='[]'
if [[ -n "$CONTEXT_RAW" ]]; then
  TOKENS_USED=$(context_transcript_tokens_used "$CONTEXT_RAW")
fi

debug_log "subagent-context-inject.sh:entry" "subagentStart hook invoked" "$(jq -nc \
  --arg t "$SUBAGENT_TYPE" \
  --arg lid "$TRANSCRIPT_LOOKUP_ID" \
  --argjson task_len "$TASK_LEN" \
  --argjson tokens "$TOKENS_USED" \
  '{subagent_type:$t, transcript_lookup_id:$lid, task_len:$task_len, tokens_used:$tokens}')"

if [[ -z "$CONTEXT_RAW" ]]; then
  debug_log "subagent-context-inject.sh:empty" "no subagent context file" "$(jq -nc --arg t "$SUBAGENT_TYPE" '{subagent_type:$t, branch:"empty_context"}')"
  echo '{"permission": "allow"}'
  exit 0
fi

CONTEXT=$(build_subagent_context "$SUBAGENT_TYPE" "$TRANSCRIPT_LOOKUP_ID" "$CONVERSATION_ID" "$SESSION_ID")
if context_has_transcript_tokens "$CONTEXT_RAW"; then
  CONTEXT_LEN=$(printf '%s' "$CONTEXT" | wc -c | tr -d ' ')
  debug_log "subagent-context-inject.sh:render" "transcript tokens substituted" "$(jq -nc \
    --argjson tokens "$TOKENS_USED" \
    --argjson len "$CONTEXT_LEN" \
    '{branch:"token_substitution", tokens_used:$tokens, rendered_len:$len}')"
fi

OUTPUT=$(jq -nc --arg ctx "$CONTEXT" '{permission: "allow", additional_context: $ctx}')
debug_log "subagent-context-inject.sh:exit" "subagentStart output" "$(echo "$OUTPUT" | jq -c --arg t "$SUBAGENT_TYPE" '{subagent_type:$t, has_additional_context: (.additional_context != null), context_len: ((.additional_context // "") | length)}')"
echo "$OUTPUT"
