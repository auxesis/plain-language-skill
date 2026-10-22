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

from shared import emit, parse_event, read_stdin, read_text  # noqa: E402

CORE = os.path.join(os.path.dirname(HERE), "core.md")


def main():
    try:
        event = parse_event(read_stdin())
    except Exception:
        # An unreadable event still gets the rules, as a SessionStart.
        event = {}

    try:
        core = read_text(CORE)
    except Exception:
        return 0

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart" if event.get("hook_event_name") == "SubagentStart" else "SessionStart",
                "additionalContext": core,
            },
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
