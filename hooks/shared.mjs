// Small helpers the hooks share.

export function readStdin() {
  return new Promise((resolve) => {
    let text = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (text += chunk));
    process.stdin.on("end", () => resolve(text));
    // Claude Code always closes stdin, but a hook run by hand might not.
    setTimeout(() => resolve(text), 2000).unref();
  });
}

// A long list of findings buries the first ones, so a reason shows at most this many.
const SHOWN = 12;

export function reasonFor(opening, lines) {
  const shown = lines.slice(0, SHOWN);
  const more = lines.length - shown.length;
  return [
    opening,
    "",
    ...shown.flatMap((line) => [line, ""]),
    more > 0 ? `There are ${more} more findings like these. Fix them too.` : "",
    "The rules and the reasons for them: ~/.claude/skills/plain-language/core.md.",
  ]
    .filter((line, i, all) => !(line === "" && all[i - 1] === ""))
    .join("\n")
    .trim();
}
