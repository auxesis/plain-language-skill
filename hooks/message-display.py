#!/usr/bin/env python3
# MessageDisplay hook: hides a reply on screen when the Stop hook will send it back for a
# rewrite, so the person sees only the rewrite. The "hide_drafts" setting turns it off.
#
# Claude Code runs the hook for each batch of lines while a reply streams. A reply can be
# checked only when it is complete, so every batch is hidden until the last one. An empty
# displayContent hides a batch: the documentation does not say so, but a test with
# Claude Code 2.1.312 showed it. Only the screen changes. The transcript, verbose mode
# and Claude keep the original.
#
# The Stop hook does not check a rewrite, so after a reply is hidden, every later reply
# is shown until the person's next message. prompt-reminder.py deletes the record then.
# The Stop hook cannot delete it, because the screen can show a rewrite after the Stop
# hook has run.
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
# Claude Code runs this hook with "python3 -I", which leaves the script's own folder off
# the import path, so it and the checker's folder are added here.
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "skills", "plain-language", "scripts")]

from failure import report, run  # noqa: E402

MISSED = "Claude's reply was shown without the plain-language check"

try:
    from check import findings, load_rules  # noqa: E402
    from settings import names_for  # noqa: E402
    from shared import display_folder, emit, file_name, hide_drafts, hooks_off, parse_event, read_stdin  # noqa: E402
except Exception as error:
    sys.exit(report("MessageDisplay", MISSED, error))


def show(text):
    emit({"hookSpecificOutput": {"hookEventName": "MessageDisplay", "displayContent": text}})
    return 0


def breaks_rules(text, cwd):
    # If the check fails, the whole reply is shown. Claude Code's own fallback would show
    # only the last batch, because the earlier ones are already hidden.
    try:
        names = names_for(cwd if isinstance(cwd, str) and cwd else os.getcwd())
        return any(one["severity"] == "block" for one in findings(text, load_rules(), mode="chat", names=names))
    except Exception:
        return False


def main():
    if hooks_off() or not hide_drafts():
        return 0

    event = parse_event(read_stdin())
    delta = event.get("delta")
    if not isinstance(delta, str):
        return 0

    folder = display_folder(event.get("session_id"))
    held = os.path.join(folder, file_name(event.get("message_id")) + ".txt")

    if not event.get("final"):
        with open(held, "a", encoding="utf-8") as handle:
            handle.write(delta)
        return show("")

    text = delta
    if os.path.exists(held):
        with open(held, encoding="utf-8") as handle:
            text = handle.read() + delta
        os.remove(held)

    hidden = os.path.join(folder, "hidden")
    if not os.path.exists(hidden) and breaks_rules(text, event.get("cwd")):
        with open(hidden, "w"):
            pass
        return show("")
    return show(text)


if __name__ == "__main__":
    sys.exit(run(main, "MessageDisplay", MISSED))
