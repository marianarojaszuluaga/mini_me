#!/usr/bin/env node
/**
 * Sync/verify the bundled agent prompt .md files against src/agents/agents.lock.json.
 *
 * Closes the gap flagged in the Basecamp/AI-hybrid-teams coupling audit: the
 * copies in src/agents/spec-kit-agents/ and src/agents/external-agents/ used
 * to rely on someone remembering to re-copy the file after editing it in the
 * canonical ia-hybrid-teams/agents/ repo. This script makes "is the copy
 * stale?" a computed answer (a sha256 hash comparison) instead of a memory.
 *
 * Modes:
 *   node scripts/sync-agents.js --check
 *     Verifies every .md file under the two bundled folders matches the hash
 *     recorded in agents.lock.json. Fails (exit 1) on any mismatch or on a
 *     .md file with no lock entry (edited/added without updating the lock).
 *     If SPEC_KIT_AGENTS_DIR or EXTERNAL_AGENTS_DIR point at an external
 *     ia-hybrid-teams checkout, also diffs the bundled copy against that
 *     source and fails if they've diverged.
 *
 *   node scripts/sync-agents.js
 *     Recomputes hashes for every .md file present and rewrites the lock
 *     file. If SPEC_KIT_AGENTS_DIR/EXTERNAL_AGENTS_DIR point outside the
 *     bundled folders, copies the source files in before hashing — this is
 *     the one command that replaces "copy the file over by hand".
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const ROOT = path.join(__dirname, "..");
const BUNDLED_SPEC_KIT_DIR = path.join(ROOT, "src", "agents", "spec-kit-agents");
const BUNDLED_EXTERNAL_DIR = path.join(ROOT, "src", "agents", "external-agents");
const LOCK_PATH = path.join(ROOT, "src", "agents", "agents.lock.json");

// Only treated as an external source to sync FROM if it's set and doesn't
// just point back at the bundled copy (the default in registry.js).
function externalSourceDir(envVar, bundledDir) {
  const value = process.env[envVar];
  if (!value) return null;
  const resolved = path.resolve(value);
  return resolved === path.resolve(bundledDir) ? null : resolved;
}

function sha256(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function listMdFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".md"))
    .sort();
}

function loadLock() {
  if (!fs.existsSync(LOCK_PATH)) return { agents: {} };
  return JSON.parse(fs.readFileSync(LOCK_PATH, "utf8"));
}

const GROUPS = [
  { key: "spec-kit-agents", bundledDir: BUNDLED_SPEC_KIT_DIR, sourceDir: externalSourceDir("SPEC_KIT_AGENTS_DIR", BUNDLED_SPEC_KIT_DIR) },
  { key: "external-agents", bundledDir: BUNDLED_EXTERNAL_DIR, sourceDir: externalSourceDir("EXTERNAL_AGENTS_DIR", BUNDLED_EXTERNAL_DIR) }
];

function runCheck() {
  const lock = loadLock();
  const problems = [];

  for (const group of GROUPS) {
    const lockEntries = lock.agents?.[group.key] || {};
    const bundledFiles = listMdFiles(group.bundledDir);

    for (const filename of bundledFiles) {
      const filePath = path.join(group.bundledDir, filename);
      const hash = sha256(filePath);
      const recorded = lockEntries[filename];
      if (!recorded) {
        problems.push(`[${group.key}] ${filename}: no lock entry — run "node scripts/sync-agents.js" to record it.`);
      } else if (recorded.sha256 !== hash) {
        problems.push(`[${group.key}] ${filename}: hash mismatch — edited locally without updating agents.lock.json.`);
      }
    }

    for (const filename of Object.keys(lockEntries)) {
      if (!bundledFiles.includes(filename)) {
        problems.push(`[${group.key}] ${filename}: in lock file but missing on disk.`);
      }
    }

    if (group.sourceDir) {
      const sourceFiles = listMdFiles(group.sourceDir);
      for (const filename of sourceFiles) {
        const sourcePath = path.join(group.sourceDir, filename);
        const bundledPath = path.join(group.bundledDir, filename);
        if (!fs.existsSync(bundledPath)) {
          problems.push(`[${group.key}] ${filename}: exists in ${group.sourceDir} but not bundled — run sync.`);
          continue;
        }
        if (sha256(sourcePath) !== sha256(bundledPath)) {
          problems.push(`[${group.key}] ${filename}: diverged from canonical source ${sourcePath} — run sync.`);
        }
      }
    }
  }

  if (problems.length > 0) {
    console.error("Agent prompt sync check FAILED:\n" + problems.map((p) => `  - ${p}`).join("\n"));
    process.exit(1);
  }
  console.log("Agent prompt sync check OK — all bundled .md files match agents.lock.json.");
}

function runSync() {
  const lock = { agents: {} };

  for (const group of GROUPS) {
    if (group.sourceDir) {
      for (const filename of listMdFiles(group.sourceDir)) {
        fs.copyFileSync(path.join(group.sourceDir, filename), path.join(group.bundledDir, filename));
      }
    }

    const entries = {};
    for (const filename of listMdFiles(group.bundledDir)) {
      entries[filename] = {
        sha256: sha256(path.join(group.bundledDir, filename)),
        syncedAt: new Date().toISOString(),
        sourcePath: group.sourceDir ? path.join(group.sourceDir, filename) : null
      };
    }
    lock.agents[group.key] = entries;
  }

  fs.writeFileSync(LOCK_PATH, JSON.stringify(lock, null, 2) + "\n");
  console.log(`Wrote ${LOCK_PATH}`);
}

if (require.main === module) {
  if (process.argv.includes("--check")) {
    runCheck();
  } else {
    runSync();
  }
}

module.exports = { runCheck, runSync };
