# Small helpers the hooks share.
import json
import os
import select
import stat
import sys
import tempfile
import time

from failure import hooks_off  # noqa: F401  (the hooks import it from here)

# The hooks are at the plugin root, and the skill is in skills/plain-language. The paths
# come from this file's own location, so they are right wherever the plugin is installed.
SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "skills", "plain-language")
CORE = os.path.join(SKILL, "core.md")

# The settings in .claude-plugin/plugin.json, and their defaults there. Claude Code passes
# a setting to a hook only after the person saves a value, so the hooks need the defaults.
FINDINGS_STYLES = ("file", "short", "full")
DEFAULT_FINDINGS = "file"
DEFAULT_HIDE_DRAFTS = True


def setting(key):
    """The saved value of a setting, or "" when the person has not saved one."""
    return os.environ.get(f"CLAUDE_PLUGIN_OPTION_{key.upper()}", "").strip().lower()


def findings_style():
    style = setting("findings")
    return style if style in FINDINGS_STYLES else DEFAULT_FINDINGS


def hide_drafts():
    value = setting("hide_drafts")
    return DEFAULT_HIDE_DRAFTS if not value else value not in ("false", "0", "no", "off")


def state_folder(name, create=True):
    """A folder for files the hooks keep between calls. Claude Code gives each plugin a data
    folder in CLAUDE_PLUGIN_DATA. The fallback is in the shared temporary folder."""
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not base:
        user = os.getuid() if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")
        base = os.path.join(tempfile.gettempdir(), f"plain-language-{user}")
        # Another user could make this folder first, then change the findings that Claude
        # reads without a permission prompt.
        os.makedirs(base, mode=0o700, exist_ok=True)
        info = os.lstat(base)
        if hasattr(os, "getuid") and (info.st_uid != os.getuid() or stat.S_ISLNK(info.st_mode) or info.st_mode & 0o022):
            raise OSError(f"{base} is not a folder that only this user can change")
    folder = os.path.join(base, name)
    if create:
        os.makedirs(folder, mode=0o700, exist_ok=True)
    return folder


def file_name(value):
    """`value`, such as a session ID, with only the characters that are safe in a file name."""
    return "".join(c for c in str(value) if c.isalnum() or c in "-_") or "none"


def display_folder(session_id, create=True):
    """The folder where message-display.py keeps a session's batches, and its record of a
    hidden reply in the file "hidden"."""
    folder = os.path.join(state_folder("display", create=create), file_name(session_id))
    if create:
        os.makedirs(folder, mode=0o700, exist_ok=True)
    return folder


def forget_hidden_reply(text):
    """Deletes the record of a hidden reply for the session in this hook event, so that the
    display hook checks each reply again. Nothing here may stop the hook's own work."""
    try:
        os.remove(os.path.join(display_folder(parse_event(text).get("session_id"), create=False), "hidden"))
    except (OSError, ValueError):
        pass


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


def broken_settings(error, what):
    """Tells Claude that the settings file is broken, instead of checking without its names."""
    return {
        "decision": "block",
        "reason": (
            f"The plain-language settings file {error.path} is broken: {error.reason}. "
            f"{what} was not checked. Fix the settings file. "
            'It can contain only "names", a list of names, such as {"names": ["aXcelerate"]}.'
        ),
    }


# A long list of findings buries the first ones, so a reason shows at most this many.
SHOWN = 12


def reason_for(opening, lines, rules=True):
    shown = lines[:SHOWN]
    more = len(lines) - len(shown)
    parts = [
        opening,
        "",
        *[part for line in shown for part in (line, "")],
        f"There are {more} more findings like these. Fix them too." if more > 0 else "",
        f"The rules and the reasons for them: {CORE}." if rules else "",
    ]
    kept = [line for i, line in enumerate(parts) if not (line == "" and i > 0 and parts[i - 1] == "")]
    return "\n".join(kept).strip()
