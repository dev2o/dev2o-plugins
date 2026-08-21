#!/usr/bin/env node

// The marketing has drifted from the hooks twice. These checks read the paths,
// filenames and limits the scripts actually resolve, then fail when a document
// names something else.

import { readFileSync, existsSync, readdirSync, statSync } from "fs";
import { resolve, dirname, join, relative } from "path";
import { fileURLToPath } from "url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const plugin = "plugins/agent-conductor";

const read = (p) => readFileSync(resolve(root, p), "utf-8");
const readJSON = (p) => JSON.parse(read(p));

function markdownFiles(dir = root, found = []) {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".git") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) markdownFiles(full, found);
    else if (entry.endsWith(".md")) found.push(relative(root, full));
  }
  return found;
}

const docs = markdownFiles();
const pluginReadme = read(`${plugin}/README.md`);
const cloudDoc = read(`${plugin}/docs/cloud-agents.md`);
const rootReadme = read("README.md");
const contextLib = read(`${plugin}/hooks/context-injector/lib/context.sh`);
const injectHook = read(
  `${plugin}/hooks/context-injector/main-agent-orchestrator-inject.sh`
);
const auditHook = read(`${plugin}/hooks/transcriptor/audit.sh`);
const denyHook = read(`${plugin}/hooks/transcriptor/shell-secrets-deny.sh`);
const transcriptsCli = read(`${plugin}/hooks/transcriptor/transcripts.py`);

function capture(source, pattern, label) {
  const match = source.match(pattern);
  if (!match) throw new Error(`cannot read ${label} from the source`);
  return match[1];
}

const checks = [
  {
    name: "relative links and images resolve",
    run() {
      const failures = [];
      for (const doc of docs) {
        const body = read(doc);
        for (const [, target] of body.matchAll(/]\(([^)\s]+)\)/g)) {
          if (/^(https?:|mailto:|#)/.test(target)) continue;
          if (/[<$]/.test(target)) continue;
          const path = resolve(root, dirname(doc), target.split("#")[0]);
          if (!existsSync(path)) failures.push(`${doc} links to ${target}`);
        }
      }
      return failures;
    },
  },
  {
    name: "docs name the config directory the hooks resolve",
    run() {
      const dir = capture(
        contextLib,
        /PROJECT_CONFIG_DIR="[^"]*?(\.cursor\/[a-z0-9-]+\/config)"/,
        "the project config directory"
      );
      const failures = [];
      if (!pluginReadme.includes(dir))
        failures.push(`the plugin README never names ${dir}`);
      for (const doc of docs) {
        for (const [wrong] of read(doc).matchAll(
          /\.cursor\/[a-z0-9-]+\/config/g
        )) {
          if (wrong !== dir) failures.push(`${doc} names ${wrong}, not ${dir}`);
        }
      }
      return failures;
    },
  },
  {
    name: "docs name the config filenames the hooks read",
    run() {
      const main = capture(
        contextLib,
        /config_file "(__agent-[a-z]+\.md)"/,
        "the main agent config filename"
      );
      const prefix = capture(
        contextLib,
        /config_file "(agent-)\$\{1\}\.md"/,
        "the subagent config prefix"
      );
      const failures = [];
      if (!pluginReadme.includes(main))
        failures.push(`the plugin README never names ${main}`);
      if (!rootReadme.includes(main))
        failures.push(`the root README never names ${main}`);
      if (!pluginReadme.includes(`${prefix}{subagent_type}.md`))
        failures.push(
          `the plugin README never shows ${prefix}{subagent_type}.md`
        );
      return failures;
    },
  },
  {
    name: "docs name the substitution tokens the library defines",
    run() {
      const failures = [];
      for (const [, token] of contextLib.matchAll(
        /^[A-Z_]+_TOKEN='(\{\{[A-Z_]+\}\})'/gm
      )) {
        if (!pluginReadme.includes(token))
          failures.push(`the plugin README never names ${token}`);
      }
      return failures;
    },
  },
  {
    name: "the documented inject cap matches the hook",
    run() {
      const cap = capture(
        injectHook,
        /MAX_INJECT_CHARS=(\d+)/,
        "the inject character cap"
      );
      return pluginReadme.includes(cap)
        ? []
        : [`the plugin README never states the ${cap} character cap`];
    },
  },
  {
    name: "the documented transcript directory matches the capture hook",
    run() {
      const dir = capture(
        auditHook,
        /LOG_DIR="\$CURSOR_PROJECT_DIR\/(\.cursor\/[a-z-]+)"/,
        "the transcript directory"
      );
      const failures = [];
      if (!pluginReadme.includes(dir))
        failures.push(`the plugin README never names ${dir}`);
      if (!rootReadme.includes(dir))
        failures.push(`the root README never names ${dir}`);
      return failures;
    },
  },
  {
    name: "every CLI subcommand the README shows exists",
    run() {
      const real = new Set(
        [...transcriptsCli.matchAll(/sub\.add_parser\("([a-z]+)"/g)].map(
          (m) => m[1]
        )
      );
      const failures = [];
      for (const [, named] of pluginReadme.matchAll(
        /_transcripts\.py ([a-z]+)/g
      )) {
        if (!real.has(named))
          failures.push(`the plugin README shows an unknown subcommand ${named}`);
      }
      for (const command of ["list", "show", "search", "brief"]) {
        if (!real.has(command))
          failures.push(`the CLI no longer has a ${command} subcommand`);
      }
      return failures;
    },
  },
  {
    name: "the documented blocked commands are the blocked commands",
    run() {
      const failures = [];
      for (const command of ["printenv", "export -p", "env"]) {
        if (!denyHook.includes(command))
          failures.push(`the deny hook no longer blocks ${command}`);
        if (!pluginReadme.includes(command))
          failures.push(`the plugin README never names ${command}`);
      }
      return failures;
    },
  },
  {
    name: "cloud/hooks.json mirrors the plugin's events minus sessionStart",
    run() {
      const own = Object.keys(readJSON(`${plugin}/hooks/hooks.json`).hooks);
      const cloud = Object.keys(readJSON(`${plugin}/cloud/hooks.json`).hooks);
      const expected = own.filter((event) => event !== "sessionStart");
      const failures = [];
      for (const event of expected) {
        if (!cloud.includes(event))
          failures.push(`cloud/hooks.json is missing ${event}`);
      }
      for (const event of cloud) {
        if (!expected.includes(event))
          failures.push(`cloud/hooks.json registers unknown event ${event}`);
      }
      if (!cloudDoc.includes("sessionStart"))
        failures.push("the cloud doc never mentions sessionStart");
      return failures;
    },
  },
  {
    name: "one version across the manifests",
    run() {
      const versions = {
        "plugin.json": readJSON(`${plugin}/.cursor-plugin/plugin.json`).version,
        "marketplace.json": readJSON(".cursor-plugin/marketplace.json").metadata
          .version,
        "package.json": readJSON("package.json").version,
      };
      const distinct = new Set(Object.values(versions));
      return distinct.size === 1
        ? []
        : [`versions disagree: ${JSON.stringify(versions)}`];
    },
  },
  {
    name: "the marketplace entry and the plugin manifest describe the same thing",
    run() {
      const entry = readJSON(".cursor-plugin/marketplace.json").plugins[0];
      const manifest = readJSON(`${plugin}/.cursor-plugin/plugin.json`);
      const failures = [];
      for (const [label, text] of [
        ["the marketplace entry", entry.description],
        ["the plugin manifest", manifest.description],
      ]) {
        if (!text) failures.push(`${label} has no description`);
        else if (!/instruction/i.test(text))
          failures.push(
            `${label} does not lead with what the plugin routes: "${text}"`
          );
      }
      return failures;
    },
  },
];

let failed = 0;
for (const check of checks) {
  let failures;
  try {
    failures = check.run();
  } catch (error) {
    failures = [error.message];
  }
  if (failures.length === 0) {
    console.log(`ok    ${check.name}`);
    continue;
  }
  failed += failures.length;
  console.error(`FAIL  ${check.name}`);
  for (const failure of failures) console.error(`        ${failure}`);
}

if (failed > 0) {
  console.error(`\n${failed} documentation claim(s) do not match the code.`);
  process.exit(1);
}
console.log("\nDocumentation matches the code.");
