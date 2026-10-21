// Turns Markdown into the pieces a reader reads as prose: paragraphs, list items,
// headings and table cells. Each piece records the source line of every part of its
// text, so a finding can name the line it came from.
//
// Code is left out, because code is exact and is not prose. Inline code becomes the
// one word CODE, and a URL becomes the one word URL, so a sentence that names
// `docs/a/long/path.md` counts it as one word.
//
// Each piece has two copies of its text. `text` is what the reader reads. `masked` is
// the same length, with everything inside double quotation marks blanked out, because
// a quoted phrase is somebody else's words: a sentence that says "write 'to', not 'in
// order to'" must not be reported for the phrase it is quoting.

const FENCE = /^\s*(```|~~~)/;
const HEADING = /^\s{0,3}#{1,6}\s+/;
const TABLE_ROW = /^\s*\|/;
const TABLE_DIVIDER = /^[\s|:-]+$/;
const LIST_ITEM = /^(\s*)(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?/;
const BLOCKQUOTE = /^\s*>\s?/;
const THEMATIC_BREAK = /^\s{0,3}(?:[-*_]\s*){3,}$/;
// A metadata line, such as "purpose: Find your record". Markdown would join a run of
// them into one paragraph, but each is a separate statement, not part of a sentence.
const FIELD_LINE = /^\s*[a-z][a-z0-9_-]*:\s/;
const ALLOW = "plain-language-allow";

export const PLACEHOLDERS = new Set(["CODE", "URL"]);

// Rewrites one line of Markdown into the words a reader sees.
export function inlineText(line) {
  return line
    .replace(/<!--.*?-->/g, " ")
    .replace(/(`+)[\s\S]*?\1/g, "CODE")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\[[^\]]*\]/g, "$1")
    .replace(/\[\^[^\]]+\]/g, "")
    .replace(/<https?:\/\/[^>]+>/g, "URL")
    .replace(/https?:\/\/[^\s)\]>]+[^\s)\]>.,;:!?'"]/g, "URL")
    .replace(/<\/?[a-zA-Z][^>]*>/g, " ")
    .replace(/\\([\\`*_{}[\]()#+\-.!|>])/g, "$1")
    .replace(/\*\*|__|~~|\*/g, "")
    .replace(/(^|[^\w])_+|_+(?=[^\w]|$)/g, "$1")
    .replace(/^\s*\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/i, "");
}

// Blanks out text between double quotation marks, keeping the length the same.
export function maskQuotes(text) {
  const blank = (match) => match[0] + " ".repeat(match.length - 2) + match[match.length - 1];
  return text
    .replace(/"[^"\n]{1,300}"/g, blank)
    .replace(/“[^”\n]{1,300}”/g, blank)
    .replace(/‘[^’\n]{1,300}’(?!\w)/g, blank)
    .replace(/(?<=^|[\s(\[])'[^'\n]{1,100}'(?=[\s.,;:!?)\]]|$)/g, blank);
}

class Piece {
  constructor(kind, line) {
    this.kind = kind;
    this.line = line;
    this.text = "";
    this.segments = [];
  }

  add(raw, line) {
    const words = inlineText(raw).trim();
    if (!words) return;
    if (this.text) this.text += " ";
    this.segments.push({ start: this.text.length, line });
    this.text += words;
  }

  lineAt(offset) {
    let line = this.line;
    for (const segment of this.segments) {
      if (segment.start > offset) break;
      line = segment.line;
    }
    return line;
  }
}

// Reads Markdown and returns its prose pieces, in order.
export function proseUnits(markdown) {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const pieces = [];
  let current = null;
  let inFence = false;
  let inComment = false;

  const finish = () => {
    if (current && current.text) {
      current.masked = maskQuotes(current.text);
      pieces.push(current);
    }
    current = null;
  };

  let start = 0;
  if (lines[0]?.trim() === "---") {
    const end = lines.indexOf("---", 1);
    if (end > 0) start = end + 1;
  }

  for (let i = start; i < lines.length; i++) {
    const number = i + 1;
    let line = lines[i];

    if (inFence) {
      if (FENCE.test(line)) inFence = false;
      continue;
    }
    if (FENCE.test(line)) {
      finish();
      inFence = true;
      continue;
    }
    if (inComment) {
      if (line.includes("-->")) inComment = false;
      continue;
    }
    if (line.includes("<!--") && !line.includes("-->", line.indexOf("<!--"))) {
      if (line.includes(ALLOW)) continue;
      line = line.slice(0, line.indexOf("<!--"));
      inComment = true;
    }
    if (line.includes(ALLOW)) continue;

    while (BLOCKQUOTE.test(line)) line = line.replace(BLOCKQUOTE, "");

    if (!line.trim() || THEMATIC_BREAK.test(line)) {
      finish();
      continue;
    }

    if (HEADING.test(line)) {
      finish();
      current = new Piece("heading", number);
      current.add(line.replace(HEADING, "").replace(/\s#+\s*$/, ""), number);
      finish();
      continue;
    }

    if (TABLE_ROW.test(line)) {
      finish();
      if (TABLE_DIVIDER.test(line)) continue;
      const cells = inlineText(line).replace(/^\s*\||\|\s*$/g, "").split("|");
      for (const cell of cells) {
        if (!cell.trim()) continue;
        const piece = new Piece("cell", number);
        piece.segments.push({ start: 0, line: number });
        piece.text = cell.trim();
        piece.masked = maskQuotes(piece.text);
        pieces.push(piece);
      }
      continue;
    }

    const item = LIST_ITEM.exec(line);
    if (item) {
      finish();
      current = new Piece("item", number);
      current.indent = item[1].length;
      current.add(line.slice(item[0].length), number);
      continue;
    }

    if (current && !FIELD_LINE.test(line) && (current.kind === "item" || current.kind === "paragraph")) {
      current.add(line, number);
      continue;
    }

    finish();
    current = new Piece("paragraph", number);
    current.add(line, number);
  }
  finish();
  return pieces;
}

// Abbreviations whose full stop does not end a sentence.
const ABBREVIATIONS = /\b(?:e\.g|i\.e|etc|vs|cf|viz|approx|Mr|Mrs|Ms|Dr|St|No|Fig|Inc|Ltd|Pty|Jr|Sr|a\.m|p\.m|U\.S)\./gi;
const HELD_STOP = "․";

// Splits one piece of prose into sentences, each with its offset in the piece.
export function sentences(text) {
  const protectedText = text.replace(ABBREVIATIONS, (match) => match.replaceAll(".", HELD_STOP));
  const found = [];
  const boundary = /(?<=[.!?]["'”’)\]*_]*)\s+(?=["'“‘(\[*_`]*[\p{Lu}\p{N}])/gu;
  let from = 0;
  let match;
  while ((match = boundary.exec(protectedText))) {
    found.push({ offset: from, text: text.slice(from, match.index) });
    from = match.index + match[0].length;
  }
  if (from < text.length) found.push({ offset: from, text: text.slice(from) });
  return found.filter((sentence) => countWords(sentence.text) > 0);
}

export function countWords(text) {
  return text.split(/\s+/).filter((token) => /[\p{L}\p{N}]/u.test(token)).length;
}
