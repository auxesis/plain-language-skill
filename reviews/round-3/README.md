# Review round 3

These are five short tests, run on 22 October 2026 with the hooks installed.
No run was told to read the skill.

| File | Task | Words | Times the Stop hook sent the reply back |
|---|---|---:|---:|
| `01-rebase-onto.md` | Chat answer about `git rebase --onto` | 516 | 1 |
| `02-commit-message.md` | Commit message for a small Slipstream diff | 183 | 0 |
| `03-pr-description.md` | Pull request description for the same diff | 287 | 1 |
| `04-still-open.md` | "what's still open?" at the end of your CI cost session | 337 | 1 |
| `05-rewrite-paragraph.md` | Rewrite of one paragraph from the Slipstream CLAUDE.md | 378 | 1 |

## How to review

Comment on a line, or select lines and suggest a change.
When you have finished, submit the review, then tell me in Claude Code.

## What changed since round 2

The checker now blocks these, from your feedback on round 2:

- a thing given a person's verb, such as "holds" or "gains";
- two statements joined by "and" or "but", and a clause that starts with ", which";
- a condition placed after the instruction;
- the phrase "on pace";
- a missing comma after an opening "If" clause, and a missing serial comma.

## Known gaps

- The checker skips code blocks. The commit message in `02-commit-message.md` is in a code block, so no hook checked it.
- No hook checks a commit message written with `git commit -m`.
- The answer in `01-rebase-onto.md` is 516 words. I expected these tests to need about 300 words or fewer.
