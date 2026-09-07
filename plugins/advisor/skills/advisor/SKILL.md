---
name: advisor
description: "Use for /advisor, a second opinion, or 'ask the advisor'. Spawns a read-only advisor-subagent against the current transcript. Never enable unasked."
disable-model-invocation: true
---

# Advisor

Locate this conversation's transcript, spawn `advisor-subagent` on a pinned model, and follow its plan.

```text
/advisor [--model <model>] [--message <message>]
```

## Step 1. Parse

`--model` and `--message` are optional. Bare text after `/advisor` is `--message`. Omit `--message` when the user gave none.

## Step 2. Resolve the model

| Input | Slug |
|---|---|
| *(none)* / `grok` | `cursor-grok-4.6-xhigh` |
| `opus` | `claude-opus-5-thinking-high` |
| `fable` | `claude-fable-5-1-thinking-low` |
| `gemini` | `gemini-3.8-flash-high` |
| exact slug | use as given |

Never pick a higher effort than the row above, and never a `-fast` variant, unless the user asked for it.

If the slug is not in `<available_subagent_models>`, spawn `generalPurpose` with `model: deepseek-no-real` and a dummy prompt. The Task error lists valid slugs. Pick the same family at the listed effort and continue.

## Step 3. Locate the transcript

Use the system prompt's transcript instructions.

- **Local IDE:** `$CURSOR_CONVERSATION_ID` under the `<agent_transcripts>` folder. File is `<id>.jsonl` or `<id>/<id>.jsonl`. Confirm it exists.
- **Cloud:** MCP `batch-fetch-details` with `includeTranscripts: true`. Path is `{path}/transcript.json`.

No path: tell the user and stop. Do not summarize the conversation.

## Step 4. Spawn

Foreground Task:

- `subagent_type`: `advisor-subagent`
- `model`: the resolved slug
- `readonly`: `true`
- `run_in_background`: `false`
- `description`: `Advisor review`
- `prompt`:

```text
Advise on the following <transcript path>
<--message, or nothing>
```

Pass only that path and the user's `--message`. Never summarize the case.

If Task rejects the slug, read the valid slugs from the error, pick the same family at the listed effort, and spawn again.

## Step 5. Act

Treat the reply as directive unless code or a hard empirical failure contradicts it. Report in a few lines, then do the work. One follow-up at most.
