---
name: env-protect-setup
description: "Install the env-protect hook into this project's .cursor/ so Cloud Agents enforce it. Use for /env-protect-setup or when the user asks to make env protection work in the cloud."
disable-model-invocation: true
---

# Env protect setup

Copy `hooks/env-protect.sh` into `.cursor/hooks/` and merge a `beforeShellExecution` entry into `.cursor/hooks.json`. Cloud Agents load hooks only from those project files. Do not write anything until the user confirms.

```text
/env-protect-setup
```

## Step 1. Locate install.sh

Prefer `"$CURSOR_PLUGIN_ROOT/scripts/install.sh"`. If `CURSOR_PLUGIN_ROOT` is unset or that path is missing, find the newest `env-protect` plugin under `~/.cursor/plugins/cache`:

```bash
plugin_root() {
  if [[ -n "${CURSOR_PLUGIN_ROOT:-}" && -x "$CURSOR_PLUGIN_ROOT/scripts/install.sh" ]]; then
    printf '%s\n' "$CURSOR_PLUGIN_ROOT"
    return 0
  fi
  local manifest name root best=""
  while IFS= read -r manifest; do
    [[ -n "$manifest" ]] || continue
    name=$(jq -r '.name // empty' "$manifest" 2>/dev/null || echo "")
    [[ "$name" == "env-protect" ]] || continue
    root=$(dirname "$(dirname "$manifest")")
    [[ -x "$root/scripts/install.sh" ]] || continue
    if [[ -z "$best" || "$manifest" -nt "$best" ]]; then
      best="$manifest"
    fi
  done < <(find "$HOME/.cursor/plugins/cache" -path '*/.cursor-plugin/plugin.json' -type f 2>/dev/null)
  [[ -n "$best" ]] || return 1
  dirname "$(dirname "$best")"
}
```

Stop if it cannot be found.

## Step 2. Check

Run `"$PLUGIN_ROOT/scripts/install.sh" --check` and show the output.

If `status: installed`, say the project copy is current and stop.

If `status: hooks-json-invalid`, report the path and stop. Do not write.

## Step 3. Ask

State the paths that would be created or modified (the `would copy` / `would create` / `would modify` lines). Ask the user to confirm. Do not run the installer before a yes.

## Step 4. Install

Run `"$PLUGIN_ROOT/scripts/install.sh"` with no `--check`. Show the output.

## Step 5. Commit reminder

Report `git add -f .cursor/hooks.json .cursor/hooks/env-protect.sh` and whether `-f` is needed (`script_gitignored` or `hooks_json_gitignored` is `yes`). Do not stage or commit.
