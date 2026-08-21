# dev2o plugins

Cursor plugins for people who run more than one agent at a time.

## Agent Conductor

**Give your main agent a standing prompt your subagents never see.**

Cursor has two places for instructions that apply on every turn, an `AGENTS.md` and an always-on rule. Both are broadcasts. Put "delegate all implementation to a subagent, never write code in this thread" in either one and the agent you are talking to obeys it. So does every subagent it spawns. Your workers delegate instead of working, and nothing gets built.

Agent Conductor addresses each instruction to one role. `__agent-main.md` reaches the agent you are chatting with and nothing else. `agent-explore.md` reaches `explore` subagents when they spawn. A role with no file gets nothing.

![A broadcast rule reaches every agent, so the workers delegate too. Agent Conductor addresses one file per role, so the workers work.](plugins/agent-conductor/docs/addressed-context.png)

The main agent's copy is read from disk before every prompt you submit and handed over as hook context rather than as a message. It never piles up in the thread, so an agent six turns into a conversation is reading exactly one copy. Edit the file mid-conversation and the next turn uses the new text.

The same routing runs in the Cursor IDE and on Cloud Agents.

Read [the plugin README](plugins/agent-conductor/README.md) for the quickstart and the configuration reference, and [Cloud Agents](plugins/agent-conductor/docs/cloud-agents.md) for the one extra step a cloud run needs.

### What else is in the box

Three pieces that came out of running that routing on real work. A read-only `advisor` subagent behind an in-thread gate, so an agent with a second opinion on tap cannot spam it. An orchestrator `MEMORY.md`. And the plugin's own scrubbed transcripts under `.cursor/chat-transcripts`, with a CLI to read them, which is what lets the advisor read a conversation on a Cloud Agent where Cursor's own `transcript_path` is `null`.

## Install

Clone the repo and link the plugin into Cursor's local plugin directory, then run **Developer: Reload Window**.

```bash
git clone https://github.com/dev2o/dev2o-plugins.git
ln -s "$PWD/dev2o-plugins/plugins/agent-conductor" ~/.cursor/plugins/local/agent-conductor
```

For a team, open **Dashboard -> Plugins**, click **Add Marketplace**, choose **Import from Repo**, and give it this repository's URL. Teammates install from **Customize** after that.

## Working on the plugins

```bash
npm install                          # ajv, for the manifest validator
npm run validate                     # manifests against the schemas, docs against the code
scripts/render-diagrams.sh           # rebuild the diagram PNGs from their SVG sources
cd plugins/agent-conductor && python3 -m pytest
```

`validate-docs.mjs` exists because the marketing has drifted from the code twice. It reads the paths, config filenames, character limits, and CLI subcommands the scripts actually resolve, then fails when a document names something else. It also fails when either README introduces the advisor, the memory index, or the transcripts before it names the routing, which is the drift that happened both times.

## License

MIT. See [LICENSE](LICENSE).
