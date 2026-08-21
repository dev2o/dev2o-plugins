# Agent Conductor

A Cursor plugin that gives your project's main agent three things: memory that survives between sessions, an advisor it can call on for a hard decision, and a searchable record of what happened in every conversation.

## Why

A long session forgets what worked last week. A stuck agent has no one to ask before it repeats the same failed approach. A subagent's tool calls disappear the moment its turn ends. Agent Conductor keeps all three around.

## What you get

- **Persistent memory.** The main agent reads and writes `.cursor/agent-memory/`, so decisions from one session carry into the next.
- **An advisor on call.** Skill `advisor-check` runs in the main thread and decides, from a short checklist, whether a decision is worth a second opinion. When it is, the main agent spawns the `advisor` subagent, which reads the session transcript and gives direction.
- **A transcript for every session.** Hooks capture and scrub each conversation to `.cursor/chat-transcripts/`, browsable with a small Python CLI. Secrets never reach the log.
- **Context injection per subagent.** Drop a markdown file named for a subagent type, and its content prepends to that subagent's first prompt automatically. No subagent has to ask for context it needs.
- **Cloud agent support.** The advisor and its transcript fallback keep working on Cursor cloud agents, even though cloud hooks load differently from desktop hooks. See [Cloud agents](#cloud-agents).

## Install

Install through Cursor's plugin marketplace, or add this repository as a plugin source and select `agent-conductor`.

On session start, the plugin seeds `.cursor/agent-memory/` and `.cursor/chat-transcripts/` in your project. There's nothing else to configure to start.

---

## Project config overrides

Place override files under your project root at:

```
.cursor/dev2o-agent-conductor/config/
```

Resolution uses `CURSOR_PROJECT_DIR`. A project file wins over the plugin's bundled copy. Resolution happens per file, so only the files you add are overridden.

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

The `agent-` prefix is fixed. The suffix must match the subagent type exactly, so `advisor` maps to `agent-advisor.md`.

Without an override file, the plugin's bundled default applies. Without a bundled default either, that agent gets no injected context.

Bundled defaults: [`hooks/context-injector/config/`](hooks/context-injector/config/)

---

## Project folders seeded on session start

On `sessionStart`, the plugin copies boilerplate into the project under `.cursor/`. Source files live in [`boilerplate/`](boilerplate/).

| Plugin source | Project destination | Behavior |
|---------------|---------------------|----------|
| `boilerplate/agent-memory/AGENTS.md` | `.cursor/agent-memory/AGENTS.md` | **Sync.** Overwritten on every session start. |
| `boilerplate/agent-memory/orchestrator/MEMORY.md` | `.cursor/agent-memory/orchestrator/MEMORY.md` | **Seed.** Copied only if the destination file does not exist. |
| `boilerplate/chat-transcripts/` | `.cursor/chat-transcripts/` | **Seed.** Docs and ignore rules copied only if missing. |
| `hooks/transcriptor/transcripts.py` | `.cursor/chat-transcripts/_transcripts.py` | **Sync.** Overwritten on every session start. |

### `agent-memory`

Cross-session persistence for the main agent:

```
.cursor/agent-memory/AGENTS.md              ← synced from plugin, do not edit
.cursor/agent-memory/orchestrator/MEMORY.md ← seeded once, edit this in your project
```

`AGENTS.md` is overwritten on every session start, so plugin updates to memory rules land automatically. `MEMORY.md` is seeded once. The plugin never overwrites it after that.

### `chat-transcripts`

Hook-captured, scrubbed audit logs land here as `{conversation_id}.jsonl`. Don't read `.jsonl` files directly. Use `_transcripts.py`, or spawn the `advisor` subagent to read them for you.

```
.cursor/chat-transcripts/
  AGENTS.md
  _transcripts.py           ← synced from plugin, do not edit
  {conversation_id}.jsonl   ← created at runtime by the audit hook
```

Bundled boilerplate: [`boilerplate/agent-memory/`](boilerplate/agent-memory/), [`boilerplate/chat-transcripts/`](boilerplate/chat-transcripts/)

---

## Cloud agents

A cloud agent loads the plugin's agents and skills but not its hooks. Cursor loads cloud hooks only from the project's own `.cursor/hooks.json` (plus team and enterprise hooks on Enterprise plans), and `sessionStart` never runs in the cloud. With no extra setup, a cloud run gets the `advisor` subagent and skill `advisor-check`, and nothing else: no transcript capture, no boilerplate seeding, no main-agent injection.

The advisor still answers rather than breaking. The main agent stamps `Advise. <id>` itself, and the advisor falls back to the plugin's own copy of the CLI. A cloud run with no captured log reports `<no_transcript …/>` and asks the main agent to restate its objective.

To run the full suite on a cloud VM, commit the launcher into the project:

```bash
mkdir -p .cursor/hooks
cp <plugin>/cloud/hooks.json .cursor/hooks.json
cp <plugin>/cloud/agent-conductor-hook.sh .cursor/hooks/
chmod +x .cursor/hooks/agent-conductor-hook.sh
git add -f .cursor/hooks.json .cursor/hooks/agent-conductor-hook.sh
```

Both files must be tracked by git, since a cloud agent clones the repo fresh. Many projects ignore `.cursor/`, hence the `-f`. The launcher resolves the installed plugin under `~/.cursor/plugins/cache/`, dispatches the event to the plugin's own hook script, and syncs `_transcripts.py` into the project on whichever hook fires first, standing in for the `sessionStart` that never runs there. It fails open on every error, exactly like the hooks it delegates to.

`cloud/hooks.json` mirrors the plugin's own [`hooks/hooks.json`](hooks/hooks.json) minus `sessionStart`. Keep them in step when you add an event.

### What actually fires in the cloud

`sessionStart` never fires there, and Cursor documents that. Every other event the plugin registers has been observed firing on a cloud VM, including `preToolUse` on `Task`, `beforeSubmitPrompt`, `afterAgentThought`, and `subagentStop`.

Read a short session's absences carefully. Early in a session, only `beforeShellExecution`, `afterShellExecution`, and `beforeReadFile` may have appeared, because the rest need the session to do the triggering thing first: `preToolUse` on `Task` needs a subagent spawn, `subagentStop` needs one to finish, `afterFileEdit` needs an edit. Two runs concluded those events were dead when the session had simply not reached them yet. Judge delivery from `cloud-launcher.log` after real work, not from a first look.

`preToolUse` on `Task` isn't guaranteed to have fired by the time the main agent spawns the advisor, so the main agent stamps the spawn line itself and the hook validates the stamp. That instruction lives in the `advisor` agent description as well as `__agent-main.md`, so it survives whether or not the inject reached the main agent.

The launcher also runs on desktop, alongside the plugin's own hooks, so both deliver the same event. `audit.sh` drops a line identical to the one before it, timestamp aside, and `main-agent-orchestrator-inject.sh` claims one delivery per generation, so a doubled event captures once and injects once. That's deliberate. A cloud VM with no plugins installed writes no plugin manifest, and a project-side installer can write one anywhere, so there's no reliable way to tell cloud from desktop. An environment guess that fails silently is worse than an idempotent write.

### Verifying a cloud run

This repository installs the launcher on itself, so a cloud agent started here exercises the shim on the first tool call. From the project root:

```bash
plugins/agent-conductor/cloud/verify-cloud-hooks.sh
```

In a project that only has the plugin installed, run the copy belonging to the plugin the launcher actually resolved. A VM can hold several cached revisions, and an older verifier grades a healthy session differently:

```bash
bash "$(cat /tmp/cursor-hook-debug/plugin-root)/cloud/verify-cloud-hooks.sh"
```

It reports whether any hook ran, which events reached the launcher, whether the CLI was synced, whether this session was captured, and prints the resulting brief.

By default the launcher dispatches to the installed plugin, whatever landed on the marketplace ref. To exercise an unreleased working tree instead, set `AGENT_CONDUCTOR_PLUGIN_ROOT`:

```bash
AGENT_CONDUCTOR_PLUGIN_ROOT="$PWD/plugins/agent-conductor" \
  .cursor/hooks/agent-conductor-hook.sh hooks/transcriptor/audit.sh <<'JSON'
{"conversation_id": "probe", "hook_event_name": "afterAgentResponse", "text": "working tree"}
JSON
```

`/tmp/cursor-hook-debug/cloud-launcher.log` holds one line per dispatch. It's the only record of which events a cloud agent actually delivers.

Watch the line for `preToolUse on Task`. If it never reaches the stamping hook, the main agent's own `Advise. <id>` stamp is carrying the transport by itself, which is the case the fallback exists for.

Bundled launcher: [`cloud/`](cloud/)
