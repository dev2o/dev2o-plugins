---
name: agent-memory-init
description: "Initialize, review, or format a role's .cursor/agent-memory/<role>/ store. Cleans up formatting, extracts inline notes into topic files, audits relevance, and removes leftover Conductor AGENTS.md. Use for /agent-memory-init, 'enroll a role', or 'cleanup agent memory'. Never enable unasked."
disable-model-invocation: true
---

# Init and Review Agent Memory

Initialize a new role store or review and clean up an existing store at `.cursor/agent-memory/<role>/`. Ensures `MEMORY.md` is strictly an index, extracts inline memory notes into properly formatted topic files, audits memory relevance against current code, and removes leftover Conductor `AGENTS.md`.

```text
/agent-memory-init <role>
```

**Recommended Model:** Gemini 3.8 Flash (`gemini-3.8-flash-high` or `gemini-3.8-flash`).

## Step 1. Role

Take `<role>` from the invocation. If missing, list existing directories under `.cursor/agent-memory/` or ask the user which role to target.

## Step 2. Existing Store: Review, Clean Up, and Format

If `.cursor/agent-memory/<role>/MEMORY.md` exists, do NOT simply skip. Review the store and bring it into compliance with the organization protocol:

1. **Audit Protocol Header**:
   Ensure `MEMORY.md` begins with the standard protocol header from [`references/MEMORY.md`](references/MEMORY.md) (replacing `{role}` with the role name), including the `## Organization & How to Save`, `## Types of Memory`, `## Do Not Save`, and `## Verify` sections.

2. **Enforce Index vs. Memory Split**:
   - Check if raw memory content, bullet lists of facts, or freeform notes have been shoved directly into `MEMORY.md`.
   - `MEMORY.md` is strictly an index. Extract every memory into its own individual topic file in `.cursor/agent-memory/<role>/<type>_<topic>.md` (e.g., `feedback_testing_approach.md`, `project_auth_migration.md`).
   - Format each topic file with YAML frontmatter:
     ```markdown
     ---
     name: <memory name>
     description: <one-line description — used to decide relevance in future conversations>
     type: <user | feedback | project | reference>
     ---

     <memory content>
     ```
   - For **feedback** and **project** types, ensure the body follows the structured format:
     - Fact or rule
     - **Why:** motivation, constraint, incident, or deadline
     - **How to apply:** concrete conditions for when this guidance applies
   - Replace extracted content in `MEMORY.md` with concise index links under the matching section (`## User`, `## Feedback`, `## Project`, `## Reference`):
     `- [Title](<filename>.md) — Brief description`
     If a section has no entries, leave `[no <type> memories inserted yet]`.

3. **Audit Relevance & Prune Stale Information**:
   - Verify every memory against the current codebase:
     - If a memory references a specific file path, verify the file still exists.
     - If a memory names a function, flag, or command, check that it exists in the codebase.
     - If a project deadline or temporary migration constraint has passed or been superseded, update or remove it.
   - Keep what is still load-bearing, accurate, and relevant.
   - Remove ephemeral task details, debugging recipes, or duplicate notes.
   - Remove dead topic files whose entries were deleted or pruned.

## Step 3. New Store: Write Template

If `.cursor/agent-memory/<role>/MEMORY.md` does not exist:
1. Create the directory `.cursor/agent-memory/<role>/` if needed.
2. Read [`references/MEMORY.md`](references/MEMORY.md).
3. Replace `{role}` with the role name.
4. Write `.cursor/agent-memory/<role>/MEMORY.md`.

## Step 4. Leftover Protocol

If `.cursor/agent-memory/AGENTS.md` exists, delete it. Leave all role directories under `.cursor/agent-memory/` intact.

## Step 5. Confirm

Report to the user:
- Path to `.cursor/agent-memory/<role>/MEMORY.md`.
- Summary of review actions: whether newly initialized or cleaned up, topic files extracted or formatted, stale memories pruned, and index links updated.
- Confirm orchestrators will pass `Memory: .cursor/agent-memory/<role>/MEMORY.md` when spawning that `subagent_type`.
- Mention if leftover `AGENTS.md` was removed.
