#!/usr/bin/env python3
# PreToolUse hook for Read: lets Claude read the findings file the Stop hook
# wrote, without a permission prompt. The file is outside the project, so in default
# permission mode Claude Code would otherwise ask the person first.
#
# Only files in the findings folder are allowed. The path is resolved first, so ".."
# and links cannot reach a file outside that folder. For any other file the hook prints
# nothing, and Claude Code's own permission rules decide.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from failure import report, run  # noqa: E402

MISSED = "Claude may need your permission to read the plain-language findings"

try:
    from shared import emit, hooks_off, parse_event, read_stdin, state_folder  # noqa: E402
except Exception as error:
    sys.exit(report("PreToolUse", MISSED, error))


def main():
    if hooks_off():
        return 0

    event = parse_event(read_stdin())
    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    path = tool_input.get("file_path")
    if event.get("tool_name") != "Read" or not isinstance(path, str) or not path:
        return 0

    try:
        folder = os.path.realpath(state_folder("findings", create=False))
    except OSError:
        return 0
    target = os.path.realpath(path)
    if os.path.dirname(target) != folder or not os.path.isfile(target):
        return 0

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "The plain-language Stop hook wrote this file for Claude to read.",
            }
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(run(main, "PreToolUse", MISSED))
