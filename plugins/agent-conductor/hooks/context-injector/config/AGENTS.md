# Agent Context Injection

Per-agent context files. `__agent-main.md` is the only system-level one: it holds the main-agent (orchestrator) grounding rules, injected at `beforeSubmitPrompt`. All other `agent-{subagent_type}.md` files are optional per-subagent prompts injected at `preToolUse` on Task via `subagent-context-pre-tool-use.sh`.

When the main agent spawns a subagent (Task tool, slash command, etc.), the hook reads `tool_input.subagent_type`. If a matching file exists here, its contents are prepended to the Task `prompt`.

## Advisor (special case)

`advisor` does **not** use `agent-advisor.md`. The hook resolves `{{CONVERSATION_ID}}` with the same token logic as other context files, runs `hooks/transcriptor/transcripts.py show <id>`, and sets the Task prompt to **only**:

```
CHAT TRANSCRIPT TO ADVISE ON:

<cli stdout>
```

The original Task prompt (`Advise.`) is dropped. If the id is unavailable or `show` fails, the same header is used with `(conversation id unavailable)`.

## Adding context for a subagent

Create `agent-{subagent_type}.md` — the part after the `agent-` prefix must match the type exactly:

```
config/
  __agent-main.md
  agent-explore.md
  agent-{subagent_type}.md
```

**No file → no injection** (hook returns `{ "permission": "allow" }`), except advisor, which always rewrites the prompt.

## Project overrides

A project can override any config file by placing it at `.cursor/dev2o-agent-conductor/config/{filename}` (resolved against `CURSOR_PROJECT_DIR`, falling back to the hook's working directory). A project file wins over the plugin's bundled one; resolution is per file.

## Transcript tokens (opt-in)

Context files may include placeholders that the hook substitutes at spawn time:

| Token | Replaced with |
|-------|----------------|
| `{{CONVERSATION_ID}}` | Parent conversation id (prefers an id with a matching `.cursor/chat-transcripts/*.jsonl`) |
| `{{PROJECT_DIR}}` | Absolute project root (`CURSOR_PROJECT_DIR`, falling back to the hook's working directory) |

**Transcripts CLI:** synced to `.cursor/chat-transcripts/_transcripts.py` on each session start (overwrite). Subagents invoke it with a workspace-relative path — no token needed.

**Why the `CURSOR_PROJECT_DIR="{{PROJECT_DIR}}"` prefix:** the CLI resolves the transcript directory from `CURSOR_PROJECT_DIR`. Subagent shells don't inherit it, and without it the CLI would look from the wrong cwd and report "No transcripts found". Baking the resolved project dir into the injected command makes it work from any cwd.

**Lazy evaluation:** substitution runs only when a context file contains a token. Subagents without a context file, or with static-only context, incur zero overhead.

If no conversation id is available, `{{CONVERSATION_ID}}` is replaced with `(conversation id unavailable)`.

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

IDE **Execution Log** → `preToolUse` (Task) → check output for `updated_input.prompt` when a file exists (or, for advisor, when the transcript dump is present).

If context does not surface, the documented fallback is `preToolUse` on the Task tool with `updated_input` (see Cursor hooks docs). This project implements that in `subagent-context-pre-tool-use.sh` — it prepends substituted context to the Task `prompt` before spawn (advisor: replaces the prompt with the transcript dump).
