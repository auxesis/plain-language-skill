# Plain language skill for Claude Code

This skill makes Claude Code write in plain language.
It follows ISO 24495-1:2023, ISO 24495-3:2026, and the GOV.UK content guidance.

## What runs, and when

- **Every session and subagent:** a hook adds the core rules in `core.md` to the context.
- **Every message you send:** a hook adds a one-line reminder of those rules.
- **Every chat reply:** a Stop hook checks the reply. If a rule that must be fixed is broken, the reply goes back to Claude once for a rewrite.
- **Every Markdown or text file Claude writes:** a hook checks the new text in the same way.
- **Documents, rewrites, and reviews:** Claude loads `SKILL.md`. It has the full process.

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

The two ISO standards are licensed to one user, and the licence prohibits copying.
This repository states their guidelines in our own words and cites the clause numbers.
It never copies the text of the standards.

The GOV.UK guidance is used under the Open Government Licence v3.0.
