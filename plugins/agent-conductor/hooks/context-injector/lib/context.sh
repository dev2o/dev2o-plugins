#!/usr/bin/env bash

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)"
PROJECT_CONFIG_DIR="${CURSOR_PROJECT_DIR:-$HOME/.cursor-fallback}/.cursor/dev2o-agent-conductor/config"

config_file() {
  local name="$1"
  if [[ -f "${PROJECT_CONFIG_DIR}/${name}" ]]; then
    printf '%s\n' "${PROJECT_CONFIG_DIR}/${name}"
  else
    printf '%s\n' "${HOOKS_DIR}/config/${name}"
  fi
}

orchestrator_context() {
  local file
  file=$(config_file "__agent-main.md")
  if [[ -f "$file" ]]; then
    cat "$file" 2>/dev/null || true
  fi
}

subagent_context() {
  local file
  file=$(config_file "agent-${1}.md")
  if [[ -f "$file" ]]; then
    cat "$file" 2>/dev/null || true
  fi
}

CONVERSATION_ID_TOKEN='{{CONVERSATION_ID}}'
PROJECT_DIR_TOKEN='{{PROJECT_DIR}}'

context_has_transcript_tokens() {
  local content="$1"
  if printf '%s' "$content" | grep -qF "$CONVERSATION_ID_TOKEN" 2>/dev/null; then
    return 0
  fi
  if printf '%s' "$content" | grep -qF "$PROJECT_DIR_TOKEN" 2>/dev/null; then
    return 0
  fi
  return 1
}

substitute_subagent_tokens() {
  local context="$1" lookup_conversation_id="$2" fallback_conversation_id="${3:-}" session_id="${4:-}"
  local py_script="${HOOKS_DIR}/lib/transcript_tokens.py"
  
  if [[ ! -f "$py_script" ]] || ! command -v python3 >/dev/null 2>&1; then
    printf '%s' "$context"
    return 0
  fi

  printf '%s' "$context" | python3 "$py_script" \
    --conversation-id "${lookup_conversation_id}" \
    --fallback-conversation-id "${fallback_conversation_id}" \
    --session-id "${session_id}" 2>/dev/null || printf '%s' "$context"
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

# Subagent identification.
#
# A cloud Task child is indistinguishable from a main agent in the hook payload:
# new conversation_id, composer_mode "agent", no parent_conversation_id, no
# subagent_type. Without this registry the orchestrator context, which tells its
# reader to delegate work to subagents, gets injected into subagents.
#
# The spawn hook knows the exact prompt each child will receive, so that prompt
# is the binding key. A child's first submission matches it; from then on the
# child is known by conversation id, which covers later turns and resumes.

REGISTRY_DIR="${CURSOR_HOOK_REGISTRY_DIR:-/tmp/cursor-hook-debug/registry}"

prompt_key() {
  local text="$1" digest=""
  if command -v sha256sum >/dev/null 2>&1; then
    digest=$(printf '%s' "$text" | sha256sum 2>/dev/null | cut -d' ' -f1)
  elif command -v shasum >/dev/null 2>&1; then
    digest=$(printf '%s' "$text" | shasum -a 256 2>/dev/null | cut -d' ' -f1)
  fi
  if [[ -z "$digest" ]]; then
    digest="len$(printf '%s' "$text" | wc -c | tr -d ' ')-$(printf '%s' "$text" | cksum 2>/dev/null | cut -d' ' -f1)"
  fi
  printf '%s' "$digest"
}

record_spawn() {
  local key
  key=$(prompt_key "$1")
  [[ -n "$key" ]] || return 0
  mkdir -p "$REGISTRY_DIR" 2>/dev/null || return 0
  grep -qxF "$key" "$REGISTRY_DIR/spawns" 2>/dev/null && return 0
  printf '%s\n' "$key" >> "$REGISTRY_DIR/spawns" 2>/dev/null || true
}

spawn_recorded() {
  local key
  key=$(prompt_key "$1")
  [[ -n "$key" ]] || return 1
  grep -qxF "$key" "$REGISTRY_DIR/spawns" 2>/dev/null
}

is_known_subagent() {
  local id="$1"
  [[ -n "$id" ]] || return 1
  grep -qxF "$id" "$REGISTRY_DIR/subagents" 2>/dev/null
}

claim_subagent() {
  local id="$1"
  [[ -n "$id" ]] || return 0
  mkdir -p "$REGISTRY_DIR" 2>/dev/null || return 0
  grep -qxF "$id" "$REGISTRY_DIR/subagents" 2>/dev/null && return 0
  printf '%s\n' "$id" >> "$REGISTRY_DIR/subagents" 2>/dev/null || true
}