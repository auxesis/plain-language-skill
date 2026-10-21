
**Every merge to `main` used to switch sign-in by text message off (#381), and the fix is one enabled provider block.**
What was measured, on one preview branch project on 2026-09-09: with every provider block off, the apply left `external_phone_enabled` false;
with `[auth.sms.messagebird]` enabled, the next apply set it true.
The Supabase tool names a provider in what it sends only when a block is enabled, while it sends `enable_signup` either way.
**The rule the platform is applying was never established** — an apply enforcing something the Management API does not, and both enforcing the same rule with the apply's own request failing it, fit every measurement equally; don't repeat either as fact.
The commits, project references and documentation each claim rests on are in **What was measured** in `.work/slipstream/enable-sms-login.md`; cite those rather than restating them.
Nothing announced the change: the login page looks identical whether a member gets a text message or an email.
`[auth.sms.messagebird]` in `slipstream/supabase/config.toml` is enabled for that reason and no other — while the `send_sms` hook is on, Supabase Auth never builds a provider, so its two values are read by nobody — and `slipstream/sms-hook-guard.test.ts` fails if it is removed.
The `sms-phone-restored` job in `.github/workflows/smoke-tests.yml` is the backstop: it runs `sms:restore` once Supabase's apply reports success on `main`, and again every morning, says so in Discord if the field ever had to be put back, and fails red if it could not be.
Two rules keep that safe — `sms:restore` does nothing while `SMS_SEND` is unset, so a merge can never undo an emergency `sms:disable`, and the job refuses to act on a commit that is not on `main`, because that same check completes on every branch and would otherwise write to production from a pull request.

