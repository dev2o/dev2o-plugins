#!/usr/bin/env node

// Claims in the docs that used to track agent-conductor hooks are gone with
// the plugin. What remains: links resolve, versions agree, logos and license exist.

import { readFileSync, existsSync, readdirSync, statSync } from "fs";
import { resolve, dirname, join, relative } from "path";
import { fileURLToPath } from "url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const read = (p) => readFileSync(resolve(root, p), "utf-8");
const readJSON = (p) => JSON.parse(read(p));

const skipDirs = new Set(["node_modules", ".git", ".cursor", "tmp"]);

function markdownFiles(dir = root, found = []) {
  for (const entry of readdirSync(dir)) {
    if (skipDirs.has(entry)) continue;
    const full = join(dir, entry);
    let stat;
    try {
      stat = statSync(full);
    } catch {
      continue;
    }
    if (stat.isDirectory()) markdownFiles(full, found);
    else if (entry.endsWith(".md")) found.push(relative(root, full));
  }
  return found;
}

const docs = markdownFiles();
const marketplace = readJSON(".cursor-plugin/marketplace.json");

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
    name: "one version across the manifests",
    run() {
      const versions = {
        "marketplace.json": marketplace.metadata.version,
        "package.json": readJSON("package.json").version,
      };
      for (const entry of marketplace.plugins ?? []) {
        const pluginJson = `${entry.source}/.cursor-plugin/plugin.json`;
        versions[pluginJson] = readJSON(pluginJson).version;
      }
      const distinct = new Set(Object.values(versions));
      return distinct.size === 1
        ? []
        : [`versions disagree: ${JSON.stringify(versions)}`];
    },
  },
  {
    name: "declared logos exist",
    run() {
      const failures = [];
      for (const entry of marketplace.plugins ?? []) {
        const manifest = readJSON(`${entry.source}/.cursor-plugin/plugin.json`);
        if (!manifest.logo) continue;
        if (!existsSync(resolve(root, entry.source, manifest.logo)))
          failures.push(
            `${entry.name} plugin.json points at a missing logo, ${manifest.logo}`
          );
      }
      return failures;
    },
  },
  {
    name: "the declared license is a license the repo actually ships",
    run() {
      if (!existsSync(resolve(root, "LICENSE")))
        return ["there is no LICENSE file"];
      const body = read("LICENSE");
      const failures = [];
      if (!body.startsWith("MIT License"))
        return ["LICENSE is not an MIT license"];
      if (readJSON("package.json").license !== "MIT")
        failures.push("package.json does not declare MIT");
      for (const entry of marketplace.plugins ?? []) {
        const declared = readJSON(
          `${entry.source}/.cursor-plugin/plugin.json`
        ).license;
        if (declared && declared !== "MIT")
          failures.push(`${entry.name} plugin.json declares ${declared}`);
      }
      return failures;
    },
  },
  {
    name: "agent-conductor marketplace entry is marked discontinued",
    run() {
      const entry = (marketplace.plugins ?? []).find(
        (p) => p.name === "agent-conductor"
      );
      if (!entry) return ["marketplace.json has no agent-conductor entry"];
      const manifest = readJSON(
        `${entry.source}/.cursor-plugin/plugin.json`
      );
      const failures = [];
      for (const [label, text] of [
        ["the marketplace entry", entry.description],
        ["the plugin manifest", manifest.description],
      ]) {
        if (!text) failures.push(`${label} has no description`);
        else if (!/discontinued/i.test(text))
          failures.push(`${label} does not say discontinued: "${text}"`);
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
