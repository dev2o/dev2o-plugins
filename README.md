# Agent Conductor

**Give your main agent a standing prompt that goes to it and no other agent.**

Cursor has two places for instructions that apply on every turn, an `AGENTS.md` and an always-on rule. Both are broadcasts. Put "delegate all implementation to a subagent, never write code in this thread" in either one and the agent you are talking to obeys it. So does every subagent it spawns. Your workers delegate instead of working, and nothing gets built.

Agent Conductor addresses each instruction to one role. The agent you are chatting with reads `__agent-main.md`, and nothing else does. Add `agent-explore.md` and `explore` subagents read that one when they spawn. A role you never write a file for is sent nothing at all.

![A broadcast rule reaches every agent, so the workers delegate too. Agent Conductor addresses one file per role, so the workers work.](plugins/agent-conductor/docs/addressed-context.png)

Read [the plugin README](plugins/agent-conductor/README.md) for the quickstart and the configuration reference. The same routing runs in the Cursor IDE and on Cloud Agents, which need [one extra step](plugins/agent-conductor/docs/cloud-agents.md).

### The same prompt on every turn, without filling the thread

The main agent's copy is read from disk before every prompt you submit and handed over as hook context rather than as a message. Instructions pasted into a chat stay in it, so rewording them leaves the old copies behind to argue with the new ones. This way there is only ever the current one. Edit the file mid-conversation and your next prompt uses the new text.

### The specialist is the boss, the orchestrator only routes

Addressing the main agent alone is also what lets you tell it to stay out of its specialists' way. The bundled `__agent-main.md` overrides Cursor's own advice to write a detailed brief for each subagent, and has the main agent pass your words through verbatim instead. A brief is a paraphrase, and a paraphrase carries the orchestrator's guess at the answer, which your specialist then follows instead of its own instructions. That is another thing you cannot write as a broadcast. [The plugin README explains it](plugins/agent-conductor/README.md#the-specialist-is-the-boss-the-orchestrator-only-routes).

### What else is in the box

Three pieces that came out of running that routing on real work. A read-only `advisor` subagent behind an in-thread gate, so an agent with a second opinion on tap cannot spam it. An orchestrator `MEMORY.md`. And the plugin's own scrubbed transcripts under `.cursor/chat-transcripts`, with a CLI to read them, which is what lets the advisor read a conversation on a Cloud Agent where Cursor's own `transcript_path` is `null`.

## Install

The plugin needs `jq` and `python3` on `PATH`.

Clone this repository and link the plugin into Cursor's local plugin directory, then run **Developer: Reload Window**.

```bash
git clone https://github.com/dev2o/dev2o-plugins.git
ln -s "$PWD/dev2o-plugins/plugins/agent-conductor" ~/.cursor/plugins/local/agent-conductor
```

For a team, this repository doubles as a Cursor plugin marketplace. Open **Dashboard -> Plugins**, click **Add Marketplace**, choose **Import from Repo**, and give it this repository's URL. Teammates install Agent Conductor from **Customize** after that.

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
