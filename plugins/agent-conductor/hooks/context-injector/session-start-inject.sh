#!/usr/bin/env bash

DUMP_DIR="/tmp/cursor-hook-debug"
mkdir -p "$DUMP_DIR" 2>/dev/null || true

# Helper: If anything breaks, log why to /tmp and output default empty JSON so session startup NEVER freezes.
fail_open() {
  local reason="$1"
  echo "$(date -u): FAILED (sessionStart) - $reason" >> "$DUMP_DIR/error.log"
  echo '{}'
  exit 0
}

# 1. Capture stdin safely and save latest payload for debugging
INPUT=$(cat 2>/dev/null || echo "")
if [[ -z "$INPUT" ]]; then
  fail_open "Received empty stdin"
fi
echo "$INPUT" > "$DUMP_DIR/latest-sessionStart-payload.json"

# 2. Check essential dependencies
if ! command -v jq >/dev/null 2>&1; then
  fail_open "'jq' is not installed in PATH: $PATH"
fi

# 3. Safely locate and source the context library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT_LIB="$SCRIPT_DIR/lib/context.sh"

if [[ ! -f "$CONTEXT_LIB" ]]; then
  fail_open "Context library missing at $CONTEXT_LIB"
fi

source "$CONTEXT_LIB" 2>/dev/null || fail_open "Failed to source $CONTEXT_LIB"

# 4. Safely resolve composer mode without pipefail crashes
COMPOSER_MODE_RAW=$(printf '%s\n' "$INPUT" | jq -r 'if .composer_mode == null then "" else .composer_mode // "" end' 2>/dev/null || echo "")
COMPOSER_MODE="${COMPOSER_MODE_RAW:-agent}"

# Fast exit if not in agent mode
if [[ "$COMPOSER_MODE" != "agent" ]]; then
  echo '{}'
  exit 0
fi

# 5. Resolve directories without blind fallbacks
# If CURSOR_PROJECT_DIR is unset, fail open rather than littering random directories across the OS
if [[ -z "${CURSOR_PROJECT_DIR:-}" ]]; then
  fail_open "CURSOR_PROJECT_DIR is unset; cannot safely determine target .cursor directory"
fi

BOILERPLATE_DIR="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd)/boilerplate"
PROJECT_CURSOR_DIR="$CURSOR_PROJECT_DIR/.cursor"

if [[ ! -d "$BOILERPLATE_DIR" ]]; then
  fail_open "Boilerplate source directory not found at $BOILERPLATE_DIR"
fi

# 6. Resilience-wrapped file seeding/syncing functions
seed_file() {
  local src="$1" dest="$2"
  [[ -f "$src" && ! -f "$dest" ]] || return 0
  if ! mkdir -p "$(dirname "$dest")" 2>/dev/null; then
    echo "$(date -u): WARN (sessionStart) - Cannot create dir for $dest" >> "$DUMP_DIR/error.log"
    return 0
  fi
  if ! cp "$src" "$dest" 2>/dev/null; then
    echo "$(date -u): WARN (sessionStart) - Failed to copy $src to $dest" >> "$DUMP_DIR/error.log"
  fi
}

sync_file() {
  local src="$1" dest="$2"
  [[ -f "$src" ]] || return 0
  if ! mkdir -p "$(dirname "$dest")" 2>/dev/null; then
    echo "$(date -u): WARN (sessionStart) - Cannot create dir for $dest" >> "$DUMP_DIR/error.log"
    return 0
  fi
  if ! cp -f "$src" "$dest" 2>/dev/null; then
    echo "$(date -u): WARN (sessionStart) - Failed to sync $src to $dest" >> "$DUMP_DIR/error.log"
    return 0
  fi
  chmod +x "$dest" 2>/dev/null || true
}

# 7. Execute syncing and seeding safely
TRANSCRIPTS_SRC="$(cd "$SCRIPT_DIR/../transcriptor" 2>/dev/null && pwd)/transcripts.py"
sync_file "$TRANSCRIPTS_SRC" "$PROJECT_CURSOR_DIR/chat-transcripts/_transcripts.py"

seed_file "$BOILERPLATE_DIR/agent-memory/orchestrator/MEMORY.md" "$PROJECT_CURSOR_DIR/agent-memory/orchestrator/MEMORY.md"

# Safe glob iteration without crashing if directory is empty or missing
if [[ -d "$BOILERPLATE_DIR/chat-transcripts" ]]; then
  for src in "$BOILERPLATE_DIR/chat-transcripts"/* "$BOILERPLATE_DIR/chat-transcripts"/.[!.]*; do
    [[ -f "$src" ]] || continue
    seed_file "$src" "$PROJECT_CURSOR_DIR/chat-transcripts/$(basename "$src")"
  done
fi

echo '{}'
exit 0