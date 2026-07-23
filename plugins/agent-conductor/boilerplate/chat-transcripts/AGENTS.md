# Chat transcripts (hook capture)

Scrubbed hook events are stored here as `{conversation_id}.jsonl` (`conversation_id` is the filename stem, e.g. `bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de` or a plain UUID). These files can be large and may contain sensitive workflow detail.

**Do not read `.jsonl` files in this folder directly.** They are consumed through the transcripts CLI, not by hand:

- Capture is performed automatically by the plugin's transcript hook.
- Browsing/searching transcripts is the job of the **advisor** subagent, which runs `.cursor/chat-transcripts/_transcripts.py`. Launch the advisor rather than trying to parse these files yourself.

`_transcripts.py` is synced from the plugin on session start. Do not edit it.
