#!/usr/bin/env python3
# UserPromptSubmit hook: adds a one-line reminder of the plain-language rules to each
# prompt. Rules given once at the start of a long session lose their effect, and a
# line per prompt costs little.
import os
import sys

# Claude Code runs this hook with "python3 -I", which leaves the script's own folder off
# the import path, so it is added here.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from shared import CORE, emit  # noqa: E402

emit(
    {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": f"Plain language is on (ISO 24495-1; full rules in {CORE}). Answer first. Write literally: no metaphor, idiom, cliché or symbol shorthand. Use complete sentences of 25 words or fewer, one idea each. Write negatives in full. Say how you know each claim.",
        },
    }
)
