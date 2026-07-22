# Chat transcripts (hook capture)

Scrubbed hook events are stored as `.cursor/chat-transcripts/{conversation_id}.jsonl`. These files can be large and may contain sensitive workflow detail.

**Agents must not read `.jsonl` files directly.** Use the browse CLI — start with a bare invocation, the tool explains itself from there:

```bash
.cursor/transcriptor/transcripts.py
```

The script is directly executable (uv shebang). Common commands:

```bash
.cursor/transcriptor/transcripts.py list
.cursor/transcriptor/transcripts.py show <conversation_id>            # short bodies, first 20 events
.cursor/transcriptor/transcripts.py show <conversation_id> --only user,assistant --offset 20 --full
.cursor/transcriptor/transcripts.py search "your keywords"
```

`conversation_id` is the filename stem (for example `bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de` or a plain UUID).

Capture is handled by `.cursor/transcriptor/audit.sh` (registered in `.cursor/hooks.json`). Legacy raw logs may remain under `raw/` until removed manually.
