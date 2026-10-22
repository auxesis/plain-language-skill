# Plain language skill for Claude Code

This skill makes Claude Code write in plain language.
It follows ISO 24495-1:2023, ISO 24495-3:2026, and the GOV.UK content guidance.

## Example

You ask Claude:

> Our GitHub Actions bill went from $189 in September to $3,865 in October. Pull requests went from 40 to 290. In two sentences, what happened?

Without the skill, Claude replies:

> PRs rose about 7x (40 → 290), but the bill rose about 20x, so the average cost per PR also nearly tripled, from about $4.73 to about $13.33. Volume explains only part of the increase; each PR is also using more or pricier CI, possibly from more pushes per PR (common with bots or AI agents that keep iterating), larger test matrices, bigger or macOS runners, or longer jobs, and plan minutes that were free in September would make the jump look even steeper. <!-- plain-language-allow -->

With the skill, Claude replies:

> Pull requests rose to 7 times September's number, but the bill rose to 20 times, so more pull requests explain only part of the increase. The rest came from each pull request costing more on average, $13.30 compared with $4.70 in September, and your figures do not show why.

## What runs, and when

- **Every session and subagent:** a hook adds the core rules in `core.md` to the context.
- **Every message you send:** a hook adds a one-line reminder of those rules.
- **Every chat reply:** a Stop hook checks the reply. If a rule that must be fixed is broken, the reply goes back to Claude once for a rewrite.
- **Every Markdown or text file Claude writes:** a hook checks the new text in the same way.
- **Documents, rewrites, and reviews:** Claude loads `SKILL.md`. It has the full process.

## Install

You need Claude Code, git, and Python 3.9 or later.
The hooks and the checker are written in Python.
They use only the modules that come with Python, so you do not need to install any packages.
The skill has been tested on Linux only, with Claude Code 2.1.306, Python 3.9.25, and Python 3.14.4.

1. Clone this repository into your Claude Code skills folder.
   The folder must be named `plain-language`, because the hooks use that path.

   ```
   git clone https://github.com/auxesis/plain-language-skill.git ~/.claude/skills/plain-language
   ```

2. Check that you have Python 3.9 or later:

   ```
   python3 --version
   ```

   Most Linux distributions include Python 3.
   On macOS, Python 3 comes with Apple's command line tools.
   If you do not have them, macOS offers to install them when you run `python3`.
   If you have no Python 3, or a version older than 3.9, install Python from [python.org](https://www.python.org/downloads/) or with your package manager.

3. Add the hooks to `~/.claude/settings.json`.
   If the file has no `hooks` key, add the `hooks` key below to the top level of the file.
   If the file already has a `hooks` key, add each entry below to the list for its event.
   Do not replace the hooks you already have.

   ```json
   {
     "hooks": {
       "SessionStart": [
         { "hooks": [{ "type": "command", "timeout": 30, "command": "command -v python3 >/dev/null 2>&1 || exit 0; python3 -I \"$HOME/.claude/skills/plain-language/hooks/session-start.py\"" }] }
       ],
       "SubagentStart": [
         { "hooks": [{ "type": "command", "timeout": 30, "command": "command -v python3 >/dev/null 2>&1 || exit 0; python3 -I \"$HOME/.claude/skills/plain-language/hooks/session-start.py\"" }] }
       ],
       "UserPromptSubmit": [
         { "hooks": [{ "type": "command", "timeout": 30, "command": "command -v python3 >/dev/null 2>&1 || exit 0; python3 -I \"$HOME/.claude/skills/plain-language/hooks/prompt-reminder.py\"" }] }
       ],
       "Stop": [
         { "hooks": [{ "type": "command", "timeout": 30, "command": "command -v python3 >/dev/null 2>&1 || exit 0; python3 -I \"$HOME/.claude/skills/plain-language/hooks/stop-guard.py\"" }] }
       ],
       "PostToolUse": [
         { "matcher": "Write|Edit|MultiEdit", "hooks": [{ "type": "command", "timeout": 30, "command": "command -v python3 >/dev/null 2>&1 || exit 0; python3 -I \"$HOME/.claude/skills/plain-language/hooks/file-guard.py\"" }] }
       ]
     }
   }
   ```

   If Python 3 is not installed, each hook exits without doing anything.
   The hooks run in the folder of the project you have open.
   The `-I` option stops that project from changing what the hooks run.
   With it, Python does not load code from the project folder.
   It also ignores packages installed in your home folder, and any environment variable whose name starts with `PYTHON`.

4. Turn off any plugin or setting that tells Claude to write in a terse style, such as the caveman plugin.
   Its instructions conflict with the rules in this skill.

5. Start a new Claude Code session.
   Claude Code loads hooks only when a session starts.
   To see the hooks that are loaded, type `/hooks`.

To check that the checker works, run this command:

```
echo "We will leverage this." | python3 ~/.claude/skills/plain-language/scripts/check.py --chat
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

### Update from the JavaScript version

Earlier versions of this skill were written in JavaScript, and their hook commands run `node`.
If your hook commands run `node`, follow these steps in this order:

1. Pull the new version, with the command above.
   Until you finish step 2, each old hook reports an error, because its file is gone.
2. In `~/.claude/settings.json`, replace your five hook entries with the entries in step 3 of the install steps.
3. Start a new Claude Code session.

Do not replace the hook entries before you pull.
If a new hook's file is missing, Python exits with code 2.
Claude Code treats exit code 2 as an instruction to block.
For the prompt hook, that means Claude Code blocks every message you send.
For the Stop hook, it means Claude cannot end its turn.

## Remove

1. Delete the five hook entries from `~/.claude/settings.json`.
   Do this first.
   Once the hook files are gone, the prompt hook blocks every message you send, as the section above explains.
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
| `scripts/check.py` | The checker that the hooks use |
| `scripts/rules.json` | The list of rules the checker applies |
| `hooks/` | The four hooks |
| `tests/` | Tests for the checker and the hooks |
| `evals/` | The test prompts used to measure the skill |

## Check a file by hand

From the skill folder, run:

```
python3 scripts/check.py path/to/file.md
```

## Run the tests

From the skill folder, run this command:

```
mise run test
```

If mise asks you to trust `mise.toml`, run `mise trust`.
The `test` task runs `python3 -m unittest` with the Python version that `mise.toml` names.
To run the tests with Python 3.9, the oldest version the skill supports, run this command:

```
mise exec python@3.9 -- python3 -m unittest
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
