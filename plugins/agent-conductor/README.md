# Agent Conductor (discontinued)

Agent Conductor no longer runs hooks, seeds project files, or injects per-agent context.

Its jobs now live in three smaller plugins from this marketplace:

| Plugin | What it does |
| --- | --- |
| [advisor](../advisor) | Strategic second opinions using native Cursor transcripts. No hooks. |
| [agent-memory](../agent-memory) | Persistent file-based memory for workflow subagents. No hooks. |
| [env-protect](../env-protect) | Denies `env`, `printenv`, `export -p`, reads of `.env` files, and `op` secret reads printed to the terminal. |

This leftover plugin ships `/agent-conductor-discontinued`. It does not auto-invoke. Run it when you want an agent to detect leftover shim files and ask before cleaning them up.

It will not delete files, edit hooks, or uninstall itself without permission.

## What the skill asks to clean up

Only after you agree, and only these leftovers from the old cloud-hook shim:

1. Remove entries in the project `.cursor/hooks.json` whose `command` forwards to `.cursor/hooks/agent-conductor-hook.sh`. Leave any other hooks alone.
2. Delete `.cursor/hooks/agent-conductor-hook.sh`.
3. Delete `.cursor/chat-transcripts/` (scrubbed session logs plus the old `_transcripts.py` CLI). Say if you want them archived first.
4. Delete `.cursor/agent-memory/AGENTS.md` (Conductor's old injected protocol). Leave the rest of `.cursor/agent-memory/` in place. That directory is the live store for the `agent-memory` plugin.

Then uninstall the plugin:

- Cursor: **Customize → Plugins → Agent Conductor → Uninstall**
- Local clone: remove `~/.cursor/plugins/local/agent-conductor`
- Then **Developer: Reload Window**

Install `advisor`, `agent-memory`, and `env-protect` from the same marketplace.

Override files under `.cursor/dev2o-agent-conductor/config/` are no longer read. You can delete them yourself if they are still around.
