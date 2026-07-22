#!/usr/bin/env bash

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_CONFIG_DIR="${CURSOR_PROJECT_DIR:-$PWD}/.cursor/dev2o-agent-conductor/config"

config_file() {
  local name="$1"
  if [[ -f "${PROJECT_CONFIG_DIR}/${name}" ]]; then
    echo "${PROJECT_CONFIG_DIR}/${name}"
  else
    echo "${HOOKS_DIR}/config/${name}"
  fi
}
DEBUG_TRIGGER="${HOOKS_DIR}/.debug"
DEBUG_LOG="${HOOKS_DIR}/hooks-debug.log"

hooks_debug_enabled() {
  [[ "${CURSOR_HOOKS_DEBUG:-}" == "1" ]] && return 0
  [[ -f "$DEBUG_TRIGGER" ]] && return 0
  return 1
}

debug_log() {
  hooks_debug_enabled || return 0
  local location="$1" message="$2" data_json="${3:-"{}"}"
  local ts
  ts=$(date +%s%3N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1000))')
  printf '{"location":"%s","message":"%s","data":%s,"timestamp":%s}\n' \
    "$location" "$message" "$data_json" "$ts" >> "$DEBUG_LOG" 2>/dev/null || true
}

orchestrator_context() {
  local file
  file=$(config_file "__agent-main.md")
  if [[ -f "$file" ]]; then
    cat "$file"
  fi
}

subagent_context() {
  local file
  file=$(config_file "agent-${1}.md")
  if [[ -f "$file" ]]; then
    cat "$file"
  fi
}

CONVERSATION_ID_TOKEN='{{CONVERSATION_ID}}'

context_has_transcript_tokens() {
  grep -qF "$CONVERSATION_ID_TOKEN" <<< "$1"
}

context_transcript_tokens_used() {
  if context_has_transcript_tokens "$1"; then
    echo '["CONVERSATION_ID"]'
  else
    echo '[]'
  fi
}

substitute_subagent_tokens() {
  local context="$1" lookup_conversation_id="$2" fallback_conversation_id="${3:-}" session_id="${4:-}"
  python3 "${HOOKS_DIR}/lib/transcript_tokens.py" \
    --conversation-id "${lookup_conversation_id}" \
    --fallback-conversation-id "${fallback_conversation_id}" \
    --session-id "${session_id}" \
    <<< "$context"
}

build_subagent_context() {
  local subagent_type="$1" lookup_conversation_id="$2" fallback_conversation_id="${3:-}" session_id="${4:-}"
  local context_raw
  context_raw=$(subagent_context "$subagent_type")
  [[ -z "$context_raw" ]] && return 0
  if context_has_transcript_tokens "$context_raw"; then
    substitute_subagent_tokens "$context_raw" "$lookup_conversation_id" "$fallback_conversation_id" "$session_id"
  else
    printf '%s' "$context_raw"
  fi
}

is_cli_agent() {
  local composer_mode_raw="$1"
  [[ -z "$composer_mode_raw" ]]
}
