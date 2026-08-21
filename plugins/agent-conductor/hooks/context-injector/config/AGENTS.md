# Agent Context Injection

Per-agent context files. `__agent-main.md` is the only system-level one: it holds the main-agent (orchestrator) grounding rules, injected at `beforeSubmitPrompt`. All other `agent-{subagent_type}.md` files are optional per-subagent prompts injected at `preToolUse` on Task via `subagent-context-pre-tool-use.sh`.

**`__agent-main.md` reaches the main agent only.** Left to the `beforeSubmitPrompt` payload alone, every subagent would receive the orchestrator rules, including the delegation protocol telling it to hand work to subagents, because a cloud Task child arrives as a new `conversation_id` with `composer_mode` of `agent`, no `parent_conversation_id` and no `subagent_type`.

Three signals identify a child, tried in that order, because each is unavailable on some surface:

1. **The payload itself.** A desktop payload names the child through `subagent_type` or a `parent_conversation_id` that differs from `conversation_id`.
2. **`subagentStart`.** The event carries the child's own id, so the binding is exact. Registered on both the plugin's `hooks.json` and `cloud/hooks.json`.
3. **The spawn prompt.** The spawn hook records the exact prompt each child will receive, including the rewritten advisor line, and the inject hook skips a prompt it recognizes, then remembers that conversation id for later turns and resumes.

The registry lives in `$CURSOR_HOOK_REGISTRY_DIR`, defaulting to `/tmp/cursor-hook-debug/registry`, alongside `inject-decisions.log`, which records why each prompt was injected or skipped. Unknown sessions are injected, so a registry failure degrades to the old behavior rather than starving the main agent.

When the main agent spawns a subagent (Task tool, slash command, etc.), the hook reads `tool_input.subagent_type`. If a matching file exists here, its contents are prepended to the Task `prompt`.

## Advisor (special case)

Neither `advisor` nor `exe-advisor` uses `agent-advisor.md`. The hook does not paste a transcript.

### `advisor` (gatekeeper)

The Executor stamps its own conversation id, so `prompt` is `Advise. <executor_id>`. The hook validates that stamp rather than supplying it: a matching id passes through unchanged, a different id is denied, and a bare `Advise.` gets the id when the parent Task `conversation_id` is a safe basename (non-empty, no `/`, no `..`).

The Executor stamps because the hook is not guaranteed to run. Cloud agents load hooks only from the project's own `.cursor/hooks.json`, never from an installed plugin, so on a cloud VM a bare `Advise.` stays bare and the gatekeeper is blind.

The gatekeeper fetches the log itself:

```
python3 .cursor/chat-transcripts/_transcripts.py brief "<spawn line verbatim>"
```

That path is synced by `sessionStart`, which cloud agents never run. Both advisor agents fall back to the plugin's own copy under `~/.cursor/plugins/cache/`.

`Advise. <id>` selects the triage view (last 10 user, assistant, and tool events) and includes `<escalate>CID:<id></escalate>`.

### `exe-advisor` (Senior Advisor)

Spawned only by the gatekeeper. The prompt is the `<escalate>` token, `CID:<executor_id>`. The hook returns `{"permission":"allow"}` and does not change the prompt.

The senior runs the same `brief` command with that spawn line. That selects the full budgeted view and does not include `<escalate>`.

If no log exists, `brief` prints `<no_transcript …/>` and exits 0. A malformed spawn line prints usage on stderr and exits 2.

## Adding context for a subagent

Create `agent-{subagent_type}.md` — the part after the `agent-` prefix must match the type exactly:

```
config/
  __agent-main.md
  agent-explore.md
  agent-{subagent_type}.md
```

**No file → no injection** (hook returns `{ "permission": "allow" }`), except `advisor`, which stamps `Advise. <executor_id>` when the parent id is a safe basename. `exe-advisor` is left unchanged.

## Project overrides

A project can override any config file by placing it at `.cursor/dev2o-agent-conductor/config/{filename}` (resolved against `CURSOR_PROJECT_DIR`, falling back to the hook's working directory). A project file wins over the plugin's bundled one; resolution is per file.

## Transcript tokens (opt-in)

Context files may include placeholders that the hook substitutes at spawn time:

| Token | Replaced with |
|-------|----------------|
| `{{CONVERSATION_ID}}` | Parent conversation id (prefers an id with a matching `.cursor/chat-transcripts/*.jsonl`) |
| `{{PROJECT_DIR}}` | Absolute project root (`CURSOR_PROJECT_DIR`, falling back to the hook's working directory) |

**Transcripts CLI:** synced to `.cursor/chat-transcripts/_transcripts.py` on each session start (overwrite). Subagents invoke it with a workspace-relative path — no token needed.

**Why the advisor agents must run from the project root:** a subagent shell does not inherit `CURSOR_PROJECT_DIR`, so the CLI falls back to walking up from its working directory to find `.cursor/chat-transcripts`. From anywhere under the project that works; from outside it, the CLI reports no transcript.

**Why the Executor stamps the id and the child cannot:** `CURSOR_CONVERSATION_ID` in a subagent shell is that subagent's own id, not its parent's. A child has no way to name the Executor's log, which is why the spawn line carries the id.

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
# spawn a subagent via the Task tool, then read what the hook received
cat /tmp/cursor-hook-debug/latest-preToolUse-payload.json
tail -20 /tmp/cursor-hook-debug/error.log
```

IDE **Execution Log** → `preToolUse` (Task) → check output for `updated_input.prompt` when a file exists (or, for `advisor`, when the stamped `Advise. <id>` line is present).

If context does not surface, the documented fallback is `preToolUse` on the Task tool with `updated_input` (see Cursor hooks docs). This project implements that in `subagent-context-pre-tool-use.sh`. It prepends substituted context to the Task `prompt` before spawn. For `advisor` it stamps the executor id. For `exe-advisor` it returns allow and leaves the prompt alone.
