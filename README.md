# Plain language skill for Claude Code

This Claude Code plugin makes Claude write in plain language.
It follows ISO 24495-1:2023, ISO 24495-3:2026, and the GOV.UK content guidance.
The plugin contains a skill and seven hooks.

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
- **While a reply appears:** a display hook hides a reply that the Stop hook will send back, so you see only the rewrite. See "Settings".
- **The findings file:** a hook lets Claude read the Stop hook's findings file without asking you.
- **Every Markdown or text file Claude writes:** a hook checks the new text in the same way.
- **Documents, rewrites, and reviews:** Claude loads the skill in `SKILL.md`. It has the full process.

## Install

You need Claude Code, git, and Python 3.9 or later.
The hooks and the checker are written in Python.
They use only the modules that come with Python, so you do not need to install any packages.
The plugin has been tested on Linux only, with Claude Code 2.1.307 and 2.1.312, Python 3.9.25, and Python 3.14.8.

The plugin's settings need Claude Code 2.1.271 or later.
Older versions of Claude Code cannot load the plugin.

1. Check that you have Python 3.9 or later:

   ```
   python3 --version
   ```

   Most Linux distributions include Python 3.
   On macOS, Python 3 comes with Apple's command line tools.
   If you do not have them, macOS offers to install them when you run `python3`.
   If you have no Python 3, or a version older than 3.9, install Python from [python.org](https://www.python.org/downloads/) or with your package manager.

   The hooks run `python3` in the folder of the project you have open.
   A tool such as mise or pyenv can give a project folder its own version of Python.
   If you use one, run `python3 --version` in your project folder as well.

2. Add the marketplace that lists the plugin:

   ```
   claude plugin marketplace add auxesis/plain-language-skill
   ```

   The marketplace is named `plain-language-skill`.

3. Install the plugin:

   ```
   claude plugin install plain-language@plain-language-skill
   ```

   In a Claude Code session, the same steps are `/plugin marketplace add auxesis/plain-language-skill` and `/plugin install plain-language@plain-language-skill`.

4. Turn off any plugin or setting that tells Claude to write in a terse style, such as the caveman plugin.
   Its instructions conflict with the rules in this plugin.

5. Start a new Claude Code session.
   Claude Code loads plugins only when a session starts.
   In a session that is already open, type `/reload-plugins` instead.

To check the install, run this command:

```
claude plugin details plain-language
```

It lists one skill and seven hooks.
In a session, type `/hooks` to see the hooks, or `/plain-language:plain-language` to load the skill.

### How the hooks run

The seven hook commands are in `hooks/hooks.json`.
Claude Code replaces `${CLAUDE_PLUGIN_ROOT}` in each command with the folder where it installed the plugin.

If Python 3 is not installed, each hook exits without doing anything.
The session hook also shows you a warning that says the hooks are off.
The other hooks stay silent, so you do not get a warning with every message.

Each command runs Python with the `-I` option.
That option stops your project from changing what the hooks run.
With it, Python does not load code from the project folder.
It also ignores packages installed in your home folder, and any environment variable whose name starts with `PYTHON`.

Each command ends with `|| exit 1`.
If a hook's file is missing, Python exits with code 2.
Claude Code treats exit code 2 as an instruction to block, so the prompt hook would block every message you send.
`|| exit 1` changes the code to 1, so Claude Code reports an error and does not block anything.

### When a hook fails

A hook can fail because of a fault in its own code or in the checker.
When that happens, the hook shows you a warning and lets Claude go on.
The warning names the hook, says what was not checked, and says where the code failed.
For example:

```text
plain-language: the Stop hook failed at check.py line 975, so Claude's reply was not checked against the plain-language rules. The error was RuntimeError: forced failure
```

A failing hook never blocks Claude, because a fault in the plugin must not stop your work.
It never stays silent either, because then you would believe your text was checked.
With `PLAIN_LANGUAGE_HOOKS=false`, a failing hook shows nothing, the same as a working one.

### Use the skill without the hooks

You can install the skill on its own, as a personal skill.
Copy or link the folder `skills/plain-language` from this repository into `~/.claude/skills/`:

```
git clone https://github.com/auxesis/plain-language-skill.git
cp -R plain-language-skill/skills/plain-language ~/.claude/skills/
```

To link the folder instead, run this command in place of `cp`:

```
ln -s "$PWD/plain-language-skill/skills/plain-language" ~/.claude/skills/plain-language
```

With a link, `git pull` in the clone updates the skill.

Claude then loads the skill only when a task matches its description.
For example, it loads the skill when you ask for a README, or for a review of text that is hard to read.
Without the hooks, nothing checks Claude's replies or files.

Copy only the `skills/plain-language` folder, not the whole repository.
Claude Code loads a folder in `~/.claude/skills/` as a plugin if it contains `.claude-plugin/plugin.json`.
The plugin's hooks would then run.

Do not install the plugin as well.
If you do, the skill appears twice.

## Move from the old install

Earlier versions had no plugin, so you installed them by hand.
You cloned the repository into `~/.claude/skills/plain-language`, and added five hook entries to `~/.claude/settings.json`.
If you installed the skill that way, remove the old install before you install the plugin.

Otherwise each hook runs twice.
One copy runs from `settings.json`, and the other runs from the plugin.
The skill also appears twice, as `plain-language` and as `plain-language:plain-language`.

Follow these steps in this order:

1. Delete the five hook entries from `~/.claude/settings.json`.
   Each one runs a file in `~/.claude/skills/plain-language/hooks/`.
   In the JavaScript version, the commands run `node` instead of `python3`.
2. Delete the old skill folder:

   ```
   rm -rf ~/.claude/skills/plain-language
   ```

   If `~/.claude/skills/plain-language` is a symbolic link to a clone somewhere else, delete only the link:

   ```
   rm ~/.claude/skills/plain-language
   ```

3. Follow steps 2 to 5 of the install steps.

Do not run `git pull` in the old folder instead.
This version adds `.claude-plugin/plugin.json`, so Claude Code would load the old folder as a plugin.
Its hooks would then run as well as the hooks in `settings.json`.

## Update

```
claude plugin marketplace update plain-language-skill
claude plugin update plain-language@plain-language-skill
```

The first command gets the latest list of plugins from the marketplace.
The second command installs the new version of the plugin.
The new version loads in your next session, or when you type `/reload-plugins`.

The plugin has no version number, so Claude Code uses a commit ID from this repository as its version.
Each new commit on the `main` branch is a new version.
If there is no new commit, the second command reports that the plugin is already at the latest version.

Claude Code can also update the plugin for you.
It does not do this for this marketplace unless you turn it on.
To turn it on, type `/plugin` in a session, open the **Marketplaces** tab, select `plain-language-skill`, and select **Enable auto-update**.

## Remove

1. Uninstall the plugin, then remove the marketplace:

   ```
   claude plugin uninstall plain-language@plain-language-skill
   claude plugin marketplace remove plain-language-skill
   ```

2. Start a new Claude Code session.

## Settings

The plugin has two settings.
To change them, type `/config` in a session.

| Setting | Values | Default |
|---|---|---|
| `findings` | `file`, `short`, or `full` | `file` |
| `hide_drafts` | `true` or `false` | `true` |

### What you see when a reply goes back for a rewrite

The `findings` setting controls what the Stop hook's message shows:

- **`file`:** the findings go in a file, and the message asks Claude to read it. You see the message and a line that says "Read 1 file".
- **`short`:** the message lists each finding with its advice. It leaves out the example at the end of the advice, and the path to `core.md`.
- **`full`:** the message lists each finding with its advice, an example, and the path to `core.md`.

In a test reply with two findings, `file` took 5 lines on screen. `short` took 10 lines, and `full` took 13.
The terminal was 100 columns wide.

With `file`, the findings are in the plugin's data folder, `~/.claude/plugins/data/plain-language-plain-language-skill/findings/`.
Claude Code normally asks you before Claude reads a file outside your project.
A PreToolUse hook lets Claude read the files in that folder without asking.
That hook allows no other file.
The Stop hook deletes the session's findings file at the end of each turn.

### Hidden drafts

With `hide_drafts` on, no reply appears until Claude has finished writing it.
Then a display hook checks the reply against the same rules as the Stop hook.
A reply that passes appears in full.
A reply that breaks a rule that must be fixed does not appear.
You see the Stop hook's message, then the rewrite.

After the display hook hides a reply, it shows every later reply until you send your next message.
The Stop hook does not check a rewrite either.

Hidden drafts have these costs:

- No reply appears line by line. Each reply appears only when it is complete.
- The hidden reply is still in the transcript. Claude also still has it in its context.
- Verbose mode shows the hidden reply. To turn verbose mode on or off, press ctrl+O.
- If you stop Claude after a reply is hidden, that reply stays hidden. Verbose mode still shows it.

Turn `hide_drafts` off to see each reply line by line, as Claude writes it.

### Where the settings are saved

Claude Code saves the values in `~/.claude/settings.json`, under `pluginConfigs`:

```json
{
  "pluginConfigs": {
    "plain-language@plain-language-skill": {
      "options": { "findings": "short", "hide_drafts": false }
    }
  }
}
```

Claude Code reads `pluginConfigs` only from your user settings and from managed settings.
A project's settings file cannot change these settings.
Until you save a value, Claude Code does not pass the setting to the hooks, and the hooks use the defaults in the table.

To try other values for one session, pass them with `--settings`:

```
claude --settings '{"pluginConfigs": {"plain-language@plain-language-skill": {"options": {"hide_drafts": false}}}}'
```

## Skip a check

- **Skip one line:** put `plain-language-allow` on the line. In Markdown, write it in a comment: `<!-- plain-language-allow -->`.
- **Skip a whole file:** put `<!-- plain-language-check: off -->` in the file, on a line of its own. The file hook then does not check the file. The marker does not work inside a sentence.
- **Turn off the hooks for one session:** start Claude Code with the environment variable `PLAIN_LANGUAGE_HOOKS` set to `false`. Each hook then exits without doing anything.

For example, this command starts a session without the hooks:

```
PLAIN_LANGUAGE_HOOKS=false claude
```

The skill still loads in that session when a task matches its description.

The variable takes the values `true` and `false`.
Upper or lower case does not matter.
Spaces around the value do not matter either.
Any other value, or no value, leaves the hooks on.
The checker script ignores the variable.

The checker never checks code blocks, inline code, URLs, or text in double quotation marks.

## Tell the checker your project's names

The checker can report a mistake where a name is written correctly:

- "aXcelerate" starts with a small letter. So a sentence that starts with it is joined to the sentence before.
- "Lift and Shift" contains "and". So the checker reads it as the end of a list.

To stop this, list the names in a file named `.plain-language.json` at the top of your project:

```json
{
  "names": ["aXcelerate", "Lift and Shift"]
}
```

The checker then reads each name as one word.
A name matches only in the same case, and only as a whole word.
Each finding still shows the name as you wrote it.

The checker looks for the file in the folder of the file it checks, then in each folder above.
It stops at the top of the git repository, the folder that contains `.git`.
For a chat reply, it starts in the folder of the Claude Code session.
The checker that you run by hand finds the same file as the hooks.

The file can list names and nothing else.
It cannot turn a rule off or change a limit, because that would hide real problems as well as false ones.
To skip one line, use `plain-language-allow`, as "Skip a check" describes.

A broken settings file is never ignored:

- The checker that you run by hand prints the file's path and the problem, and exits with code 2.
- The hooks tell Claude what is wrong with the file, and that nothing was checked.
- When Claude writes the file, the file hook checks it straight away.

## Files

| File | What it contains |
|---|---|
| `.claude-plugin/plugin.json` | The plugin's name, description, and licence |
| `.claude-plugin/marketplace.json` | The marketplace that lists the plugin |
| `skills/plain-language/SKILL.md` | The process for documents, rewrites, and reviews |
| `skills/plain-language/core.md` | The rules for every reply and file |
| `skills/plain-language/references/guidelines.md` | Every guideline in both ISO standards, in our own words |
| `skills/plain-language/references/content-guidance.md` | The GOV.UK rules, including the words to avoid |
| `skills/plain-language/scripts/check.py` | The checker that the hooks use |
| `skills/plain-language/scripts/rules.json` | The list of rules the checker applies |
| `skills/plain-language/scripts/settings.py` | The code that finds and reads a project's `.plain-language.json` |
| `hooks/hooks.json` | The commands that run the hooks |
| `hooks/*.py` | The hooks, and the code they share |
| `tests/` | Tests for the checker, the hooks, and the plugin files |
| `evals/` | The test prompts used to measure the skill |

## Check a file by hand

From the root of this repository, run:

```
python3 skills/plain-language/scripts/check.py path/to/file.md
```

For text that is not in a file, pipe it in and add `--chat`:

```
echo "We will leverage this." | python3 skills/plain-language/scripts/check.py --chat
```

The checker reports that "leverage" must be fixed.
It exits with code 1.

Claude Code keeps its copy of the plugin in `~/.claude/plugins/cache/plain-language-skill/plain-language/`.
That folder contains one folder for each version you have installed.
Each of those folders is named after a commit ID.
The checker is in `skills/plain-language/scripts/check.py` inside that version's folder.

## Local development

Install the plugin from GitHub, as in the install steps.
To work on a change, start Claude Code with the `--plugin-dir` option and the path to your clone:

```
claude --plugin-dir path/to/plain-language-skill
```

For that session, Claude Code loads the plugin from your clone instead of the installed copy.
Sessions that you start without `--plugin-dir` still use the installed copy.

After you change `hooks/hooks.json` or the skill, type `/reload-plugins`.
Claude Code then reads the plugin from your clone again.
A change to a Python file takes effect the next time its hook runs, because each hook starts Python again.

To compare with a session that has no part of the plugin, turn the plugin off for one session:

```
claude --settings '{"enabledPlugins": {"plain-language@plain-language-skill": false}}'
```

A value that you pass with `--settings` takes priority over your settings files, for that session only.
To turn off only the hooks, use `PLAIN_LANGUAGE_HOOKS=false`, as "Skip a check" describes.

Do not add your clone as a second marketplace.
The clone's marketplace has the same name as the one on GitHub, `plain-language-skill`.
Claude Code allows only one marketplace with each name.

To check the plugin files, run these commands from the root of the repository:

```
claude plugin validate .
claude plugin validate skills
```

The first command checks `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json`.
It warns that the plugin has no version.
The plugin leaves out the version on purpose.
The second command checks the skill.

### Release a change

Merge the change into the `main` branch.
The plugin has no version number, so each commit on `main` is a new version.
Users get it when they run the update commands, or when auto-update runs.

## Run the tests

From the root of this repository, run this command:

```
mise run test
```

If mise asks you to trust `mise.toml`, run `mise trust`.
The `test` task runs `python3 -m unittest` with the Python version that `mise.toml` names.
To run the tests with Python 3.9, the oldest version the plugin supports, run this command:

```
mise exec python@3.9 -- python3 -m unittest
```

GitHub Actions also runs the tests on Linux for every pull request.

## How reviews work

Each review round is a pull request that adds a `reviews/round-N/` folder.
Each file in it contains one test output, with one sentence on each line.
To give feedback, comment on a line or suggest a change.
Once the feedback is applied, the pull request is closed without merging.

## Licences

This repository is licensed under the Apache License 2.0, in `LICENSE`.
The material adapted from the GOV.UK content guidance is an exception.
It stays under the Open Government Licence v3.0.
That material is in `skills/plain-language/references/content-guidance.md`.
It is also in the rules `govuk-words-to-avoid` and `govuk-tone` in `skills/plain-language/scripts/rules.json`.

The file `NOTICE` credits the GOV.UK material.
If you share this repository or a work based on it, you must keep that credit.

Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

The two ISO standards are licensed to one user, and their licence prohibits copying.
This repository states their guidelines in our own words and cites the clause numbers.
It never copies the text of the standards.
