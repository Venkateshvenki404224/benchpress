#!/usr/bin/env node
// Every .md link in a generated agent index must resolve to a generated file.
import { existsSync, readdirSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const TREES = ["docs-site", "docs-bundle"];
const LINKED_TEXT = new Set([".md", ".txt"]);
const MARKDOWN_LINK = /\]\(([^)\s]+\.md)\)/g;
const ABSOLUTE_URL = /^[a-z][a-z0-9+.-]*:/i;

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const child = path.join(dir, entry.name);
    return entry.isDirectory() ? walk(child) : [child];
  });
}

const dead = [];
let scanned = 0;

for (const tree of TREES) {
  const root = path.join(ROOT, tree);
  if (!existsSync(root)) {
    dead.push(`${tree}/ is not generated`);
    continue;
  }
  for (const file of walk(root)) {
    if (!LINKED_TEXT.has(path.extname(file))) {
      continue;
    }
    scanned += 1;
    const text = await readFile(file, "utf8");
    for (const [, target] of text.matchAll(MARKDOWN_LINK)) {
      if (ABSOLUTE_URL.test(target)) {
        continue;
      }
      const resolved = target.startsWith("/")
        ? path.join(root, target)
        : path.resolve(path.dirname(file), target);
      if (!existsSync(resolved)) {
        dead.push(`${path.relative(ROOT, file)} -> ${target}`);
      }
    }
  }
}

if (dead.length > 0) {
  console.error(`${dead.length} dead link(s) in the generated docs:`);
  for (const line of dead) {
    console.error(`  ${line}`);
  }
  console.error("Run: npm run docs:build");
  process.exit(1);
}

console.log(`${scanned} generated files scanned, every .md link resolves.`);
