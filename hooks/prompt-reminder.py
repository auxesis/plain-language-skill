#!/usr/bin/env python3
# UserPromptSubmit hook: adds a one-line reminder of the plain-language rules to each
# prompt. Rules given once at the start of a long session lose their effect, and a
# line per prompt costs little.
import os
import sys

# Claude Code runs this hook with "python3 -I", which leaves the script's own folder off
# the import path, so it is added here.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from failure import report, run  # noqa: E402

MISSED = "the plain-language reminder was not added to this message"

try:
    from shared import CORE, emit, hooks_off, read_stdin, start_turn  # noqa: E402
except Exception as error:
    sys.exit(report("UserPromptSubmit", MISSED, error))


def main():
    if hooks_off():
        return 0
    start_turn(read_stdin())
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"Plain language is on (ISO 24495-1; full rules in {CORE}). Answer first. Write literally: no metaphor, idiom, cliché or symbol shorthand. Use complete sentences of 25 words or fewer, one idea each. Write negatives in full. Say how you know each claim.",
            },
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(run(main, "UserPromptSubmit", MISSED))
