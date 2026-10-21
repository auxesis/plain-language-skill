**The request:**

> This paragraph from our CLAUDE.md is hard to follow. Rewrite it. It's in paragraph.md.
>
> The original paragraph:
>
> - **Run the language guards after `git add`, never before.**
>   `terminology-guard`, `hold-carry-guard`, `reader-acronyms-guard`, `copy-contractions-guard` and `markdown-line-breaks` all read **tracked** files, so a new or unstaged file is invisible to them and every one of them passes on nothing.
>   Stage first, then run them: `cd slipstream && npx jest hold-carry-guard terminology-guard reader-acronyms-guard copy-contractions-guard markdown-line-breaks`.
>   This has cost a continuous integration cycle twice: on #539, and again on #615, where the guards passed locally and the `test` job then failed on one figurative verb in a new Markdown file.
>   It is the one check in this repository that a correct local run can miss entirely, because nothing in its output says which files it read.

---

I could not save this to `paragraph.md`, because this session has no tool that edits files or runs commands.
You need to paste the rewrite in yourself:

```markdown
- **Run `git add` before you run the language guards.**
  After you run `git add`, run all five guards with this command:

  ```sh
  cd slipstream && npx jest hold-carry-guard terminology-guard reader-acronyms-guard copy-contractions-guard markdown-line-breaks
  ```

  The guards read only files that git tracks.
  They skip any new or unstaged file without failing.
  Their output does not list which files they read, so a pass does not show that they checked your file.
  No other check in this repository can miss a problem when you run it correctly.

  Running the guards before `git add` has caused two failed continuous integration runs, in #539 and #615.
  In #615, the guards passed locally.
  The `test` job then failed because a new Markdown file contained one figurative verb.
```

These are the changes:

- **New order:** the rule and the command come first, then the reason, then the history.
  The history is now its own paragraph.
- **Command:** it is in its own code block, so you can copy it.
- **Guard names:** I removed the separate list of the five names, because the command already names all five.
  Every other fact from the original is still there.
- **Wording:** I replaced the figurative phrases with literal ones:
  - "invisible to them" became "skip".
  - "passes on nothing" became "without failing".
  - "cost a continuous integration cycle" became "caused two failed continuous integration runs".

The original may contradict itself.
It says the guards read tracked files, but also that they skip unstaged files.
In git, a file with unstaged edits is still a tracked file.
If the guards read the working copy of tracked files, they would check those edits.
In that case, they would skip only new files.

I kept the original wording because the guard code is not in this folder, so I could not check which is true.
If only new files are skipped, change "any new or unstaged file" to "any new file".

The plain-language checker script needs a command run, so I could not run it on this text.
I checked the rewrite against the rules by reading it myself.
