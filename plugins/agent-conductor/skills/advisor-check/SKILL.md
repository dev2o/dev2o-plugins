---
name: advisor-check
description: "Quick checklist before spawning the advisor subagent. Run in-thread when stuck, facing recurring errors, designing complex logic, or resolving a conflict with prior advice. Same gates as /advisor."
---

# Advisor check

Run this skill **in the main thread** before spawning the `advisor` subagent. You already have the live conversation in context; do not read transcripts for this step.

## When to run

- You are about to spawn `advisor` (including after logging a conflict with prior advice).
- The user invoked `/advisor` or asked for strategic guidance.
- You hit a stubborn error loop or a non-converging approach.

## Checklist

Answer each item from what you already know in this thread.

| # | Gate | Spawn advisor? |
|---|------|----------------|
| 1 | **Too simple** — typo fix, boilerplate, simple CRUD, or baseline intelligence is enough | **No** — continue yourself |
| 2 | **Premature** — you gathered context but have not attempted implementation or established a baseline | **No** — formulate a plan, start work, retry only if stuck |
| 3 | **Legitimate need** — complex architecture, stubborn error loop, conflicting requirements, or massive refactor | **Yes** — spawn advisor |

## If gate 1 or 2 applies

Do **not** spawn `advisor`. Reply to yourself (or the user) with:

- **Gate 1:** The request is straightforward. Continue execution. Re-run this skill only if scope grows materially.
- **Gate 2:** Context is gathered but no implementation attempt yet. Start execution first; re-run this skill only if you get stuck.

## If gate 3 applies

Spawn the advisor:

1. `subagent_type`: `advisor`
2. `prompt`: `Advise. <id>` where `<id>` is your conversation id from `$CURSOR_CONVERSATION_ID`. If that variable is empty, use the literal string `Advise.` (the hook stamps the id when it runs).
3. Never pass questions, summaries, or user quotes in the prompt.
4. Treat the advisor's return as strictly directive unless hard evidence contradicts it.

## Conflict tie-break

If codebase evidence conflicts with prior advisor guidance, log the conflict in your turn (e.g. "Conflict: Advisor suggested X, but file shows Y"), re-run this skill, then spawn advisor when gate 3 applies.
