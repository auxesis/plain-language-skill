# Plain language skill for Claude Code

This skill makes Claude Code write in plain language.
It follows ISO 24495-1:2023, ISO 24495-3:2026, and the GOV.UK content guidance.

## Example

You ask Claude:

> I'm not a developer. My app shows this error: `connect ECONNREFUSED 127.0.0.1:5432`. In two sentences, what does it mean? <!-- plain-language-allow -->

| Without the skill | With the skill |
|---|---|
| Your app tried to connect to its database (PostgreSQL, which uses port 5432) on the same computer it's running on, and nothing answered. Usually the database isn't running or hasn't finished starting, so starting or restarting it typically fixes the error, though sometimes the app is just pointed at the wrong address. | Your app could not connect to the database on the same computer. This usually means the database is not running, or the app's settings point to the wrong place. <!-- plain-language-allow --> |

Both replies are from Claude Opus 5.5, on 22 October 2026.

## What runs, and when

- **Every session and subagent:** a hook adds the core rules in `core.md` to the context.
- **Every message you send:** a hook adds a one-line reminder of those rules.
- **Every chat reply:** a Stop hook checks the reply. If a rule that must be fixed is broken, the reply goes back to Claude once for a rewrite.
- **Every Markdown or text file Claude writes:** a hook checks the new text in the same way.
- **Documents, rewrites, and reviews:** Claude loads `SKILL.md`. It has the full process.

## Install

You need Claude Code, git, and Node.js 20 or later.
The hooks and the checker are written in JavaScript, so they need Node.js.
The skill has been tested on Linux, with Claude Code 2.1.306 and Node.js 24.

1. Clone this repository into your Claude Code skills folder.
   The folder must be named `plain-language`, because the hooks use that path.

   ```
   git clone https://github.com/auxesis/plain-language-skill.git ~/.claude/skills/plain-language
   ```

2. Add the hooks to `~/.claude/settings.json`.
   If the file has no `hooks` key, add the `hooks` key below to the top level of the file.
   If the file already has a `hooks` key, add each entry below to the list for its event.
   Do not replace the hooks you already have.

   ```json
   {
     "hooks": {
       "SessionStart": [
         { "hooks": [{ "type": "command", "timeout": 30, "command": "command -v node >/dev/null 2>&1 || exit 0; node \"$HOME/.claude/skills/plain-language/hooks/session-start.mjs\"" }] }
       ],
       "SubagentStart": [
         { "hooks": [{ "type": "command", "timeout": 30, "command": "command -v node >/dev/null 2>&1 || exit 0; node \"$HOME/.claude/skills/plain-language/hooks/session-start.mjs\"" }] }
       ],
       "UserPromptSubmit": [
         { "hooks": [{ "type": "command", "timeout": 30, "command": "command -v node >/dev/null 2>&1 || exit 0; node \"$HOME/.claude/skills/plain-language/hooks/prompt-reminder.mjs\"" }] }
       ],
       "Stop": [
         { "hooks": [{ "type": "command", "timeout": 30, "command": "command -v node >/dev/null 2>&1 || exit 0; node \"$HOME/.claude/skills/plain-language/hooks/stop-guard.mjs\"" }] }
       ],
       "PostToolUse": [
         { "matcher": "Write|Edit|MultiEdit", "hooks": [{ "type": "command", "timeout": 30, "command": "command -v node >/dev/null 2>&1 || exit 0; node \"$HOME/.claude/skills/plain-language/hooks/file-guard.mjs\"" }] }
       ]
     }
   }
   ```

   If Node.js is not installed, each hook exits without doing anything.

3. Turn off any plugin or setting that tells Claude to write in a terse style, such as the caveman plugin.
   Its instructions conflict with the rules in this skill.

4. Start a new Claude Code session.
   Claude Code loads hooks only when a session starts.
   To see the hooks that are loaded, type `/hooks`.

To check that the checker works, run this command:

```
echo "We will leverage this." | node ~/.claude/skills/plain-language/scripts/check.mjs --chat
```

The checker reports that "leverage" must be fixed.
It exits with code 1.

### Use the skill without the hooks

Step 1 on its own installs the skill.
Claude then loads the skill only when a task matches its description.
For example, it loads the skill when you ask for a README, or for a review of text that is hard to read.
Without the hooks, nothing checks Claude's replies or files.

## Update

```
git -C ~/.claude/skills/plain-language pull
```

The checks use the new version straight away.
The core rules change at the start of the next session.

## Remove

1. Delete the five hook entries from `~/.claude/settings.json`.
   Do this first, because each hook reports an error once its file is missing.
2. Delete the skill folder:

   ```
   rm -rf ~/.claude/skills/plain-language
   ```

3. Start a new Claude Code session.

## Skip a check

- **Skip one line:** put `plain-language-allow` on the line. In Markdown, write it in a comment: `<!-- plain-language-allow -->`.
- **Skip a whole file:** put `<!-- plain-language-check: off -->` in the file, on a line of its own. The file hook then does not check the file. The marker does not work inside a sentence.

The checker never checks code blocks, inline code, URLs, or text in double quotation marks.

## Files

| File | What it contains |
|---|---|
| `core.md` | The rules for every reply and file |
| `SKILL.md` | The process for documents, rewrites, and reviews |
| `references/guidelines.md` | Every guideline in both ISO standards, in our own words |
| `references/content-guidance.md` | The GOV.UK rules, including the words to avoid |
| `scripts/check.mjs` | The checker that the hooks use |
| `scripts/rules.json` | The list of rules the checker applies |
| `hooks/` | The four hooks |
| `tests/` | Tests for the checker and the hooks |
| `evals/` | The test prompts used to measure the skill |

## Check a file by hand

From the skill folder, run:

```
node scripts/check.mjs path/to/file.md
```

## Run the tests

```
node --test tests/*.test.mjs
```

## How reviews work

Each review round is a pull request that adds a `reviews/round-N/` folder.
Each file in it contains one test output, with one sentence on each line.
To give feedback, comment on a line or suggest a change.
Once the feedback is applied, the pull request is closed without merging.

## Licences

This repository is licensed under the Apache License 2.0, in `LICENSE`.
The material adapted from the GOV.UK content guidance is an exception.
It stays under the Open Government Licence v3.0.
That material is in `references/content-guidance.md`.
It is also in the rules `govuk-words-to-avoid` and `govuk-tone` in `scripts/rules.json`.

The file `NOTICE` credits the GOV.UK material.
If you share this repository or a work based on it, you must keep that credit.

Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

The two ISO standards are licensed to one user, and their licence prohibits copying.
This repository states their guidelines in our own words and cites the clause numbers.
It never copies the text of the standards.
