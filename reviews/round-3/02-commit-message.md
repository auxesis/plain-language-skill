**The request:**

> Write a commit message for the change in change.diff.
>
> (change.diff is commit 58e74b56 from the Slipstream repository: two test files, 26 lines added and 20 removed.)

---

I wrote this commit message from the diff in `change.diff`:

```
Type-check the ResizeObserver stand-in in two tests

Two tests install a stand-in for window.ResizeObserver, because jsdom
does not provide one. They are the CapabilityMatrixTable heading
clearance test and the SlideOverDialog reports width test.

Both tests used `@ts-expect-error` to install and remove the stand-in.
That comment hides any type error on the next line. So the compiler
could not report when the stand-in stopped matching the real
ResizeObserver.

Now the stand-in in each test:

- implements `ResizeObserver` and takes a `ResizeObserverCallback`
- is assigned to a constant of type `typeof ResizeObserver`, so the
  compiler checks the constructor as well as the methods
- calls the callback with an empty list of entries and the observer,
  to match the real callback signature

The tests install the stand-in with `Object.defineProperty` and remove
it with `Reflect.deleteProperty`. Neither call needs
`@ts-expect-error`. What the tests check has not changed.
```

The folder contains only the diff, so I have not compiled or run the tests.
If the repository uses Conventional Commits, start the subject line with `test: `.
