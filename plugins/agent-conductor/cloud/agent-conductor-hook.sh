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

fail_open() {
  local reason="$1"
  echo "$(date -u): FAILED (cloud launcher) - $reason" >> "$DUMP_DIR/error.log"
  local event=""
  if command -v jq >/dev/null 2>&1; then
    event=$(printf '%s\n' "$INPUT" | jq -r '.hook_event_name // empty' 2>/dev/null || echo "")
  fi
  case "$event" in
    beforeShellExecution|beforeReadFile|preToolUse|beforeMCPExecution)
      echo '{"permission": "allow"}' ;;
    *)
      echo '{}' ;;
  esac
  exit 0
}

TARGET="${1:-}"
[[ -n "$TARGET" ]] || fail_open "No plugin script argument"
[[ -n "$INPUT" ]] || fail_open "Received empty stdin"
command -v jq >/dev/null 2>&1 || fail_open "'jq' is not installed in PATH: $PATH"

plugin_root() {
  local manifest name
  # Newest install wins: the cache keeps one directory per plugin revision.
  while IFS= read -r manifest; do
    name=$(jq -r '.name // empty' "$manifest" 2>/dev/null || echo "")
    if [[ "$name" == "agent-conductor" ]]; then
      printf '%s\n' "$(dirname "$(dirname "$manifest")")"
      return 0
    fi
  done < <(ls -1t "$HOME"/.cursor/plugins/cache/*/*/*/.cursor-plugin/plugin.json 2>/dev/null)
  return 1
}

PLUGIN_ROOT=$(plugin_root) || fail_open "No installed agent-conductor plugin under $HOME/.cursor/plugins/cache"

SCRIPT="$PLUGIN_ROOT/$TARGET"
[[ -f "$SCRIPT" ]] || fail_open "Plugin script missing at $SCRIPT"

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
[[ -n "$OUTPUT" ]] || fail_open "No output from $SCRIPT"

printf '%s\n' "$OUTPUT"
exit 0
