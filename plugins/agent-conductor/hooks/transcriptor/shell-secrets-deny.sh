#!/usr/bin/env bash

DUMP_DIR="/tmp/cursor-hook-debug"
mkdir -p "$DUMP_DIR" 2>/dev/null || true

fail_open() {
  local reason="$1"
  echo "$(date -u): FAILED (command-blocker) - $reason" >> "$DUMP_DIR/error.log"
  echo '{"permission": "allow"}'
  exit 0
}

# 1. Capture stdin safely and save latest payload for debugging
INPUT=$(cat 2>/dev/null || echo "")
if [[ -z "$INPUT" ]]; then
  fail_open "Received empty stdin"
fi
echo "$INPUT" > "$DUMP_DIR/latest-command-blocker-payload.json"

# 2. Check essential dependencies
if ! command -v jq >/dev/null 2>&1; then
  fail_open "'jq' is not installed in PATH: $PATH"
fi

if ! command -v grep >/dev/null 2>&1; then
  fail_open "'grep' is not installed in PATH: $PATH"
fi

# 3. Safely extract the command string without pipefail crashes
COMMAND=$(printf '%s\n' "$INPUT" | jq -r '.command // .tool_input.command // empty' 2>/dev/null || echo "")

if [[ -z "$COMMAND" ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

MSG="Blocked: dumping environment variables or reading .env files is not allowed. Test credentials via the tool directly (e.g. command -v op) instead."

# 4. Perform regex checks safely
# Note: We use printf '%s\n' instead of echo because if the agent generates a command starting with -e or -n,
# echo will misinterpret it as a command-line flag instead of piping the string!
block_command=false

if printf '%s\n' "$COMMAND" | grep -qE '(^|[;&|[:space:]])(printenv|export -p)([[:space:]]|$|[;&|])' 2>/dev/null; then
  block_command=true
elif printf '%s\n' "$COMMAND" | grep -qE '(^|[;&|[:space:]])env([[:space:]]|$|[;&|])' 2>/dev/null; then
  block_command=true
elif printf '%s\n' "$COMMAND" | grep -qE '(^|[;&|[:space:]])(cat|less|head|tail|more|type|grep|awk|sed)[[:space:]]+[^;&|[:space:]]*\.env([^A-Za-z0-9_]|$)' 2>/dev/null; then
  block_command=true
fi

# 5. Return deny JSON if a rule matched, otherwise allow
if [[ "$block_command" == "true" ]]; then
  if ! OUTPUT_JSON=$(jq -nc --arg m "$MSG" '{permission: "deny", user_message: $m}' 2>/dev/null); then
    fail_open "Failed to construct deny JSON payload with jq"
  fi
  echo "$OUTPUT_JSON"
  exit 0
fi

echo '{"permission": "allow"}'
exit 0