#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/context.sh"

INPUT=$(cat)
debug_log "session-start-inject.sh:entry" "sessionStart hook invoked" "$(echo "$INPUT" | jq -c '{composer_mode, conversation_id, cursor_version, generation_id, hook_event_name, is_background_agent, model, model_id, model_params, session_id, transcript_path, user_email, workspace_roots}' 2>/dev/null || echo '{"parse_error":true}')"
debug_log "session-start-inject.sh:env" "hook environment variables" "$(jq -nc \
  --arg project_dir "${CURSOR_PROJECT_DIR:-}" \
  --arg version "${CURSOR_VERSION:-}" \
  --arg user_email "${CURSOR_USER_EMAIL:-}" \
  --arg transcript_path "${CURSOR_TRANSCRIPT_PATH:-}" \
  --arg code_remote "${CURSOR_CODE_REMOTE:-}" \
  --arg claude_project_dir "${CLAUDE_PROJECT_DIR:-}" \
  '{CURSOR_PROJECT_DIR:$project_dir, CURSOR_VERSION:$version, CURSOR_USER_EMAIL:$user_email, CURSOR_TRANSCRIPT_PATH:$transcript_path, CURSOR_CODE_REMOTE:$code_remote, CLAUDE_PROJECT_DIR:$claude_project_dir}')"
COMPOSER_MODE_RAW=$(echo "$INPUT" | jq -r 'if .composer_mode == null then "" else .composer_mode // "" end')
IS_CLI=$(is_cli_agent "$COMPOSER_MODE_RAW" && echo "true" || echo "false")
COMPOSER_MODE="${COMPOSER_MODE_RAW:-agent}"
debug_log "session-start-inject.sh:branch" "composer_mode resolved" "$(jq -nc --arg raw "$COMPOSER_MODE_RAW" --arg mode "$COMPOSER_MODE" --arg cli "$IS_CLI" '{composer_mode_raw:$raw, composer_mode:$mode, is_cli:$cli}')"

if [[ "$COMPOSER_MODE" != "agent" ]]; then
  debug_log "session-start-inject.sh:skip" "skipped non-agent mode" "$(jq -nc --arg mode "$COMPOSER_MODE" '{composer_mode:$mode}')"
  echo '{}'
  exit 0
fi

BOILERPLATE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)/boilerplate"
PROJECT_CURSOR_DIR="${CURSOR_PROJECT_DIR:-$PWD}/.cursor"
SEEDED=()

seed_file() {
  local src="$1" dest="$2"
  [[ -f "$src" && ! -f "$dest" ]] || return 0
  mkdir -p "$(dirname "$dest")"
  cp "$src" "$dest"
  SEEDED+=("$dest")
}

seed_file "$BOILERPLATE_DIR/agent-memory/orchestrator/MEMORY.md" "$PROJECT_CURSOR_DIR/agent-memory/orchestrator/MEMORY.md"
for src in "$BOILERPLATE_DIR/chat-transcripts"/* "$BOILERPLATE_DIR/chat-transcripts"/.[!.]*; do
  [[ -f "$src" ]] || continue
  seed_file "$src" "$PROJECT_CURSOR_DIR/chat-transcripts/$(basename "$src")"
done

if ((${#SEEDED[@]} > 0)); then
  debug_log "session-start-inject.sh:seed" "boilerplate files seeded" "$(printf '%s\n' "${SEEDED[@]}" | jq -R . | jq -s -c '{seeded: .}')"
fi

OUTPUT='{}'
debug_log "session-start-inject.sh:exit" "sessionStart output" "$OUTPUT"
echo "$OUTPUT"
