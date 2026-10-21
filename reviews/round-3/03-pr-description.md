**The request:**

> Write the pull request description for the change in change.diff. It is a branch of the Slipstream repository, for issue #558.
>
> (The same diff as the commit message test.)

---

```markdown
## What

jsdom does not provide `ResizeObserver`. Two component tests supply their own untyped class in its place. They install and remove that class on lines marked `@ts-expect-error`:

- the capability matrix table's heading clearance test
- the slide-over dialog's width test

This PR checks both classes against the real `ResizeObserver` type instead of suppressing the errors.

Closes #558.

## Why

- `@ts-expect-error` suppresses every type error on its line, not only the one its comment describes.
- While the suppression was in place, the compiler could not report a test class that no longer matched the real `ResizeObserver`.
- The old classes called the callback with no arguments. The browser passes the resize entries and the observer.
- Once the classes match the real type, a change to how the table or the dialog uses `ResizeObserver` shows up as a compile error in its test.

## How

- **Implement the real interface.** Each test class declares `implements ResizeObserver` and accepts a `ResizeObserverCallback`.
- **Check the constructor.** Each test assigns its class to a constant of type `typeof ResizeObserver` before it installs the class.
- **Pass typed arguments.** The tests call the callback with an empty list of entries and the observer.
- **Install without suppression.** The tests install the class with `Object.defineProperty` and remove it with `Reflect.deleteProperty`.
```

I wrote this from `change.diff` alone, so there are two things for you to check:

- **Issue #558:** I could not see the issue.
  If this PR fixes only part of it, change "Closes #558" to "Refs #558".
  Then GitHub will not close the issue when the PR merges.
- **Tests and type check:** I did not run either one, because the folder contains only the diff.
