#!/usr/bin/env node
// PostToolUse hook: checks prose Claude has just written into a file against the
// plain-language rules, and asks for a rewrite when a rule that must be fixed is broken.
//
// It checks only what this tool call wrote. For Write, that is the whole file. For Edit
// and MultiEdit, it is each paragraph the new text touches, so an edit to one line of
// an old document is not held up by problems in the lines around it.
//
// Prose files are Markdown and plain text. A file with "plain-language-check: off" on a
// line of its own, or in an HTML comment on a line of its own, is skipped. That is how a
// file that discusses the banned phrases opts out. The marker inside a sentence does not
// count, so a README that tells you how to use it is still checked. A line containing
// "plain-language-allow" is skipped too.
import { readFileSync } from "node:fs";
import path from "node:path";
import { findings, format, loadRules } from "../scripts/check.mjs";
import { readStdin, reasonFor } from "./shared.mjs";

const PROSE = new Set([".md", ".mdx", ".markdown", ".txt", ".rst", ".adoc"]);
const SKIPPED_DIRECTORIES = /[\\/](?:node_modules|\.git|vendor|dist|build)[\\/]/;
const CHECK_OFF = /^\s*(?:<!--\s*)?plain-language-check:\s*off\s*(?:-->)?\s*$/m;

// The line ranges in `file` that hold each piece of new text.
function changedRanges(file, newTexts) {
  const ranges = [];
  for (const text of newTexts) {
    if (!text?.trim()) continue;
    let from = 0;
    let at;
    while ((at = file.indexOf(text, from)) !== -1) {
      const first = file.slice(0, at).split("\n").length;
      const last = first + text.split("\n").length - 1;
      ranges.push([first, last]);
      from = at + text.length;
    }
  }
  return ranges;
}

const event = JSON.parse((await readStdin()) || "{}");
const tool = event.tool_name;
const target = event.tool_input?.file_path;
if (!["Write", "Edit", "MultiEdit"].includes(tool) || typeof target !== "string") process.exit(0);
if (!PROSE.has(path.extname(target).toLowerCase()) || SKIPPED_DIRECTORIES.test(target)) process.exit(0);

let found = [];
try {
  const file = readFileSync(target, "utf8");
  if (CHECK_OFF.test(file)) process.exit(0);
  const all = findings(file, loadRules(), { mode: "file" }).filter((one) => one.severity === "block");
  if (tool === "Write") {
    found = all;
  } else {
    const newTexts =
      tool === "Edit" ? [event.tool_input.new_string] : (event.tool_input.edits ?? []).map((edit) => edit.new_string);
    const ranges = changedRanges(file, newTexts);
    found = all.filter((one) => ranges.some(([first, last]) => one.span[0] <= last && one.span[1] >= first));
  }
} catch {
  // A broken guard must not stop the work.
  process.exit(0);
}
if (found.length === 0) process.exit(0);

process.stdout.write(
  JSON.stringify({
    decision: "block",
    reason: reasonFor(
      `The prose just written to ${target} breaks the plain-language rules (ISO 24495-1). Fix these lines in the file now. Do not explain the rule.`,
      found.map((one) => format(path.basename(target), one)),
    ),
  }),
);
