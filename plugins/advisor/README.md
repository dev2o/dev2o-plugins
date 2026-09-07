# Advisor

Strategic second opinions for Cursor agents without hooks, state tracking files, or background infrastructure.

Advisor pairs your working agent with a read-only `advisor-subagent` running a strong reasoning model. The main agent locates the native Cursor transcript, resolves the desired model, and spawns the advisor with the transcript path. The advisor analyzes the transcript and repository directly, then provides concrete, directive guidance.

## Installation

Link the plugin into your Cursor local plugins directory:

```bash
ln -s "$PWD/plugins/advisor" ~/.cursor/plugins/local/advisor
```

Then run **Developer: Reload Window** in Cursor.

## Usage

Invoke the advisor in any conversation via the `/advisor` skill:

```text
/advisor
/advisor --model grok
/advisor --model opus --message "Why is the test loop failing?"
/advisor --message "Can you take a second look at this migration?"
```

- `--model <name>`: Model alias or exact slug (defaults to `cursor-grok-4.6-xhigh`).
- `--message <text>`: Optional context, friction description, or focus question.

## Model Selection

Advisor maps user-specified model aliases to standard subagent model slugs:

| Input | Subagent Model Slug | Details |
|---|---|---|
| *(default)* / `grok` | `cursor-grok-4.6-xhigh` | Default strong reasoning model |
| `opus` | `claude-opus-5-thinking-high` | High-reasoning Claude |
| `fable` | `claude-fable-5-1-thinking-low` | Low-reasoning Claude Fable |
| `gemini` | `gemini-3.8-flash-high` | High-reasoning Gemini |
| *(exact slug)* | Exact slug | Any subagent model slug |

### Model Rules
- **Effort tier**: Defaults to the reasoning tiers listed above; never picks a higher effort tier unless explicitly requested.
- **No fast variants**: Never selects `-fast` variants unless explicitly requested.
- **Model probe**: If a model is not listed in `<available_subagent_models>`, the skill probes valid slugs by spawning a test subagent with an invalid slug (`deepseek-no-real`) to receive the error list of allowed models.

## Architecture

1. **Skill ([skills/advisor/SKILL.md](skills/advisor/SKILL.md))**:
   - Parses `--model` and `--message` parameters.
   - Discovers the native transcript path (local `agent-transcripts` directory in the IDE, or `batch-fetch-details` on Cloud Agents).
   - Spawns `advisor-subagent` with `Advise on the following <path to transcript>`.
2. **Agent ([agents/advisor-subagent.md](agents/advisor-subagent.md))**:
   - Read-only subagent.
   - Reads the transcript file as its first action.
   - Provides focused architectural direction, identifies missed constraints, or forces a pivot when stuck.

## License

MIT
