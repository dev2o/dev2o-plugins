## Parent conversation transcript

Parent conversation id: `{{CONVERSATION_ID}}`

The transcript is not injected. Review it with the transcripts CLI before advising:

```bash
.cursor/transcriptor/transcripts.py show {{CONVERSATION_ID}} --offset -20
```

Page backward with larger negative offsets (`--offset -40`, ...), widen with `--full`, or narrow with `--only user,assistant`. Run the CLI bare for usage.

If the id above reads `(conversation id unavailable)`, or the `show` command errors or returns no events: do NOT advise from guesses or the invocation prompt. Reply only: "Cannot advise — transcript context is unavailable (id: <what you saw>). Fix the transcript capture/injection before consulting me."
