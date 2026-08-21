# Run Agent Conductor on Cloud Agents

Cursor loads a Cloud Agent's hooks only from the project's own `.cursor/hooks.json`, never from an installed plugin. Team and enterprise hooks also load on Enterprise plans. So a cloud run picks up the plugin's `advisor` agent and the `advisor-check` skill, and nothing else. No per-agent routing, no transcript capture, no seeded boilerplate.

The advisor still answers instead of breaking. The main agent stamps `Advise. <id>` itself, and the advisor falls back to the plugin's own copy of the CLI, so a cloud run with no captured log reports `<no_transcript />` and asks the main agent to restate its objective.

To get the whole plugin, commit a launcher into the project.

## Install the launcher

```bash
mkdir -p .cursor/hooks
cp <plugin>/cloud/hooks.json .cursor/hooks.json
cp <plugin>/cloud/agent-conductor-hook.sh .cursor/hooks/
chmod +x .cursor/hooks/agent-conductor-hook.sh
git add -f .cursor/hooks.json .cursor/hooks/agent-conductor-hook.sh
```

Git has to track both files, because a Cloud Agent clones the repo fresh. Many projects ignore `.cursor/`, which is why `-f` is there.

The launcher finds the installed plugin under `~/.cursor/plugins/cache/`, passes the event to the plugin's own hook script, and syncs `_transcripts.py` into the project on whichever hook fires first. That sync stands in for the `sessionStart` that never runs. Every error path fails open, exactly like the hooks it delegates to.

`cloud/hooks.json` mirrors [`hooks/hooks.json`](../hooks/hooks.json) minus `sessionStart`. Keep the two in step when you add an event.

## What fires in the cloud

`sessionStart` never fires. Cursor documents that. Everything else the plugin registers has been observed firing on a cloud VM, including `preToolUse` on `Task`, `beforeSubmitPrompt`, `subagentStart`, `subagentStop`, `stop`, `afterAgentResponse` and `afterAgentThought`.

Read a short session's absences carefully. Measure early and only `beforeShellExecution`, `afterShellExecution` and `beforeReadFile` have appeared, because the rest need the session to do the triggering thing first. `preToolUse` on `Task` needs a subagent spawn, `subagentStop` needs one to finish, `afterFileEdit` needs an edit. Two separate runs concluded those events were dead when the session had simply not reached them yet. Judge delivery from `cloud-launcher.log` after real work, not from a first look.

`preToolUse` on `Task` is not guaranteed to have fired by the time the main agent spawns the advisor, so the main agent stamps the spawn line itself and the hook validates the stamp. That instruction lives in the `advisor` agent description as well as in `__agent-main.md`, so it survives whether or not the routing reached the main agent.

The launcher also runs on desktop, alongside the plugin's own hooks, so both deliver the same event. Capture drops a line identical to the one before it apart from the timestamp, and the routing hook claims one delivery per conversation and generation with an atomic write, so a doubled event captures once and injects once. That is deliberate. A cloud VM with no plugins installed writes no plugin manifest, and a project-side installer can write one anywhere, so nothing reliably distinguishes cloud from desktop. An environment guess that fails silently is worse than an idempotent write.

## Verify a run

This repository installs the launcher on itself, so a cloud agent started here exercises the shim on its first tool call.

```bash
plugins/agent-conductor/cloud/verify-cloud-hooks.sh
```

In a project that only has the plugin installed, run the copy belonging to the plugin the launcher actually resolved. A VM can hold several cached revisions, and an older verifier grades a healthy session differently.

```bash
bash "$(cat /tmp/cursor-hook-debug/plugin-root)/cloud/verify-cloud-hooks.sh"
```

A healthy session looks like this.

```text
PASS some hook ran (dump directory exists)
PASS the cloud launcher ran

events delivered to the launcher:
     69 event=beforeReadFile
     58 event=beforeShellExecution
     47 event=afterAgentThought
     29 event=preToolUse
     12 event=beforeSubmitPrompt
      1 event=subagentStart

PASS preToolUse on Task reached the stamping hook
PASS the copied launcher matches the installed plugin
PASS the copied hooks.json registers the same events as the plugin's
PASS a copy of the CLI answers brief
PASS the project copy of the CLI understands brief
PASS this session has a captured transcript

VERDICT agent-conductor is live in this session
```

The verifier reports whether any hook ran, which events reached the launcher, whether the CLI was synced, whether this session was captured, and it prints the resulting brief. The line to watch is `preToolUse on Task`. If it never reaches the stamping hook, the main agent's own `Advise. <id>` stamp is carrying the advisor transport by itself, which is the case the fallback exists for.

## Test an unreleased working tree

By default the launcher dispatches to the installed plugin, which is whatever landed on the marketplace ref. Set `AGENT_CONDUCTOR_PLUGIN_ROOT` to exercise a working tree instead.

```bash
AGENT_CONDUCTOR_PLUGIN_ROOT="$PWD/plugins/agent-conductor" \
  .cursor/hooks/agent-conductor-hook.sh hooks/transcriptor/audit.sh <<'JSON'
{"conversation_id": "probe", "hook_event_name": "afterAgentResponse", "text": "working tree"}
JSON
```

`/tmp/cursor-hook-debug/cloud-launcher.log` holds one line per dispatch. It is the only record of which events a Cloud Agent actually delivers.
