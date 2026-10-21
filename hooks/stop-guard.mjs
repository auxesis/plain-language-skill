#!/usr/bin/env node
// Stop hook: checks what Claude wrote in the chat this turn against the plain-language
// rules, and sends it back for a rewrite when a rule that must be fixed is broken.
//
// It checks the reply Claude Code passes in last_assistant_message, plus any earlier
// text Claude wrote in the same turn, which it reads from the transcript. The
// transcript alone is not enough: when the hook runs, the final reply has often not
// been written to the file yet, so a hook that reads only the transcript misses it.
// That was measured on 21 October 2026 with Claude Code 2.1.306. Text inside code
// blocks, inline code and double quotation marks is not checked (see scripts/prose.mjs).
//
// Input is the Stop hook's JSON on stdin:
// { transcript_path, last_assistant_message, stop_hook_active }.
// Output is nothing, which lets the turn end, or {"decision":"block","reason":...},
// which gives the reason back to Claude to act on.
//
// When the hook has already sent this turn back once, stop_hook_active is true and the
// hook lets the turn end. Sending it back a second time could loop for ever.
import { findings, format, loadRules } from "../scripts/check.mjs";
import { readStdin, reasonFor } from "./shared.mjs";
import { tail, turnText } from "./transcript.mjs";

const input = JSON.parse((await readStdin()) || "{}");
if (input.stop_hook_active) process.exit(0);

function earlierText(transcriptPath) {
  try {
    return transcriptPath ? turnText(tail(transcriptPath)) : "";
  } catch {
    // A missing or unreadable transcript is not a language problem.
    return "";
  }
}

const last = typeof input.last_assistant_message === "string" ? input.last_assistant_message.trim() : "";
const earlier = earlierText(input.transcript_path);
const text = last && !earlier.includes(last) ? [earlier, last].filter(Boolean).join("\n\n") : earlier;
if (!text) process.exit(0);

let found = [];
try {
  found = findings(text, loadRules(), { mode: "chat" }).filter((one) => one.severity === "block");
} catch {
  // A broken guard must not stop the work.
  process.exit(0);
}
if (found.length === 0) process.exit(0);

process.stdout.write(
  JSON.stringify({
    decision: "block",
    reason: reasonFor(
      "Your reply breaks the plain-language rules (ISO 24495-1). Write the reply again with these sentences fixed. Do not apologise, and do not explain the rule. Write the corrected reply as if it were the first.",
      found.map((one) => format(null, one)),
    ),
  }),
);
