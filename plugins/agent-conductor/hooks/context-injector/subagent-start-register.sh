#!/usr/bin/env bash
# subagentStart: record the child's own id so later hooks can tell it apart from
# a main agent. This is the exact signal; prompt matching is the fallback for
# surfaces that never deliver this event.

DUMP_DIR="/tmp/cursor-hook-debug"
mkdir -p "$DUMP_DIR" 2>/dev/null || true

fail_open() {
  echo "$(date -u): FAILED (subagentStart) - $1" >> "$DUMP_DIR/error.log"
  echo '{"permission": "allow"}'
  exit 0
}

INPUT=$(cat 2>/dev/null || echo "")
[[ -n "$INPUT" ]] || fail_open "Received empty stdin"
echo "$INPUT" > "$DUMP_DIR/latest-subagentStart-payload.json"

command -v jq >/dev/null 2>&1 || fail_open "'jq' is not installed in PATH: $PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT_LIB="$SCRIPT_DIR/lib/context.sh"
[[ -f "$CONTEXT_LIB" ]] || fail_open "Context library missing at $CONTEXT_LIB"
source "$CONTEXT_LIB" 2>/dev/null || fail_open "Failed to source $CONTEXT_LIB"

command -v record_subagent_start >/dev/null 2>&1 || fail_open "record_subagent_start not found"
record_subagent_start "$INPUT"

echo '{"permission": "allow"}'
exit 0
