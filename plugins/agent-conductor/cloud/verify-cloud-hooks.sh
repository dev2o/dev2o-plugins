#!/usr/bin/env bash
# Live verdict on whether agent-conductor is working in the current session.
# Run it from the project root. Read-only apart from the dump directory.
#
# FAIL means the advisor cannot see the session. WARN means a documented
# limitation that something else absorbs.

DUMP_DIR="/tmp/cursor-hook-debug"
LAUNCHER_LOG="$DUMP_DIR/cloud-launcher.log"
CID="${CURSOR_CONVERSATION_ID:-}"
ROOT="${CURSOR_PROJECT_DIR:-$PWD}"
PROJECT_CLI="$ROOT/.cursor/chat-transcripts/_transcripts.py"
LOG="$ROOT/.cursor/chat-transcripts/$CID.jsonl"
fail=0

say() { printf '%s %s\n' "$1" "$2"; }
check() {
  if [[ "$1" == "yes" ]]; then say "PASS" "$2"; else say "FAIL" "$2"; fail=1; fi
}
note() {
  if [[ "$1" == "yes" ]]; then say "PASS" "$2"; else say "WARN" "$3"; fi
}

# The advisor agents resolve the CLI the same way: first copy that answers wins.
working_cli() {
  local cli
  for cli in "$PROJECT_CLI" $(find "$HOME/.cursor/plugins/cache" -path '*/hooks/transcriptor/transcripts.py' 2>/dev/null); do
    [[ -f "$cli" ]] || continue
    if python3 "$cli" brief "Advise. ${CID:-none}" >/dev/null 2>&1; then
      printf '%s\n' "$cli"
      return 0
    fi
  done
  return 1
}

printf 'conversation=%s\nproject=%s\n\n' "${CID:-unset}" "$ROOT"

[[ -d "$DUMP_DIR" ]] && hooks_ran=yes || hooks_ran=no
check "$hooks_ran" "some hook ran (dump directory exists)"

if [[ -f "$LAUNCHER_LOG" ]]; then
  say "PASS" "the cloud launcher ran"
  printf '\nevents delivered to the launcher:\n'
  awk '{print $2}' "$LAUNCHER_LOG" | sort | uniq -c | sort -rn
  printf '\n'
  # The Executor stamps the spawn line itself, so a missing Task hook costs the
  # id-mismatch deny and nothing else.
  note \
    "$(grep -q 'target=hooks/context-injector/subagent-context-pre-tool-use.sh' "$LAUNCHER_LOG" && echo yes || echo no)" \
    "preToolUse on Task reached the stamping hook" \
    "preToolUse on Task never reached the stamping hook; the Executor's own stamp is carrying the transport, and the id-mismatch deny is not enforceable here"
else
  say "WARN" "no launcher log; this project uses its own shim generation, or none. Hook delivery is judged by the capture below instead"
fi

# A project copies the launcher and its hooks.json, so both go stale whenever the
# plugin changes them. That staleness is silent: the events simply stop arriving.
PLUGIN_ROOT_FILE="$DUMP_DIR/plugin-root"
if [[ -f "$PLUGIN_ROOT_FILE" ]]; then
  PLUGIN_ROOT=$(cat "$PLUGIN_ROOT_FILE" 2>/dev/null)
  LOCAL_LAUNCHER="$ROOT/.cursor/hooks/agent-conductor-hook.sh"
  if [[ -f "$LOCAL_LAUNCHER" && -f "$PLUGIN_ROOT/cloud/agent-conductor-hook.sh" ]]; then
    note "$(cmp -s "$LOCAL_LAUNCHER" "$PLUGIN_ROOT/cloud/agent-conductor-hook.sh" && echo yes || echo no)" \
      "the copied launcher matches the installed plugin" \
      "the copied launcher differs from the installed plugin's; re-copy cloud/agent-conductor-hook.sh"
  fi
  # Compared by target, so a project prefix such as an env assignment is ignored.
  targets() {
    jq -r '.hooks | to_entries[] | .value[] | .command' "$1" 2>/dev/null |
      sed 's/.*agent-conductor-hook\.sh //' | sort
  }
  if [[ -f "$ROOT/.cursor/hooks.json" && -f "$PLUGIN_ROOT/cloud/hooks.json" ]]; then
    note "$([[ "$(targets "$ROOT/.cursor/hooks.json")" == "$(targets "$PLUGIN_ROOT/cloud/hooks.json")" ]] && echo yes || echo no)" \
      "the copied hooks.json registers the same events as the plugin's" \
      "the copied hooks.json registers different events than the plugin's; re-copy cloud/hooks.json. Missing here: $(comm -13 <(targets "$ROOT/.cursor/hooks.json") <(targets "$PLUGIN_ROOT/cloud/hooks.json") | tr '\n' ' ')"
  fi
fi

CLI=$(working_cli || echo "")
[[ -n "$CLI" ]] && cli_ok=yes || cli_ok=no
check "$cli_ok" "a copy of the CLI answers brief"
if [[ "$cli_ok" == "yes" ]]; then
  say "INFO" "using $CLI"
  note \
    "$([[ "$CLI" == "$PROJECT_CLI" ]] && echo yes || echo no)" \
    "the project copy of the CLI understands brief" \
    "the project copy is missing or predates brief, so the advisor falls back to the plugin's own copy"
fi

[[ -n "$CID" && -f "$LOG" ]] && captured=yes || captured=no
check "$captured" "this session has a captured transcript"

if [[ "$captured" == "yes" && "$cli_ok" == "yes" ]]; then
  dupes=$(jq -Sc 'del(.ts)' "$LOG" 2>/dev/null | sort | uniq -d | wc -l | tr -d ' ')
  note "$([[ "${dupes:-0}" == "0" ]] && echo yes || echo no)" \
    "no duplicate lines in the transcript" \
    "$dupes duplicate lines in the transcript; two hook sources may be delivering the same event without dedupe"
  printf '\nbrief for this session:\n'
  python3 "$CLI" brief "Advise. $CID" 2>&1 | head -20
fi

if [[ -s "$DUMP_DIR/error.log" ]]; then
  printf '\nlast hook errors:\n'
  tail -10 "$DUMP_DIR/error.log"
fi

printf '\n'
if [[ "$fail" == "0" ]]; then
  say "VERDICT" "agent-conductor is live in this session; WARN lines are expected limitations, FAIL lines are not"
else
  say "VERDICT" "agent-conductor is degraded in this session; see the FAIL lines"
fi
exit 0
