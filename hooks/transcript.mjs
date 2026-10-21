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

// A message the person typed: a user entry with text in it. Tool results and text the
// harness adds (isMeta) are user entries too, and do not start a turn.
function isPersonMessage(entry) {
  if (entry?.type !== "user" || entry.isMeta || entry.isSidechain) return false;
  const content = entry.message?.content;
  if (typeof content === "string") return true;
  return Array.isArray(content) && content.some((block) => block?.type === "text");
}

// Every text block Claude wrote since the person's last message, in order.
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
    if (isPersonMessage(entry)) break;
    if (entry?.type !== "assistant" || entry.isSidechain) continue;
    const content = entry.message?.content;
    if (!Array.isArray(content)) continue;
    for (const block of content.toReversed()) {
      if (block?.type === "text" && typeof block.text === "string") parts.push(block.text);
    }
  }
  return parts.reverse().join("\n\n").trim();
}
