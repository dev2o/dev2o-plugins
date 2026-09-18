# Agent Memory

Persistent, file-based memory for Cursor workflow subagents without hooks, background infrastructure, or prompt injection.

## How It Works

Instead of injecting a large memory protocol into system prompts or maintaining complex hook scripts, `agent-memory` uses a two-sentence model:

1. **The rules live in the file, not in the agent**: Each role's `MEMORY.md` starts with a condensed, self-describing protocol header. Because the subagent reads the file to access past memories, it receives the instructions, categories, exclusions, and verification rules at the exact moment it needs them.
2. **The path is the switch**: A lightweight, always-on rule directs the orchestrator to pass `Memory: .cursor/agent-memory/<role>/MEMORY.md` in the `Task` tool prompt if and only if that file exists. If a subagent does not have a `Memory:` line in its prompt, it ignores memory completely.

## Memory Organization

Memories are organized into topic files within each role's directory (`.cursor/agent-memory/<role>/`):

- **`MEMORY.md` is an index, not a memory file**: It contains pointers to topic memory files with brief descriptions under four sections (`## User`, `## Feedback`, `## Project`, `## Reference`). It has no frontmatter and never holds raw memory content directly.
- **Individual topic files**: Each memory is stored in its own markdown file (e.g., `feedback_testing.md`, `project_auth_rewrite.md`) with YAML frontmatter:
  ```markdown
  ---
  name: <memory name>
  description: <one-line description — used to decide relevance in future conversations, so be specific>
  type: <user | feedback | project | reference>
  ---

  <memory content — for feedback/project types, structure as: rule/fact, then **Why:** and **How to apply:** lines>
  ```
- **Two-step save process**:
  1. Write the memory to its own topic file (`<type>_<topic>.md`).
  2. Add an index pointer to `MEMORY.md`: `- [Title](<filename>.md) — <brief one-line description>`.
  Before writing a new memory, agents check for existing topic files to update.

## Installation

Link the plugin into your Cursor local plugins directory:

```bash
ln -s "$PWD/plugins/agent-memory" ~/.cursor/plugins/local/agent-memory
```

Then run **Developer: Reload Window** in Cursor.

## Enrolling or Auditing a Role

A subagent role is enrolled into memory when its store exists at `.cursor/agent-memory/<role>/MEMORY.md`.

You can enroll a new role or audit and clean up an existing role store using the included skill:

```text
/agent-memory-init testing
/agent-memory-init backend-reviewer
```

Running `/agent-memory-init <role>`:
- **New roles**: Creates the role directory and seeds `MEMORY.md` with the protocol header and section index.
- **Existing roles**: Audits the store to ensure `MEMORY.md` is formatted as a clean index. Any memory content accidentally written directly into `MEMORY.md` is extracted into dedicated topic files (`<type>_<topic>.md`) with YAML frontmatter. Audits existing memories against the current codebase to prune stale, dead, or obsolete notes while preserving relevant knowledge.
- **Model recommendation**: Gemini 3.8 Flash (`gemini-3.8-flash-high`) is recommended for the cleanup and formatting process.
- Deletes leftover `.cursor/agent-memory/AGENTS.md` (Conductor's old injected protocol) and leaves the rest of that directory alone.

Or by creating the file manually using the template at [`skills/agent-memory-init/references/MEMORY.md`](skills/agent-memory-init/references/MEMORY.md).

To un-enroll a role, simply delete or move its `.cursor/agent-memory/<role>/MEMORY.md` file.

## Independence from Agent Conductor

`agent-memory` is completely standalone:
- **Zero hooks**: No shell scripts, no lifecycle interception (`preToolUse`, `beforeSubmitPrompt`), and no background daemons.
- **Same store as Agent Conductor**: Uses `.cursor/agent-memory/<role>/`, so existing role stores keep working.
- Can be used on its own in any workspace.

## License

MIT
