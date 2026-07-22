#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/context.sh"

MAX_INJECT_CHARS=9000

INPUT=$(cat)
debug_log "main-agent-orchestrator-inject.sh:entry" "beforeSubmitPrompt hook invoked" "$(echo "$INPUT" | jq -c '{composer_mode, prompt: (.prompt // ""), prompt_len: ((.prompt // "") | length)}' 2>/dev/null || echo '{"parse_error":true}')"
COMPOSER_MODE_RAW=$(echo "$INPUT" | jq -r 'if .composer_mode == null then "" else .composer_mode // "" end')
IS_CLI=$(is_cli_agent "$COMPOSER_MODE_RAW" && echo "true" || echo "false")
COMPOSER_MODE="${COMPOSER_MODE_RAW:-agent}"
debug_log "main-agent-orchestrator-inject.sh:branch" "composer_mode resolved" "$(jq -nc --arg raw "$COMPOSER_MODE_RAW" --arg mode "$COMPOSER_MODE" --arg cli "$IS_CLI" '{composer_mode_raw:$raw, composer_mode:$mode, is_cli:$cli}')"

if [[ "$COMPOSER_MODE" != "agent" ]]; then
  debug_log "main-agent-orchestrator-inject.sh:skip" "skipped non-agent mode" "$(jq -nc --arg mode "$COMPOSER_MODE" --arg cli "$IS_CLI" '{composer_mode:$mode, is_cli:$cli}')"
  echo '{"continue": true}'
  exit 0
fi

CONTEXT=$(orchestrator_context)
if [[ -z "$CONTEXT" ]]; then
  debug_log "main-agent-orchestrator-inject.sh:empty" "no grounding rules file" '{"branch":"empty_context"}'
  echo '{"continue": true}'
  exit 0
fi

CONTEXT_LEN=${#CONTEXT}
if (( CONTEXT_LEN > MAX_INJECT_CHARS )); then
  HOOK_MSG="HOOK ISSUE:  ALERT USER THAT THE HOOK IS TRYING TO INJECT A MESSAGE ABOVE 9000 CHARS.  INJECTION ATTEMPT HAD ${CONTEXT_LEN} CHARS."
  OUTPUT=$(jq -nc --arg msg "$HOOK_MSG" '{continue: true, additional_context: $msg}')
else
  OUTPUT=$(jq -nc --arg ctx "$CONTEXT" '{continue: true, additional_context: $ctx}')
fi

debug_log "main-agent-orchestrator-inject.sh:exit" "beforeSubmitPrompt output" "$(echo "$OUTPUT" | jq -c --arg cli "$IS_CLI" --argjson context_len "$CONTEXT_LEN" '{
  has_additional_context: (.additional_context != null),
  context_len: $context_len,
  is_cli: $cli,
  preview: ((.additional_context // .user_message // "") | .[0:60])
}')"
echo "$OUTPUT"
