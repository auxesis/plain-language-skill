#!/usr/bin/env python3
# SessionStart and SubagentStart hook: adds core.md, the always-on plain-language
# rules, to the context of every session and every subagent.
#
# A skill loads only when Claude decides a task needs it, so on its own it would not
# shape every chat reply. This hook puts the short rule set in front of every session;
# the skill keeps the full process for documents, rewrites and reviews.
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
# Claude Code runs this hook with "python3 -I", which leaves the script's own folder off
# the import path, so it is added here.
sys.path.insert(0, HERE)

from failure import report, run  # noqa: E402

MISSED = {
    "SessionStart": "the plain-language rules were not added to this session",
    "SubagentStart": "the plain-language rules were not added to this subagent",
}

try:
    from shared import CORE, emit, hooks_off, parse_event, read_stdin, read_text  # noqa: E402
except Exception as error:
    sys.exit(report("SessionStart", MISSED["SessionStart"], error))


def main():
    if hooks_off():
        return 0

    try:
        event = parse_event(read_stdin())
    except Exception:
        # An unreadable event still gets the rules, as a SessionStart.
        event = {}

    name = "SubagentStart" if event.get("hook_event_name") == "SubagentStart" else "SessionStart"
    try:
        core = read_text(CORE)
    except Exception as error:
        return report(name, MISSED[name], error)

    emit({"hookSpecificOutput": {"hookEventName": name, "additionalContext": core}})
    return 0


if __name__ == "__main__":
    sys.exit(run(main, "SessionStart", MISSED["SessionStart"]))
