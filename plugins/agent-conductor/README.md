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
| `boilerplate/agent-memory/` | `.cursor/agent-memory/` | **Seed** — copied only if the destination file does not exist |
| `boilerplate/chat-transcripts/` | `.cursor/chat-transcripts/` | **Seed** — docs and ignore rules copied only if missing |
| `hooks/transcriptor/transcripts.py` | `.cursor/chat-transcripts/_transcripts.py` | **Sync** — overwritten on every session start |

### `agent-memory`

Cross-session persistence for the orchestrator. Seeded once:

```
.cursor/agent-memory/orchestrator/MEMORY.md
```

Edit this file in your project; the plugin will not overwrite it once it exists.

### `chat-transcripts`

Hook-captured, scrubbed audit logs land here as `{conversation_id}.jsonl`. Seeded docs explain usage; do not read `.jsonl` files directly — use `_transcripts.py` or the advisor subagent.

```
.cursor/chat-transcripts/
  AGENTS.md
  _transcripts.py    ← synced from plugin; do not edit
  {conversation_id}.jsonl   ← created at runtime by audit hook
```

Bundled boilerplate: [`boilerplate/agent-memory/`](boilerplate/agent-memory/), [`boilerplate/chat-transcripts/`](boilerplate/chat-transcripts/)
