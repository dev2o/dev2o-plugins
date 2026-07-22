#!/usr/bin/env bash
set -euo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEBUG_TRIGGER="${HOOKS_DIR}/.debug"
DEBUG_LOG="${HOOKS_DIR}/hooks-debug.log"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command>

Commands:
  on      Enable hook debug logging (creates .cursor/hooks/.debug)
  off     Disable hook debug logging
  status  Show whether debug is enabled and log path
  clear   Delete the debug log file
  tail    Follow the debug log (tail -f)
EOF
}

cmd="${1:-status}"

case "$cmd" in
  on)
    touch "$DEBUG_TRIGGER"
    echo "Hook debug ON → $DEBUG_LOG"
    ;;
  off)
    rm -f "$DEBUG_TRIGGER"
    echo "Hook debug OFF"
    ;;
  status)
    if [[ -f "$DEBUG_TRIGGER" ]] || [[ "${CURSOR_HOOKS_DEBUG:-}" == "1" ]]; then
      echo "Hook debug ON"
    else
      echo "Hook debug OFF"
    fi
    echo "Trigger file: $DEBUG_TRIGGER"
    echo "Env override: CURSOR_HOOKS_DEBUG=1"
    echo "Log file:     $DEBUG_LOG"
    if [[ -f "$DEBUG_LOG" ]]; then
      echo "Log lines:    $(wc -l < "$DEBUG_LOG")"
    fi
    ;;
  clear)
    rm -f "$DEBUG_LOG"
    echo "Cleared $DEBUG_LOG"
    ;;
  tail)
    if [[ ! -f "$DEBUG_LOG" ]]; then
      echo "No log yet. Enable debug (hooks-debug.sh on) and run a hook."
      exit 1
    fi
    tail -f "$DEBUG_LOG"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
