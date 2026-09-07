---
name: agent-conductor-discontinued
description: "Use for /agent-conductor-discontinued. Detects leftover Agent Conductor shim files, asks before cleanup, then points at advisor, agent-memory, and env-protect. Never enable unasked."
disable-model-invocation: true
---

# Agent Conductor is discontinued

```text
/agent-conductor-discontinued
```

Subagents: ignore this skill. Do not mention it. Do not clean anything.

This plugin no longer runs hooks, seeds files, or injects context. Its jobs now live in three smaller plugins from the same marketplace:

- `advisor` — strategic second opinions, no hooks
- `agent-memory` — file-based memory for workflow subagents, no hooks
- `env-protect` — denies `env`, `printenv`, `export -p`, and reads of `.env` files

Leave `.cursor/agent-memory/` untouched.

## Detect leftovers

Check, in this order, and report what you find:

1. `.cursor/hooks.json` contains any `command` that invokes `agent-conductor-hook.sh`
2. `.cursor/hooks/agent-conductor-hook.sh` exists
3. `.cursor/chat-transcripts/` exists

If none of those exist, skip cleanup and go to **Uninstall**.

If any exist, tell the user what you found and **ask for explicit permission** before changing anything. Do not proceed on silence. Do not commit. Do not run `rm -rf` outside the paths listed below. Show the proposed `.cursor/hooks.json` diff before writing it.

Optional mention only: `.cursor/dev2o-agent-conductor/config/` override files, if present, are no longer read.

## Cleanup (only after permission)

Do this in order:

1. Edit `.cursor/hooks.json`: remove only entries whose `command` invokes `.cursor/hooks/agent-conductor-hook.sh`. Keep unrelated hooks. Drop an event key when its array is empty. If `hooks` is then empty, leave `{"version": 1, "hooks": {}}`, or delete the file only if the user agrees.
2. Delete `.cursor/hooks/agent-conductor-hook.sh`. If `.cursor/hooks/` is then empty, delete the directory.
3. `.cursor/chat-transcripts/` may hold scrubbed session logs (`_transcripts.py`, `AGENTS.md`, `.cursorignore`, `*.jsonl`). Ask once more if the user wants them archived first. Then delete the directory.
4. Do not touch `.cursor/agent-memory/`.

## Uninstall

After leftovers are gone (or were already gone), tell the user to uninstall this plugin so the skill goes away:

- Cursor: **Customize → Plugins → Agent Conductor → Uninstall**
- Local clone: remove the `~/.cursor/plugins/local/agent-conductor` symlink
- Then **Developer: Reload Window**

Recommend installing `advisor`, `agent-memory`, and `env-protect` from the same marketplace.
