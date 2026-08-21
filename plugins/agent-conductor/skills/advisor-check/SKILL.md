---
name: advisor-check
description: "Proactively use this when you need a second opinion on workflow directions or course verification. Use when facing critical decisions, recurring errors, architectural pivots, or when user feedback signals friction (e.g., 'Go', 'I need it to...', 'That sucks', 'you are not'). Evaluates whether to escalate for strategic direction."
---

# Advisor check

Use in-thread to verify direction before proceeding or escalating.

## Checklist

| Gate | Condition | Action |
|---|---|---|
| **Simple / Boilerplate** | Typo, standard CRUD, mechanical task | Continue in-thread. |
| **Premature** | Context gathered but no implementation attempted | Attempt plan first. |
| **Legitimate Need** | Architecture fork, persistent failure, conflict, or high friction | Spawn `advisor` with `Advise. <id>`. |

## Escalation

When Legitimate Need applies, call Task with `subagent_type: "advisor"` and prompt `Advise. <id>` using `$CURSOR_CONVERSATION_ID` (or literal `Advise.` if unset). Never pass summaries or questions.
