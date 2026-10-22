#!/usr/bin/env python3
# PostToolUse hook: checks prose Claude has just written into a file against the
# plain-language rules, and asks for a rewrite when a rule that must be fixed is broken.
#
# It checks only what this tool call wrote. For Write, that is the whole file. For Edit
# and MultiEdit, it is each paragraph the new text touches, so an edit to one line of
# an old document is not held up by problems in the lines around it.
#
# Prose files are Markdown and plain text. A file with "plain-language-check: off" on a
# line of its own, or in an HTML comment on a line of its own, is skipped. That is how a
# file that discusses the banned phrases opts out. The marker inside a sentence does not
# count, so a README that tells you how to use it is still checked. A line containing
# "plain-language-allow" is skipped too.
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
# Claude Code runs this hook with "python3 -I", which leaves the script's own folder off
# the import path, so it and the checker's folder are added here.
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "scripts")]

from check import findings, format_finding, load_rules  # noqa: E402
from shared import emit, parse_event, read_stdin, read_text, reason_for  # noqa: E402

PROSE = {".md", ".mdx", ".markdown", ".txt", ".rst", ".adoc"}
SKIPPED_DIRECTORIES = re.compile(r"[\\/](?:node_modules|\.git|vendor|dist|build)[\\/]")
CHECK_OFF = re.compile(r"^\s*(?:<!--\s*)?plain-language-check:\s*off\s*(?:-->)?\s*$", re.MULTILINE)


def basename(path):
    """The last part of a path, ignoring a slash at the end, as Node.js's path.basename does."""
    return os.path.basename(path.rstrip("/"))


def extname(path):
    """A file's extension, as Node.js's path.extname gives it: ".md" for "a.md", and ""
    for ".md", which is a hidden file with no extension."""
    name = basename(path)
    dot = name.rfind(".")
    return "" if dot <= 0 or name == ".." else name[dot:]


def changed_ranges(file, new_texts):
    """The line ranges in `file` that hold each piece of new text."""
    ranges = []
    for text in new_texts:
        if text is None or not text.strip():
            continue
        start = 0
        while True:
            at = file.find(text, start)
            if at == -1:
                break
            first = file.count("\n", 0, at) + 1
            last = first + text.count("\n")
            ranges.append((first, last))
            start = at + len(text)
    return ranges


def main():
    event = parse_event(read_stdin())
    tool = event.get("tool_name")
    tool_input = event.get("tool_input")
    target = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if tool not in ("Write", "Edit", "MultiEdit") or not isinstance(target, str):
        return 0
    if extname(target).lower() not in PROSE or SKIPPED_DIRECTORIES.search(target):
        return 0

    try:
        file = read_text(target)
        if CHECK_OFF.search(file):
            return 0
        found = [one for one in findings(file, load_rules(), mode="file") if one["severity"] == "block"]
        if tool != "Write":
            if tool == "Edit":
                new_texts = [tool_input.get("new_string")]
            else:
                new_texts = [edit.get("new_string") if isinstance(edit, dict) else None for edit in tool_input.get("edits") or []]
            ranges = changed_ranges(file, new_texts)
            found = [one for one in found if any(one["span"][0] <= last and one["span"][1] >= first for first, last in ranges)]
    except Exception:
        # A broken guard must not stop the work.
        return 0
    if not found:
        return 0

    emit(
        {
            "decision": "block",
            "reason": reason_for(
                f"The prose just written to {target} breaks the plain-language rules (ISO 24495-1). Fix these lines in the file now. Do not explain the rule.",
                [format_finding(basename(target), one) for one in found],
            ),
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
