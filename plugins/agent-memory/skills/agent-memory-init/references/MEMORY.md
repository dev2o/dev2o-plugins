# Agent Memory: {role}

Read before acting. Update before finishing. If the user asks to remember something, save it now. If they ask to forget it, remove it.

## Organization & How to Save

`MEMORY.md` is an INDEX, not a memory file. NEVER write memory content directly into this file.

Saving memory is a two-step process:

1. **Step 1 — Write memory to its own topic file:**
   Create or update a markdown file in this directory (`.cursor/agent-memory/{role}/<type>_<topic>.md`, e.g., `feedback_testing.md`, `project_auth.md`) using this frontmatter format:
   ```markdown
   ---
   name: <memory name>
   description: <one-line description — used to decide relevance in future conversations, so be specific>
   type: <user | feedback | project | reference>
   ---

   <memory content>
   ```
   For **feedback** and **project** types, structure the body as:
   - Rule/Fact
   - **Why:** reason/motivation (past incident, preference, constraint, deadline)
   - **How to apply:** when and where this kicks in

2. **Step 2 — Add an index pointer to `MEMORY.md`:**
   Add a link under the matching section below (`## User`, `## Feedback`, `## Project`, or `## Reference`):
   `- [Title](<filename>.md) — Brief description`
   (Replace `[no <type> memories inserted yet]` when adding the first entry.)

- Check existing topic files first — update an existing file instead of creating duplicate memories.
- Organize semantically by topic, not chronologically.
- Keep `MEMORY.md` concise: it is an index of pointers, not raw content.

## Types of Memory

- **User:** role, preferences, background, collaboration style.
- **Feedback:** corrections and validated approaches. Rule, then **Why:**, then **How to apply:**.
- **Project:** non-obvious facts, deadlines, constraints. Absolute dates (YYYY-MM-DD). Fact, then **Why:**, then **How to apply:**.
- **Reference:** pointers to external systems (Linear, Slack, dashboards, docs).

## Do Not Save

Code patterns, architecture, git history, fix recipes, ephemeral task state, or anything the repo already states.

## Verify

A memory names a thing that existed when it was written. Check the file, flag, or function still exists before recommending it. Remove or update stale entries and their index links. Trust current observation over a recalled snapshot.

## User

[no user memories inserted yet]

## Feedback

[no feedback memories inserted yet]

## Project

[no project memories inserted yet]

## Reference

[no reference memories inserted yet]
