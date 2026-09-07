# Agent Memory

Persistent, file-based memory for Cursor workflow subagents without hooks, background infrastructure, or prompt injection.

## How It Works

Instead of injecting a large memory protocol into system prompts or maintaining complex hook scripts, `agent-memory` uses a two-sentence model:

1. **The rules live in the file, not in the agent**: Each role's `MEMORY.md` starts with a condensed, self-describing protocol header. Because the subagent reads the file to access past memories, it receives the instructions, categories, exclusions, and verification rules at the exact moment it needs them.
2. **The path is the switch**: A lightweight, always-on rule directs the orchestrator to pass `Memory: .cursor/memory/<role>/MEMORY.md` in the `Task` tool prompt if and only if that file exists. If a subagent does not have a `Memory:` line in its prompt, it ignores memory completely.

## Installation

Link the plugin into your Cursor local plugins directory:

```bash
ln -s "$PWD/plugins/agent-memory" ~/.cursor/plugins/local/agent-memory
```

Then run **Developer: Reload Window** in Cursor.

## Enrolling a Role

A subagent role is enrolled into memory when its store exists at `.cursor/memory/<role>/MEMORY.md`.

You can enroll a role using the included skill:

```text
/agent-memory-init testing
/agent-memory-init backend-reviewer
```

Or by creating the file manually using the template at [`skills/agent-memory-init/references/MEMORY.md`](skills/agent-memory-init/references/MEMORY.md).

To un-enroll a role, simply delete or move its `.cursor/memory/<role>/MEMORY.md` file.

## Independence from Agent Conductor

`agent-memory` is completely standalone:
- **Zero hooks**: No shell scripts, no lifecycle interception (`preToolUse`, `beforeSubmitPrompt`), and no background daemons.
- **Isolated storage**: Uses `.cursor/memory/<role>/` rather than `.cursor/agent-memory/`, ensuring zero conflicts with `agent-conductor` or legacy setups.
- Can be used alongside `agent-conductor` or completely on its own in any workspace.

## License

MIT
