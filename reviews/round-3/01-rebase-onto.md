**The request:**

> What does `git rebase --onto` do, and when would I use it instead of a normal rebase?

---

`git rebase --onto` lets you choose two things separately: which commits to move, and where to put them.
A normal rebase uses one branch for both choices.
You use `--onto` when those two places are different branches.

## How to read the command

```
git rebase --onto <new-base> <old-base> [<branch>]
```

1. Git finds the commits that are on `<branch>` but not on `<old-base>`.
2. Git copies those commits, one at a time, on top of `<new-base>`.
3. Git moves `<branch>` to the last copied commit.

If you leave out `<branch>`, Git uses the branch you have checked out.

A normal `git rebase main` works the same as `git rebase --onto main main`.
A normal rebase uses the same branch for the old base and the new base.
The `git rebase` manual page (`git help rebase`) documents this default.

## Use it when the branch under yours has been squash-merged

This is the most common reason to use `--onto`.
Say you started `feature-b` from `feature-a`:

```
main:       A---B
                 \
feature-a:        C---D
                       \
feature-b:              E---F
```

Then someone squash-merged `feature-a` into `main` as commit `S`.
Commit `S` contains the changes from `C` and `D`, but Git sees it as a different commit:

```
main:       A---B---S
```

If you run `git rebase main` on `feature-b`, Git tries to copy `C`, `D`, `E`, and `F`.
Git cannot tell that `S` already contains `C` and `D`.
You then often get conflicts with changes that are already in `main`.

Run this instead:

```
git rebase --onto main feature-a feature-b
```

Git copies only `E` and `F`, because they are the only commits on `feature-b` that are not on `feature-a`:

```
main:       A---B---S
                     \
feature-b:            E'---F'
```

`E'` and `F'` are new commits with the same changes as `E` and `F`.

Your local `feature-a` branch must still point at `D` for this to work.
If you have deleted `feature-a`, use the hash of commit `D` in its place.

## Use it when you started a branch from the wrong branch

Say you meant to branch from `main` but branched from `develop` by mistake.
Your branch now includes commits from `develop` that you do not want.
This command moves only your own commits onto `main`:

```
git rebase --onto main develop my-branch
```

## Use it to remove commits from the middle of a branch

This command deletes the two commits before your latest one:

```
git rebase --onto HEAD~3 HEAD~1
```

Git copies only `HEAD`, the commit you have checked out, onto `HEAD~3`.
The commits `HEAD~2` and `HEAD~1` are left out.
If you would rather pick commits from a list, `git rebase -i` gives the same result.

## Rebasing replaces your commits with new ones

- **If you have already pushed the branch,** you need to force-push it after the rebase.
  Use `git push --force-with-lease`.
  That option refuses to push if someone else has pushed to the branch since you last fetched.
- **If the result is wrong,** `git reset --hard ORIG_HEAD` puts the branch back where it was before the rebase. `git reflog` lists earlier positions of the branch as well.
