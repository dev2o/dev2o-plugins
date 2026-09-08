---
name: agent-memory-init
description: "Write a role's .cursor/agent-memory/<role>/MEMORY.md store and remove leftover Conductor AGENTS.md. Use for /agent-memory-init, 'enroll a role', or adding memory for a subagent. Never enable unasked."
disable-model-invocation: true
---

# Init agent memory

Write `.cursor/agent-memory/<role>/MEMORY.md` from `references/MEMORY.md`. Do not overwrite an existing store. Delete leftover `.cursor/agent-memory/AGENTS.md` if present.

```text
/agent-memory-init <role>
```

## Step 1. Role

Take `<role>` from the invocation. If missing, ask once.

## Step 2. Existing store

If `.cursor/agent-memory/<role>/MEMORY.md` exists, skip the write. Tell the user it is already enrolled. Still do Step 4.

## Step 3. Write

If the store does not exist: read [`references/MEMORY.md`](references/MEMORY.md). Replace `{role}` with the role name. Write `.cursor/agent-memory/<role>/MEMORY.md`.

## Step 4. Leftover protocol

If `.cursor/agent-memory/AGENTS.md` exists, delete it. Leave every other file under `.cursor/agent-memory/` alone.

## Step 5. Confirm

The path exists. Orchestrators pass `Memory: .cursor/agent-memory/<role>/MEMORY.md` when spawning that `subagent_type`. Say if `AGENTS.md` was removed.
