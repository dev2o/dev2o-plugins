# dev2o plugins

Cursor plugins from dev2o.

## Plugins

| Plugin | What it does |
|---|---|
| [agent-conductor](plugins/agent-conductor) | Gives Cursor's main agent persistent memory, an on-call advisor for hard decisions, and a searchable transcript of every session. |

## Install

Open Cursor's plugin marketplace, search for the plugin name, and install it into your project or team. Each plugin's own README covers setup, configuration, and cloud agent support.

## Repository layout

- `plugins/<name>/` holds one plugin: its `.cursor-plugin/plugin.json` manifest, agents, skills, and hooks.
- `.cursor-plugin/marketplace.json` lists every plugin this repository publishes.
- `schemas/` holds the JSON schemas that validate `plugin.json` and `marketplace.json`.
- `scripts/validate-plugins.mjs` checks every plugin against those schemas.

## Contributing

Run the validator before opening a pull request:

```bash
node scripts/validate-plugins.mjs
```

Each plugin also ships its own test suite. For agent-conductor:

```bash
cd plugins/agent-conductor/hooks/transcriptor/tests
python3 -m pytest
```
