#!/usr/bin/env bash
# Live verdict on whether agent-conductor is working in the current session.
# Run it from the project root. Read-only apart from the dump directory.

DUMP_DIR="/tmp/cursor-hook-debug"
LAUNCHER_LOG="$DUMP_DIR/cloud-launcher.log"
CID="${CURSOR_CONVERSATION_ID:-}"
ROOT="${CURSOR_PROJECT_DIR:-$PWD}"
CLI="$ROOT/.cursor/chat-transcripts/_transcripts.py"
LOG="$ROOT/.cursor/chat-transcripts/$CID.jsonl"
fail=0

say() { printf '%s %s\n' "$1" "$2"; }
check() {
  if [[ "$1" == "yes" ]]; then say "PASS" "$2"; else say "FAIL" "$2"; fail=1; fi
}

printf 'conversation=%s\nproject=%s\n\n' "${CID:-unset}" "$ROOT"

[[ -d "$DUMP_DIR" ]] && hooks_ran=yes || hooks_ran=no
check "$hooks_ran" "some hook ran (dump directory exists)"

if [[ -f "$LAUNCHER_LOG" ]]; then
  check yes "the cloud launcher ran"
  printf '\nevents delivered to the launcher:\n'
  awk '{print $2}' "$LAUNCHER_LOG" | sort | uniq -c | sort -rn
  if grep -q 'event=preToolUse' "$LAUNCHER_LOG"; then
    say "PASS" "preToolUse reached the launcher"
  else
    say "FAIL" "preToolUse never reached the launcher"
    fail=1
  fi
  if grep -q 'target=hooks/context-injector/subagent-context-pre-tool-use.sh' "$LAUNCHER_LOG"; then
    say "PASS" "preToolUse on Task reached the stamping hook"
  else
    say "FAIL" "preToolUse on Task never reached the stamping hook; the Executor's own stamp is carrying the transport"
  fi
  printf '\n'
else
  check no "the cloud launcher ran (no .cursor/hooks.json, or the project shim is not installed)"
fi

[[ -f "$CLI" ]] && cli_present=yes || cli_present=no
check "$cli_present" "_transcripts.py is present in the project"

if [[ "$cli_present" == "yes" ]] && python3 "$CLI" brief "Advise. ${CID:-none}" >/dev/null 2>&1; then
  check yes "the project CLI understands brief"
else
  check no "the project CLI understands brief"
fi

[[ -n "$CID" && -f "$LOG" ]] && captured=yes || captured=no
check "$captured" "this session has a captured transcript"

if [[ "$captured" == "yes" ]]; then
  printf '\nbrief for this session:\n'
  python3 "$CLI" brief "Advise. $CID" 2>&1 | head -20
fi

if [[ -s "$DUMP_DIR/error.log" ]]; then
  printf '\nlast hook errors:\n'
  tail -10 "$DUMP_DIR/error.log"
fi

printf '\n'
if [[ "$fail" == "0" ]]; then
  say "VERDICT" "agent-conductor is live in this session"
else
  say "VERDICT" "agent-conductor is degraded in this session; see the FAIL lines"
fi
exit 0
