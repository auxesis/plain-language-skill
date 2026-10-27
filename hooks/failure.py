# What a hook does when its own code fails: it prints a warning that Claude Code shows
# to the person, and lets Claude go on. Blocking would stop all work for a fault in the
# plugin. Saying nothing would leave the person believing their text was checked.
#
# This file uses only the standard library, so it still works when shared.py or the
# checker cannot be imported.
import json
import os
import sys
import traceback

LIMIT = 200


def hooks_off():
    """True when PLAIN_LANGUAGE_HOOKS is "false", in any case and with any spaces around it.

    "PLAIN_LANGUAGE_HOOKS=false claude" starts a session in which every hook exits at once
    and prints nothing, even when its own code is broken. The skill still loads. Any
    other value, or no value, leaves the hooks on.
    """
    return os.environ.get("PLAIN_LANGUAGE_HOOKS", "").strip().lower() == "false"


def where(error):
    if isinstance(error, SyntaxError) and error.filename:
        return f"{os.path.basename(error.filename)} line {error.lineno}"
    frames = traceback.extract_tb(error.__traceback__)
    if not frames:
        return "an unknown place"
    return f"{os.path.basename(frames[-1].filename)} line {frames[-1].lineno}"


def report(hook, missed, error):
    """Prints the warning and returns 0, the exit code that lets Claude go on."""
    if hooks_off():
        return 0
    detail = " ".join(f"{type(error).__name__}: {error}".split())
    if len(detail) > LIMIT:
        detail = detail[: LIMIT - 3] + "..."
    message = f"plain-language: the {hook} hook failed at {where(error)}, so {missed}. The error was {detail}"
    sys.stdout.buffer.write(json.dumps({"systemMessage": message}, ensure_ascii=False, separators=(",", ":")).encode("utf-8", "replace"))
    sys.stdout.buffer.flush()
    return 0


def run(main, hook, missed):
    try:
        return main()
    except Exception as error:
        return report(hook, missed, error)
