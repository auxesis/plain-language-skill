#!/usr/bin/env python3
# Stop hook: checks what Claude wrote in the chat this turn against the plain-language
# rules, and sends it back for a rewrite when a rule that must be fixed is broken.
#
# It checks the reply Claude Code passes in last_assistant_message, plus any earlier
# text Claude wrote in the same turn, which it reads from the transcript. The
# transcript alone is not enough: when the hook runs, the final reply has often not
# been written to the file yet, so a hook that reads only the transcript misses it.
# That was measured on 21 October 2026 with Claude Code 2.1.306. Text inside code
# blocks, inline code and double quotation marks is not checked (see
# skills/plain-language/scripts/prose.py).
#
# Input is the Stop hook's JSON on stdin:
# { transcript_path, last_assistant_message, stop_hook_active }.
# Output is nothing, which lets the turn end, or {"decision":"block","reason":...},
# which gives the reason back to Claude to act on.
#
# When the hook has already sent this turn back once, stop_hook_active is true and the
# hook lets the turn end. Sending it back a second time could loop for ever.
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
# Claude Code runs this hook with "python3 -I", which leaves the script's own folder off
# the import path, so it and the checker's folder are added here.
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "skills", "plain-language", "scripts")]

from check import findings, format_finding, load_rules  # noqa: E402
from shared import emit, hooks_off, parse_event, read_stdin, reason_for, truthy  # noqa: E402
from transcript import tail, turn_text  # noqa: E402


def earlier_text(transcript_path):
    if not isinstance(transcript_path, str) or not transcript_path:
        return ""
    try:
        return turn_text(tail(transcript_path))
    except Exception:
        # A missing or unreadable transcript is not a language problem.
        return ""


def main():
    if hooks_off():
        return 0

    event = parse_event(read_stdin())
    if truthy(event.get("stop_hook_active")):
        return 0

    last = event.get("last_assistant_message")
    last = last.strip() if isinstance(last, str) else ""
    earlier = earlier_text(event.get("transcript_path"))
    text = "\n\n".join(part for part in (earlier, last) if part) if last and last not in earlier else earlier
    if not text:
        return 0

    try:
        found = [one for one in findings(text, load_rules(), mode="chat") if one["severity"] == "block"]
    except Exception:
        # A broken guard must not stop the work.
        return 0
    if not found:
        return 0

    emit(
        {
            "decision": "block",
            "reason": reason_for(
                "Your reply breaks the plain-language rules (ISO 24495-1). Write the reply again with these sentences fixed. Do not apologise, and do not explain the rule. Write the corrected reply as if it were the first.",
                [format_finding(None, one) for one in found],
            ),
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
