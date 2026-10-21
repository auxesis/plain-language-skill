**The request:**

> what's still open?
>
> (Asked at the end of a copy of your CI cost session.)

---

All eight questions from my last message are still open.
You have not answered any of them yet.

## Questions waiting for your answer

- **Q1:** run gate checks in a merge queue, and have each queue run test only the paths the pull request changed.
- **Q2:** decide which checks become gate checks.
- **Q3:** set up push and gate checks in stack only.
- **Q4:** agree the order of changes before 31 October.
- **Q5:** buy the RunsOn licence and reuse the setup the trial built in your AWS account.
- **Q6:** watch spending with alerts instead of a hard limit.
- **Q7:** write a decision record for the move off Blacksmith.
- **Q8:** run each job only when a path it reads has changed.

## Questions for the next round

These depend on your answers above.

- **Weekly cost estimate:** where it gets posted.
  This depends on Q6.
- **Required checks:** the names of the summary checks that become required.
  This depends on Q1 and Q2.
- **Dependabot:** whether to group its updates.
  In 20 days, 40 Dependabot branches cost $115.
- **Agent pushes:** whether agents should push less often or work in draft pull requests.
- **Tool setup:** the mise tool-setup step takes about 16% of all job time.
- **Bun job:** this job hides its own failures.
- **Cancelling superseded runs:** I estimate this saves about $55 a month.

## Facts I still need to check

- Whether commits the merge queue makes pass the rule that requires signed commits.
- Whether a private repository on the Team plan can use a merge queue.
  This affects cipherstash-suite only.
- Whether the RunsOn trial licence has an end date.

## Files

- I created `.github/CONTEXT.md` and edited `CONTEXT-MAP.md`.
  Neither change is committed.
- I have posted nothing to GitHub.
- The fact base file was in this session's temporary folder.
  I can no longer use that folder.
  If you want to keep the fact base, I can write it again inside the repository.
