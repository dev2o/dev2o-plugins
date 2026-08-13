#!/usr/bin/env bash

# Resolve base directories safely without relying on PWD fallbacks
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

# No-op debug function kept purely for backwards compatibility if external scripts call it
debug_log() {
  return 0
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

# Uses printf piping instead of here-strings (<<<) to avoid ephemeral /tmp file creation crashes in containers
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
    # If python3 or the script is missing, fail-open by returning raw context instead of crashing
    printf '%s' "$context"
    return 0
  fi

  # Pipe via printf to prevent Bash string truncation and avoid <<< /tmp file hazards
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

ID_UNAVAILABLE='(conversation id unavailable)'

advisor_wrap_transcript() {
  local transcript="$1"
  cat <<'EOF'
The Executor agent has paused its workflow. You must provide strategic oversight based on the transcript of its actions so far.

<environment_awareness>
You are operating within the Cursor IDE. You have implicit access to the workspace context, file contents, and codebase embeddings attached to this session. The <execution_transcript> represents what the Executor *thinks* it is doing; you must verify its assumptions against the actual codebase reality.
</environment_awareness>

<execution_transcript>
EOF
  printf '%s\n' "$transcript"
  cat <<'EOF'
</execution_transcript>

<advisor_directives>
1. Deduce the Objective: Read the earliest entries in the <execution_transcript> to identify the user's original goal.
2. Analyze the State: Evaluate the Executor's recent steps and errors. Are they on the right track or stuck in a loop?
3. Cross-Reference: Compare the transcript against your Cursor workspace context. Is the Executor making false assumptions about file structures or dependencies?
4. Direct: Output your strategic guidance immediately. Tell the Executor exactly what to do next, which files to target, or why its current approach is failing.
</advisor_directives>
EOF
}

_advisor_stub() {
  local dump_dir="/tmp/cursor-hook-debug"
  mkdir -p "$dump_dir" 2>/dev/null || true
  echo "$(date -u): FAILED (advisor inject) - $1" >> "$dump_dir/error.log"
  advisor_wrap_transcript "$ID_UNAVAILABLE"
}

advisor_injection_prompt() {
  local lookup_conversation_id="$1" fallback_conversation_id="${2:-}" session_id="${3:-}"
  local cid output transcripts_py

  cid=$(substitute_subagent_tokens "$CONVERSATION_ID_TOKEN" "$lookup_conversation_id" "$fallback_conversation_id" "$session_id")
  if [[ -z "$cid" || "$cid" == "$ID_UNAVAILABLE" || "$cid" == "$CONVERSATION_ID_TOKEN" ]]; then
    _advisor_stub "conversation id unavailable"
    return 0
  fi

  transcripts_py="${HOOKS_DIR}/../transcriptor/transcripts.py"
  if [[ ! -f "$transcripts_py" ]] || ! command -v python3 >/dev/null 2>&1; then
    _advisor_stub "transcripts CLI missing"
    return 0
  fi

  output=$(python3 "$transcripts_py" show "$cid" 2>/dev/null) || output=""
  if [[ -z "$output" ]]; then
    _advisor_stub "show failed or empty for ${cid}"
    return 0
  fi

  advisor_wrap_transcript "$output"
}

is_cli_agent() {
  local composer_mode_raw="$1"
  [[ -z "$composer_mode_raw" ]]
}