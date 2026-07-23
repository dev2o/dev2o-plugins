#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.command // .tool_input.command // empty')

if [[ -z "$COMMAND" ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

MSG="Blocked: dumping environment variables or reading .env files is not allowed. Test credentials via the tool directly (e.g. command -v op) instead."

if echo "$COMMAND" | grep -qE '(^|[;&|[:space:]])(printenv|export -p)([[:space:]]|$|[;&|])'; then
  jq -nc --arg m "$MSG" '{permission: "deny", user_message: $m}'
  exit 0
fi

if echo "$COMMAND" | grep -qE '(^|[;&|[:space:]])env([[:space:]]|$|[;&|])'; then
  jq -nc --arg m "$MSG" '{permission: "deny", user_message: $m}'
  exit 0
fi

if echo "$COMMAND" | grep -qE '(^|[;&|[:space:]])(cat|less|head|tail|more|type|grep|awk|sed)[[:space:]]+[^;&|[:space:]]*\.env([^A-Za-z0-9_]|$)'; then
  jq -nc --arg m "$MSG" '{permission: "deny", user_message: $m}'
  exit 0
fi

echo '{"permission": "allow"}'
