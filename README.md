# dev2o plugins

A Cursor plugin marketplace. One plugin lives here so far.

## Agent Conductor

**Standing instructions for one Cursor agent, not for all of them.**

A rule with `alwaysApply` and an `AGENTS.md` reach every agent in the workspace, the one you are chatting with and every subagent it spawns. So "delegate implementation to a subagent" reaches the subagents too, and they delegate instead of working.

Agent Conductor gives each role its own file. `__agent-main.md` goes to the agent you are talking to and nowhere else, re-read before every prompt you submit and never stored in the thread. `agent-explore.md` goes to `explore` subagents when they spawn. A role with no file gets nothing.

![How Agent Conductor routes context, compared with a broadcast rule](plugins/agent-conductor/docs/addressed-context.png)

It also ships an advisor subagent behind an in-thread gate, an orchestrator `MEMORY.md`, and its own scrubbed chat transcripts under `.cursor/chat-transcripts` with a CLI to read them. That capture is how the advisor reads a conversation on a Cloud Agent, where Cursor's own `transcript_path` is `null`.

Read [the plugin README](plugins/agent-conductor/README.md) for the quickstart and the configuration reference, and [Cloud Agents](plugins/agent-conductor/docs/cloud-agents.md) for the one extra step a cloud run needs.

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

`validate-docs.mjs` exists because the marketing has drifted from the code twice. It reads the paths, config filenames, character limits, and CLI subcommands the scripts actually resolve, then fails when a document names something else.
