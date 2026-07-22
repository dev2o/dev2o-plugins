# Agent Context Injection

Per-agent context files. `__agent-main.md` is the only system-level one: it holds the main-agent (orchestrator) grounding rules, injected at `beforeSubmitPrompt`. All other `agent-{subagent_type}.md` files are optional per-subagent prompts injected at **`subagentStart`** via `subagent-context-inject.sh`.

When the main agent spawns a subagent (Task tool, slash command, etc.), Cursor calls `subagentStart` with a `subagent_type`. If a matching file exists here, its contents are returned as `additional_context`.

## Adding context for a subagent

Create `agent-{subagent_type}.md` — the part after the `agent-` prefix must match the type exactly:

```
config/
  __agent-main.md
  agent-advisor.md
  agent-explore.md
  agent-{subagent_type}.md
```

**No file → no injection** (hook returns `{ "permission": "allow" }`).

## Project overrides

A project can override any config file by placing it at `.cursor/dev2o-agent-conductor/config/{filename}` (resolved against `CURSOR_PROJECT_DIR`, falling back to the hook's working directory). A project file wins over the plugin's bundled one; resolution is per file.

## Transcript tokens (opt-in)

Context files may include placeholders that the hook substitutes at spawn time:

| Token | Replaced with |
|-------|----------------|
| `{{CONVERSATION_ID}}` | Parent conversation id (prefers an id with a matching `.cursor/chat-transcripts/*.jsonl`) |
| `{{TRANSCRIPTS_CLI}}` | Absolute path to the plugin's `transcripts.py` in the plugins cache (resolved at runtime) |
| `{{PROJECT_DIR}}` | Absolute project root (`CURSOR_PROJECT_DIR`, falling back to the hook's working directory) |

**Why `{{TRANSCRIPTS_CLI}}`:** the transcript data lives in the *project* (`.cursor/chat-transcripts/`) but the CLI ships in the *plugin* cache, whose absolute location is not knowable ahead of time. Hardcoding a path (e.g. `.cursor/transcriptor/transcripts.py`) points at a script that does not exist and derails the subagent. Always use the token so the injected command is runnable as-is.

**Why the `CURSOR_PROJECT_DIR="{{PROJECT_DIR}}"` prefix:** the CLI resolves the transcript directory from `CURSOR_PROJECT_DIR`. Subagent shells don't inherit it, and without it the CLI would look near the plugin cache and report "No transcripts found". Baking the resolved project dir into the injected command makes it work from any cwd. The CLI is a stdlib-only `python3` script (its shebang is `#!/usr/bin/env python3`, with an empty PEP-723 dependency block so `uv run` still works but is not required) — it lives in the plugin cache, which may sit outside sandbox-allowed paths, so agents must run it with `required_permissions: ["all"]`.

**Lazy evaluation:** substitution runs only when a context file contains a token. Subagents without a context file, or with static-only context, incur zero overhead.

If no conversation id is available, `{{CONVERSATION_ID}}` is replaced with `(conversation id unavailable)`. Transcripts themselves are never injected — subagents read them via the substituted `{{TRANSCRIPTS_CLI}}` command.

### Example (`agent-advisor.md`)

Advisor is read-only; it reviews the transcript itself via the transcripts CLI:

```markdown
Parent conversation id: `{{CONVERSATION_ID}}`

Review it: CURSOR_PROJECT_DIR="{{PROJECT_DIR}}" {{TRANSCRIPTS_CLI}} show {{CONVERSATION_ID}} --offset -20
```

## Example (`agent-explore.md`)

```markdown
Read-only research scout. Retrieve, classify, and surface findings; never make final decisions.
Prefer the project's designated skills and data sources.
```

Keep files short. Subagents already have full agent definitions in `.cursor/agents/`. Use this for hook-specific reminders that should not live in the main thread or agent file.

## What not to put here

- Main-agent grounding rules (`__agent-main.md`) — those are main-agent only, never injected into subagents.
- Long duplicates of `.cursor/agents/{name}.md` — edit the agent file instead.

## Verifying

```bash
make hooks-debug-on
# spawn subagent via Task tool
make hooks-debug-tail
```

IDE **Execution Log** → `subagentStart` → check output for `additional_context` when a file exists. Debug log entries include `tokens_used` and `render` branch when substitution runs.

If context does not surface, the documented fallback is `preToolUse` on the Task tool with `updated_input` (see Cursor hooks docs). This project implements that fallback in `subagent-context-pre-tool-use.sh` — it prepends substituted context to the Task `prompt` before spawn. `subagentStart` `additional_context` is also returned but is not reliably delivered to subagents in current Cursor builds.
