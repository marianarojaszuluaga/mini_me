/**
 * Storage abstraction: filesystem locally, Redis (Upstash, via Vercel
 * Marketplace) in serverless.
 *
 * Local dev / self-hosted (Railway, Render, EC2, ...): STORAGE_DIR is a real,
 * persistent disk — plain JSON files work fine, no Redis needed.
 *
 * Vercel serverless: there is no persistent disk across invocations. If Redis
 * REST credentials are present, reads/writes go there instead. Without them,
 * this still "works" per-request but state will NOT survive between
 * invocations — see README's Vercel deploy section before relying on this in
 * production. `@vercel/kv` is deprecated (Vercel's own npm warning on
 * install); this uses `@upstash/redis` directly, the package Vercel's Redis
 * Marketplace integration is actually built on.
 */

const fs = require("fs");
const path = require("path");

const STORAGE_DIR = process.env.STORAGE_DIR || path.join(__dirname, "..", "storage");

// Vercel's Redis Marketplace integration has used different env var prefixes
// depending on when/how it was added (KV_* for the old native product, now
// UPSTASH_REDIS_* for the Marketplace integration) — accept either.
const REDIS_URL = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
const REDIS_TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
const usingKV = !!(REDIS_URL && REDIS_TOKEN);

let redis = null;
if (usingKV) {
  // Lazy-required: local/file-mode deployments never need this package to exist.
  const { Redis } = require("@upstash/redis");
  redis = new Redis({ url: REDIS_URL, token: REDIS_TOKEN });
} else if (!fs.existsSync(STORAGE_DIR)) {
  fs.mkdirSync(STORAGE_DIR, { recursive: true });
}

function filePath(name) {
  return path.join(STORAGE_DIR, `${name}.json`);
}

async function readList(name) {
  if (usingKV) {
    const value = await redis.get(name);
    return value || [];
  }
  const file = filePath(name);
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

async function writeList(name, value) {
  if (usingKV) {
    await redis.set(name, value);
    return;
  }
  fs.writeFileSync(filePath(name), JSON.stringify(value, null, 2));
}

async function appendLog(name, entry) {
  const logs = await readList(name);
  logs.push(entry);
  await writeList(name, logs);
}

module.exports = {
  usingKV,
  readProjects: () => readList("projects"),
  writeProjects: (projects) => writeList("projects", projects),
  readWorkflows: () => readList("workflows"),
  writeWorkflows: (workflows) => writeList("workflows", workflows),
  logActivity: (entry) => appendLog("activity-log", entry),
  logToolInvocation: (entry) => appendLog("orchestrator-log", entry)
};
