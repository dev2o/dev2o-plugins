---
name: save-to-memory
description: >-
  Save, update, recall, or delete persistent agent memory under
  .cursor/agent-memory/. Triggers: /save-to-memory,
  "remember that", "forget X", "what did we save about Y".
disable-model-invocation: true
---

# Persistent Agent Memory

Persistent file-based memory at `.cursor/agent-memory/{agent-name}/`. Resolve `{agent-name}` from your own prompt or the project's AGENTS.md; default: `orchestrator`. Directory exists → write directly with the Write tool (never mkdir or existence-check). Directory missing → create it with an empty `MEMORY.md` index first.

Build it up across conversations: who the user is, how they collaborate, behaviors to repeat/avoid, context behind their work.

User asks to remember something → save immediately as the best-fitting type. User asks to forget → find and remove the entry.

## Types of memory

---
memory_type: user
description: The user's role, goals, responsibilities, knowledge, and preferences. Purpose — tailor future behavior to this specific user (a senior engineer and a first-time coder warrant different collaboration). Never save anything that reads as negative judgment of the user or is irrelevant to the shared work.
save_when: You learn any detail about the user's role, preferences, responsibilities, or knowledge.
use_when: Work should be shaped by the user's profile — e.g., pitch explanations to their existing mental model and domain knowledge.
examples:
  - user: "I'm a data scientist investigating what logging we have in place"
    save: user is a data scientist, currently focused on observability/logging
  - user: "I've been writing Go for ten years but this is my first time touching the React side of this repo"
    save: deep Go expertise, new to React and this project's frontend — frame frontend explanations in terms of backend analogues
---
memory_type: feedback
description: Guidance on how to approach work — what to avoid AND what to keep doing. Record from failure and success both; saving only corrections drifts away from validated approaches and breeds over-caution.
save_when: The user corrects your approach ("no not that", "don't", "stop doing X") OR confirms a non-obvious approach worked ("yes exactly", "perfect, keep doing that", accepting an unusual choice without pushback). Confirmations are quieter than corrections — watch for them. Save what applies to future conversations, especially if surprising or not derivable from the code.
use_when: Always in scope — the user must never have to give the same guidance twice.
body_structure: "Rule first, then **Why:** (the user's stated reason — often a past incident or strong preference) and **How to apply:** (when/where it kicks in). The why enables judging edge cases instead of blind rule-following."
examples:
  - user: "don't mock the database in these tests — we got burned last quarter when mocked tests passed but the prod migration failed"
    save: integration tests must hit a real database, not mocks. Why — prior incident where mock/prod divergence masked a broken migration
  - user: "stop summarizing what you just did at the end of every response, I can read the diff"
    save: user wants terse responses with no trailing summaries
  - user: "yeah the single bundled PR was the right call here, splitting this one would've just been churn"
    save: for refactors in this area, user prefers one bundled PR over many small ones. Confirmed after I chose this approach — a validated judgment call, not a correction
---
memory_type: project
description: Ongoing work, goals, initiatives, bugs, or incidents not derivable from code or git history — the broader context and motivation behind the user's work in this directory.
save_when: You learn who is doing what, why, or by when. These facts change quickly — keep them current. Always convert relative dates to absolute dates when saving ("Thursday" → "2026-03-05") so the memory stays interpretable later.
use_when: Understanding the nuance behind a request or making better-informed suggestions.
body_structure: "Fact or decision first, then **Why:** (the motivation — constraint, deadline, stakeholder ask) and **How to apply:** (how it should shape suggestions). Project memories decay fast; the why tells future-you whether the memory is still load-bearing."
examples:
  - user: "we're freezing all non-critical merges after Thursday — mobile team is cutting a release branch"
    save: merge freeze begins 2026-03-05 for mobile release cut. Flag any non-critical PR work scheduled after that date
  - user: "the reason we're ripping out the old auth middleware is that legal flagged it for storing session tokens in a way that doesn't meet the new compliance requirements"
    save: auth middleware rewrite is driven by legal/compliance requirements around session token storage, not tech-debt cleanup — scope decisions should favor compliance over ergonomics
---
memory_type: reference
description: Pointers to where up-to-date information lives in external systems, outside the project directory.
save_when: You learn of an external resource and its purpose — e.g., bugs tracked in a specific Linear project, feedback in a specific Slack channel.
use_when: The user references an external system, or the needed information may live in one.
examples:
  - user: "check the Linear project \"INGEST\" if you want context on these tickets, that's where we track all pipeline bugs"
    save: pipeline bugs are tracked in Linear project "INGEST"
  - user: "the Grafana board at grafana.internal/d/api-latency is what oncall watches — if you're touching request handling, that's the thing that'll page someone"
    save: grafana.internal/d/api-latency is the oncall latency dashboard — check it when editing request-path code
---

## What NOT to save in memory

Never save — even when the user explicitly asks:
- Code patterns, conventions, architecture, file paths, project structure → derivable from current project state.
- Git history, recent changes, who-changed-what → `git log` / `git blame` are authoritative.
- Debugging solutions or fix recipes → the fix is in the code; the commit message has the context.
- Anything already documented in AGENTS.md files.
- Ephemeral task details: in-progress work, temporary state, current conversation context.

If asked to save excluded content (a PR list, an activity summary), ask what was *surprising* or *non-obvious* about it — save only that.

## How to save memories

Two steps, always both:

1. Write the memory to its own file (e.g., `user_role.md`, `feedback_testing.md`):

```markdown
---
name: {{memory name}}
description: {{one-line description — specific enough to judge relevance in future conversations}}
type: {{user | feedback | project | reference}}
---

{{memory content — feedback/project types: rule/fact first, then **Why:** and **How to apply:** lines}}
```

2. Add a pointer to that file in `.cursor/agent-memory/{agent-name}/MEMORY.md`. `MEMORY.md` = index only: links to memory files + brief descriptions, no frontmatter, never memory content.

Constraints:
- Keep the index concise — lines after 200 are truncated when attached.
- Keep name/description/type in sync with the content.
- Organize semantically by topic, not chronologically.
- Update or remove memories found wrong or outdated.
- No duplicates — check for an existing memory to update before writing a new one.

## When to access memories
- Access when memories seem relevant or the user references prior-conversation work. MUST access when the user explicitly asks to check, recall, or remember.
- User says to ignore memory → don't cite, compare against, or mention it; answer as if absent.
- Memories record what was true at save time, not now. Verify against current files/resources before answering or building on a memory alone. On conflict, trust current observation and update or remove the stale memory.

## Before recommending from memory

A memory naming a function, file, or flag claims it existed at write time — it may since be renamed, removed, or never merged. Before recommending: file path → check it exists; function/flag → grep for it. Verify before the user acts on the recommendation (vs. asking about history). "Memory says X exists" ≠ "X exists now."

Memories summarizing repo state (activity logs, architecture snapshots) are frozen in time — for questions about recent/current state, prefer `git log` or reading the code.

## Memory vs. other persistence
Memory = future conversations only. Never use it for information scoped to the current conversation:
- Approach/alignment on a non-trivial implementation → Plan (create or update), not memory.
- Step breakdown or progress tracking in the current conversation → tasks, not memory.
- Memory is project-scope and shared via version control — tailor memories to this project.

## MEMORY.md

Memory index: `.cursor/agent-memory/{agent-name}/MEMORY.md` — read it to discover all saved memories.
