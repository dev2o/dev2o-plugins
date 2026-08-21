# Cursor Agent Conductor

Project-level overrides for hook-injected context. Bundled defaults live in the plugin; a project can replace them file-by-file without forking the plugin.

---

## Project config overrides

Place override files under your project root at:

```
.cursor/dev2o-agent-conductor/config/
```

Resolution uses `CURSOR_PROJECT_DIR`. A project file wins over the plugin's bundled copy; resolution is **per file** — only the files you add are overridden.


| File                       | Injected to                                        |
| -------------------------- | -------------------------------------------------- |
| `__agent-main.md`          | Main agent (`beforeSubmitPrompt`)                  |
| `agent-{subagent_type}.md` | Subagent matching that type (`preToolUse` on Task) |


Examples:

```
.cursor/dev2o-agent-conductor/config/
  __agent-main.md
  agent-advisor.md
  agent-explore.md
```

The `agent-` prefix is fixed; the suffix must match the subagent type exactly (e.g. `advisor` → `agent-advisor.md`).

**No override file → plugin default.** No plugin default and no override → no injection for that agent.

Bundled defaults: [`hooks/context-injector/config/`](hooks/context-injector/config/)

---

## Project folders seeded on session start

On `sessionStart`, the plugin copies boilerplate into the project under `.cursor/`. Source files live in [`boilerplate/`](boilerplate/).

| Plugin source | Project destination | Behavior |
|---------------|---------------------|----------|
| `boilerplate/agent-memory/AGENTS.md` | `.cursor/agent-memory/AGENTS.md` | **Sync** — overwritten on every session start |
| `boilerplate/agent-memory/orchestrator/MEMORY.md` | `.cursor/agent-memory/orchestrator/MEMORY.md` | **Seed** — copied only if the destination file does not exist |
| `boilerplate/chat-transcripts/` | `.cursor/chat-transcripts/` | **Seed** — docs and ignore rules copied only if missing |
| `hooks/transcriptor/transcripts.py` | `.cursor/chat-transcripts/_transcripts.py` | **Sync** — overwritten on every session start |

### `agent-memory`

Cross-session persistence for the orchestrator:

```
.cursor/agent-memory/AGENTS.md              ← synced from plugin; do not edit
.cursor/agent-memory/orchestrator/MEMORY.md ← seeded once; edit this in your project
```

`AGENTS.md` is overwritten on every session start so plugin updates to memory rules land automatically. `MEMORY.md` is seeded once; the plugin will not overwrite it once it exists.

### `chat-transcripts`

Hook-captured, scrubbed audit logs land here as `{conversation_id}.jsonl`. Seeded docs explain usage; do not read `.jsonl` files directly — use `_transcripts.py` or the advisor subagent.

```
.cursor/chat-transcripts/
  AGENTS.md
  _transcripts.py    ← synced from plugin; do not edit
  {conversation_id}.jsonl   ← created at runtime by audit hook
```

Bundled boilerplate: [`boilerplate/agent-memory/`](boilerplate/agent-memory/), [`boilerplate/chat-transcripts/`](boilerplate/chat-transcripts/)

---

## Cloud agents

A cloud agent loads the plugin's agents but **not** the plugin's hooks. Cursor loads cloud hooks only from the project's own `.cursor/hooks.json` (plus team and enterprise hooks on Enterprise plans), and `sessionStart` does not run in the cloud at all. With no extra setup, a cloud run gets the `advisor` and `exe-advisor` subagents and nothing else: no transcript capture, no boilerplate seeding, no orchestrator injection.

The advisor still answers rather than breaking. The Executor stamps `Advise. <id>` itself, and both advisor agents fall back to the plugin's own copy of the CLI, so a cloud gatekeeper with no captured log reports `<no_transcript …/>` and asks the Executor to restate its objective.

To run the full suite on a cloud VM, commit the launcher into the project:

```bash
mkdir -p .cursor/hooks
cp <plugin>/cloud/hooks.json .cursor/hooks.json
cp <plugin>/cloud/agent-conductor-hook.sh .cursor/hooks/
chmod +x .cursor/hooks/agent-conductor-hook.sh
git add -f .cursor/hooks.json .cursor/hooks/agent-conductor-hook.sh
```

Both files must be tracked by git, since a cloud agent clones the repo fresh. Many projects ignore `.cursor/`, hence the `-f`. The launcher resolves the installed plugin under `~/.cursor/plugins/cache/`, dispatches the event to the plugin's own hook script, and syncs `_transcripts.py` into the project on whichever hook fires first, standing in for the `sessionStart` that never runs. It fails open on every error, exactly like the hooks it delegates to.

`cloud/hooks.json` mirrors the plugin's own [`hooks/hooks.json`](hooks/hooks.json) minus `sessionStart`. Keep them in step when you add an event.

### What actually fires in the cloud

Measured on run `bc-46559db3` across 131 captured events, with the project shim installed. Cursor's docs list more events than this as supported.

| Fires | Never fires |
|---|---|
| `beforeReadFile`, `beforeShellExecution`, `afterShellExecution`, `preToolUse` (Grep only), `postToolUse`, `postToolUseFailure`, `afterFileEdit` | `sessionStart`, `beforeSubmitPrompt`, `preToolUse` on `Task`, `afterAgentResponse`, `afterAgentThought`, `preCompact`, `subagentStop` |

Two consequences. `preToolUse` on `Task` never runs, so nothing hook-side stamps the advisor spawn line, which is why the Executor stamps it and why that instruction lives in the `advisor` agent description rather than only in `__agent-main.md`. And `beforeSubmitPrompt` never runs, so the orchestrator context in `__agent-main.md` is not injected on a cloud VM at all; a project that wants those rules there has to put them somewhere the agent reads on its own, such as a committed `AGENTS.md`.

`cloud/hooks.json` still registers the events that never fire. They cost nothing when absent, and registering them is how the next run finds out that Cursor started delivering them.

### Verifying a cloud run

This repository installs the launcher on itself, so a cloud agent started here exercises the shim on the first tool call. From the project root:

```bash
plugins/agent-conductor/cloud/verify-cloud-hooks.sh
```

It reports whether any hook ran, which events reached the launcher, whether the CLI was synced, whether this session was captured, and prints the resulting brief.

By default the launcher dispatches to the installed plugin, which is whatever landed on the marketplace ref. To exercise an unreleased working tree instead, set `AGENT_CONDUCTOR_PLUGIN_ROOT`:

```bash
AGENT_CONDUCTOR_PLUGIN_ROOT="$PWD/plugins/agent-conductor" \
  .cursor/hooks/agent-conductor-hook.sh hooks/transcriptor/audit.sh <<'JSON'
{"conversation_id": "probe", "hook_event_name": "afterAgentResponse", "text": "working tree"}
JSON
``` `/tmp/cursor-hook-debug/cloud-launcher.log` holds one line per dispatch, which is the only record of which events a cloud agent actually delivers.

The line to watch is `preToolUse on Task`. If it never reaches the stamping hook, the Executor's own `Advise. <id>` stamp is carrying the transport by itself, which is the case the fallback exists for.

Bundled launcher: [`cloud/`](cloud/)
