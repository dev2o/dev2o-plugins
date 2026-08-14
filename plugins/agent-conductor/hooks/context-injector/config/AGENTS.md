# Agent Context Injection

Per-agent context files. `__agent-main.md` is the only system-level one: it holds the main-agent (orchestrator) grounding rules, injected at `beforeSubmitPrompt`. All other `agent-{subagent_type}.md` files are optional per-subagent prompts injected at `preToolUse` on Task via `subagent-context-pre-tool-use.sh`.

When the main agent spawns a subagent (Task tool, slash command, etc.), the hook reads `tool_input.subagent_type`. If a matching file exists here, its contents are prepended to the Task `prompt`.

## Advisor (special case)

Neither `advisor` nor `exe-advisor` uses `agent-advisor.md`. Both always rewrite the Task prompt.

### `advisor` (gatekeeper)

Spawned by the Executor with prompt `Advise.` The hook resolves the executor conversation id (same token logic as other context files), runs `hooks/transcriptor/transcripts.py show <id> --last 10`, and sets the Task prompt to **only**:

```
The Executor agent has invoked you for strategic guidance.

<inputs>
- Conversation ID: <id>

- RECENT_TRANSCRIPT:
<last 10 user/assistant/tool events>
</inputs>

Apply your <evaluation_rules> to the <inputs> above.
If a LEGITIMATE NEED is met, invoke the `exe-advisor` subagent with prompt exactly `CID:<id>` and the appropriate model. Otherwise, output the appropriate rejection message to return directly to the Executor.
```

The original Task prompt (`Advise.`) is dropped.

### `exe-advisor` (Senior Advisor)

Spawned only by the gatekeeper. The gatekeeper's Task prompt must be exactly `CID:<executor_conversation_id>`. The hook parses that string (not the nested hook `conversation_id`), runs `hooks/transcriptor/transcripts.py show <id>`, and sets the Task prompt to **only**:

```
The Executor agent has paused its workflow. You must provide strategic oversight based on the transcript of its actions so far.

<environment_awareness>
You are operating within the Cursor IDE. You have implicit access to the workspace context, file contents, and codebase embeddings attached to this session. The <execution_transcript> represents what the Executor *thinks* it is doing; you must verify its assumptions against the actual codebase reality.
</environment_awareness>

<execution_transcript>
<cli stdout>
</execution_transcript>

<advisor_directives>
1. Deduce the Objective: Read the earliest entries in the <execution_transcript> to identify the user's original goal.
2. Analyze the State: Evaluate the Executor's recent steps and errors. Are they on the right track or stuck in a loop?
3. Cross-Reference: Compare the transcript against your Cursor workspace context. Is the Executor making false assumptions about file structures or dependencies?
4. Direct: Output your strategic guidance immediately. Tell the Executor exactly what to do next, which files to target, or why its current approach is failing.
</advisor_directives>
```

The `CID:` line is dropped. If the id is missing, malformed (`..` or `/`), or `show` fails, the same wrapper is used with `(conversation id unavailable)` inside `<execution_transcript>`.

## Adding context for a subagent

Create `agent-{subagent_type}.md` — the part after the `agent-` prefix must match the type exactly:

```
config/
  __agent-main.md
  agent-explore.md
  agent-{subagent_type}.md
```

**No file → no injection** (hook returns `{ "permission": "allow" }`), except `advisor` and `exe-advisor`, which always rewrite the prompt.

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

IDE **Execution Log** → `preToolUse` (Task) → check output for `updated_input.prompt` when a file exists (or, for advisor / exe-advisor, when the rewritten prompt is present).

If context does not surface, the documented fallback is `preToolUse` on the Task tool with `updated_input` (see Cursor hooks docs). This project implements that in `subagent-context-pre-tool-use.sh` — it prepends substituted context to the Task `prompt` before spawn (`advisor`: gatekeeper template; `exe-advisor`: full transcript dump).
