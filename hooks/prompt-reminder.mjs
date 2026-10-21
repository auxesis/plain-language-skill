#!/usr/bin/env node
// UserPromptSubmit hook: adds a one-line reminder of the plain-language rules to each
// prompt. Rules given once at the start of a long session lose their effect, and a
// line per prompt costs little.
process.stdout.write(
  JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext:
        "Plain language is on (ISO 24495-1; full rules in ~/.claude/skills/plain-language/core.md). Answer first. Write literally: no metaphor, idiom, cliché or symbol shorthand. Use complete sentences of 25 words or fewer, one idea each. Write negatives in full. Say how you know each claim.",
    },
  }),
);
