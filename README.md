# Plain language skill for Claude Code

This skill makes Claude Code write in plain language.
It follows ISO 24495-1:2023, ISO 24495-3:2026, and the GOV.UK content guidance.

## Example: the same request, without and with the skill

The request asked Claude for a short message to a manager about a failed database backup.
It included these notes:

```text
- nightly pg_dump kicked off 02:00 as usual
- took 3h10m, normally ~40m. events table is now 180GB since we turned on audit logging last Tues
- job has a 3h timeout so it got killed before the S3 upload
- so no backup from last night. last good one is the night before, finished 02:41
- plan: bump timeout to 6h tonight, then split audit rows into their own dump next sprint
```

Each reply below is from a single run on 22 October 2026, with Claude Opus 5.5 in Claude Code 2.1.306.
The run without the skill had every hook and skill turned off.
In both replies, the last paragraph is a note to the person who asked, not part of the message.

### Without the skill

The reply also had a subject line, a greeting, and a sign-off.
This README leaves them out.

> Last night's database backup didn't finish. The pg_dump started at 02:00 as usual but ran for 3h10m instead of the normal ~40 minutes. The job has a 3-hour timeout, so it was killed before the upload to S3, and we have no backup from last night. It slowed down because the events table has grown to 180GB since we turned on audit logging last Tuesday. Our most recent good backup is from the night before, finished at 02:41. <!-- plain-language-allow -->
>
> Tonight we're raising the job timeout to 6 hours so the backup can finish. Next sprint we'll move the audit rows into their own separate dump. That should bring the main backup back to its normal run time, and the growing audit log won't be able to block it again. <!-- plain-language-allow -->
>
> Your manager will probably ask whether you're running a backup by hand today rather than waiting for tonight's job. If you are, it's worth adding a line saying so. <!-- plain-language-allow -->

### With the skill

> Last night's database backup failed. Our most recent good backup is from the night before, and it finished at 02:41. Last night's backup started at 02:00 and ran for 3 hours 10 minutes, compared with the usual 40 minutes. The backup job has a 3-hour time limit, so the job was stopped before it uploaded the backup to S3. The backup now takes longer because the events table has grown to 180 GB since we turned on audit logging last Tuesday.
>
> Tonight, we will raise the time limit to 6 hours so the backup can finish. Next sprint, we will back up the audit rows separately from the rest of the database.
>
> Your notes say the backup ran for 3 hours 10 minutes, but the time limit is 3 hours. Your manager may ask how both of those can be true. If you know the reason, add one sentence that explains it.

### What the skill changed

- **The most important facts come first.** The backup failed, and the last good backup is from the night before.
- **Negatives are written in full.** The reply says "did not", not "didn't".
- **Numbers are written in words and units.** The reply says "3 hours 10 minutes" and "180 GB", not "3h10m", "~40", or "180GB".
- **The reply claims nothing that the notes do not say.** The reply without the skill says the audit log "won't be able to block it again". The notes do not say that.
- **The reply points out a gap in the notes.** The backup ran for longer than its time limit, and the notes do not explain how.

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

2. Install Node.js, if you do not have version 20 or later.
   If you use [mise](https://mise.jdx.dev/), the file `mise.toml` in this repository names the version to install:

   ```
   cd ~/.claude/skills/plain-language
   mise install
   ```

   If mise asks you to trust the file, run `mise trust`.
   The version applies only inside the skill folder.
   The hooks run in the folder of the project you have open, so they need Node.js there too.
   To install Node.js 24 for every folder, run this command:

   ```
   mise use --global node@24
   ```

   Without mise, install Node.js in any way you choose.

3. Add the hooks to `~/.claude/settings.json`.
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

4. Turn off any plugin or setting that tells Claude to write in a terse style, such as the caveman plugin.
   Its instructions conflict with the rules in this skill.

5. Start a new Claude Code session.
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

From the skill folder, run this command:

```
mise run test
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
