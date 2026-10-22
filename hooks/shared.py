# Small helpers the hooks share.
import json
import os
import select
import sys
import time

# The hooks are at the plugin root, and the skill is in skills/plain-language. The paths
# come from this file's own location, so they are right wherever the plugin is installed.
SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "skills", "plain-language")
CORE = os.path.join(SKILL, "core.md")


def hooks_off():
    """True when PLAIN_LANGUAGE_HOOKS is "false", in any case and with any spaces around it.

    "PLAIN_LANGUAGE_HOOKS=false claude" starts a session in which every hook exits at once
    and prints nothing. The skill still loads. Any other value, or no value, leaves the
    hooks on.
    """
    return os.environ.get("PLAIN_LANGUAGE_HOOKS", "").strip().lower() == "false"


def read_stdin(timeout=2.0):
    """Reads standard input as UTF-8.

    Claude Code always closes stdin, but a hook run by hand might not, so this stops
    waiting after `timeout` seconds.
    """
    try:
        fd = sys.stdin.fileno()
    except (AttributeError, OSError, ValueError):
        return ""
    chunks = []
    deadline = time.monotonic() + timeout
    while True:
        left = deadline - time.monotonic()
        if left <= 0 or not select.select([fd], [], [], left)[0]:
            break
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", "replace")


def _reject(constant):
    # JavaScript's JSON.parse rejects NaN and Infinity, so the hooks do too.
    raise ValueError(f"{constant} is not valid JSON")


def parse_json(text):
    return json.loads(text, parse_constant=_reject)


def parse_event(text):
    """The hook's input event. Anything that is not a JSON object counts as an empty one."""
    event = parse_json(text or "{}")
    return event if isinstance(event, dict) else {}


def truthy(value):
    """JavaScript's idea of true, in which an empty list or object counts as true."""
    return True if isinstance(value, (list, dict)) else bool(value)


def emit(payload):
    """Writes the hook's JSON answer, as compact as JavaScript's JSON.stringify."""
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8", "replace"))
    sys.stdout.buffer.flush()


def read_text(path):
    """Reads a file as UTF-8, keeping its line endings."""
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


# A long list of findings buries the first ones, so a reason shows at most this many.
SHOWN = 12


def reason_for(opening, lines):
    shown = lines[:SHOWN]
    more = len(lines) - len(shown)
    parts = [
        opening,
        "",
        *[part for line in shown for part in (line, "")],
        f"There are {more} more findings like these. Fix them too." if more > 0 else "",
        f"The rules and the reasons for them: {CORE}.",
    ]
    kept = [line for i, line in enumerate(parts) if not (line == "" and i > 0 and parts[i - 1] == "")]
    return "\n".join(kept).strip()
