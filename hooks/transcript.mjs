// Reads the text Claude wrote in the current turn out of a Claude Code transcript.
import { closeSync, fstatSync, openSync, readSync } from "node:fs";

// A long session's transcript runs to tens of megabytes, and the turn is at the end.
const TAIL_BYTES = 4 * 1024 * 1024;

export function tail(file) {
  const fd = openSync(file, "r");
  try {
    const size = fstatSync(fd).size;
    const length = Math.min(size, TAIL_BYTES);
    const buffer = Buffer.alloc(length);
    readSync(fd, buffer, 0, length, size - length);
    const text = buffer.toString("utf8");
    return length < size ? text.slice(text.indexOf("\n") + 1) : text;
  } finally {
    closeSync(fd);
  }
}

// A user entry with text in it starts a turn. Tool results are user entries too, and do
// not start one. Text the harness adds is marked isMeta, and most of it, such as a
// skill's text, arrives in the middle of a turn. Two kinds of it start a turn: a
// message from another agent, which has turnOrigin and origin, and Stop hook feedback.
// Checked against transcripts from Claude Code 2.1.306 on 22 October 2026.
function startsTurn(entry) {
  if (entry?.type !== "user" || entry.isSidechain) return false;
  const content = entry.message?.content;
  const text =
    typeof content === "string"
      ? content
      : Array.isArray(content)
        ? content.find((block) => block?.type === "text")?.text
        : undefined;
  if (typeof text !== "string") return false;
  if (!entry.isMeta) return true;
  if (entry.turnCompanion || entry.sourceToolUseID) return false;
  return Boolean(entry.turnOrigin || entry.origin) || text.startsWith("Stop hook feedback:");
}

// Every text block Claude wrote since the turn started, in order.
export function turnText(transcript) {
  const lines = transcript.split("\n").filter(Boolean);
  const parts = [];
  for (let i = lines.length - 1; i >= 0; i--) {
    let entry;
    try {
      entry = JSON.parse(lines[i]);
    } catch {
      continue;
    }
    if (startsTurn(entry)) break;
    if (entry?.type !== "assistant" || entry.isSidechain) continue;
    const content = entry.message?.content;
    if (!Array.isArray(content)) continue;
    for (const block of content.toReversed()) {
      if (block?.type === "text" && typeof block.text === "string") parts.push(block.text);
    }
  }
  return parts.reverse().join("\n\n").trim();
}
