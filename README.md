# dev2o-plugins

Cursor plugins for people who run more than one agent at a time.

This repository is a Cursor plugin marketplace. Open **Dashboard → Plugins**, click **Add Marketplace**, choose **Import from Repo**, and give it this repository's URL.

## Plugins

- **[advisor](plugins/advisor)** — Strategic second opinions using native Cursor transcripts. Pinned models, no hooks.
- **[agent-memory](plugins/agent-memory)** — Persistent file-based memory for workflow subagents without hooks or complex injection.
- **[env-protect](plugins/env-protect)** — Denies `env`, `printenv`, `export -p`, reads of `.env` files, and `op` secret reads printed to the terminal in agent shell commands.

**Agent Conductor is discontinued.** Routing, memory, transcripts, and secret deny used to ship as one plugin. Those jobs now live in the plugins above. The leftover [agent-conductor](plugins/agent-conductor) entry ships `/agent-conductor-discontinued`, which asks before cleaning the old cloud hook shim and `.cursor/chat-transcripts/`.

## Working on the plugins

```bash
npm install
npm run validate
```

## License

MIT. See [LICENSE](LICENSE).
