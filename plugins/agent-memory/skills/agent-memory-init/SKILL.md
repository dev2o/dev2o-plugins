---
name: agent-memory-init
description: "Write a role's .cursor/memory/<role>/MEMORY.md store. Use for /agent-memory-init, 'enroll a role', or adding memory for a subagent. Never enable unasked."
disable-model-invocation: true
---

# Init agent memory

Write `.cursor/memory/<role>/MEMORY.md` from `references/MEMORY.md`. Do not overwrite an existing store.

```text
/agent-memory-init <role>
```

## Step 1. Role

Take `<role>` from the invocation. If missing, ask once.

## Step 2. Existing store

If `.cursor/memory/<role>/MEMORY.md` exists, stop. Tell the user it is already enrolled.

## Step 3. Write

Read [`references/MEMORY.md`](references/MEMORY.md). Replace `{role}` with the role name. Write `.cursor/memory/<role>/MEMORY.md`.

## Step 4. Confirm

The path exists. Orchestrators pass `Memory: .cursor/memory/<role>/MEMORY.md` when spawning that `subagent_type`.
