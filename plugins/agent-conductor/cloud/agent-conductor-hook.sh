#!/usr/bin/env bash
# Runs one agent-conductor hook script from the installed plugin.
#
# Cloud agents load hooks only from the project's own .cursor/hooks.json, so a
# project that wants agent-conductor on a cloud VM commits this launcher and
# cloud/hooks.json into .cursor/. See the plugin README, "Cloud agents".
#
# Usage: agent-conductor-hook.sh <plugin-relative script path>

DUMP_DIR="/tmp/cursor-hook-debug"
mkdir -p "$DUMP_DIR" 2>/dev/null || true

INPUT=$(cat 2>/dev/null || echo "")

default_payload() {
  local event=""
  if command -v jq >/dev/null 2>&1; then
    event=$(printf '%s\n' "$INPUT" | jq -r '.hook_event_name // empty' 2>/dev/null || echo "")
  fi
  case "$event" in
    beforeShellExecution|beforeReadFile|preToolUse|beforeMCPExecution)
      echo '{"permission": "allow"}' ;;
    beforeSubmitPrompt)
      echo '{"continue": true}' ;;
    *)
      echo '{}' ;;
  esac
}

CLOUD_MANIFEST="$HOME/.cursor/plugins/cache/.cloud-plugin-manifest.json"

fail_open() {
  local reason="$1"
  echo "$(date -u): FAILED (cloud launcher) - $reason" >> "$DUMP_DIR/error.log"
  default_payload
  exit 0
}

TARGET="${1:-}"

# One line per dispatch. This is the only record of which events a cloud agent
# actually delivers, since the events themselves are invisible from the session.
{
  event=""
  if command -v jq >/dev/null 2>&1; then
    event=$(printf '%s\n' "$INPUT" | jq -r '.hook_event_name // "?"' 2>/dev/null || echo "?")
  fi
  [[ -f "$CLOUD_MANIFEST" ]] && where="cloud" || where="desktop"
  printf '%s event=%s target=%s env=%s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${event:-?}" "${TARGET:-none}" "$where" \
    >> "$DUMP_DIR/cloud-launcher.log"
} 2>/dev/null

# Only a cloud VM writes this manifest, and only a cloud VM refuses to load the
# plugin's own hooks. On desktop the plugin hooks are already running, so
# dispatching here would double-fire every one of them.
if [[ ! -f "$CLOUD_MANIFEST" ]]; then
  default_payload
  exit 0
fi

[[ -n "$TARGET" ]] || fail_open "No plugin script argument"
[[ -n "$INPUT" ]] || fail_open "Received empty stdin"
command -v jq >/dev/null 2>&1 || fail_open "'jq' is not installed in PATH: $PATH"

plugin_root() {
  local manifest name root best=""
  # Depth-agnostic on purpose. Observed layouts include
  # cache/<marketplace>/<pluginId>/<sha>/ and cache/<marketplace>/<sha>/current/<name>/,
  # so a fixed-depth glob silently finds nothing on half of them. Newest wins.
  while IFS= read -r manifest; do
    [[ -n "$manifest" ]] || continue
    name=$(jq -r '.name // empty' "$manifest" 2>/dev/null || echo "")
    [[ "$name" == "agent-conductor" ]] || continue
    root=$(dirname "$(dirname "$manifest")")
    [[ -d "$root/hooks" ]] || continue
    if [[ -z "$best" || "$manifest" -nt "$best" ]]; then
      best="$manifest"
    fi
  done < <(find "$HOME/.cursor/plugins/cache" -path '*/.cursor-plugin/plugin.json' -type f 2>/dev/null)
  [[ -n "$best" ]] || return 1
  printf '%s\n' "$(dirname "$(dirname "$best")")"
}

# The override exists so this repository can test its own working tree on a
# cloud VM, where the installed copy is whatever landed on the marketplace ref.
if [[ -n "${AGENT_CONDUCTOR_PLUGIN_ROOT:-}" ]]; then
  PLUGIN_ROOT="$AGENT_CONDUCTOR_PLUGIN_ROOT"
  [[ -d "$PLUGIN_ROOT/hooks" ]] || fail_open "AGENT_CONDUCTOR_PLUGIN_ROOT has no hooks directory: $PLUGIN_ROOT"
else
  PLUGIN_ROOT=$(plugin_root) || fail_open "No installed agent-conductor plugin under $HOME/.cursor/plugins/cache"
fi

SCRIPT="$PLUGIN_ROOT/$TARGET"
[[ -f "$SCRIPT" ]] || fail_open "Plugin script missing at $SCRIPT"

export CURSOR_PLUGIN_ROOT="$PLUGIN_ROOT"
# A project hook runs with the working directory at the project root, so this is
# a resolved path rather than a guess. The delegated scripts refuse to write
# anything without it.
export CURSOR_PROJECT_DIR="${CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"

# sessionStart never runs on a cloud VM, so the CLI the advisor agents call is
# synced here instead, on whichever hook fires first.
if [[ -n "${CURSOR_PROJECT_DIR:-}" ]]; then
  CLI_SRC="$PLUGIN_ROOT/hooks/transcriptor/transcripts.py"
  CLI_DEST="$CURSOR_PROJECT_DIR/.cursor/chat-transcripts/_transcripts.py"
  # Compared by content, not mtime: a clone stamps a stale committed copy with a
  # fresh timestamp, and that copy may predate the brief verb the advisor calls.
  if [[ -f "$CLI_SRC" ]] && ! cmp -s "$CLI_SRC" "$CLI_DEST"; then
    if mkdir -p "$(dirname "$CLI_DEST")" 2>/dev/null; then
      cp -f "$CLI_SRC" "$CLI_DEST" 2>/dev/null || \
        echo "$(date -u): WARN (cloud launcher) - Failed to sync CLI to $CLI_DEST" >> "$DUMP_DIR/error.log"
      chmod +x "$CLI_DEST" 2>/dev/null || true
    fi
  fi
fi

OUTPUT=$(printf '%s\n' "$INPUT" | bash "$SCRIPT" 2>/dev/null)
STATUS=$?
[[ "$STATUS" -eq 0 ]] || fail_open "$SCRIPT exited $STATUS"

# The capture hooks answer with nothing at all, which is not a failure.
[[ -n "$OUTPUT" ]] || { default_payload; exit 0; }

printf '%s\n' "$OUTPUT"
exit 0
