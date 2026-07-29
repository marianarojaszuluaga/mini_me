/**
 * Real API-key authentication.
 *
 * Replaces the placebo check from the original prototype (any token >10 chars,
 * or the literal string "test-key", was accepted). APP_API_KEYS is a
 * comma-separated allowlist of keys this service issues to its own clients
 * (dashboard, CLI, CI). It is NOT the Anthropic key — that stays server-side
 * only, read from ANTHROPIC_API_KEY, and is never sent to or accepted from a
 * client.
 */

const crypto = require("crypto");

function timingSafeEqual(a, b) {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

function loadAllowedKeys() {
  const raw = process.env.APP_API_KEYS || "";
  return raw
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);
}

function authenticateToken(req, res, next) {
  const allowedKeys = loadAllowedKeys();

  if (allowedKeys.length === 0) {
    console.error(
      "APP_API_KEYS is not set — refusing all requests. Configure at least one key in .env."
    );
    return res.status(500).json({ error: "Server misconfigured: no API keys configured" });
  }

  const authHeader = req.headers["authorization"];
  const token = authHeader && authHeader.split(" ")[1];

  if (!token) {
    return res.status(401).json({ error: "No token provided" });
  }

  const isValid = allowedKeys.some((key) => timingSafeEqual(token, key));
  if (!isValid) {
    return res.status(403).json({ error: "Invalid token" });
  }

  req.token = token;
  next();
}

module.exports = { authenticateToken };
