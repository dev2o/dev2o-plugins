# Cursor Hooks

Project hooks inject **additional context** into agent sessions via [Cursor hooks](https://cursor.com/docs/hooks). Registration is in `.cursor/hooks.json`.

Injected context is internal to the agent loop — it does **not** appear in exported chat transcripts.

## Layout

```
hooks/
  AGENTS.md                          ← this file
  session-start-inject.sh            ← sessionStart
  main-agent-orchestrator-inject.sh  ← beforeSubmitPrompt (main agent, IDE + CLI)
  subagent-context-inject.sh         ← subagentStart
  subagent-context-pre-tool-use.sh   ← preToolUse (Task) — actual delivery path
  lib/context.sh                     ← shared loaders + optional debug_log
  hooks-debug.sh                     ← enable/disable/tail hook debug log
  config/
    AGENTS.md                        ← per-agent injection docs
    __agent-main.md                  ← main-agent (orchestrator) grounding rules
    agent-{subagent_type}.md         ← optional, one file per subagent type
```

## What runs when

| Hook event | Script | Audience | Injects |
|------------|--------|----------|---------|
| `sessionStart` | `session-start-inject.sh` | Main agent | `uv run` guidance |
| `beforeSubmitPrompt` | `main-agent-orchestrator-inject.sh` | Main agent (IDE + CLI) | Grounding rules from `config/__agent-main.md` |
| `subagentStart` | `subagent-context-inject.sh` | Subagent | Optional file from `config/agent-{type}.md` (additional_context; not reliably delivered) |
| `preToolUse` (Task) | `subagent-context-pre-tool-use.sh` | Subagent | Prepends substituted context to Task `prompt` via `updated_input` |

**Main agent only** — `beforeSubmitPrompt` fires on user send in the main composer / CLI; it never runs inside subagent sessions. Subagent context with transcript tokens is delivered via `preToolUse` on the Task tool.

## IDE vs CLI

| | IDE | CLI (`agent`, `cursor agent`) |
|---|-----|-------------------------------|
| Detect | `composer_mode: "agent"` | `composer_mode` is null/empty |
| Grounding rules | Every user message (`beforeSubmitPrompt`) | Every user message (`beforeSubmitPrompt`) |
| `uv run` note | Session start | Session start |

## Injection size limit (main agent)

`main-agent-orchestrator-inject.sh` caps `additional_context` at **8000 characters** (`MAX_INJECT_CHARS` in the script). Cursor does not reliably deliver larger hook injections.

If the assembled context (today: `config/__agent-main.md`) exceeds that limit, the hook **does not** inject the rules. It injects a short alert instead, telling the user the hook tried to inject a message above 8000 chars and reporting the actual character count (for example: `INJECTION ATTEMPT HAD 19174 CHARS`).

Keep grounding and other `beforeSubmitPrompt` payload under 8000 chars, or trim/split content (on-demand memory, subagent files, etc.).

## Editing injected content

- **Main-agent rules:** edit `config/__agent-main.md` — not `AGENTS.md` at repo root (subagents read that file; these rules should stay hook-only).
- **On-demand memory:** `.cursor/skills/commands/save-to-memory/` — not in grounding (keeps hook under size limits).
- **Subagent rules:** see `config/AGENTS.md`.

## Debugging

- **IDE:** Cursor Settings → Hooks, or the **Execution Log** panel (shows hook input/output per event).
- **CLI / scripts:** Built-in opt-in debug log when hooks fire.

```bash
make hooks-debug-on          # create .cursor/hooks/.debug trigger
make hooks-debug-tail        # follow .cursor/hooks/hooks-debug.log
make hooks-debug-status      # on/off + log path
make hooks-debug-off         # disable
make hooks-debug-clear       # delete log file
```

One-off without the trigger file: `CURSOR_HOOKS_DEBUG=1 cursor agent`

Log format is NDJSON (one JSON object per line). Each entry includes `location`, `message`, `data`, and `timestamp`.

Scripts must be executable (`chmod +x`). Paths in `hooks.json` are relative to the project root.
