#!/usr/bin/env bash
# Copy env-protect into a project's .cursor/ so Cloud Agents enforce it.
# Not a hook: exits non-zero when it cannot finish the job.
#
# Usage: install.sh [--check] [project-dir]

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install.sh [--check] [project-dir]

Copy hooks/env-protect.sh into the project's .cursor/hooks/ and merge a
beforeShellExecution entry into .cursor/hooks.json.

  --check       Report state and exit 0 without writing.
  project-dir   Defaults to CURSOR_PROJECT_DIR, then the current directory.
EOF
}

die() {
  printf 'env-protect-setup: %s\n' "$1" >&2
  exit 1
}

CHECK=0
PROJECT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) die "unknown option: $1" ;;
    *) PROJECT="$1"; shift; break ;;
  esac
done
[[ $# -eq 0 ]] || die "unexpected argument: $1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$PLUGIN_ROOT/hooks/env-protect.sh"
[[ -f "$SRC" ]] || die "plugin hook missing at $SRC"

if [[ -z "$PROJECT" ]]; then
  PROJECT="${CURSOR_PROJECT_DIR:-$PWD}"
fi
[[ -d "$PROJECT" ]] || die "project directory does not exist: $PROJECT"
PROJECT="$(cd "$PROJECT" && pwd)"

DEST_DIR="$PROJECT/.cursor/hooks"
DEST="$DEST_DIR/env-protect.sh"
HOOKS_JSON="$PROJECT/.cursor/hooks.json"
ENTRY_CMD=".cursor/hooks/env-protect.sh"

command -v jq >/dev/null 2>&1 || die "'jq' is not installed in PATH"

gitignored() {
  git -C "$PROJECT" check-ignore -q -- "$1" 2>/dev/null
}

in_git_repo() {
  git -C "$PROJECT" rev-parse --is-inside-work-tree >/dev/null 2>&1
}

ignore_state() {
  local path="$1"
  if ! in_git_repo; then
    printf 'n/a'
  elif gitignored "$path"; then
    printf 'yes'
  else
    printf 'no'
  fi
}

script_state() {
  if [[ ! -f "$DEST" ]]; then
    printf 'missing'
  else
    printf 'present'
  fi
}

script_matches_state() {
  if [[ ! -f "$DEST" ]]; then
    printf 'n/a'
  elif cmp -s "$SRC" "$DEST"; then
    printf 'yes'
  else
    printf 'no'
  fi
}

hooks_json_state() {
  if [[ ! -e "$HOOKS_JSON" ]]; then
    printf 'missing'
  else
    printf 'present'
  fi
}

hooks_json_valid_state() {
  if [[ ! -e "$HOOKS_JSON" ]]; then
    printf 'n/a'
  elif jq -e . "$HOOKS_JSON" >/dev/null 2>&1; then
    printf 'yes'
  else
    printf 'no'
  fi
}

entry_present_state() {
  if [[ ! -e "$HOOKS_JSON" ]]; then
    printf 'no'
  elif ! jq -e . "$HOOKS_JSON" >/dev/null 2>&1; then
    printf 'n/a'
    elif jq -e '
      any(.hooks.beforeShellExecution[]?; .command | tostring | endswith("env-protect.sh"))
    ' "$HOOKS_JSON" >/dev/null 2>&1; then
    printf 'yes'
  else
    printf 'no'
  fi
}

status_line() {
  local script matches hooks valid entry
  script=$(script_state)
  matches=$(script_matches_state)
  hooks=$(hooks_json_state)
  valid=$(hooks_json_valid_state)
  entry=$(entry_present_state)
  if [[ "$valid" == "no" ]]; then
    printf 'hooks-json-invalid'
  elif [[ "$script" == "present" && "$matches" == "yes" && "$entry" == "yes" ]]; then
    printf 'installed'
  elif [[ "$script" == "present" || "$entry" == "yes" ]]; then
    printf 'stale'
  else
    printf 'not-installed'
  fi
}

print_check() {
  local status
  status=$(status_line)
  cat <<EOF
project: $PROJECT
plugin_root: $PLUGIN_ROOT
script: $(script_state)
script_matches: $(script_matches_state)
hooks_json: $(hooks_json_state)
hooks_json_valid: $(hooks_json_valid_state)
entry_present: $(entry_present_state)
script_gitignored: $(ignore_state ".cursor/hooks/env-protect.sh")
hooks_json_gitignored: $(ignore_state ".cursor/hooks.json")
status: $status
EOF
  case "$status" in
    installed)
      printf 'nothing to write: project copy is current\n'
      ;;
    hooks-json-invalid)
      printf 'would not write: %s is not valid JSON\n' "$HOOKS_JSON"
      ;;
    *)
      if [[ "$(script_state)" != "present" || "$(script_matches_state)" != "yes" ]]; then
        printf 'would copy: .cursor/hooks/env-protect.sh\n'
      fi
      if [[ "$(entry_present_state)" != "yes" ]]; then
        if [[ "$(hooks_json_state)" == "missing" ]]; then
          printf 'would create: .cursor/hooks.json\n'
        else
          printf 'would modify: .cursor/hooks.json (append beforeShellExecution entry)\n'
        fi
      fi
      ;;
  esac
}

need_force_add() {
  [[ "$(ignore_state ".cursor/hooks/env-protect.sh")" == "yes" \
    || "$(ignore_state ".cursor/hooks.json")" == "yes" ]]
}

print_commit_reminder() {
  if need_force_add; then
    printf 'commit: git add -f .cursor/hooks.json .cursor/hooks/env-protect.sh\n'
  else
    printf 'commit: git add .cursor/hooks.json .cursor/hooks/env-protect.sh\n'
  fi
}

if [[ "$CHECK" -eq 1 ]]; then
  print_check
  exit 0
fi

if [[ -e "$HOOKS_JSON" ]] && ! jq -e . "$HOOKS_JSON" >/dev/null 2>&1; then
  die "invalid JSON at $HOOKS_JSON; leaving it untouched"
fi

mkdir -p "$DEST_DIR" || die "cannot create $DEST_DIR"

copied=no
if [[ ! -f "$DEST" ]] || ! cmp -s "$SRC" "$DEST"; then
  cp -f "$SRC" "$DEST" || die "failed to copy hook to $DEST"
  copied=yes
fi
chmod +x "$DEST" || die "failed to chmod +x $DEST"

hooks_action=unchanged
if [[ ! -e "$HOOKS_JSON" ]]; then
  tmp=$(mktemp)
  if ! jq --indent 2 -n --arg cmd "$ENTRY_CMD" '{
      version: 1,
      hooks: {
        beforeShellExecution: [
          {command: $cmd, timeout: 30}
        ]
      }
    }' >"$tmp"; then
    rm -f "$tmp"
    die "failed to write $HOOKS_JSON"
  fi
  mv "$tmp" "$HOOKS_JSON"
  hooks_action=created
elif [[ "$(entry_present_state)" != "yes" ]]; then
  tmp=$(mktemp)
  if ! jq --indent 2 --arg cmd "$ENTRY_CMD" --argjson timeout 30 '
      .hooks = (.hooks // {})
      | .hooks.beforeShellExecution = (.hooks.beforeShellExecution // [])
      | .hooks.beforeShellExecution += [{command: $cmd, timeout: $timeout}]
    ' "$HOOKS_JSON" >"$tmp"; then
    rm -f "$tmp"
    die "failed to merge $HOOKS_JSON"
  fi
  mv "$tmp" "$HOOKS_JSON"
  hooks_action=updated
fi

printf 'copied: %s  .cursor/hooks/env-protect.sh\n' "$copied"
printf 'hooks.json: %s\n' "$hooks_action"
print_commit_reminder
exit 0
