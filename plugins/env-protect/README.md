# Env Protect

Denies agent shell commands that dump the environment or read `.env` files.

On desktop the plugin hook runs by itself. Cloud Agents load hooks only from the project's own `.cursor/hooks.json`, so they never see the plugin copy. `/env-protect-setup` installs a project copy when you ask. Nothing writes into a project on its own.

## What is blocked

`beforeShellExecution` denies a command when it matches one of:

- `env` as a command (including `env | grep` and `env VAR=1 cmd`)
- `printenv` or `export -p`
- a reader (`cat`, `less`, `head`, `tail`, `more`, `type`, `grep`, `awk`, `sed`) whose argument looks like a `.env` path
- a 1Password CLI command that prints secret values to the terminal: `op environment read`, `op read`, `op document get`, `op item get --reveal`, or `op inject` without `-o`, when it is the last stage of a pipeline and stdout is not redirected. Redirecting only stderr (`2>file`) does not count.

Anything else is allowed, including `command -v op`, `node --env-file=.env`, `ls .env`, `cat .envrc`, `source .env`, `set`, and `declare -p`. For `op`: `op run`, `op whoami`, `op vault list`, `op item list`, `op item get x` (no `--reveal`), `op read op://x > file`, `op read op://x | jq`, and `op inject -i t -o out` are allowed. Known gaps: `VAR=$(op read op://x)` is not detected, and `op read op://x 2>&1 | head` is allowed because it is piped. Failures (`jq` missing, empty stdin) return allow so a broken hook never freezes the agent.

## Cloud Agents

Cursor does not load plugin `hooks.json` on a cloud VM. The project needs:

- `.cursor/hooks/env-protect.sh` (a copy of the plugin script)
- a `beforeShellExecution` entry in `.cursor/hooks.json` pointing at `.cursor/hooks/env-protect.sh`

The script has no plugin-cache dependency, so the project file is the hook. No launcher shim.

```text
/env-protect-setup
```

The skill reports what it would write, waits for a yes, copies the script, merges the entry, and reminds you to commit. It does not stage or commit.

```bash
git add -f .cursor/hooks.json .cursor/hooks/env-protect.sh
```

`-f` is required when `.cursor/` is gitignored. Many projects ignore it.

The same install by hand:

```bash
bash <plugin>/scripts/install.sh
# or dry-run:
bash <plugin>/scripts/install.sh --check
```

Once the project copy is in place, desktop evaluates the rule twice (plugin hook plus project hook). Both return the same allow or deny.

## Updating project copies

The plugin copy updates itself on desktop when the plugin updates. Project copies do not. After a plugin update, re-run `/env-protect-setup` in each project: `--check` reports `status: stale` and `script_matches: no`, and the install re-copies the script.

## License

MIT
