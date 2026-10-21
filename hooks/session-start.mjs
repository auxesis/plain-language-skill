#!/usr/bin/env node
// SessionStart and SubagentStart hook: adds core.md, the always-on plain-language
// rules, to the context of every session and every subagent.
//
// A skill loads only when Claude decides a task needs it, so on its own it would not
// shape every chat reply. This hook puts the short rule set in front of every session;
// the skill keeps the full process for documents, rewrites and reviews.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readStdin } from "./shared.mjs";

const CORE = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "core.md");

let event = {};
try {
  event = JSON.parse((await readStdin()) || "{}");
} catch {
  // An unreadable event still gets the rules, as a SessionStart.
}

let core;
try {
  core = readFileSync(CORE, "utf8");
} catch {
  process.exit(0);
}

process.stdout.write(
  JSON.stringify({
    hookSpecificOutput: {
      hookEventName: event.hook_event_name === "SubagentStart" ? "SubagentStart" : "SessionStart",
      additionalContext: core,
    },
  }),
);
