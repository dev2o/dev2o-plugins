# Agent Conductor (discontinued)

Agent Conductor no longer runs hooks, seeds project files, or injects per-agent context.

Its jobs now live in three smaller plugins from this marketplace:

| Plugin | What it does |
| --- | --- |
| [advisor](../advisor) | Strategic second opinions using native Cursor transcripts. No hooks. |
| [agent-memory](../agent-memory) | Persistent file-based memory for workflow subagents. No hooks. |
| [env-protect](../env-protect) | Denies `env`, `printenv`, `export -p`, and reads of `.env` files. |

This leftover plugin ships one always-on rule. On the next agent run it tells the agent the plugin is discontinued, then asks **you** before touching anything.

It will not delete files, edit hooks, or uninstall itself without permission.

## What the rule asks to clean up

Only after you agree, and only these leftovers from the old cloud-hook shim:

1. Remove entries in the project `.cursor/hooks.json` whose `command` forwards to `.cursor/hooks/agent-conductor-hook.sh`. Leave any other hooks alone.
2. Delete `.cursor/hooks/agent-conductor-hook.sh`.
3. Delete `.cursor/chat-transcripts/` (scrubbed session logs plus the old `_transcripts.py` CLI). Say if you want them archived first.
4. Leave `.cursor/agent-memory/` in place.

Then uninstall the plugin so the notice stops:

- Cursor: **Customize → Plugins → Agent Conductor → Uninstall**
- Local clone: remove `~/.cursor/plugins/local/agent-conductor`
- Then **Developer: Reload Window**

Install `advisor`, `agent-memory`, and `env-protect` from the same marketplace.

Override files under `.cursor/dev2o-agent-conductor/config/` are no longer read. You can delete them yourself if they are still around.
