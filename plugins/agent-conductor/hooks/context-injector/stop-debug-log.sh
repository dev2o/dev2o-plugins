#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/context.sh"

INPUT=$(cat)
debug_log "stop-debug-log.sh:entry" "stop hook invoked" "$(echo "$INPUT" | jq -c '{composer_mode, conversation_id, cursor_version, generation_id, hook_event_name, is_background_agent, model, model_id, model_params, session_id, transcript_path, user_email, workspace_roots, status, keys: (keys // [])}' 2>/dev/null || echo '{"parse_error":true}')"
debug_log "stop-debug-log.sh:env" "hook environment variables" "$(jq -nc \
  --arg project_dir "${CURSOR_PROJECT_DIR:-}" \
  --arg version "${CURSOR_VERSION:-}" \
  --arg user_email "${CURSOR_USER_EMAIL:-}" \
  --arg transcript_path "${CURSOR_TRANSCRIPT_PATH:-}" \
  --arg code_remote "${CURSOR_CODE_REMOTE:-}" \
  --arg claude_project_dir "${CLAUDE_PROJECT_DIR:-}" \
  '{CURSOR_PROJECT_DIR:$project_dir, CURSOR_VERSION:$version, CURSOR_USER_EMAIL:$user_email, CURSOR_TRANSCRIPT_PATH:$transcript_path, CURSOR_CODE_REMOTE:$code_remote, CLAUDE_PROJECT_DIR:$claude_project_dir}')"
echo '{}'
