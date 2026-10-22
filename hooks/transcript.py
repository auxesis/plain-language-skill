# Reads the text Claude wrote in the current turn out of a Claude Code transcript.
import os

from shared import parse_json, truthy

# A long session's transcript runs to tens of megabytes, and the turn is at the end.
TAIL_BYTES = 4 * 1024 * 1024


def tail(file):
    with open(file, "rb") as handle:
        size = os.fstat(handle.fileno()).st_size
        length = min(size, TAIL_BYTES)
        handle.seek(size - length)
        text = handle.read(length).decode("utf-8", "replace")
    return text[text.find("\n") + 1 :] if length < size else text


def _content(entry):
    message = entry.get("message")
    return message.get("content") if isinstance(message, dict) else None


# A user entry with text in it starts a turn. Tool results are user entries too, and do
# not start one. Text the harness adds is marked isMeta, and most of it, such as a
# skill's text, arrives in the middle of a turn. Two kinds of it start a turn: a
# message from another agent, which has turnOrigin and origin, and Stop hook feedback.
# Checked against transcripts from Claude Code 2.1.306 on 22 October 2026.
def starts_turn(entry):
    if not isinstance(entry, dict) or entry.get("type") != "user" or truthy(entry.get("isSidechain")):
        return False
    content = _content(entry)
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        block = next((block for block in content if isinstance(block, dict) and block.get("type") == "text"), None)
        text = block.get("text") if block is not None else None
    else:
        text = None
    if not isinstance(text, str):
        return False
    if not truthy(entry.get("isMeta")):
        return True
    if truthy(entry.get("turnCompanion")) or truthy(entry.get("sourceToolUseID")):
        return False
    return truthy(entry.get("turnOrigin")) or truthy(entry.get("origin")) or text.startswith("Stop hook feedback:")


def turn_text(transcript):
    """Every text block Claude wrote since the turn started, in order."""
    lines = [line for line in transcript.split("\n") if line]
    parts = []
    for line in reversed(lines):
        try:
            entry = parse_json(line)
        except (ValueError, RecursionError):
            continue
        if starts_turn(entry):
            break
        if not isinstance(entry, dict) or entry.get("type") != "assistant" or truthy(entry.get("isSidechain")):
            continue
        content = _content(entry)
        if not isinstance(content, list):
            continue
        for block in reversed(content):
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "\n\n".join(reversed(parts)).strip()
