// Creates .env from .env.example and fills the secrets that are still blank
// with random values. Safe to run twice: existing values are never replaced.
//
//   node scripts/init-env.mjs

import { randomBytes } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const examplePath = join(root, ".env.example");
const envPath = join(root, ".env");

// name -> number of random bytes (hex doubles the length)
const GENERATED = {
  NEXUS_DB_PASSWORD: 16,
  CHATWOOT_SECRET_KEY_BASE: 64,
  CHATWOOT_POSTGRES_PASSWORD: 16,
  CHATWOOT_REDIS_PASSWORD: 16,
};

const source = existsSync(envPath) ? envPath : examplePath;
const filled = [];

const lines = readFileSync(source, "utf8")
  .split(/\r?\n/)
  .map((line) => {
    const match = /^([A-Z0-9_]+)=(.*)$/.exec(line);
    if (!match) return line;
    const [, name, value] = match;
    if (name in GENERATED && value.trim() === "") {
      filled.push(name);
      return `${name}=${randomBytes(GENERATED[name]).toString("hex")}`;
    }
    return line;
  });

writeFileSync(envPath, lines.join("\n"));

console.log(existsSync(envPath) && source === envPath ? "Updated .env" : "Created .env from .env.example");
console.log(filled.length ? `Generated: ${filled.join(", ")}` : "No blank secrets to generate.");
console.log("Still to fill in during the lesson: CHATWOOT_API_TOKEN, CHATWOOT_WEBHOOK_SECRET, CHATWOOT_INBOX_IDENTIFIER");
