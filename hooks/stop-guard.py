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
# { session_id, transcript_path, last_assistant_message, stop_hook_active, cwd }.
# The names in the settings file for cwd, the session's folder, are read as one word.
# Output is nothing, which lets the turn end, or {"decision":"block","reason":...},
# which gives the reason back to Claude to act on. When the hook's own code fails, the
# output is {"systemMessage":...}, a warning for the person (see failure.py).
#
# The hook sends a turn back at most once, because a second time could loop for ever.
# stop_hook_active is true when a Stop hook from any plugin sent the turn back, so the
# hook keeps its own record in the "sent-back" folder.
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
# Claude Code runs this hook with "python3 -I", which leaves the script's own folder off
# the import path, so it and the checker's folder are added here.
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "skills", "plain-language", "scripts")]

from failure import report, run  # noqa: E402

MISSED = "Claude's reply was not checked against the plain-language rules"

try:
    from check import findings, format_finding, load_rules  # noqa: E402
    from settings import SettingsError, names_for  # noqa: E402
    from shared import broken_settings, emit, file_name, findings_style, hooks_off, parse_event, read_stdin, reason_for, state_folder, truthy  # noqa: E402
    from transcript import tail, turn_text  # noqa: E402
except Exception as error:
    sys.exit(report("Stop", MISSED, error))

OPENING = "Your reply breaks the plain-language rules (ISO 24495-1). Write the reply again with these sentences fixed. Do not apologise, and do not explain the rule. Write the corrected reply as if it were the first."
# An example at the end of a piece of advice, such as: Write two sentences: "Six ... you."
EXAMPLE = re.compile(r':\s*"[^"]*"\s*$')
# A session that ends during a turn leaves its files. Files this old are deleted.
STALE = 24 * 60 * 60


def earlier_text(transcript_path):
    if not isinstance(transcript_path, str) or not transcript_path:
        return ""
    try:
        return turn_text(tail(transcript_path))
    except OSError:
        # A missing or unreadable transcript is not a language problem. The reply in
        # last_assistant_message is still checked.
        return ""


def reason(found, session):
    lines = [format_finding(None, one) for one in found]
    style = findings_style()
    if style == "short":
        return reason_for(OPENING, [EXAMPLE.sub(".", line) for line in lines], rules=False)
    if style == "file":
        # read-findings.py lets Claude read this file without a permission prompt.
        path = os.path.join(state_folder("findings"), session + ".txt")
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(reason_for(OPENING, lines) + "\n")
        except OSError:
            return reason_for(OPENING, lines)
        return f"Your reply breaks the plain-language rules (ISO 24495-1). Read {path} for the sentences to fix. Then write the corrected reply as if it were the first."
    return reason_for(OPENING, lines)


def end_turn(session):
    """Deletes this session's record and findings file, and any file older than STALE. The
    display hook's files stay: see message-display.py."""
    oldest = time.time() - STALE
    for name, mine in (("sent-back", session), ("findings", session + ".txt"), ("display", None)):
        try:
            entries = list(os.scandir(state_folder(name, create=False)))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.name == mine or entry.stat(follow_symlinks=False).st_mtime < oldest:
                    shutil.rmtree(entry.path) if entry.is_dir(follow_symlinks=False) else os.remove(entry.path)
            except OSError:
                pass


def send_back(session, payload):
    with open(os.path.join(state_folder("sent-back"), session), "w"):
        pass
    emit(payload)
    return 0


def main():
    if hooks_off():
        return 0

    event = parse_event(read_stdin())
    session = file_name(event.get("session_id"))
    if truthy(event.get("stop_hook_active")) and os.path.exists(os.path.join(state_folder("sent-back"), session)):
        end_turn(session)
        return 0

    last = event.get("last_assistant_message")
    last = last.strip() if isinstance(last, str) else ""
    earlier = earlier_text(event.get("transcript_path"))
    text = "\n\n".join(part for part in (earlier, last) if part) if last and last not in earlier else earlier
    if not text:
        end_turn(session)
        return 0

    cwd = event.get("cwd")
    try:
        names = names_for(cwd if isinstance(cwd, str) and cwd else os.getcwd())
        found = [one for one in findings(text, load_rules(), mode="chat", names=names) if one["severity"] == "block"]
    except SettingsError as error:
        return send_back(session, broken_settings(error, "Your reply"))
    if not found:
        end_turn(session)
        return 0
    return send_back(session, {"decision": "block", "reason": reason(found, session)})


if __name__ == "__main__":
    sys.exit(run(main, "Stop", MISSED))
